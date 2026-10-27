"""Conservative SQL lowering for scalar DAX and grouped SUMMARIZE iterators.

Unsupported AST nodes return to the bounded Python evaluator. No source code runs.
"""
from dax_metadata import schema as model_schema, type_name
from dax_core import Parser, qi, sv, cached_ast
from dax_budget import check_budget
import threading
import time
from decimal import Decimal
import uuid
import re

class UnsupportedSql(ValueError):pass

class SqlRow(dict):
    def __init__(self,table,values):
        super().__init__(values);self.table=table

class SqlDax:
    def __init__(self, engine):
        self.counter=0;self.stack=[];self.has_row_transition=False;self.numeric_aliases=set();self.shared_aggregates=None
        external=engine.external_filters or []
        if engine.filters is None or engine.filters[:len(external)]!=external:raise UnsupportedSql('Noncanonical external context')
        self.base=engine.child(external)
        # Materialize the external context once; every relationship hop below
        # also reads that filtered model, preserving joint fact-row predicates.
        self.engine=engine.child(engine.filters[len(external):]);self.engine.sql_bound_groups=getattr(engine,'sql_bound_groups',{})

    def source(self,table):
        where=self.base.where(table)
        if not where:return qi(table)
        cache=self.base.budget.setdefault('sql_sources',{});key=(table,where)
        if key not in cache:
            name='__d2bi_filtered_'+uuid.uuid4().hex
            self.base.check_budget()
            self.base.con.execute('CREATE TEMP TABLE '+qi(name)+' AS SELECT * FROM '+qi(table)+' WHERE '+where)
            cache[key]=name
        return qi(cache[key])+' AS '+qi(table)

    def where(self,e,table):
        # Apply group/context-transition predicates against the same externally
        # filtered model on every hop, including intermediate fact tables.
        sql=e.where(table)
        for metadata in e.model['tables']:
            name=metadata['name'];token='FROM '+qi(name)+' WHERE '
            if token in sql:sql=sql.replace(token,'FROM '+self.source(name)+' WHERE ')
        return sql

    def grouped_iterator_safety(self,extensions,table,e,env):
        """Keep nested correlated grouping out of native scalar SQL plans.

        A SUMMARIZE extension adds a group transition. Nested groups and
        aggregates reached through several relationship hops need staged
        evaluation: alias/context flattening can change the group domain, and
        these plans can crash DuckDB's native correlated-query execution.
        Basic one-hop fact/dimension summaries keep their existing SQL path.
        """
        cache=e.budget.setdefault('sql_group_safety',{})
        relationships=repr(e.model.get('relationships',[]))
        def inspect(node,bindings,seen=frozenset(),home=None):
            e.check_budget()
            kind=node[0]
            if kind=='name' and node[1].casefold() in bindings:
                expression,scope=bindings[node[1].casefold()]
                return inspect(expression,scope,seen,home)
            if kind=='col':
                matches=[m for m in e.model['measures'] if m['Name'].casefold()==node[2].casefold() and (not node[1] or m['TableName'].casefold()==node[1].casefold())]
                if len(matches)!=1:return None
                measure=matches[0];identity=(measure['TableName'],measure['Name'])
                if identity in seen:return None
                if len(seen)>=30:return 'excessive grouped measure dependency'
                key=(table,measure['TableName'],measure['Name'],measure['Expression'],relationships)
                if key in cache:return cache[key]
                reason=inspect(cached_ast(e,measure['Expression']),{},seen|{identity},measure['TableName'])
                if len(cache)<2000:cache[key]=reason
                return reason
            if kind=='let':
                local=dict(bindings)
                for name,expression in node[1]:
                    reason=inspect(expression,local,seen,home)
                    if reason:return reason
                    local[name.casefold()]=(expression,dict(local))
                return inspect(node[2],local,seen,home)
            if kind=='call':
                fn,args=node[1],node[2]
                if fn=='SUMMARIZE':return 'nested grouped iterator'
                target=None
                if fn in ('SUM','AVERAGE','MIN','MAX','COUNT','MEDIAN','COUNTA','DISTINCTCOUNT') and len(args)==1 and args[0][0]=='col':target=args[0][1] or home
                if fn=='COUNTROWS' and len(args)==1 and args[0][0]=='name' and args[0][1].casefold() not in bindings:target=args[0][1]
                if target:
                    source=next((t['name'] for t in e.model['tables'] if t['name'].casefold()==target.casefold()),None)
                    path=e.path(source,table) if source else None
                    if path is not None and len(path)>1:return 'grouped aggregate across multiple relationship hops'
                if fn=='CROSSFILTER':return 'grouped iterator relationship override'
                children=args
            elif kind in ('op','unary'):children=node[2:]
            elif kind in ('tuple','table'):children=node[1]
            else:children=[]
            for child in children:
                reason=inspect(child,bindings,seen,home)
                if reason:return reason
            return None
        for extension in extensions:
            home=self.stack[-1][0] if self.stack else e.stack[-1][0] if e.stack else None
            reason=inspect(extension,env,home=home)
            if reason:
                e.budget['sqlSafetyFallbacks']=e.budget.get('sqlSafetyFallbacks',0)+1
                reasons=e.budget.setdefault('sqlSafetyReasons',[])
                if reason not in reasons and len(reasons)<8:reasons.append(reason)
                raise UnsupportedSql('SQL safety fallback: '+reason+' requires staged evaluation')

    def shared_aggregate(self,sql,table,column,e,row):
        """Reuse safe physical aggregate leaves in a grouped scalar plan.

        Correlations may use only the enclosing group identity. Iterator and
        lexical-variable aliases belong to narrower scopes and are never
        hoisted. Every leaf still reads the same secured, filtered connection.
        """
        shared=self.shared_aggregates
        if shared is None or row is not None or e.iterator_depth or e.row_stack:return sql
        aliases=[alias for pair in re.findall(r'(?:"(__[^"]+)"|\b(__\w+))\.',sql) for alias in pair if alias]
        if any(alias not in ('__g','__filter_domain') for alias in aliases):return sql
        types=e.budget.setdefault('sql_shared_types',{});key=(table,column)
        if key not in types:types[key]=type_name(e,table,column)
        if not types[key].startswith(('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','UHUGEINT','FLOAT','DOUBLE','REAL','DECIMAL')):return sql
        if sql not in shared['queries']:
            if len(shared['queries'])>=64 or shared['bytes']+len(sql)>2000000:return sql
            shared['queries'][sql]='__d2bi_aggregate_'+str(len(shared['queries']));shared['bytes']+=len(sql)
        return qi(shared['queries'][sql])+'."value"'

    def constant(self,node,e,env):
        """Fold fixed parameter selections, never a group- or row-dependent value."""
        if node[0]=='lit':return (node[1],)
        if node[0]=='name' and node[1].casefold() in env:
            expr,scope=env[node[1].casefold()]
            return self.constant(expr,e,scope)
        if node[0]=='op' and node[1] in ('+','-','*','/','^','=','==','<>','<','>','<=','>=','&&','||','&'):
            values=[self.constant(n,e,env) for n in node[2:]]
            if all(value is not None for value in values):
                return (e.scalar(e.run(('op',node[1],('lit',values[0][0]),('lit',values[1][0])),{},None)),)
        if node[0]=='call' and node[1]=='SELECTEDVALUE' and node[2][0][0]=='col' and not e.iterator_depth and not e.row_stack:
            table,col=e.column(node[2][0])
            if any(e.path(table,t) is not None for t,c in getattr(e,'sql_bound_groups',{})):return None
            # An alternate may depend on a group even when the column does not.
            if len(node[2])>1:
                alternate=self.constant(node[2][1],e,env)
                if alternate is None:return None
                node=('call','SELECTEDVALUE',[node[2][0],('lit',alternate[0])])
            sql=self.scalar(node,e,env)
            if any(alias in sql for alias in ('__g','__dax','__var_')):return None
            cache=e.budget.setdefault('constant_selections',{})
            if sql not in cache:
                e.check_budget()
                timer=threading.Timer(max(.001,e.budget['deadline']-time.monotonic()),e.con.interrupt);timer.daemon=True;timer.start()
                try:cache[sql]=e.con.execute('SELECT '+sql).fetchone()[0]
                except Exception:
                    e.check_budget();raise
                finally:timer.cancel()
                e.check_budget()
            return (cache[sql],)
        return None

    def numeric(self,node,e,env,seen=frozenset()):
        """Prove scalar math inputs before lowering numeric-only SQL functions."""
        kind=node[0]
        if kind=='lit':return node[1] is None or isinstance(node[1],(bool,int,float,Decimal))
        if kind=='__sql':return node[1] in self.numeric_aliases
        if kind=='name' and node[1].casefold() in env:
            expression,scope=env[node[1].casefold()];return self.numeric(expression,e,scope,seen)
        if kind=='let':
            local=dict(env)
            for name,expression in node[1]:local[name.casefold()]=(expression,dict(local))
            return self.numeric(node[2],e,local,seen)
        if kind=='col':
            matches=[m for m in e.model['measures'] if m['Name'].casefold()==node[2].casefold() and (not node[1] or m['TableName'].casefold()==node[1].casefold())]
            if len(matches)==1:
                measure=matches[0];identity=(measure['TableName'],measure['Name'])
                return identity not in seen and self.numeric(cached_ast(e,measure['Expression']),e,{},seen|{identity})
            if not node[1]:return False
            table,col=e.column(node);dtype=type_name(e,table,col)
            return dtype.startswith(('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','UHUGEINT','FLOAT','DOUBLE','REAL','DECIMAL'))
        if kind=='unary':return self.numeric(node[2],e,env,seen)
        if kind=='op':return node[1] in ('+','-','*','/','^') and all(self.numeric(n,e,env,seen) for n in node[2:])
        if kind!='call':return False
        fn,args=node[1],node[2]
        if fn in ('COUNT','COUNTA','DISTINCTCOUNT','COUNTROWS','YEAR','MONTH','DAY','HOUR','MINUTE','SECOND','PI','BLANK'):return True
        if fn in ('SELECTEDVALUE','SUM','AVERAGE','MIN','MAX','MEDIAN'):
            return bool(args) and all(self.numeric(n,e,env,seen) for n in args)
        if fn=='CALCULATE':return bool(args) and self.numeric(args[0],e,env,seen)
        if fn=='IF' and len(args) in (2,3):
            fixed=self.constant(args[0],e,env)
            return (self.numeric(args[1] if fixed[0] else args[2],e,env,seen) if fixed[0] or len(args)>2 else True) if fixed is not None else all(self.numeric(n,e,env,seen) for n in args[1:])
        if fn in ('COS','SIN','RADIANS','ABS','DIVIDE','ROUND','ROUNDUP','ROUNDDOWN','INT','TRUNC','POWER','COALESCE'):
            return all(self.numeric(n,e,env,seen) for n in args)
        return False

    def scalar(self,n,e=None,env=None,row=None):
        e=e or self.engine;env={} if env is None else env
        kind=n[0]
        if kind!='col':e.check_budget()
        if kind=='lit':return sv(n[1])
        if kind=='__sql':return n[1]
        if kind=='unary' and n[1] in ('+','-'):
            if not self.numeric(n[2],e,env):raise UnsupportedSql('Non-numeric unary input')
            return '('+n[1]+'COALESCE('+self.scalar(n[2],e,env,row)+',0))'
        if kind=='let':
            local=dict(env);sources=[]
            for name,expr in n[1]:
                fixed=self.constant(expr,e,local) if row is None else None
                if fixed is not None:
                    local[name.casefold()]=(('lit',fixed[0]),{});continue
                alias='__var_'+uuid.uuid4().hex
                try:value=self.scalar(expr,e,local,row)
                except UnsupportedSql:
                    local[name.casefold()]=(expr,dict(local));continue
                sources.append('LATERAL (SELECT '+value+' AS '+qi(name)+') AS '+qi(alias))
                reference=qi(alias)+'.'+qi(name)
                if self.numeric(expr,e,local):self.numeric_aliases.add(reference)
                local[name.casefold()]=( ('__sql',reference),{} )
            result=self.scalar(n[2],e,local,row)
            return '(SELECT '+result+' FROM '+' CROSS JOIN '.join(sources)+')' if sources else result
        if kind=='name':
            key=n[1].casefold()
            if key in env:
                expr,scope=env[key];return self.scalar(expr,e,scope,row)
            if key in ('true','false'):return key.upper()
            raise UnsupportedSql('Scalar name')
        if kind=='col':
            if row:
                column=next((c for c in row if c.casefold()==n[2].casefold()),None)
                if column is not None:return row[column]
            matches=[m for m in e.model['measures'] if m['Name'].casefold()==n[2].casefold() and (not n[1] or m['TableName'].casefold()==n[1].casefold())]
            if len(matches)!=1:raise UnsupportedSql('Column outside row')
            m=matches[0];key=(m['TableName'],m['Name'])
            if key in self.stack or len(self.stack)>20:raise UnsupportedSql('Measure recursion')
            self.stack.append(key)
            # Physical unqualified columns resolve against each measure's own
            # home table, including nested measures expanded by this compiler.
            # A runtime caller may already own the same frame; retain it.
            home_stack=e.stack;home_pushed=not home_stack or home_stack[-1]!=key
            if home_pushed:home_stack.append(key)
            try:
                expression=cached_ast(e,m['Expression'])
                if row:
                    self.has_row_transition=True
                    table=getattr(row,'table',None)
                    if table is None:raise UnsupportedSql('Iterator measure requires context transition')
                    filters=[*self.base.require_filters(),*e.require_filters()]
                    cols=[(table,c) for c in row]
                    filters=e.child(filters).remove(cols)
                    keys=e.budget.setdefault('sql_row_keys',{})
                    if table not in keys:
                        keys[table]=None
                        schema=model_schema(e,table)
                        integers=[name for name,dtype,*rest in schema if name in row and str(dtype).startswith(('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UBIGINT','UINTEGER'))]
                        if integers:
                            first=integers[0];names=[d[0] for d in schema];position=names.index(first)
                            duplicate=e.con.execute('SELECT * FROM '+qi(table)+' WHERE '+qi(first)+' IN (SELECT '+qi(first)+' FROM '+qi(table)+' GROUP BY '+qi(first)+' HAVING COUNT(*)>1) OR '+qi(first)+' IS NULL LIMIT 5001').fetchall()
                            if len(duplicate)<=5000:
                                positions=[position]
                                while True:
                                    groups={};conflict=None
                                    for values in duplicate:
                                        identity=tuple(values[i] for i in positions)
                                        if identity in groups and groups[identity]!=values:
                                            conflict=(groups[identity],values);break
                                        groups[identity]=values
                                    if conflict is None:break
                                    positions.append(next(i for i in range(len(names)) if conflict[0][i]!=conflict[1][i]))
                                keys[table]=[names[i] for i in positions]
                    key_columns=keys[table]
                    if not key_columns:raise UnsupportedSql('Iterator requires a bounded row identity')
                    def changes_key(node,visited=None):
                        visited=set() if visited is None else visited
                        if node[0]=='col':
                            mm=next((x for x in e.model['measures'] if x['Name'].casefold()==node[2].casefold() and (not node[1] or x['TableName'].casefold()==node[1].casefold())),None)
                            if mm and mm['Name'] not in visited:return changes_key(cached_ast(e,mm['Expression']),visited|{mm['Name']})
                        if node[0]=='call':
                            if node[1] in ('ALL','REMOVEFILTERS','ALLNOBLANKROW','ALLEXCEPT') and any(x[0]=='col' and x[1] and e.column(x) in [(table,c) for c in key_columns] for x in node[2]):return True
                            if node[1]=='CALCULATE' and any(any((table,c) in list(e.referenced_columns(x)) for c in key_columns) for x in node[2][1:] if x[0]=='op'):return True
                            return any(changes_key(x,visited) for x in node[2])
                        if node[0]=='let':return any(changes_key(x,visited) for name,x in node[1]) or changes_key(node[2],visited)
                        if node[0]=='op':return any(changes_key(x,visited) for x in node[2:])
                        return False
                    if changes_key(expression):raise UnsupportedSql('Iterator modifies its row identity')
                    filters.extend({'table':table,'columns':[c],'sql':qi(table)+'.'+qi(c)+' IS NOT DISTINCT FROM '+row[c]} for c in key_columns)
                    for r in e.model.get('relationships',[]):
                        if not r.get('IsActive') or r.get('Cardinality') not in ('M:1','1:1') or r['FromTableName']!=table or r['FromColumnName'] not in row:continue
                        target=r['ToTableName'];key=r['ToColumnName'];ref=row[r['FromColumnName']]
                        # Restrict this fast path to one-hop expanded transitions.
                        if any(x.get('IsActive') and x.get('Cardinality') in ('M:1','1:1') and x['FromTableName']==target for x in e.model.get('relationships',[])):raise UnsupportedSql('Deep expanded row transition')
                        # A unique dimension key identifies its expanded row.
                        # Column-level modifiers on that dimension need the full
                        # projected tuple semantics, so retain the Python path.
                        def partial(node,visited=None):
                            visited=set() if visited is None else visited
                            if node[0]=='col':
                                mm=next((x for x in e.model['measures'] if x['Name'].casefold()==node[2].casefold() and (not node[1] or x['TableName'].casefold()==node[1].casefold())),None)
                                if mm and mm['Name'] not in visited:return partial(cached_ast(e,mm['Expression']),visited|{mm['Name']})
                            if node[0]=='call':
                                if node[1] in ('ALL','REMOVEFILTERS','ALLNOBLANKROW','ALLEXCEPT') and any(x[0]=='col' and x[1] and e.canonical_table(x[1])==target for x in node[2]):return True
                                if node[1]=='CALCULATE' and any(any(t==target for t,c in e.referenced_columns(x)) for x in node[2][1:] if x[0]=='op'):return True
                                return any(partial(x,visited) for x in node[2])
                            if node[0]=='let':return any(partial(x,visited) for name,x in node[1]) or partial(node[2],visited)
                            if node[0]=='op':return any(partial(x,visited) for x in node[2:])
                            return False
                        if partial(expression):raise UnsupportedSql('Partial expanded dimension modifier')
                        validated=e.budget.setdefault('sql_unique_dimensions',set());token=(target,key)
                        if token not in validated:
                            if e.con.execute('SELECT 1 FROM '+qi(target)+' GROUP BY '+qi(key)+' HAVING COUNT(*)>1 LIMIT 1').fetchone():raise ValueError('Relationship one-side key is not unique')
                            validated.add(token)
                        filters=e.child(filters).remove([], [target])
                        domain='SELECT 1 FROM '+qi(target)+' AS __rel WHERE __rel.'+qi(key)+' IS NOT DISTINCT FROM '+ref
                        filters.append({'table':target,'columns':[key],'sql':'(NOT EXISTS ('+domain+') OR '+qi(target)+'.'+qi(key)+' IS NOT DISTINCT FROM '+ref+')'})
                    child=e.child(filters);child.external_filters=[]
                    compiler=SqlDax(child);compiler.stack=list(self.stack)
                    # An explicit root CALCULATE performs the measure transition itself.
                    # Its filter arguments see the pre-transition context; applying an
                    # implicit transition first incorrectly narrows their value domains.
                    if expression[0]=='call' and expression[1]=='CALCULATE':
                        compiler.calculate_filter_context=(self,e)
                    return compiler.scalar(expression,compiler.engine,{},None)
                return self.scalar(expression,e,{},None)
            finally:
                if home_pushed:home_stack.pop()
                self.stack.pop()
        if kind=='op':
            op={'&&':'AND','||':'OR','==':'=','&':'||'}.get(n[1],n[1])
            if op not in ('+','-','*','/','=','<>','<','>','<=','>=','AND','OR','||'):raise UnsupportedSql('Operator')
            a=self.scalar(n[2],e,env,row);b=self.scalar(n[3],e,env,row)
            if op=='||':return '(COALESCE(CAST('+a+" AS VARCHAR),'') || COALESCE(CAST("+b+" AS VARCHAR),''))"
            if op=='AND':
                if 'FALSE' in (a,b):return 'FALSE'
                if a=='TRUE':return b
                if b=='TRUE':return a
            if op=='OR':
                if 'TRUE' in (a,b):return 'TRUE'
                if a=='FALSE':return b
                if b=='FALSE':return a
            if row and getattr(row,'table',None) and op in ('=','<>','<','>','<=','>='):
                numeric=False
                for part in n[2:]:
                    if part[0]=='col' and part[2] in row:
                        dtype=type_name(e,row.table,part[2])
                        numeric=numeric or dtype.startswith(('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','FLOAT','DOUBLE','DECIMAL'))
                if numeric and not any(part[0]=='lit' and isinstance(part[1],str) for part in n[2:]):a='COALESCE('+a+',0)';b='COALESCE('+b+',0)'
            if op in ('+','-'):a='COALESCE('+a+',0)';b='COALESCE('+b+',0)'
            if op in ('=','<>') and any(x[0]=='lit' and isinstance(x[1],str) for x in n[2:]):a='lower(CAST('+a+' AS VARCHAR))';b='lower(CAST('+b+' AS VARCHAR))'
            return '('+a+' '+op+' '+('NULLIF('+b+',0)' if op=='/' else b)+')'
        if kind!='call':raise UnsupportedSql('AST form')
        fn,args=n[1].upper(),n[2]
        val=lambda node:self.scalar(node,e,env,row)
        if fn in ('TRUE','FALSE','BLANK'):return {'TRUE':'TRUE','FALSE':'FALSE','BLANK':'NULL'}[fn]
        if fn=='ISINSCOPE':return 'TRUE' if e.column(args[0]) in e.scope else 'FALSE'
        if fn in ('MIN','MAX') and len(args)==2:
            a,b=val(args[0]),val(args[1]);return '(CASE WHEN '+a+' IS NULL AND '+b+' IS NULL THEN NULL ELSE '+('LEAST' if fn=='MIN' else 'GREATEST')+'(COALESCE('+a+',0),COALESCE('+b+',0)) END)'
        if fn=='CALCULATE':
            filter_context=getattr(self,'calculate_filter_context',None)
            if filter_context is not None:del self.calculate_filter_context
            resolved=[]
            for arg in args:
                keep=arg[0]=='call' and arg[1]=='KEEPFILTERS'
                if keep:arg=arg[2][0]
                if arg[0]=='op':
                    rhs=arg[3];scope=env;seen=set()
                    while rhs[0]=='name' and rhs[1].casefold() in scope and rhs[1].casefold() not in seen:
                        seen.add(rhs[1].casefold());rhs,scope=scope[rhs[1].casefold()]
                    if rhs[0]=='lit':arg=(arg[0],arg[1],arg[2],rhs)
                resolved.append(('call','KEEPFILTERS',[arg]) if keep else arg)
            args=resolved
            if row:raise UnsupportedSql('CALCULATE SQL row transition')
            filters=[*self.base.require_filters(),*e.require_filters()];remove=[];add=[];kept=[];relationships={}
            for arg in args[1:]:
                keep=arg[0]=='call' and arg[1]=='KEEPFILTERS'
                if keep:arg=arg[2][0]
                if arg[0]=='call' and arg[1]=='CROSSFILTER':
                    a,b=e.column(arg[2][0]),e.column(arg[2][1]);direction=str(arg[2][2][1]).casefold()
                    found=next((r for r in e.model.get('relationships',[]) if {(r['FromTableName'],r['FromColumnName']),(r['ToTableName'],r['ToColumnName'])}=={a,b}),None)
                    if not found or direction not in ('both','none','oneway') or direction=='oneway' and found.get('Cardinality')=='M:M':raise UnsupportedSql('CROSSFILTER relationship or direction')
                    relationships[id(found)]=direction;continue
                if arg[0]=='col':
                    table,col=e.column(arg);dtype=type_name(e,table,col)
                    if dtype!='BOOLEAN':raise UnsupportedSql('Nonboolean column filter')
                    (kept if keep else add).append(((table,col),{'table':table,'columns':[col],'sql':qi(table)+'.'+qi(col)+' IS TRUE'}));continue
                if arg[0]=='call' and arg[1] in ('ALL','ALLNOBLANKROW','REMOVEFILTERS'):
                    remove.append(e.modifier_targets(arg[2]));continue
                if arg[0]!='op' or arg[1] not in ('=','==','<>','>','>=','<','<=') or arg[2][0]!='col' or arg[3][0]!='lit':raise UnsupportedSql('CALCULATE SQL filter')
                table,col=e.column(arg[2]);value=arg[3][1];ref=qi(table)+'.'+qi(col)
                pred=('lower(CAST('+ref+' AS VARCHAR))=lower('+sv(value)+')') if isinstance(value,str) else ref+' IS NOT DISTINCT FROM '+sv(value)
                if arg[1]=='<>':
                    pred=('lower(COALESCE(CAST('+ref+" AS VARCHAR),'')) <> lower("+sv(value)+')') if isinstance(value,str) else 'COALESCE('+ref+',0) <> '+sv(value) if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool) else ref+' IS DISTINCT FROM '+sv(value)
                if arg[1] in ('>','>=','<','<='):
                    if not isinstance(value,(int,float,Decimal)) or isinstance(value,bool):raise UnsupportedSql('Non-numeric ordered CALCULATE filter')
                    pred='COALESCE('+ref+',0) '+arg[1]+' '+sv(value)
                before_compiler,before_engine=filter_context or (self,e)
                original=before_engine.child([])
                original=original.child(original.remove([(table,col)]));original.external_filters=[]
                before=SqlDax(original);domain_where=before.where(before.engine,table)
                domain='SELECT '+ref+' FROM '+before.source(table)+' WHERE '+(domain_where+' AND ' if domain_where else '')+pred
                pred='EXISTS (SELECT 1 FROM ('+domain+') AS __filter_domain WHERE __filter_domain.'+qi(col)+' IS NOT DISTINCT FROM '+ref+')'
                (kept if keep else add).append(((table,col),{'table':table,'columns':[col],'sql':pred}))
            for targets in remove:filters=e.child(filters).remove(*targets)
            if add:filters=e.child(filters).remove([c for c,f in add])
            filters.extend(f for c,f in [*add,*kept])
            child=e.child(filters);child.external_filters=[];child.sql_bound_groups=getattr(e,'sql_bound_groups',{})
            if relationships:
                child.model={**e.model,'relationships':[{**r,**({'IsActive':False} if relationships[id(r)]=='none' else {'CrossFilteringBehavior':'Both' if relationships[id(r)]=='both' else 'Single'})} if id(r) in relationships else r for r in e.model.get('relationships',[])]}
            compiler=SqlDax(child);compiler.stack=list(self.stack);compiler.shared_aggregates=self.shared_aggregates
            return compiler.scalar(args[0],compiler.engine,env,None)
        if fn=='NOT':return '(NOT '+val(args[0])+')'
        if fn in ('COS','SIN','RADIANS') and len(args)==1:
            if not self.numeric(args[0],e,env):raise UnsupportedSql('Non-numeric '+fn+' input')
            return fn+'(COALESCE(CAST('+val(args[0])+' AS DOUBLE),0))'
        if fn=='YEAR' and len(args)==1:
            node=args[0];scope=env;seen=set()
            while node[0]=='name' and node[1].casefold() in scope and node[1].casefold() not in seen:
                seen.add(node[1].casefold());node,scope=scope[node[1].casefold()]
            if node[0]=='lit':
                from dax_functions import FUNCTIONS
                return sv(FUNCTIONS['YEAR'][3](node[1]))
            target=node[2][0] if node[0]=='call' and node[1] in ('SELECTEDVALUE','MIN','MAX') and len(node[2])==1 else node
            if target[0]!='col':raise UnsupportedSql('YEAR needs a typed temporal scalar')
            table,col=e.column(target);dtype=type_name(e,table,col)
            if dtype!='DATE' and not dtype.startswith('TIMESTAMP'):raise UnsupportedSql('YEAR temporal type')
            value=val(args[0])
            return "(CASE WHEN "+value+" IS NULL THEN error('Expected a DAX date value') ELSE YEAR("+value+") END)"
        if fn=='LOG':
            a=val(args[0]);b=val(args[1]) if len(args)>1 else '10'
            return '(LN('+a+')/LN('+b+'))'
        if fn=='ISBLANK':return '('+val(args[0])+' IS NULL)'
        if fn=='SELECTEDVALUE' and args[0][0]=='col':
            table,col=e.column(args[0]);where=self.where(e,table);ref=qi(table)+'.'+qi(col)
            dtype=type_name(e,table,col)
            key='lower('+ref+')' if dtype=='VARCHAR' else ref
            distinct='COUNT(DISTINCT '+key+')+CASE WHEN COUNT(*)>COUNT('+ref+') THEN 1 ELSE 0 END'
            alternate=val(args[1]) if len(args)>1 else 'NULL'
            return '(SELECT CASE WHEN ('+distinct+')=1 THEN MIN('+ref+') ELSE '+alternate+' END FROM '+self.source(table)+(' WHERE '+where if where else '')+')'
        if fn=='DIVIDE':return '(CASE WHEN '+val(args[1])+' IS NULL OR '+val(args[1])+'=0 THEN '+(val(args[2]) if len(args)>2 else 'NULL')+' ELSE COALESCE('+val(args[0])+',0)/'+val(args[1])+' END)'
        if fn=='IF':
            fixed=self.constant(args[0],e,env) if row is None else None
            if fixed is not None:return val(args[1]) if fixed[0] else val(args[2]) if len(args)>2 else 'NULL'
            return '(CASE WHEN '+val(args[0])+' THEN '+val(args[1])+' ELSE '+(val(args[2]) if len(args)>2 else 'NULL')+' END)'
        if fn=='SWITCH':
            fixed=self.constant(args[0],e,env) if row is None else None
            pairs=args[1:]
            if fixed is not None:
                for i in range(0,len(pairs)-1,2):
                    match=self.constant(pairs[i],e,env)
                    if match is None:break
                    if e.equal(fixed[0],match[0],True):return val(pairs[i+1])
                else:return val(pairs[-1]) if len(pairs)%2 else 'NULL'
            value=val(args[0]);pairs=args[1:];parts=[]
            for i in range(0,len(pairs)-1,2):
                left,right=value,val(pairs[i])
                if left in ('TRUE','FALSE') and right in ('TRUE','FALSE'):
                    if left!=right:continue
                    chosen=val(pairs[i+1])
                    return '(CASE '+' '.join(parts)+' ELSE '+chosen+' END)' if parts else chosen
                if pairs[i][0]=='lit' and isinstance(pairs[i][1],str):left='lower(CAST('+left+' AS VARCHAR))';right='lower(CAST('+right+' AS VARCHAR))'
                parts.append('WHEN '+left+' IS NOT DISTINCT FROM '+right+' THEN '+val(pairs[i+1]))
            other=val(pairs[-1]) if len(pairs)%2 else 'NULL'
            return '(CASE '+' '.join(parts)+' ELSE '+other+' END)' if parts else other
        if fn in ('SUM','AVERAGE','MIN','MAX','COUNT','MEDIAN') and len(args)==1 and args[0][0]=='col':
            table,col=e.column(args[0]);where=self.where(e,table)
            aggregate={'AVERAGE':'AVG'}.get(fn,fn)+'('+qi(table)+'.'+qi(col)+')'
            if fn=='COUNT':aggregate='NULLIF('+aggregate+',0)'
            sql='(SELECT '+aggregate+' FROM '+self.source(table)+(' WHERE '+where if where else '')+')'
            return self.shared_aggregate(sql,table,col,e,row)
        if fn=='COUNTROWS' and args[0][0]=='name':
            if args[0][1].casefold() in env:raise UnsupportedSql('COUNTROWS virtual table')
            table=e.canonical_table(args[0][1]);where=self.where(e,table)
            return '(SELECT NULLIF(COUNT(*),0) FROM '+self.source(table)+(' WHERE '+where if where else '')+')'
        if fn in ('SUMX','AVERAGEX','MINX','MAXX','MEDIANX'):
            source=args[0];scope=env
            while source[0]=='name' and source[1].casefold() in scope:source,scope=scope[source[1].casefold()]
            if source[0]=='call' and source[1]=='CALCULATETABLE' and all(a[0]=='call' and a[1]=='CROSSFILTER' for a in source[2][1:]):
                return self.scalar(('call','CALCULATE',[('call',fn,[source[2][0],*args[1:]]),*source[2][1:]]),e,scope,row)
            if fn in ('MINX','MAXX') and source[0]=='call' and source[1]=='ALL' and len(source[2])==1 and source[2][0][0]=='name' and args[1][0]=='col':
                table=e.canonical_table(source[2][0][1]);ct,col=e.column(args[1])
                if table!=ct:raise UnsupportedSql('Extremum column outside ALL table')
                dtype=type_name(e,table,col)
                if dtype in ('VARCHAR','BOOLEAN','BLOB'):raise UnsupportedSql('ALL iterator extremum requires numeric or temporal data')
                child=e.child([*self.base.require_filters(),*e.require_filters()])
                child=child.child(child.remove(*child.modifier_targets(source[2])));where=child.where(table)
                return '(SELECT '+fn[:-1]+'('+qi(table)+'.'+qi(col)+') FROM '+qi(table)+(' WHERE '+where if where else '')+')'
            self.counter+=1;alias='__dax'+str(self.counter)
            if source[0]=='name' and source[1].casefold() not in scope:
                table=e.canonical_table(source[1]);schema=dict((d[0],str(d[1])) for d in model_schema(e,table))
                def numeric_row(node):
                    if node[0]=='lit':return node[1] is None or isinstance(node[1],(int,float,Decimal)) and not isinstance(node[1],bool)
                    if node[0]=='col':
                        if not node[1]:return False
                        ct,col=e.column(node)
                        return ct==table and any(schema[col].startswith(t) for t in ('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','FLOAT','DOUBLE','DECIMAL'))
                    if node[0]=='op':return node[1] in ('+','-','*','/') and all(numeric_row(x) for x in node[2:])
                    if node[0]=='call':return node[1]=='DIVIDE' and all(numeric_row(x) for x in node[2])
                    return False
                if not numeric_row(args[1]):raise UnsupportedSql('Base iterator expression requires bounded numeric row arithmetic')
                mapping={c:qi(table)+'.'+qi(c) for c in schema};expr=self.scalar(args[1],e,scope,mapping);where=self.where(e,table)
                if fn=='MEDIANX':expr='COALESCE('+expr+',0)'
                return '(SELECT '+fn[:-1].replace('AVERAGE','AVG')+'('+expr+') FROM '+self.source(table)+(' WHERE '+where if where else '')+')'
            if source[0]=='call' and source[1].upper()=='SUMMARIZE':
                if fn=='MEDIANX':raise UnsupportedSql('MEDIANX virtual groups require a numeric type proof')
                a=source[2]
                if a[0][0]!='name':raise UnsupportedSql('SUMMARIZE source')
                if a[0][1].casefold() in env:raise UnsupportedSql('SUMMARIZE virtual table')
                table=e.canonical_table(a[0][1]);cols=[];i=1
                while i<len(a) and a[i][0]=='col':cols.append(e.column(a[i]));i+=1
                if not cols or any(t!=table for t,c in cols):raise UnsupportedSql('SUMMARIZE grouping')
                self.grouped_iterator_safety([a[j+1] for j in range(i,len(a),2) if j+1<len(a)],table,e,scope)
                bound=getattr(e,'sql_bound_groups',{})
                if all(col in bound for col in cols):
                    mapping={c:bound[t,c] for t,c in cols}
                    for j in range(i,len(a),2):
                        if a[j][0]!='lit' or j+1>=len(a):raise UnsupportedSql('SUMMARIZE extensions')
                        mapping[a[j][1]]=self.scalar(a[j+1],e,scope,None)
                    return self.scalar(args[1],e,env,mapping)
                filters=list(e.require_filters())+[{'table':t,'columns':[c],'sql':qi(t)+'.'+qi(c)+' IS NOT DISTINCT FROM '+qi(alias)+'.'+qi(c)} for t,c in cols]
                child=e.child(filters);child.sql_bound_groups={**bound,**{(t,c):qi(alias)+'.'+qi(c) for t,c in cols}};where=self.where(e,table)
                inner='SELECT DISTINCT '+','.join(qi(c) for t,c in cols)+' FROM '+self.source(table)+(' WHERE '+where if where else '')
                mapping={c:qi(alias)+'.'+qi(c) for t,c in cols}
                for j in range(i,len(a),2):
                    if a[j][0]!='lit' or j+1>=len(a):raise UnsupportedSql('SUMMARIZE extensions')
                    mapping[a[j][1]]=self.scalar(a[j+1],child,scope,None)
                expr=self.scalar(args[1],child,env,mapping)
                return '(SELECT '+fn[:-1].replace('AVERAGE','AVG')+'('+expr+') FROM ('+inner+') '+qi(alias)+')'
            if source[0]=='call' and source[1].upper()=='FILTER' and (source[2][0][0]=='name' or source[2][0][0]=='call' and source[2][0][1]=='ALL' and len(source[2][0][2])==1 and source[2][0][2][0][0]=='name'):
                if source[2][0][0]=='call':
                    targets=e.modifier_targets(source[2][0][2])
                    table=e.canonical_table(source[2][0][2][0][1])
                    def row_only(node):
                        if node[0]=='lit':return True
                        if node[0]=='col':
                            try:return e.column(node)[0]==table
                            except ValueError:return False
                        if node[0]=='op':return all(row_only(x) for x in node[2:])
                        if node[0]=='call':return node[1] in ('DIVIDE','NOT','ISBLANK','ABS') and all(row_only(x) for x in node[2])
                        return False
                    if not row_only(source[2][1]) or not row_only(args[1]):raise UnsupportedSql('ALL table iterator with context-sensitive expressions')
                    # ALL(table) used as a rowset enumerates every secured row,
                    # including rows hidden by filters propagated through bridges.
                    # It is different from a CALCULATE removal modifier.
                    e=e.child([]);e.external_filters=[]
                    compiler=SqlDax(e);compiler.stack=list(self.stack)
                    rewritten=('call',fn,[('call','FILTER',[source[2][0][2][0],source[2][1]]),*args[1:]])
                    return compiler.scalar(rewritten,compiler.engine,scope,None)
                if source[2][0][1].casefold() in env:raise UnsupportedSql('FILTER virtual table')
                table=e.canonical_table(source[2][0][1]);cols=e.budget.setdefault('columns',{}).get(table)
                if cols is None:cols=[d[0] for d in model_schema(e,table)]
                if fn=='MEDIANX':
                    schema={d[0]:str(d[1]) for d in model_schema(e,table)}
                    def numeric_median(node):
                        if node[0]=='lit':return node[1] is None or isinstance(node[1],(int,float,Decimal)) and not isinstance(node[1],bool)
                        if node[0]=='col' and node[1]:
                            ct,col=e.column(node)
                            return ct==table and schema[col].split('(')[0] in ('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','UHUGEINT','FLOAT','DOUBLE','DECIMAL','REAL')
                        if node[0]=='op':return node[1] in ('+','-','*','/') and all(numeric_median(x) for x in node[2:])
                        return node[0]=='call' and node[1]=='DIVIDE' and all(numeric_median(x) for x in node[2])
                    if not numeric_median(args[1]):raise UnsupportedSql('MEDIANX requires bounded numeric row arithmetic')
                mapping=SqlRow(table,{c:qi(alias)+'.'+qi(c) for c in cols});pred=self.scalar(source[2][1],e,scope,mapping);where=self.where(e,table)
                expr=self.scalar(args[1],e,env,mapping)
                if fn=='MEDIANX':expr='COALESCE('+expr+',0)'
                return '(SELECT '+fn[:-1].replace('AVERAGE','AVG')+'('+expr+') FROM ('+'SELECT * FROM '+self.source(table)+(' WHERE '+where if where else '')+') AS '+qi(alias)+' WHERE '+pred+')'
            raise UnsupportedSql('Iterator source')
        raise UnsupportedSql(fn)

