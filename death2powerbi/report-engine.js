/* Deliberately bounded PBIR-to-SQL translator. Unsupported semantics fail closed. */
(function(root){
const qi=s=>'"'+String(s).replaceAll('"','""')+'"';
const fail=m=>{throw Error(m)};
function literal(v){
 const s=v?.Literal?.Value;
 if(typeof s!=='string')return fail('Unsupported filter literal.');
 if(s==='null')return null;
 if(s==='true'||s==='false')return s==='true';
 if(s.startsWith("'")&&s.endsWith("'"))return s.slice(1,-1).replaceAll("''","'");
 if(/^[-+]?\d+(?:\.\d+)?(?:[dDlLmM])?$/.test(s))return Number(s.replace(/[dDlLmM]$/,''));
 if(/^datetime'[^']+'$/i.test(s))return s.slice(9,-1);
 return fail('Unsupported filter literal: '+s);
}
const sqlValue=v=>v===null?'NULL':typeof v==='number'?String(v):typeof v==='boolean'?String(v):"'"+String(v).replaceAll("'","''")+"'";
function column(expr,aliases={}){
 const c=expr?.Column||expr?.GroupRef;
 if(!c)return fail('This filter or field is not a direct column.');
 const source=c.Expression?.SourceRef||{};
 const table=source.Entity||aliases[source.Source];
 if(!table||!c.Property)return fail('Unresolved source column.');
 return {table,column:c.Property};
}
const colsql=c=>qi(c.table)+'.'+qi(c.column);
function filterEntries(value){
 if(!value)return [];
 if(Array.isArray(value))return value.flatMap(filterEntries);
 if(value.reportFilters)return filterEntries(value.reportFilters);
 if(Array.isArray(value.filters))return value.filters.flatMap(filterEntries);
 return [value];
}
function parseFilters(values){
 const result=[];
 for(const entry of filterEntries(values)){
  // A filter-well or drill-through field without a predicate is not a selection.
  if(!entry.filter){
   if(entry.Condition)return fail('Unsupported legacy filter expression.');
   if(entry.expression){
    const keys=Object.keys(entry.expression);
    const fields=['Column','GroupRef','Measure','Aggregation','Hierarchy','HierarchyLevel'];
    if(keys.length!==1||!fields.includes(keys[0]))return fail('Unsupported legacy filter expression.');
   }
   continue;
  }
  const f=entry.filter, aliases=Object.fromEntries((f.From||[]).map(x=>[x.Name,x.Entity]));
  if(Object.keys(f).some(k=>!['Version','From','Where'].includes(k)))fail('Unsupported source filter structure.');
  for(const where of f.Where||[]){
   const tupleFilter=where.Condition?.In;
   if(tupleFilter){
    const columns=tupleFilter.Expressions.map(e=>column(e,aliases));
    if(new Set(columns.map(c=>c.table)).size>1){
     result.push({alternatives:tupleFilter.Values.map(row=>{if(row.length!==columns.length)fail('Invalid categorical selection.');return row.map((v,i)=>{const value=literal(v);return {table:columns[i].table,columns:[columns[i].column],sql:colsql(columns[i])+(value===null?' IS NULL':' = '+sqlValue(value))}})})});
     continue;
    }
   }
   const tables=new Set(),usedColumns=new Set();
   function field(x){const c=column(x,aliases);tables.add(c.table);usedColumns.add(c.column);return colsql(c)}
   function condition(c){
    if(c.In){const a=c.In;const fields=a.Expressions.map(field);if(!a.Values.length)return 'FALSE';return '('+a.Values.map(row=>{if(row.length!==fields.length)fail('Invalid categorical filter.');return '('+row.map((v,i)=>{const value=literal(v);return fields[i]+(value===null?' IS NULL':' = '+sqlValue(value))}).join(' AND ')+')'}).join(' OR ')+')'}
    if(c.Not)return '(NOT '+condition(c.Not.Expression||c.Not)+')';
    if(c.And||c.Or){const a=c.And||c.Or;return '('+condition(a.Left)+(c.And?' AND ':' OR ')+condition(a.Right)+')'}
    if(c.Comparison){const a=c.Comparison;const ops={0:'=',1:'>',2:'>=',3:'<',4:'<=',5:'<>'};const op=ops[a.ComparisonKind];if(!op)fail('Unsupported comparison kind.');const left=field(a.Left),v=literal(a.Right);return left+(v===null?(op==='='?' IS NULL':op==='<>'?' IS NOT NULL':fail('Invalid NULL comparison.')):' '+op+' '+sqlValue(v))}
    return fail('Unsupported source filter condition: '+Object.keys(c||{}).join(', '));
   }
   const sql=condition(where.Condition);
   if(tables.size!==1)fail('Multi-table filter predicates need further translation.');
   result.push({table:[...tables][0],columns:[...usedColumns],sql});
  }
 }
 return result;
}
function relationPath(from,to,relationships){
 const queue=[[from,[]]],seen=new Set([from]);
 while(queue.length){const [t,path]=queue.shift();if(t===to)return path;
  for(const r of relationships||[]){if(!r.IsActive||!['M:1','1:1'].includes(r.Cardinality))continue;
   // Search from the queried table towards dimensions whose filters reach it.
   const edges=[{a:r.FromTableName,ac:r.FromColumnName,b:r.ToTableName,bc:r.ToColumnName}];
   if(r.CrossFilteringBehavior==='Both')edges.push({a:r.ToTableName,ac:r.ToColumnName,b:r.FromTableName,bc:r.FromColumnName});
   for(const e of edges)if(e.a===t&&!seen.has(e.b)){seen.add(e.b);queue.push([e.b,[...path,e]])}
  }
 }
 return null;
}
function whereFor(table,filters,model){
 const combined=new Map();for(const f of filters.filter(f=>!f.alternatives))combined.set(f.table,[...(combined.get(f.table)||[]),f.sql]);
 const terms=[...combined].map(([table,conditions])=>({table,sql:'('+conditions.join(' AND ')+')'})).map(f=>{if(f.table===table)return f.sql;const path=relationPath(table,f.table,model.relationships);if(!path)return null;
  let sql=f.sql;for(const e of [...path].reverse())sql='EXISTS (SELECT 1 FROM '+qi(e.b)+' WHERE '+qi(e.b)+'.'+qi(e.bc)+' = '+qi(e.a)+'.'+qi(e.ac)+' AND '+sql+')';return sql;
 }).filter(Boolean);
 for(const f of filters.filter(f=>f.alternatives))terms.push(f.alternatives.length?'('+f.alternatives.map(row=>'('+ (whereFor(table,row,model)||'TRUE') +')').join(' OR ')+')':'FALSE');
 return terms.join(' AND ');
}
function projections(def){
 const state=def.query?.queryState;
 if(!state)return fail('Legacy visual queries need further translation.');
 return Object.values(state).flatMap(role=>(role.projections||[]).filter(p=>p.active!==false));
}
function dateHierarchy(e,model){
 const h=e?.HierarchyLevel, hierarchy=h?.Expression?.Hierarchy;
 const source=hierarchy?.Expression?.PropertyVariationSource;
 if(!source||hierarchy.Hierarchy!=='Date Hierarchy'||!['Year','Quarter','Month','Day'].includes(h.Level))return fail('Unsupported hierarchy definition.');
 const table=source.Expression?.SourceRef?.Entity,property=source.Property;
 const matches=(model.relationships||[]).filter(r=>r.IsActive&&r.FromTableName===table&&r.FromColumnName===property&&r.ToTableName?.startsWith('LocalDateTable_'));
 if(matches.length!==1)return fail('Cannot resolve the automatic date hierarchy relationship.');
 const column=h.Level==='Month'?'MonthNo':h.Level==='Quarter'?'QuarterNo':h.Level;
 if(!model.tables?.find(t=>t.name===matches[0].ToTableName)?.columns.some(c=>c.name===column))return fail('The date hierarchy column was not imported.');
 return {table:matches[0].ToTableName,column,sourceTable:table,sourceColumn:property,level:h.Level};
}
function normalizeDateAxis(model,visual){
 const ps=visual.definition?.query?.queryState?.Category?.projections?.filter(p=>p.active!==false)||[];
 if(ps.length<2||!ps.every(p=>p.field?.HierarchyLevel))return visual;
 const levels=ps.map(p=>dateHierarchy(p.field,model)),first=levels[0];
 const order=['Year','Quarter','Month','Day'];
 if(first.level!=='Year'||levels.some(l=>l.table!==first.table)||levels.some((l,i)=>i&&order.indexOf(l.level)<=order.indexOf(levels[i-1].level)))return fail('Unsupported date hierarchy drill combination.');
 const deepest=levels.at(-1),copy=structuredClone(visual);
 copy.definition.query.queryState.Category.projections=[{field:{DateBucket:{table:first.sourceTable,column:first.sourceColumn,unit:deepest.level.toLowerCase()}},nativeQueryRef:first.sourceColumn}];
 // A date axis has one chronological identity, rather than numeric year/day value series.
 for(const sort of copy.definition.query.sortDefinition?.sort||[])if(ps.some(p=>JSON.stringify(p.field)===JSON.stringify(sort.field)))sort.field=copy.definition.query.queryState.Category.projections[0].field;
 return copy;
}
function buildQuery(model,page,visual,extra=[]){
 visual=normalizeDateAxis(model,visual);
 const def=visual.definition;
 const filters=parseFilters([page.reportFilters,page.filters,visual.filters,...extra]);
 const tables=new Set(),aggregateTables=new Set(),labels=[],groups=[],stack=new Set(),warnings=[];
 const fields=projections(def);
 function measure(m){
  const name=m.Property,table=m.Expression?.SourceRef?.Entity;
  const matches=model.measures.filter(x=>(x.Name||x.MeasureName)===name&&(!table||!x.TableName||x.TableName===table));
  if(matches.length!==1)fail('Cannot resolve measure: '+name);
  if(stack.has(name))fail('Cyclic measure dependency.');stack.add(name);
  const text=matches[0].Expression.trim();let sql;
  if(/^[-+]?\d*\.?\d+$/.test(text))sql=text;
  else{
   const agg=text.match(/^(SUM|AVERAGE|MIN|MAX|COUNT|DISTINCTCOUNT)\s*\(\s*(?:(?:'([^']+)'|([\w ]+))\s*)?\[([^\]]+)\]\s*\)$/i);
   if(agg){const t=agg[2]||agg[3]||matches[0].TableName||table;if(!t)fail('Cannot resolve the home table for DAX aggregate '+name);tables.add(t);aggregateTables.add(t);const c=qi(t)+'.'+qi(agg[4]);sql=agg[1].toUpperCase()==='DISTINCTCOUNT'?'COUNT(DISTINCT '+c+')':({AVERAGE:'AVG'}[agg[1].toUpperCase()]||agg[1].toUpperCase())+'('+c+')'}
   else{
    const reference=text.match(/^\[([^\]]+)\]$/);
    const countRows=text.match(/^COUNTROWS\s*\(\s*(?:'([^']+)'|([\w ]+))\s*\)$/i);
    const divide=text.match(/^DIVIDE\s*\((.*)\)$/is);
    if(reference)sql=measure({Property:reference[1]}).sql;
    else if(countRows){const t=countRows[1]||countRows[2];tables.add(t);aggregateTables.add(t);sql='NULLIF(COUNT(*),0)'}
    else if(divide){
     let depth=0,start=0,quote=null;const args=[];
     for(let i=0;i<divide[1].length;i++){const c=divide[1][i];if(quote){if(c===quote){if(divide[1][i+1]===quote)i++;else quote=null}continue}if(c==='\''||c==='"'){quote=c;continue}if(c==='('||c==='[')depth++;if(c===')'||c===']')depth--;if(c===','&&!depth){args.push(divide[1].slice(start,i).trim());start=i+1}}
     args.push(divide[1].slice(start).trim());
     if(args.length<2||args.length>3)fail('DIVIDE expects two or three arguments.');
     function operand(value){if(/^[-+]?\d*\.?\d+$/.test(value))return value;const ref=value.match(/^\[([^\]]+)\]$/);if(ref)return measure({Property:ref[1]}).sql;fail('DIVIDE currently supports numeric literals and measure references.')}
     const left=operand(args[0]),right=operand(args[1]),alternate=args[2]?operand(args[2]):'NULL';
     sql='CASE WHEN ('+right+') IS NULL OR ('+right+')=0 THEN '+alternate+' ELSE ('+left+')/('+right+') END';
    }else fail('DAX measure “'+name+'” needs a SQL mapping; this DAX expression is not supported yet.');
   }
  }
  stack.delete(name);return {sql,aggregate:!/^[-+]?\d*\.?\d+$/.test(text)};
 }
 function expression(e){
  if(e.HierarchyLevel){const c=dateHierarchy(e,model);tables.add(c.table);return {sql:colsql(c),aggregate:false}}
  if(e.DateBucket){const c=e.DateBucket;if(!['year','quarter','month','day'].includes(c.unit))fail('Unsupported date grain.');tables.add(c.table);return {sql:"date_trunc('"+c.unit+"', "+colsql(c)+')',aggregate:false}}
  if(e.Column||e.GroupRef){const c=column(e);tables.add(c.table);return {sql:colsql(c),aggregate:false}}
  if(e.Measure)return measure(e.Measure);
  if(e.Aggregation){const a=e.Aggregation,c=expression(a.Expression);aggregateTables.add(column(a.Expression).table);if(c.aggregate)fail('Nested aggregation unsupported.');const fn={0:'SUM',1:'AVG',2:'COUNT',3:'MIN',4:'MAX',5:'DISTINCTCOUNT'}[a.Function];if(!fn)fail('Unsupported aggregation.');return {sql:fn==='DISTINCTCOUNT'?'COUNT(DISTINCT '+c.sql+')':fn+'('+c.sql+')',aggregate:true}}
  if(e.Arithmetic){const a=e.Arithmetic,l=expression(a.Left),r=expression(a.Right),op={0:'+',1:'-',2:'*',3:'/'}[a.Operator];if(!op)fail('Unsupported arithmetic.');return {sql:'('+l.sql+op+(op==='/'?'NULLIF('+r.sql+',0)':r.sql)+')',aggregate:l.aggregate||r.aggregate}}
  if(e.ScopedEval&&Array.isArray(e.ScopedEval.Scope)&&!e.ScopedEval.Scope.length){const a=expression(e.ScopedEval.Expression);if(!a.aggregate)fail('Total scope requires an aggregate.');return {sql:'SUM('+a.sql+') OVER ()',aggregate:true}}
  return fail('Unsupported visual field expression: '+Object.keys(e).join(', '));
 }
 const selections=fields.map((p,i)=>{const e=expression(p.field);labels.push(p.displayName||p.nativeQueryRef||p.queryRef||'Value');if(!e.aggregate)groups.push(e.sql);return {...e,sql:e.sql+' AS '+qi('v'+i)}});
 if(!selections.length)fail('No query fields found.');
 if(aggregateTables.size>1)fail('Measures from multiple fact tables require separate aggregation plans.');
 const table=[...aggregateTables][0]||[...tables][0];
 let from=table?qi(table):'',joined=new Set(table?[table]:[]);
 for(const target of tables){
  if(joined.has(target))continue;
  const path=relationPath(table,target,model.relationships);
  if(path){
   for(const e of path)if(!joined.has(e.b)){
    const r=model.relationships.find(r=>(r.FromTableName===e.a&&r.ToTableName===e.b&&r.FromColumnName===e.ac&&r.ToColumnName===e.bc)||(r.Cardinality==='1:1'&&r.FromTableName===e.b&&r.ToTableName===e.a&&r.FromColumnName===e.bc&&r.ToColumnName===e.ac));
    if(!r||!['M:1','1:1'].includes(r.Cardinality))fail('Reverse many-side projections need a separate aggregation plan.');
    from+=' LEFT JOIN '+qi(e.b)+' ON '+qi(e.a)+'.'+qi(e.ac)+' = '+qi(e.b)+'.'+qi(e.bc);joined.add(e.b);
   }
  }else{
   const columns=fields.filter(p=>p.field.Column||p.field.GroupRef).map(p=>column(p.field)).filter(c=>c.table===target).map(c=>qi(c.column));
   if(!columns.length)fail('Disconnected aggregate expressions need a separate aggregation plan.');
   const where=whereFor(target,filters,model);
   from+=' CROSS JOIN (SELECT DISTINCT '+[...new Set(columns)].join(',')+' FROM '+qi(target)+(where?' WHERE '+where:'')+') AS '+qi(target);joined.add(target);
   warnings.push(target+' has no active filter path to '+table+'. The filtered total repeats for each disconnected category.');
  }
 }
 let sql='SELECT '+selections.map(s=>s.sql).join(', ')+(from?' FROM '+from:'');
 const where=table?whereFor(table,filters,model):'';if(where)sql+=' WHERE '+where;
 if(selections.some(s=>s.aggregate)&&groups.length)sql+=' GROUP BY '+groups.join(', ');
 else if(!selections.some(s=>s.aggregate)&&!['histogram','histogramChart','boxplot','boxPlot','stripPlot','stripChart','ternaryPlot','ternaryChart','scatterChart','pointMap','map'].includes(visual.type))sql=sql.replace('SELECT ','SELECT DISTINCT ');
 const sorts=def.query?.sortDefinition?.sort||[];
 if(sorts.length){const parts=sorts.map(s=>{const i=fields.findIndex(p=>JSON.stringify(p.field)===JSON.stringify(s.field));if(i<0)fail('Source sort field is not projected.');return qi('v'+i)+(s.direction==='Descending'?' DESC':' ASC')});sql+=' ORDER BY '+parts.join(', ')}
 else if(fields.some(p=>p.field.DateBucket))sql+=' ORDER BY '+qi('v'+fields.findIndex(p=>p.field.DateBucket))+' ASC';
 return {sql,labels,warnings,formats:fields.map(p=>fieldFormat(model,p)),roles:Object.entries(def.query.queryState).flatMap(([role,v])=>(v.projections||[]).filter(p=>p.active!==false).map(()=>role))};
}
function fieldFormat(model,p){
 if(p.format)return p.format;
 let f=p.field;while(f.Aggregation)f=f.Aggregation.Expression;
 if(f.Measure){const m=f.Measure;return model.measures.find(x=>x.Name===m.Property&&(!m.Expression?.SourceRef?.Entity||x.TableName===m.Expression.SourceRef.Entity))?.FormatString||''}
 const c=f.Column||f.GroupRef;return c?model.tables?.find(t=>t.name===c.Expression?.SourceRef?.Entity)?.columns?.find(x=>x.name===c.Property)?.formatString||'':'';
}
async function pythonQuery(model,page,visual,extra,query,api){
 const fields=projections(visual.definition),indices=fields.map((p,i)=>p.field.Column||p.field.GroupRef?i:-1).filter(i=>i>=0);
 const filters=parseFilters([page.reportFilters,page.filters,visual.filters,...extra]);
 let groupRows=[[]];
 if(indices.length){
  const def={...visual.definition,query:{queryState:{Category:{projections:indices.map(i=>fields[i])}}}};
  const plan=buildQuery(model,page,{...visual,type:'tableEx',definition:def},extra),result=await query(plan.sql);
  if(result.truncated)throw Error('Python DAX grouping exceeds 1,000 groups. Narrow the filters.');groupRows=result.rows;
 }
 const groups=groupRows.map(row=>{
  const groupFilters=indices.map((i,j)=>{const c=column(fields[i].field);return {table:c.table,columns:[c.column],sql:colsql(c)+(row[j]===null?' IS NULL':' = '+sqlValue(row[j]))}});
  return {values:Object.fromEntries(indices.map((i,j)=>[i,row[j]])),externalFilters:filters,filters:[...filters,...groupFilters],scope:indices.map(i=>{const c=column(fields[i].field);return [c.table,c.column]}),contexts:Object.fromEntries(model.tables.map(t=>[t.name,whereFor(t.name,[...filters,...groupFilters],model)]))};
 });
 const result=await api('/api/dax',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:model.id,fields:fields.map(p=>p.field),contexts:{},groups})});
 const sorts=visual.definition.query?.sortDefinition?.sort||[];
 if(sorts.length){
  const indices=sorts.map(sort=>{const index=fields.findIndex(p=>JSON.stringify(p.field)===JSON.stringify(sort.field));if(index<0)fail('Source sort field is not projected.');return {index,descending:sort.direction==='Descending'}});
  result.rows.sort((a,b)=>{for(const sort of indices){const x=a[sort.index],y=b[sort.index];let order=x===y?0:x===null?-1:y===null?1:typeof x==='string'&&typeof y==='string'?x.localeCompare(y):x<y?-1:1;if(order)return sort.descending?-order:order}return 0});
 }
 return {compiled:{labels:fields.map(p=>p.displayName||p.nativeQueryRef||p.queryRef||'Value'),formats:fields.map(p=>fieldFormat(model,p)),roles:Object.entries(visual.definition.query.queryState).flatMap(([role,v])=>(v.projections||[]).filter(p=>p.active!==false).map(()=>role)),warnings:[]},result};
}
const api={pythonQuery,fieldFormat,literal,parseFilters,whereFor,buildQuery,filterEntries};
if(typeof module!=='undefined')module.exports=api;root.ReportEngine=api;
})(globalThis);