def add_columns(engine,rows,expressions):
    """Batch context transitions over genuine column-lineage iterator domains."""
    from dax_rowset import evaluate_rows
    try:return evaluate_rows(engine,rows,expressions)
    except UnsupportedSql:pass
    from dax_vector import cumulative_columns
    try:return cumulative_columns(engine,rows,expressions)
    except UnsupportedSql:pass
    columns=rows.columns
    if not columns or any(t.startswith('__') for t,c in columns) or len({t for t,c in columns})!=1:raise UnsupportedSql('Virtual addcolumns domain')
    columns=list(columns);identities=[{(t,c):r[1][c] for t,c in columns} for r in rows]
    seen={t for t,c in columns}
    while True:
        relationship=next((r for r in engine.model.get('relationships',[]) if r.get('IsActive') and r.get('Cardinality') in ('M:1','1:1') and (r['FromTableName'],r['FromColumnName']) in columns and r['ToTableName'] not in seen),None)
        if not relationship:break
        r=relationship;seen.add(r['ToTableName']);target=engine.child([]).table(r['ToTableName'])
        index={}
        identity=lambda v:('blank',) if v is None else ('value',v.casefold() if isinstance(v,str) else v)
        for item in target:index.setdefault(identity(item[1].get(r['ToColumnName'])),[]).append(item)
        for values in identities:
            if (r['FromTableName'],r['FromColumnName']) not in values:continue
            matches=index.get(identity(values[r['FromTableName'],r['FromColumnName']]),[])
            if len(matches)>1:raise ValueError('Relationship one-side key is not unique')
            if not matches:continue
            values.update({(r['ToTableName'],c):v for c,v in matches[0][1].items()})
        columns.extend(c for c in target.columns if c not in columns)
    def safe(n):
        if n[0]=='lit':return
        if n[0]=='col' and any(m['Name'].casefold()==n[2].casefold() and (not n[1] or m['TableName'].casefold()==n[1].casefold()) for m in engine.model['measures']):return
        if n[0]=='call' and n[1]=='CALCULATE':return
        if n[0]=='call' and n[1] in ('IF','ISBLANK','NOT','BLANK'):
            for a in n[2]:safe(a)
            return
        if n[0]=='op':
            safe(n[2]);safe(n[3]);return
        raise UnsupportedSql('Addcolumns expression needs Python row context')
    for n in expressions:safe(n)
    partitions={}
    for i,lineage in enumerate(identities):partitions.setdefault(tuple(lineage),[]).append((i,lineage))
    output=[None]*len(rows)
    for keys,items in partitions.items():
        columns=list(keys)
        fields=[{'Column':{'Expression':{'SourceRef':{'Entity':t}},'Property':c}} for t,c in columns]+[{} for _ in expressions]
        base=engine.remove(columns);groups=[]
        for index,lineage in items:
            values={str(i):lineage[t,c] for i,(t,c) in enumerate(columns)}
            filters=[{'table':t,'columns':[c],'sql':qi(t)+'.'+qi(c)+(' IS NULL' if values[str(i)] is None else ' = '+sv(values[str(i)]))} for i,(t,c) in enumerate(columns)]
            groups.append({'values':values,'filters':[*base,*filters],'externalFilters':base,'scope':engine.scope})
        asts={len(columns)+i:n for i,n in enumerate(expressions)}
        # Match the visual evaluator's bounded group plans. A large iterator
        # domain must not create one native correlated plan for every row.
        for offset in range(0,len(groups),64):
            engine.check_budget()
            result=evaluate_groups(engine.con,engine.model,{'groups':groups[offset:offset+64],'fields':fields},engine.budget,asts)
            for (index,lineage),r in zip(items[offset:offset+64],result):output[index]=list(r[len(columns):])
    return output


def filter_rows(engine,source,predicate,env):
    """Push bounded base-table numeric filters down without materializing rejects."""
    from dax_runtime import Table
    from dax_runtime import RuntimeEvaluator
    if source[0]!='name' or source[1].casefold() in env:raise UnsupportedSql('Filter source')
    table=engine.canonical_table(source[1]);compiler=SqlDax(engine)
    schema=model_schema(engine,table)
    alias='__filter_row';mapping=SqlRow(table,{d[0]:qi(alias)+'.'+qi(d[0]) for d in schema})
    numeric={d[0] for d in schema if str(d[1]).startswith(('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','FLOAT','DOUBLE','DECIMAL'))}
    def value(n):
        if n[0]=='col' and n[2] in mapping:
            t,c=engine.column(('col',n[1] or table,n[2]))
            if t!=table or c not in numeric:raise UnsupportedSql('Non-numeric filter column')
        elif n[0]=='col':
            # Only explicitly context-independent measures are accepted by scalar.
            pass
        elif n[0]=='lit':
            if not isinstance(n[1],(int,float,Decimal)) or isinstance(n[1],bool):raise UnsupportedSql('Non-numeric filter literal')
        elif n[0]=='op' and n[1] in ('+','-','*','/'):
            value(n[2]);value(n[3])
        elif n[0]=='call' and n[1]=='DIVIDE':
            for a in n[2]:value(a)
        else:raise UnsupportedSql('Numeric filter expression')
        return compiler.scalar(n,compiler.engine,{},mapping)
    def pred(n):
        if n[0]=='op' and n[1] in ('&&','||'):return '('+pred(n[2])+(' AND ' if n[1]=='&&' else ' OR ')+pred(n[3])+')'
        if n[0]=='op' and n[1]=='IN' and n[2][0]=='col' and n[3][0]=='name' and n[3][1].casefold() in env:
            t,c=engine.column(n[2]);values=env[n[3][1].casefold()]
            if t!=table or not isinstance(values,Table) or len(values.columns)!=1:raise UnsupportedSql('Membership lineage')
            domain=[next(iter(r[1].values())) for r in values]
            if len(domain)>100000:raise UnsupportedSql('Membership domain budget')
            if not domain:return 'FALSE'
            name='__membership_'+uuid.uuid4().hex
            engine.con.execute('CREATE TEMP TABLE '+qi(name)+' AS SELECT unnest(?) AS value',[domain])
            reference=mapping[c];member='__member.value'
            if next(str(d[1]) for d in schema if d[0]==c)=='VARCHAR':reference='lower('+reference+')';member='lower('+member+')'
            return 'EXISTS (SELECT 1 FROM '+qi(name)+' AS __member WHERE '+member+' IS NOT DISTINCT FROM '+reference+')'
        if n[0]!='op' or n[1] not in ('=','<>','<','>','<=','>='):raise UnsupportedSql('Numeric filter predicate')
        a,b=value(n[2]),value(n[3])
        return '(COALESCE('+a+',0) '+n[1]+' COALESCE('+b+',0))'
    condition=pred(predicate);where=compiler.where(compiler.engine,table)
    sql='SELECT * FROM (SELECT * FROM '+compiler.source(table)+(' WHERE '+where if where else '')+') AS '+qi(alias)+' WHERE '+condition+' LIMIT 100001'
    engine.check_budget()
    timer=threading.Timer(max(.001,engine.budget['deadline']-time.monotonic()),engine.con.interrupt);timer.daemon=True;timer.start()
    try:rows=engine.con.execute(sql).fetchall()
    except Exception:
        check_budget(engine.budget);raise
    finally:timer.cancel()
    engine.check_budget()
    if len(rows)>100000:raise UnsupportedSql('Filter row budget')
    cols=[d[0] for d in schema]
    return Table([(table,dict(zip(cols,r))) for r in rows],[(table,c) for c in cols])

def evaluate_scalar(engine,name,table=None):
    return evaluate_expression(engine,('col',table,name))

def evaluate_expression(engine,node,env=None):
    bindings={k:((('lit',v) if v is None or isinstance(v,(str,int,float,bool,Decimal)) else ('__unsupported',)),{}) for k,v in (env or {}).items()}
    compiler=SqlDax(engine);sql='SELECT '+compiler.scalar(node,env=bindings)
    check_budget(engine.budget)
    cache=engine.budget.setdefault('scalar_sql_values',{})
    if sql in cache:return cache[sql]
    timer=threading.Timer(max(.001,engine.budget['deadline']-time.monotonic()),engine.con.interrupt);timer.daemon=True;timer.start()
    try:result=engine.con.execute(sql).fetchone()[0]
    except Exception:
        check_budget(engine.budget)
        raise
    finally:timer.cancel()
    check_budget(engine.budget)
    if len(cache)<2000 and not isinstance(result,str):cache[sql]=result
    return result

def evaluate_groups(con,model,payload,budget,expressions_by_index=None):
    """Lower a common filter context over typed group identities in one query."""
    from dax_grouped import evaluate_grouped
    try:return evaluate_grouped(con,model,payload,budget,expressions_by_index)
    except UnsupportedSql:pass
    from dax_runtime import RuntimeEvaluator
    groups=payload['groups'];fields=payload['fields']
    if not groups:raise UnsupportedSql('Empty context')
    grouping=[(i,f.get('Column') or f.get('GroupRef')) for i,f in enumerate(fields) if f.get('Column') or f.get('GroupRef')]
    if not grouping:raise UnsupportedSql('No grouping identities')
    external=groups[0].get('externalFilters');scope=groups[0].get('scope')
    if external is None or any(g.get('externalFilters')!=external or g.get('scope')!=scope for g in groups):raise UnsupportedSql('Distinct contexts')
    engine=RuntimeEvaluator(con,model,{},filters=list(external),budget=budget);engine.scope=[tuple(c) for c in scope or []];engine.external_filters=external
    cols=[];filters=list(external);bound={};types=[]
    for index,c in grouping:
        table,col=engine.column(('col',c['Expression']['SourceRef']['Entity'],c['Property']));cols.append(index)
        dtype=type_name(engine,table,col)
        if dtype=='DATE' or dtype.startswith('TIMESTAMP'):raise UnsupportedSql('Temporal groups use bounded scalar plans')
        if not all(ch.isalnum() or ch in '(),_ ' for ch in dtype):raise UnsupportedSql('Group type')
        types.append(dtype);ref='"__g".'+qi('v'+str(index));bound[table,col]=ref
        filters.append({'table':table,'columns':[col],'sql':qi(table)+'.'+qi(col)+' IS NOT DISTINCT FROM '+ref})
    # Only the canonical per-group equality predicates may be replaced by aliases.
    for group in groups:
        if any(str(i) not in group.get('values',{}) and i not in group.get('values',{}) for i in cols):raise UnsupportedSql('Missing group value')
        tail=group.get('filters',[])[len(external):]
        if len(tail)!=len(grouping):raise UnsupportedSql('Additional group predicates')
        for f,(i,c) in zip(tail,grouping):
            value=group['values'].get(str(i),group['values'].get(i));table=c['Expression']['SourceRef']['Entity'];column=c['Property']
            expected=qi(table)+'.'+qi(column)+(' IS NULL' if value is None else ' = '+sv(value))
            # Browser group filters use JSON/JavaScript number literals. The
            # bound group relation below gives floats their exact DOUBLE type.
            legacy=qi(table)+'.'+qi(column)+' = '+str(value) if isinstance(value,float) else expected
            if f.get('sql') not in (expected,legacy):raise UnsupportedSql('Noncanonical group predicate')
    engine.filters=filters;engine.sql_bound_groups=bound;compiler=SqlDax(engine);compiler.shared_aggregates={'queries':{},'bytes':0}
    values=[]
    for i,g in enumerate(groups):
        parts=[str(i)]+['CAST('+sv(g['values'].get(str(index),g['values'].get(index)))+' AS '+dtype+')' for (index,c),dtype in zip(grouping,types)]
        values.append('('+','.join(parts)+')')
    expressions=[]
    for i,f in enumerate(fields):
        if expressions_by_index and i in expressions_by_index:expr=compiler.scalar(expressions_by_index[i])
        elif f.get('Column') or f.get('GroupRef'):expr='"__g".'+qi('v'+str(i))
        elif f.get('Measure'):
            m=f['Measure'];expr=compiler.scalar(('col',m.get('Expression',{}).get('SourceRef',{}).get('Entity'),m['Property']))
        elif f.get('Aggregation'):
            a=f['Aggregation'];c=a['Expression'].get('Column');fn={0:'SUM',1:'AVERAGE',2:'DISTINCTCOUNT',3:'MIN',4:'MAX',5:'COUNTA',6:'MEDIAN'}.get(a['Function'])
            if not c or not fn:raise UnsupportedSql('Aggregate form')
            expr=compiler.scalar(('call',fn,[('col',c['Expression']['SourceRef']['Entity'],c['Property'])]))
        else:raise UnsupportedSql('Visual expression')
        expressions.append(expr+' AS '+qi('out'+str(i)))
    if compiler.has_row_transition and len(groups)>1:raise UnsupportedSql('Nested row transitions use bounded scalar groups')
    relation=None
    if len(groups)>1024:
        relation='__dax_groups_'+uuid.uuid4().hex
        import pyarrow as pa
        view=relation+'_input'
        records={'__index':pa.array(range(len(groups)),type=pa.int64())}
        for index in cols:
            records['v'+str(index)]=pa.array([None if g['values'].get(str(index),g['values'].get(index)) is None else str(g['values'].get(str(index),g['values'].get(index))) for g in groups],type=pa.string())
        con.register(view,pa.table(records))
        try:con.execute('CREATE TEMP TABLE '+qi(relation)+' AS SELECT __index,'+','.join('CAST('+qi('v'+str(i))+' AS '+dtype+') AS '+qi('v'+str(i)) for i,dtype in zip(cols,types))+' FROM '+qi(view))
        finally:con.unregister(view)
        domain=qi(relation)+' AS "__g"'
    else:domain='(VALUES '+','.join(values)+') AS "__g"("__index",'+','.join(qi('v'+str(i)) for i in cols)+')'
    shared=compiler.shared_aggregates['queries']
    joins=''.join(' CROSS JOIN LATERAL (SELECT '+expression+' AS "value") AS '+qi(alias) for expression,alias in shared.items())
    sql='SELECT '+','.join(expressions)+' FROM '+domain+joins+' ORDER BY "__g"."__index"'
    try:check_budget(budget)
    except Exception:
        if relation:con.execute('DROP TABLE IF EXISTS '+qi(relation))
        raise
    timer=threading.Timer(max(.001,budget['deadline']-time.monotonic()),con.interrupt);timer.daemon=True;timer.start()
    try:
        rows=con.execute(sql).fetchall()
        if shared:budget['shared_aggregate_plans']=budget.get('shared_aggregate_plans',0)+1
    except Exception:
        check_budget(budget)
        raise
    finally:
        timer.cancel()
        if relation:con.execute('DROP TABLE IF EXISTS '+qi(relation))
    check_budget(budget)
    return rows


def rank_value(engine,args,env,row):
    """Batch scores for column-lineage ALL/ALLSELECTED RANKX domains.

    Only measure-based scores are lowered: a bare aggregate has different row
    context semantics. The secured connection remains the source even for ALL.
    """
    import bisect
    if row is not None or engine.row_stack or env:raise UnsupportedSql('Outer iterator or variable rank context')
    source=args[0]
    if source[0]!='call' or source[1] not in ('ALL','ALLSELECTED') or not source[2] or any(n[0]!='col' for n in source[2]):
        raise UnsupportedSql('Rank domain')
    columns=[engine.column(n) for n in source[2]]
    if len({t for t,c in columns})!=1:raise UnsupportedSql('Rank domain tables')
    def safe(n):
        if n[0]=='call' and n[1] in ('SUM','AVERAGE','COUNT','COUNTA','MIN','MAX','DISTINCTCOUNT','COUNTROWS'):
            raise UnsupportedSql('Bare rank aggregate')
        if n[0]=='call':
            for a in n[2]:safe(a)
        elif n[0]=='op':safe(n[2]);safe(n[3])
    safe(args[1])
    filters=engine.remove(columns) if source[1]=='ALL' else engine.selected_filters(source[2])
    key=(repr(columns),repr(args[1]),repr(filters),repr(env),repr(engine.scope),repr(engine.model.get('relationships',[])))
    cache=engine.budget.setdefault('rank_domains',{})
    if key not in cache:
        if len(cache)>=64:raise UnsupportedSql('Rank cache domain limit')
        base=engine.child(filters);base.external_filters=[]
        compiler=SqlDax(base);table=columns[0][0]
        refs=[qi(t)+'.'+qi(c) for t,c in columns]
        where=base.where(table)
        domain='SELECT DISTINCT '+','.join(ref+' AS '+qi('k'+str(i)) for i,ref in enumerate(refs))+' FROM '+qi(table)+(' WHERE '+where if where else '')
        score=base.child(list(filters));score.external_filters=[]
        for i,(t,c) in enumerate(columns):
            score.filters.append({'table':t,'columns':[c],'sql':qi(t)+'.'+qi(c)+' IS NOT DISTINCT FROM "__rank_g".'+qi('k'+str(i))})
        sql='SELECT '+compiler.scalar(args[1],score,env)+' AS "score" FROM ('+domain+') AS "__rank_g" LIMIT 100001'
        check_budget(engine.budget)
        timer=threading.Timer(max(.001,engine.budget['deadline']-time.monotonic()),engine.con.interrupt);timer.daemon=True;timer.start()
        try:scores=[r[0] for r in engine.con.execute(sql).fetchall()]
        finally:timer.cancel()
        if len(scores)>100000:raise ValueError('RANKX score domain exceeds 100,000 rows')
        if any(v is not None and not isinstance(v,(int,float,Decimal)) for v in scores):raise UnsupportedSql('Non-numeric rank scores')
        cache[key]=sorted(0 if v is None else v for v in scores)
    scores=cache[key]
    target=engine.scalar(engine.run(args[2] if len(args)>2 and args[2]!=('lit',None) else args[1],env,row))
    target=0 if target is None else target
    ascending=engine.scalar(engine.run(args[3],env,row)) if len(args)>3 else False
    ties=engine.scalar(engine.run(args[4],env,row)) if len(args)>4 else 'SKIP'
    if ties not in ('SKIP','DENSE',None):raise ValueError('RANKX ties must be SKIP or DENSE')
    if ties=='DENSE':scores=sorted(set(scores))
    return (bisect.bisect_left(scores,target) if ascending in (True,1,'ASC') else len(scores)-bisect.bisect_right(scores,target))+1


def iterator_scores(e,expr,values):
    """Batch simple same-table aggregate measure keys without per-row SQL."""
    import re
    if not values or expr[0]!='col':raise UnsupportedSql('Iterator score expression')
    table=values[0][0]
    if table.startswith('__') or any(r[0]!=table for r in values):raise UnsupportedSql('Virtual iterator score')
    matches=[m for m in e.model['measures'] if m['Name'].casefold()==expr[2].casefold() and (not expr[1] or m['TableName'].casefold()==expr[1].casefold())]
    if len(matches)!=1:raise UnsupportedSql('Iterator measure')
    ast=cached_ast(e,matches[0]['Expression'])
    if ast[0]!='call' or ast[1] not in ('SUM','AVERAGE','MIN','MAX','COUNT') or len(ast[2])!=1 or ast[2][0][0]!='col':raise UnsupportedSql('Complex iterator measure')
    target,column=e.column(ast[2][0])
    if target!=table:raise UnsupportedSql('Related iterator aggregate')
    e.check_budget();cursor=e.con.execute('SELECT * FROM '+qi(table)+((' WHERE '+e.where(table)) if e.where(table) else '')+' LIMIT 100001');names=[d[0] for d in cursor.description]
    if values.columns!=[(table,c) for c in names]:raise UnsupportedSql('Partial iterator row context')
    rows=cursor.fetchall()
    if len(rows)>100000:raise UnsupportedSql('Iterator source row budget')
    index=names.index(column);groups={}
    for item in rows:
        e.check_budget();key=tuple(v.casefold() if isinstance(v,str) else v for v in item);groups.setdefault(key,[]).append(item[index])
    scores={}
    for key,items in groups.items():
        valid=[x for x in items if x is not None];fn=ast[1]
        scores[key]=(len(valid) or None) if fn=='COUNT' else None if not valid else sum(valid) if fn=='SUM' else sum(valid)/len(valid) if fn=='AVERAGE' else min(valid) if fn=='MIN' else max(valid)
    return scores
