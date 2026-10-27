/* Deliberately bounded PBIR-to-SQL translator. Unsupported semantics fail closed. */
(function(root){
const qi=s=>'"'+String(s).replaceAll('"','""')+'"';
const fail=m=>{throw Error(m)};
function assertTableAvailable(model,table){
 if(typeof table!=='string')return;
 const key=table.toLowerCase();if((model.tables||[]).some(item=>String(item.name).toLowerCase()===key))return;
 const unavailable=(model.unavailableTables||[]).find(item=>String(item.name).toLowerCase()===key);if(!unavailable)return;
 const error=Error('Data for source table “'+unavailable.name+'” could not be extracted during import.'+(unavailable.error?' Extraction error: '+unavailable.error:''));error.code='SOURCE_DATA_UNAVAILABLE';throw error;
}
function assertPhysicalFieldsAvailable(model,fields){
 function walk(node){if(!node||typeof node!=='object'||node.Measure)return;const column=node.Column||node.GroupRef;if(column)assertTableAvailable(model,column.Expression?.SourceRef?.Entity);if(node.DateBucket)assertTableAvailable(model,node.DateBucket.table);if(node.GeoMean)assertTableAvailable(model,node.GeoMean.table);for(const value of Object.values(node))if(value&&typeof value==='object')walk(value)}
 fields.forEach(walk);
}
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
function temporalMillis(value){
 if(value==null)return Date.parse('1899-12-30T00:00:00Z');
 if(typeof value==='number'){const date=Date.parse('1899-12-30T00:00:00Z')+value*86400000;return Number.isFinite(date)&&Math.abs(date)<=8.64e15?date:NaN}
 const text=String(value).replace(' ','T');if(!/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)?$/.test(text))return NaN;
 return Date.parse(text.length===10?text+'T00:00:00Z':text.endsWith('Z')?text:text+'Z');
}
function dateSpanBounds(value){
 if(!value?.DateSpan)return null;
 const span=value.DateSpan,raw=span.Expression?.Literal?.Value;
 if(typeof raw!=='string'||!/^datetime'[^']+'$/i.test(raw)||!Number.isInteger(span.TimeUnit))fail('DateSpan requires a static datetime and supported time unit.');
 const start=new Date(temporalMillis(literal(span.Expression)));if(!Number.isFinite(start.getTime()))fail('Invalid DateSpan datetime.');
 switch(span.TimeUnit){
  case 0:start.setUTCHours(0,0,0,0);break;
  case 2:start.setUTCDate(1);start.setUTCHours(0,0,0,0);break;
  case 3:start.setUTCMonth(0,1);start.setUTCHours(0,0,0,0);break;
  case 4:start.setUTCFullYear(Math.floor(start.getUTCFullYear()/10)*10,0,1);start.setUTCHours(0,0,0,0);break;
  case 5:start.setUTCMilliseconds(0);break;
  case 6:start.setUTCSeconds(0,0);break;
  case 7:start.setUTCMinutes(0,0,0);break;
  default:fail('Unsupported DateSpan time unit. Week spans require an explicit week-start convention.');
 }
 const end=new Date(start);if(span.TimeUnit===0)end.setUTCDate(end.getUTCDate()+1);else if(span.TimeUnit===2)end.setUTCMonth(end.getUTCMonth()+1);else if(span.TimeUnit===3||span.TimeUnit===4)end.setUTCFullYear(end.getUTCFullYear()+(span.TimeUnit===4?10:1));else end.setTime(end.getTime()+({5:1000,6:60000,7:3600000})[span.TimeUnit]);
 return {start:start.toISOString().slice(0,-1),end:end.toISOString().slice(0,-1)};
}
function dateSpanSQL(reference,kind,span){
 const epoch="TIMESTAMP '1899-12-30T00:00:00'",numeric="regexp_matches(typeof("+reference+"),'^(U?(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT)|FLOAT|DOUBLE|DECIMAL)')",ref='(CASE WHEN '+reference+' IS NULL THEN '+epoch+' WHEN '+numeric+' THEN TRY('+epoch+' + TRY_CAST('+reference+" AS DOUBLE) * INTERVAL '1 day') ELSE TRY_CAST("+reference+' AS TIMESTAMP) END)',start=sqlValue(span.start),end=sqlValue(span.end);
 switch(kind){case 0:return '('+ref+' >= '+start+' AND '+ref+' < '+end+')';case 5:return '('+ref+' < '+start+' OR '+ref+' >= '+end+')';case 1:return ref+' >= '+end;case 2:return ref+' >= '+start;case 3:return ref+' < '+start;case 4:return ref+' < '+end;default:fail('Unsupported date-span comparison.');}
}
function dateSpanTest(value,kind,span){
 const date=temporalMillis(value),start=temporalMillis(span.start),end=temporalMillis(span.end);if(!Number.isFinite(date))return false;
 switch(kind){case 0:return date>=start&&date<end;case 5:return date<start||date>=end;case 1:return date>=end;case 2:return date>=start;case 3:return date<start;case 4:return date<end;default:fail('Unsupported date-span comparison.');}
}
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
  const top=topN(entry);if(top){result.push({topN:top});continue}
  const f=entry.filter, aliases=Object.fromEntries((f.From||[]).map(x=>[x.Name,x.Entity]));
  if(Object.keys(f).some(k=>!['Version','From','Where'].includes(k)))fail('Unsupported source filter structure.');
  for(const where of f.Where||[]){
   if(where.Condition?.Or||where.Condition?.And){
    function expand(c){const op=c.Or||c.And;if(!op)return [parseFilters([{filter:{From:f.From||[],Where:[{Condition:c}]}}])];const a=expand(op.Left),b=expand(op.Right);if(a.length*b.length>4096||a.length+b.length>4096)fail('Filter selection exceeds 4096 alternatives.');return c.Or?[...a,...b]:a.flatMap(x=>b.map(y=>[...x,...y]))}
    result.push({alternatives:expand(where.Condition)});continue;
   }
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
    if(c.Comparison){const a=c.Comparison;const ops={0:'=',1:'>',2:'>=',3:'<',4:'<=',5:'<>'};const op=ops[a.ComparisonKind];if(!op)fail('Unsupported comparison kind.');const left=field(a.Left),span=dateSpanBounds(a.Right);if(span)return dateSpanSQL(left,a.ComparisonKind,span);const v=literal(a.Right);return left+(v===null?(op==='='?' IS NULL':op==='<>'?' IS NOT NULL':fail('Invalid NULL comparison.')):' '+op+' '+sqlValue(v))}
    return fail('Unsupported source filter condition: '+Object.keys(c||{}).join(', '));
   }
   const sql=condition(where.Condition);
   if(tables.size!==1)fail('Multi-table filter predicates need further translation.');
   result.push({table:[...tables][0],columns:[...usedColumns],sql});
  }
 }
 return result;
}
function topN(entry){
 const f=entry.filter,sub=f?.From?.filter(x=>x.Expression?.Subquery);if(!sub?.length)return null;
 const q=sub[0].Expression.Subquery.Query,condition=f.Where?.[0]?.Condition?.In;
 if(sub.length!==1||f.Where?.length!==1||!condition?.Table||condition.Table.SourceRef?.Source!==sub[0].Name||condition.Expressions?.length!==1||q.Select?.length!==1||q.OrderBy?.length!==1||!Number.isInteger(q.Top)||q.Top<1||q.Top>10000||Object.keys(q).some(k=>!['Version','From','Select','OrderBy','Top'].includes(k)))fail('Unsupported Top N source filter.');
 const aliases=Object.fromEntries((q.From||[]).map(x=>[x.Name,x.Entity]));
 function resolve(x){if(Array.isArray(x))return x.map(resolve);if(!x||typeof x!=='object')return x;if(x.SourceRef?.Source){const entity=aliases[x.SourceRef.Source];if(!entity)fail('Unresolved Top N source.');return {SourceRef:{Entity:entity}}}return Object.fromEntries(Object.entries(x).filter(([k])=>k!=='Name').map(([k,v])=>[k,resolve(v)]))}
 const field=resolve(q.Select[0]),outer=column(condition.Expressions[0],Object.fromEntries((f.From||[]).map(x=>[x.Name,x.Entity]))),inner=column(field);
 if(outer.table!==inner.table||outer.column!==inner.column)fail('Top N category does not match its subquery.');
 return {field,by:resolve(q.OrderBy[0].Expression),count:q.Top,descending:q.OrderBy[0].Direction===2};
}
function resolvedFilters(model,page,visual,extra=[]){
 function normalize(value){if(!value||typeof value!=='object')return value;if(value.HierarchyLevel){const c=dateHierarchy(value,model);return {Column:{Expression:{SourceRef:{Entity:c.table}},Property:c.column}}}return Array.isArray(value)?value.map(normalize):Object.fromEntries(Object.entries(value).map(([k,v])=>[k,normalize(v)]))}
 const raw=filterEntries(normalize([page.reportFilters,page.filters,visual.filters,...extra])),filters=parseFilters(raw),ordinary=raw.filter(e=>!topN(e));
 return filters.map(f=>{if(!f.topN)return f;const t=f.topN,c=column(t.field),candidate={type:'tableEx',filters:ordinary,definition:{query:{queryState:{Category:{projections:[{field:t.field}]},Y:{projections:[{field:t.by}]}}}}};
 const plan=buildQuery(model,{reportFilters:[],filters:[]},candidate),sql='SELECT "v0" FROM (SELECT "v0", RANK() OVER (ORDER BY "v1" '+(t.descending?'DESC':'ASC')+' NULLS LAST) AS "_rank" FROM ('+plan.sql+') AS candidates WHERE "v1" IS NOT NULL) AS ranked WHERE "_rank" <= '+t.count;
 return {table:c.table,columns:[c.column],sql:colsql(c)+' IN ('+sql+')'};});
}
function underlyingPlan(model,page,visual,extra=[],table){
 assertTableAvailable(model,table);
 if(!model.tables.some(t=>t.name===table))fail('Choose a valid source table.');
 const filters=resolvedFilters(model,page,visual,extra),where=whereFor(table,filters,model);return {sql:'SELECT '+qi(table)+'.* FROM '+qi(table)+(where?' WHERE '+where:''),table};
}
function relationPath(from,to,relationships){
 const queue=[[from,[]]],seen=new Set([from]);
 while(queue.length){const [t,path]=queue.shift();if(t===to)return path;
  for(const r of relationships||[]){if(!r.IsActive||!['M:1','1:1','M:M'].includes(r.Cardinality))continue;
   // Search from the queried table towards dimensions whose filters reach it.
   const edges=[{a:r.FromTableName,ac:r.FromColumnName,b:r.ToTableName,bc:r.ToColumnName}];
   if(r.CrossFilteringBehavior==='Both')edges.push({a:r.ToTableName,ac:r.ToColumnName,b:r.FromTableName,bc:r.FromColumnName});
   for(const e of edges)if(e.a===t&&!seen.has(e.b)){seen.add(e.b);queue.push([e.b,[...path,e]])}
  }
 }
 return null;
}
function whereFor(table,filters,model){
 assertTableAvailable(model,table);
 const combined=new Map();for(const f of filters.filter(f=>!f.alternatives))combined.set(f.table,[...(combined.get(f.table)||[]),f.sql]);
 const tree={conditions:[],edges:new Map()};
 for(const [source,conditions] of combined){const path=source===table?[]:relationPath(table,source,model.relationships);if(!path)continue;let node=tree;for(const edge of path){assertTableAvailable(model,edge.b);const key=JSON.stringify(edge);if(!node.edges.has(key))node.edges.set(key,{edge,conditions:[],edges:new Map()});node=node.edges.get(key)}node.conditions.push(...conditions)}
 const render=node=>[...node.conditions.map(c=>'('+c+')'),...[...node.edges.values()].map(child=>{const e=child.edge,predicate=render(child);return 'EXISTS (SELECT 1 FROM '+qi(e.b)+' WHERE '+qi(e.b)+'.'+qi(e.bc)+' = '+qi(e.a)+'.'+qi(e.ac)+(predicate?' AND '+predicate:'')+')'})].join(' AND ');
 const base=render(tree),terms=base?[base]:[];
 for(const f of filters.filter(f=>f.alternatives))terms.push(f.alternatives.length?'('+f.alternatives.map(row=>'('+ (whereFor(table,row,model)||'TRUE') +')').join(' OR ')+')':'FALSE');
 return terms.join(' AND ');
}
function parameterQuery(model,page,visual,table,extra=[]){
 assertTableAvailable(model,table);
 const relevant=entry=>{let match=false;const aliases=Object.fromEntries((entry.filter?.From||[]).map(x=>[x.Name,x.Entity]));
  const walk=x=>{if(!x||typeof x!=='object')return;const ref=x.SourceRef,t=ref?.Entity||aliases[ref?.Source];if(t&&(t===table||relationPath(table,t,model.relationships)))match=true;for(const value of Object.values(x))if(value&&typeof value==='object')walk(value)};
  walk(entry.field||entry.filter||entry);return match;
 };
 const entries=filterEntries([page.reportFilters,page.filters,visual.filters,...extra]).filter(relevant),filters=parseFilters(entries);
 if(filters.some(f=>f.topN))throw Error('Field-parameter Top N filters require a parameter-domain query.');
 const where=whereFor(table,filters,model);return 'SELECT * FROM '+qi(table)+(where?' WHERE '+where:'');
}
function measureFilterPlan(visual){
 const kept=[],predicates=[],fields=[],sqlPredicates=[];
 for(const entry of filterEntries(visual.filters)){
  const condition=entry.filter?.Where?.map(w=>w.Condition);if(!condition||!/("Measure"|"Aggregation")/.test(JSON.stringify(condition))){kept.push(entry);continue}
  const aliases=Object.fromEntries((entry.filter.From||[]).map(f=>[f.Name,f.Entity]));
  function compile(node){
   if(node.And||node.Or){const op=node.And||node.Or,a=compile(op.Left),b=compile(op.Right);return row=>node.And?a(row)&&b(row):a(row)||b(row)}
   if(node.Not){const inner=compile(node.Not.Expression);return row=>!inner(row)}
   const c=node.Comparison;if(!(c?.Left?.Measure||c?.Left?.Aggregation)||!c.Right?.Literal&&!c.Right?.DateSpan)fail('Unsupported DAX measure-filter expression.');
   const field=structuredClone(c.Left);function sources(node){if(!node||typeof node!=='object')return;const ref=node.SourceRef;if(ref?.Source){ref.Entity=aliases[ref.Source];delete ref.Source;if(!ref.Entity)fail('Unknown aggregate-filter source.')}Object.values(node).forEach(sources)}sources(field);
   const key=JSON.stringify(field);let index=fields.findIndex(p=>JSON.stringify(p.field)===key);if(index<0){index=fields.length;fields.push({field,nativeQueryRef:field.Measure?.Property||'Aggregate filter'})}
   const span=dateSpanBounds(c.Right);if(span){sqlPredicates.push({index,dateSpan:span,comparisonKind:c.ComparisonKind});return row=>dateSpanTest(row[index],c.ComparisonKind,span)}
   const expected=literal(c.Right);const operator={0:'=',1:'>',2:'>=',3:'<',4:'<=',5:'<>'}[c.ComparisonKind];if(operator)sqlPredicates.push({index,operator,value:expected});return row=>{let a=row[index],b=expected;if(a==null)a=typeof b==='string'?'':0;if(b==null)b=typeof a==='string'?'':0;if(typeof a==='string'&&typeof b==='string'){a=a.toLowerCase();b=b.toLowerCase()}switch(c.ComparisonKind){case 0:return a===b;case 1:return a>b;case 2:return a>=b;case 3:return a<b;case 4:return a<=b;case 5:return a!==b;default:fail('Unsupported measure-filter comparison.')}};
  }
  predicates.push(...condition.map(compile));
 }
 if(!predicates.length)return null;
 const copy=structuredClone(visual);copy.filters={filters:kept};copy.definition.query.queryState.__MeasureFilters={projections:fields};
 return {visual:copy,predicates,count:fields.length,sqlPredicates,simple:predicates.length===sqlPredicates.length};
}
function activeProjection(projection,definition={}){
 // `active` describes grouping drill state. Custom-visual scalar bindings
 // remain part of their data view, even when the source marks them inactive.
 const field=projection.field||{};
 return projection.active!==false||/[0-9a-f]{32}$/i.test(definition.visualType||'')&&!!(field.Measure||field.Aggregation||field.Arithmetic||field.ScopedEval||field.NativeVisualCalculation);
}
function projectionRoles(def){return Object.entries(def.query?.queryState||{}).flatMap(([role,state])=>(state.projections||[]).filter(p=>activeProjection(p,def)).map(()=>role))}
function projections(def){
 const state=def.query?.queryState;
 if(!state)return fail('Legacy visual queries need further translation.');
 return Object.values(state).flatMap(role=>(role.projections||[]).filter(p=>activeProjection(p,def)));
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
function normalizeSourceSort(model,visual){
 if(visual.definition?.query?.sortDefinition?.isDefaultSort!==true)return visual;
 const fields=projections(visual.definition),sorts=visual.definition.query.sortDefinition.sort||[],changes=[];
 for(const [index,sort] of sorts.entries()){
  const column=sort.field?.Aggregation?.Expression?.Column;if(!column)continue;
  const same=(a,b)=>typeof a==='string'&&typeof b==='string'&&a.toLowerCase()===b.toLowerCase(),table=model.tables?.find(t=>same(t.name,column.Expression?.SourceRef?.Entity));if(!table||table.columns?.some(c=>same(c.name,column.Property)))continue;
  const matches=fields.filter(p=>p.field.Measure?.Property===column.Property&&model.measures?.some(m=>m.Name===column.Property&&m.TableName===p.field.Measure.Expression?.SourceRef?.Entity));
  if(matches.length===1)changes.push({index,field:matches[0].field,name:column.Property});
 }
 if(!changes.length)return visual;
 const copy=structuredClone(visual);for(const c of changes)copy.definition.query.sortDefinition.sort[c.index].field=structuredClone(c.field);
 copy._sortWarnings=[...(visual._sortWarnings||[]),...changes.map(c=>'Default sort uses the projected '+c.name+' measure because its legacy column reference is absent from the model.')];return copy;
}
function normalizeHierarchySort(visual){
 const fields=visual.definition?.query?.queryState?.Category?.projections?.filter(p=>p.active!==false)||[];
 if(fields.length<2||!fields.every(p=>p.field?.Column||p.field?.GroupRef))return visual;
 const sorts=visual.definition.query.sortDefinition?.sort||[],same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),level=sorts.length?fields.findIndex(p=>same(p.field,sorts[0].field)):fields.length;
 // A descendant's authored order applies within its parent groups. Metric
 // sorts retain their existing scope rather than inventing parent aggregates.
 if(level<1)return visual;
 const parents=fields.slice(0,level),prefix=parents.map(p=>sorts.find(s=>same(s.field,p.field))||{field:p.field,direction:'Ascending'}),ordered=[...prefix,...sorts.filter(s=>!parents.some(p=>same(p.field,s.field)))];
 const copy=structuredClone(visual);copy.definition.query.sortDefinition={...copy.definition.query.sortDefinition,sort:structuredClone(ordered)};return copy;
}
function compareSortStrings(a,b){
 // Invisible prefixes are used in authored models to order labels with the
 // same visible text. Locale collation can erase that ordering information.
 return /[\u200b-\u200d\u2060\ufeff]/.test(a+b)?a===b?0:a<b?-1:1:a.localeCompare(b);
}
function buildQuery(model,page,visual,extra=[]){
 visual=normalizeHierarchySort(normalizeSourceSort(model,visual));
 assertPhysicalFieldsAvailable(model,projections(visual.definition).map(p=>p.field));
 const filterPlan=measureFilterPlan(visual);
 if(filterPlan){if(projections(filterPlan.visual.definition).slice(-filterPlan.count).some(p=>p.field.Measure)||!filterPlan.simple)fail('DAX measure filters require grouped evaluation.');const plan=buildQuery(model,page,filterPlan.visual,extra),count=projections(visual.definition).length;plan.sql='SELECT '+Array.from({length:count},(_,i)=>qi('v'+i)).join(', ')+' FROM ('+plan.sql+') AS __filtered WHERE '+filterPlan.sqlPredicates.map(p=>{const ref=qi('v'+(count+p.index));if(p.dateSpan)return dateSpanSQL(ref,p.comparisonKind,p.dateSpan);if(typeof p.value==='string')return "lower(COALESCE(CAST("+ref+" AS VARCHAR),'')) "+p.operator+" lower('"+p.value.replaceAll("'","''")+"')";return 'COALESCE('+ref+','+(typeof p.value==='boolean'?'FALSE':'0')+') '+p.operator+' '+String(p.value??0)}).join(' AND ');for(const key of ['labels','formats','roles'])plan[key]=plan[key].slice(0,count);return plan;}
 visual=normalizeDateAxis(model,visual);
 const def=visual.definition;
 if(projections(def).some(p=>p.field.NativeVisualCalculation))return fail('DAX visual calculations require result evaluation.');
 const filters=resolvedFilters(model,page,visual,extra);
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
   if(agg){const t=agg[2]||agg[3]?.trim()||matches[0].TableName||table;if(!t)fail('Cannot resolve the home table for DAX aggregate '+name);tables.add(t);aggregateTables.add(t);const c=qi(t)+'.'+qi(agg[4]);sql=agg[1].toUpperCase()==='DISTINCTCOUNT'?'COUNT(DISTINCT '+c+')':({AVERAGE:'AVG'}[agg[1].toUpperCase()]||agg[1].toUpperCase())+'('+c+')'}
   else{
    const reference=text.match(/^\[([^\]]+)\]$/);
    const countRows=text.match(/^COUNTROWS\s*\(\s*(?:'([^']+)'|([\w ]+))\s*\)$/i);
    const divide=text.match(/^DIVIDE\s*\((.*)\)$/is);
    if(reference)sql=measure({Property:reference[1]}).sql;
    else if(countRows){const t=countRows[1]||countRows[2].trim();tables.add(t);aggregateTables.add(t);sql='NULLIF(COUNT(*),0)'}
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
  if(e.GeoMean){const g=e.GeoMean;if(!g.table||!g.column||!g.latitude||!g.longitude||![g.latitude,g.longitude].includes(g.column))fail('Invalid geographic mean field.');tables.add(g.table);aggregateTables.add(g.table);return {sql:'AVG(CASE WHEN '+qi(g.table)+'.'+qi(g.latitude)+' BETWEEN -90 AND 90 AND '+qi(g.table)+'.'+qi(g.longitude)+' BETWEEN -180 AND 180 THEN '+qi(g.table)+'.'+qi(g.column)+' END)',aggregate:true}}
  if(e.Aggregation){const a=e.Aggregation,c=expression(a.Expression);aggregateTables.add(column(a.Expression).table);if(c.aggregate)fail('Nested aggregation unsupported.');const fn={0:'SUM',1:'AVG',2:'DISTINCTCOUNT',3:'MIN',4:'MAX',5:'COUNT',6:'MEDIAN'}[a.Function];if(!fn)fail('Unsupported aggregation.');return {sql:fn==='DISTINCTCOUNT'?'COUNT(DISTINCT '+c.sql+')':fn+'('+c.sql+')',aggregate:true}}
  if(e.Arithmetic){const a=e.Arithmetic,l=expression(a.Left),r=expression(a.Right),op={0:'+',1:'-',2:'*',3:'/'}[a.Operator];if(!op)fail('Unsupported arithmetic.');return {sql:'('+l.sql+op+(op==='/'?'NULLIF('+r.sql+',0)':r.sql)+')',aggregate:l.aggregate||r.aggregate}}
  if(e.ScopedEval&&Array.isArray(e.ScopedEval.Scope)&&!e.ScopedEval.Scope.length){const a=expression(e.ScopedEval.Expression);if(!a.aggregate)fail('Total scope requires an aggregate.');return {sql:'SUM('+a.sql+') OVER ()',aggregate:true}}
  if(e.SparklineData)return fail('DAX sparkline requires grouped evaluation.');
  return fail('Unsupported visual field expression: '+Object.keys(e).join(', '));
 }
 const selections=fields.map((p,i)=>{const e=expression(p.field);labels.push(p.displayName||p.nativeQueryRef||p.queryRef||'Value');if(!e.aggregate)groups.push(e.sql);return {...e,sql:e.sql+' AS '+qi('v'+i)}});
 for(const table of tables)assertTableAvailable(model,table);
 if(!selections.length)fail('No query fields found.');
 if(aggregateTables.size>1)fail('Measures from multiple fact tables require separate aggregation plans.');
 const table=[...aggregateTables][0]||[...tables].find(candidate=>[...tables].every(target=>target===candidate||relationPath(candidate,target,model.relationships)))||[...tables][0];
 let from=table?qi(table):'',joined=new Set(table?[table]:[]),disconnected=[];
 for(const target of tables){
  if(joined.has(target))continue;
  const path=relationPath(table,target,model.relationships);
  if(path){
   for(const e of path)if(!joined.has(e.b)){
    assertTableAvailable(model,e.b);
    // The grouping query only enumerates category identities; its anchor value
    // is discarded. Reverse Both joins are safe here even when they duplicate
    // anchor rows. Final measures still use independent, secured contexts.
    const r=model.relationships.find(r=>(r.FromTableName===e.a&&r.ToTableName===e.b&&r.FromColumnName===e.ac&&r.ToColumnName===e.bc)||((r.Cardinality==='1:1'||visual._groupEnumeration&&r.CrossFilteringBehavior==='Both')&&r.FromTableName===e.b&&r.ToTableName===e.a&&r.FromColumnName===e.bc&&r.ToColumnName===e.ac));
    if(r?.Cardinality==='M:M'&&!visual._groupEnumeration)fail('Many-to-many projections require separate aggregation plans.');
    if(!r||!['M:1','1:1','M:M'].includes(r.Cardinality))fail('Reverse many-side projections need a separate aggregation plan.');
    from+=' LEFT JOIN '+qi(e.b)+' ON '+qi(e.a)+'.'+qi(e.ac)+' = '+qi(e.b)+'.'+qi(e.bc);joined.add(e.b);
   }
  }else{
   const columns=fields.filter(p=>p.field.Column||p.field.GroupRef).map(p=>column(p.field)).filter(c=>c.table===target).flatMap(c=>{const sort=model.tables?.find(t=>t.name===c.table)?.columns?.find(col=>col.name===c.column)?.sortByColumn;return [qi(c.column),...(sort?[qi(sort)]:[])]});
   if(!columns.length)fail('Disconnected aggregate expressions need a separate aggregation plan.');
   const where=whereFor(target,filters,model);
   disconnected.push({target,sql:' CROSS JOIN (SELECT DISTINCT '+[...new Set(columns)].join(',')+' FROM '+qi(target)+(where?' WHERE '+where:'')+') AS '+qi(target)});joined.add(target);
   warnings.push(target+' has no active filter path to '+table+'. The filtered total repeats for each disconnected category.');
  }
 }
 const detached=new Set(disconnected.map(d=>d.target)),factored=disconnected.length>0&&selections.some(s=>s.aggregate)&&selections.every((s,i)=>s.aggregate||((fields[i].field.Column||fields[i].field.GroupRef)&&detached.has(column(fields[i].field).table)));
 const where=table?whereFor(table,filters,model):'';
 let sql;
 if(factored){
  // Independent category domains must not multiply the fact rows before aggregation.
  const total='SELECT '+selections.filter(s=>s.aggregate).map(s=>s.sql).join(', ')+(from?' FROM '+from:'')+(where?' WHERE '+where:'');
  sql='SELECT '+selections.map((s,i)=>s.aggregate?qi('__visual_total')+'.'+qi('v'+i)+' AS '+qi('v'+i):s.sql).join(', ')+' FROM ('+total+') AS '+qi('__visual_total')+disconnected.map(d=>d.sql).join('');
 }else{
  sql='SELECT '+selections.map(s=>s.sql).join(', ')+(from?' FROM '+from:'')+disconnected.map(d=>d.sql).join('')+(where?' WHERE '+where:'');
  if(selections.some(s=>s.aggregate)&&groups.length)sql+=' GROUP BY '+groups.join(', ');
  else if(!selections.some(s=>s.aggregate)&&!['histogram','histogramChart','boxplot','boxPlot','stripPlot','stripChart','ternaryPlot','ternaryChart','scatterChart','pointMap','map'].includes(visual.type))sql=sql.replace('SELECT ','SELECT DISTINCT ');
 }
 const sorts=def.query?.sortDefinition?.sort||[];
 if(sorts.length){const parts=sorts.map(s=>{const i=fields.findIndex(p=>JSON.stringify(p.field)===JSON.stringify(s.field));if(i<0)fail('DAX source sort field is not projected.');const c=s.field.Column||s.field.GroupRef,t=c?.Expression?.SourceRef?.Entity,by=model.tables?.find(x=>x.name===t)?.columns?.find(x=>x.name===c?.Property)?.sortByColumn;const ref=by?qi(t)+'.'+qi(by):qi('v'+i);return (by&&selections.some(x=>x.aggregate)&&!factored?'MIN('+ref+')':ref)+(s.direction==='Descending'?' DESC':' ASC')});const tied=fields.flatMap((p,i)=>!selections[i].aggregate&&!sorts.some(s=>JSON.stringify(s.field)===JSON.stringify(p.field))?[qi('v'+i)+' ASC']:[]);sql+=' ORDER BY '+[...parts,...tied].join(', ')}
 else if(fields.some(p=>p.field.DateBucket))sql+=' ORDER BY '+qi('v'+fields.findIndex(p=>p.field.DateBucket))+' ASC';
 else {const order=fields.flatMap(p=>{const c=p.field.Column;if(!c)return [];const table=c.Expression?.SourceRef?.Entity,sort=model.tables?.find(t=>t.name===table)?.columns?.find(col=>col.name===c.Property)?.sortByColumn;if(!sort)return [];const key=qi(table)+'.'+qi(sort);return [(selections.some(s=>s.aggregate)&&!factored?'MIN('+key+')':key)+' ASC']});if(order.length)sql+=' ORDER BY '+order.join(', ')}

 return {sql,labels,_resolvedFilters:filters,warnings:[...warnings,...visualWarnings(visual)],formats:fields.map(p=>fieldFormat(model,p,visual)),roles:projectionRoles(def)};
}
function visualWarnings(visual){return [...(visual._sortWarnings||[]),...(visual._embeddedCoordinateMeans?['Map positions use the mean of embedded latitude/longitude rows for each location.']:[]),...((visual.definition?.objects?.forecast||[]).some(e=>e.properties?.transform?.algorithm==='Forecast'&&e.properties?.show?.expr?.Literal?.Value!=='false')?['Historical series shown; Power BI forecast bands are not translated.']:[])]}
function fieldFormat(model,p,visual){
 if(typeof p.format==='string')return p.format;
 const Formats=typeof module!=='undefined'?require('./model-formats'):root.ModelFormats,authored=Formats?.visualFormat?.(visual,p);
 if(authored)return authored.format;
 if(p.field?.Arithmetic?.Operator===3&&p.field.Arithmetic.Right?.ScopedEval)return '0.00%';
 let f=p.field;while(f.Aggregation)f=f.Aggregation.Expression;
 if(f.Measure){const m=f.Measure;return model.measures.find(x=>x.Name===m.Property&&(!m.Expression?.SourceRef?.Entity||x.TableName===m.Expression.SourceRef.Entity))?.FormatString||''}
 const c=f.Column||f.GroupRef;return c?model.tables?.find(t=>t.name===c.Expression?.SourceRef?.Entity)?.columns?.find(x=>x.name===c.Property)?.formatString||'':'';
}
function nonEmptyVisual(model,visual,data){
 const ps=projections(visual.definition);if(ps.some(p=>p.showAll===true||p.showItemsWithNoData===true)||visual._groupEnumeration)return data;
 const roles=data.compiled.roles||[],indices=ps.flatMap((p,i)=>(p.field.Measure||p.field.Aggregation)&&!/^formatting$|^__|^tooltips?$/i.test(roles[i]||'')?[i]:[]);
 if(!indices.length)return data;
 const keep=data.result.rows.flatMap((r,i)=>indices.some(j=>r[j]!==null&&r[j]!==undefined)?[i]:[]);
 return {...data,result:{...data.result,rows:keep.map(i=>data.result.rows[i]),...(data.result.rowFormats?{rowFormats:keep.map(i=>data.result.rowFormats[i])}:{})}};
}
// SelectRef and AllRolesRef describe the executed visual domain. Resolve their
// presentation summaries locally, preserving filters and point multiplicity
// without sending visual-scoped aggregate wrappers to the DAX evaluator.
function visualExpression(field){return !!field&&typeof field==='object'&&(Object.hasOwn(field,'SelectRef')||Object.hasOwn(field,'RangePercent')||Object.hasOwn(field,'ScopedEval')||Object.values(field).some(x=>x&&typeof x==='object'&&visualExpression(x)))}
function visualExpressionValues(field,base,data){
 const rows=data.result.rows;let nodes=0;
 function resolve(ref){
  const name=ref?.ExpressionName;if(typeof name!=='string')fail('Invalid visual series reference.');
  const eligible=base.flatMap((p,i)=>!/^tooltips?$|^formatting$/i.test(data.compiled.roles?.[i]||'')?[{p,i}]:[]);
  let found=eligible.filter(({p})=>p.queryRef===name);
  if(!found.length)found=eligible.filter(({p,i})=>{const c=p.field.Measure||p.field.Column||p.field.GroupRef||p.field.Aggregation?.Expression?.Column;return [p.nativeQueryRef,p.displayName,data.compiled.labels?.[i],c?.Property,c?.Expression?.SourceRef?.Entity&&c.Property?c.Expression.SourceRef.Entity+'.'+c.Property:null].includes(name)});
  if(found.length!==1)fail('Visual series reference is missing or ambiguous: '+name);return found[0].i;
 }
 const checked=x=>{if(typeof x==='number'&&!Number.isFinite(x))fail('Non-finite visual formatting result.');return x};
 function projected(field){
  const key=JSON.stringify(field),found=base.flatMap((p,i)=>JSON.stringify(p.field)===key&&!/^tooltips?$|^formatting$/i.test(data.compiled.roles?.[i]||'')?[i]:[]);
  if(!found.length||found.slice(1).some(i=>rows.some(row=>row[i]!==row[found[0]])))fail('Visual formatting input is missing or ambiguous.');
  return {values:rows.map(row=>row[found[0]]??null),aggregate:false};
 }
 function evaluate(x){
  if(++nodes>256||!x||typeof x!=='object')fail('Unsupported visual formatting expression.');
  if(x.SelectRef){const index=resolve(x.SelectRef);return {values:rows.map(row=>row[index]??null),aggregate:false}}
  if(x.Literal){const v=literal(x);return {values:rows.map(()=>v),aggregate:false}}
  if(x.ScopedEval){
   const scoped=x.ScopedEval,scope=scoped.Scope;
   if(Array.isArray(scope)&&scope.length===1&&Object.hasOwn(scope[0],'AllRolesRef'))return scoped.Expression?.SelectRef?evaluate(scoped.Expression):projected(scoped.Expression);
   if(Array.isArray(scope)&&!scope.length){const result=evaluate(scoped.Expression);if(result.aggregate)return result}
   fail('Unsupported visual formatting scope.');
  }
  if(x.RangePercent){
   const range=x.RangePercent,min=evaluate(range.Min),max=evaluate(range.Max),percent=typeof range.Percent==='number'?{values:rows.map(()=>range.Percent),aggregate:false}:evaluate(range.Percent);
   return {values:min.values.map((low,i)=>{const high=max.values[i],p=percent.values[i];if(low==null||high==null||p==null)return null;if(![low,high,p].every(Number.isFinite))fail('Visual range formatting requires numeric bounds.');return checked(low+(high-low)*p)}),aggregate:min.aggregate||max.aggregate||percent.aggregate};
  }
  if(x.Aggregation){
   if(data.result.truncated||data.result.sampling?.validRows>data.result.sampling?.plottedRows)fail('Visual summary requires the complete result domain.');
   const a=x.Aggregation,input=evaluate(a.Expression);if(input.aggregate)fail('Nested visual formatting aggregates are unsupported.');
   const values=input.values.filter(v=>v!==null&&v!==undefined);let result;
   if(a.Function===2){const unique=new Set(input.values.map(v=>typeof v==='string'?'s:'+v.toLowerCase():JSON.stringify(v??null)));result=unique.size}
   else if(a.Function===5)result=values.length;
   else {if(values.some(v=>typeof v!=='number'||!Number.isFinite(v)))fail('Visual numeric summary requires numeric series values.');
    if(![0,1,3,4,6].includes(a.Function))fail('Unsupported visual formatting aggregate.');
    if(!values.length)result=null;
    else if(a.Function===0||a.Function===1){result=values.reduce((sum,v)=>sum+v,0);if(a.Function===1)result/=values.length}
    else if(a.Function===3)result=values.reduce((a,b)=>Math.min(a,b));
    else if(a.Function===4)result=values.reduce((a,b)=>Math.max(a,b));
    else {values.sort((a,b)=>a-b);const middle=Math.floor(values.length/2);result=values.length%2?values[middle]:(values[middle-1]+values[middle])/2}
   }
   checked(result);return {values:rows.map(()=>result),aggregate:true};
  }
  if(x.Arithmetic){const a=x.Arithmetic,left=evaluate(a.Left),right=evaluate(a.Right);if(![0,1,2,3].includes(a.Operator))fail('Unsupported visual formatting arithmetic.');return {values:left.values.map((v,i)=>{const w=right.values[i];if(v!=null&&typeof v!=='number'||w!=null&&typeof w!=='number')fail('Visual formatting arithmetic requires numeric values.');if(a.Operator<2)return checked(v==null&&w==null?null:a.Operator===0?(v??0)+(w??0):(v??0)-(w??0));return checked(v==null||w==null||a.Operator===3&&w===0?null:a.Operator===2?v*w:v/w)}),aggregate:left.aggregate||right.aggregate}}
  fail('Unsupported visual formatting expression.');
 }
 return evaluate(field).values;
}
async function optionalFormatting(model,page,visual,extra,data,api){
 const optional=visual.definition?.query?.queryState?.Formatting?.projections||[];if(!optional.length||!data.result.rows.length)return data;
 const ps=projections(visual.definition),base=ps.slice(0,ps.length-optional.length),indices=base.flatMap((p,i)=>p.field.Column||p.field.GroupRef?[i]:[]),filters=data.compiled._resolvedFilters??resolvedFilters(model,page,measureFilterPlan(visual)?.visual||visual,extra),groups=data.result.rows.map(row=>({values:Object.fromEntries(indices.map((index,i)=>[String(i),row[index]])),scope:indices.map(i=>{const c=column(base[i].field);return [c.table,c.column]}),filters:indices.map(i=>{const c=column(base[i].field);return {table:c.table,columns:[c.column],sql:colsql(c)+(row[i]===null?' IS NULL':' = '+sqlValue(row[i]))}})}));
 const run=async fields=>{const whole=fields.every(p=>p.formattingScope==='visual'),requestGroups=whole?[{scope:[],filters:[]}]:groups;const result=await api('/api/dax',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:model.id,fields:[...(whole?[]:indices.map(i=>base[i].field)),...fields.map(p=>p.field)],baseFilters:filters,groups:requestGroups})});const offset=whole?0:indices.length,values=result.rows.map(row=>row.slice(offset));return {...result,rows:whole?groups.map(()=>values[0]):values,types:result.types?.slice(offset)}};
 let rows=groups.map(()=>optional.map(()=>null)),types=optional.map(()=>'VARCHAR'),warnings=[];
 const remote=optional.map((p,i)=>({p,i})).filter(x=>!visualExpression(x.p.field));
 try{for(const whole of [false,true]){const selected=remote.filter(x=>(x.p.formattingScope==='visual')===whole);if(!selected.length)continue;const result=await run(selected.map(x=>x.p));selected.forEach(({i},k)=>{result.rows.forEach((r,j)=>rows[j][i]=r[k]);types[i]=result.types?.[k]||'VARCHAR'})}}catch(error){
  for(const {i} of remote){rows.forEach(row=>row[i]=null);types[i]='VARCHAR'}
  const budget=/budget|limit exceeded|interrupt|timeout/i.test(error.message);
  if(budget)warnings.push('Optional formatting was skipped: '+error.message);
  else for(const {i,p} of remote){try{const result=await run([p]);result.rows.forEach((r,j)=>rows[j][i]=r[0]);types[i]=result.types?.[0]||'VARCHAR'}catch(e){warnings.push('Optional formatting '+(p.field.Measure?.Property||p.nativeQueryRef||i)+': '+e.message);if(/budget|limit exceeded|interrupt|timeout/i.test(e.message))break}}
 }
 // A rule may summarize a measure used only for formatting. Query that scalar
 // per point once, then compute scoped bounds locally over the same result.
 const localBase=[...base,...remote.map(x=>x.p)],localData={compiled:{...data.compiled,roles:[...(data.compiled.roles||[]),...remote.map(()=>'FormattingInput')]},result:{...data.result,rows:data.result.rows.map((row,j)=>[...row,...remote.map(x=>rows[j][x.i])])}};
 for(const [i,p] of optional.entries())if(visualExpression(p.field)){try{const values=visualExpressionValues(p.field,localBase,localData);values.forEach((v,j)=>rows[j][i]=v);types[i]=values.some(v=>typeof v==='number')?'DOUBLE':'VARCHAR'}catch(error){warnings.push('Optional formatting '+(p.nativeQueryRef||i)+': '+error.message)}}
 return {compiled:{...data.compiled,labels:[...data.compiled.labels,...optional.map(p=>p.nativeQueryRef||p.queryRef||'Formatting value')],formats:[...data.compiled.formats,...optional.map(p=>fieldFormat(model,p,visual))],roles:[...data.compiled.roles,...optional.map(()=>'Formatting')],warnings:[...(data.compiled.warnings||[]),...warnings]},result:{...data.result,rows:data.result.rows.map((r,i)=>[...r,...rows[i]]),columns:[...(data.result.columns||base.map((_,i)=>'v'+i)),...optional.map((_,i)=>'v'+(base.length+i))],types:[...(data.result.types||[]),...types]}};
}
async function dynamicFormats(model,page,visual,extra,data,api){
 const fields=projections(visual.definition);if(!fields.some(p=>{const m=p.field.Measure;return m&&model.measures?.some(x=>x.Name===m.Property&&(!m.Expression?.SourceRef?.Entity||x.TableName===m.Expression.SourceRef.Entity)&&x.FormatStringExpression)}))return data;
 const indices=fields.flatMap((p,i)=>p.field.Column||p.field.GroupRef?[i]:[]),baseFilters=data.compiled._resolvedFilters??resolvedFilters(model,page,measureFilterPlan(visual)?.visual||visual,extra);
 const groups=data.result.rows.map(row=>({measureValues:row,scope:indices.map(i=>{const c=column(fields[i].field);return [c.table,c.column]}),filters:indices.map(i=>{const c=column(fields[i].field);return {table:c.table,columns:[c.column],sql:colsql(c)+(row[i]===null?' IS NULL':' = '+sqlValue(row[i]))}})}));
 const formats=await api('/api/dax',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:model.id,operation:'formats',fields:fields.map(p=>p.field),baseFilters,groups})});
 return {...data,compiled:{...data.compiled,warnings:[...(data.compiled.warnings||[]),...(formats.warnings||[]).map(w=>'Dynamic format: '+w)]},result:{...data.result,rowFormats:formats.rowFormats.map(row=>row.map((f,i)=>typeof fields[i]?.format==='string'?fields[i].format:f??data.compiled.formats[i]))}};
}
async function hiddenSortQuery(model,page,visual,extra,query,api){
 const fields=projections(visual.definition),sorts=visual.definition.query?.sortDefinition?.sort||[];
 if(!sorts.some(s=>!fields.some(p=>JSON.stringify(p.field)===JSON.stringify(s.field))))return null;
 const base=structuredClone(visual);delete base.definition.query.sortDefinition;
 async function load(v){try{const compiled=buildQuery(model,page,v,extra);return {compiled,result:await query(compiled.sql)}}catch(e){if(!/DAX|DIVIDE|fact tables|aggregation plans/.test(e.message))throw e;return pythonQuery(model,page,v,extra,query,api)}}
 const evaluated=await load(base),keys=[];
 for(const sort of sorts){const projected=fields.findIndex(p=>JSON.stringify(p.field)===JSON.stringify(sort.field));if(projected>=0){keys.push(row=>row[projected]);continue}
  const scoped=sort.field.ScopedEval,scope=scoped?.Scope,expression=scoped?.Expression||sort.field;
  let dimensions=fields.filter(p=>p.field.Column||p.field.GroupRef);
  if(scoped){if(!Array.isArray(scope))fail('DAX sort scope must be a list.');dimensions=scope.flatMap(item=>{if(item.RoleRef){const q=visual.definition.query.queryState[item.RoleRef.Role];if(!q)fail('Unknown DAX sort scope role.');return (q.projections||[]).filter(p=>p.active!==false)}return [{field:item}]});if(dimensions.some(p=>!p.field.Column&&!p.field.GroupRef))fail('DAX sort scope requires model columns.');}
  const indices=dimensions.map(p=>fields.findIndex(f=>JSON.stringify(f.field)===JSON.stringify(p.field)));if(indices.some(i=>i<0))fail('DAX sort scope is not part of the visual grouping.');
  const v={...base,definition:{...base.definition,query:{queryState:{Category:{projections:dimensions},Y:{projections:[{field:expression,nativeQueryRef:'Sort value'}]}}}}},values=await load(v);
  if(values.result.truncated)fail('DAX sorting requires the complete sort domain. Narrow report filters.');
  const map=new Map(values.result.rows.map(row=>[JSON.stringify(row.slice(0,dimensions.length)),row[dimensions.length]]));keys.push(row=>map.get(JSON.stringify(indices.map(i=>row[i])))??null);
 }
 const rows=evaluated.result.rows.map((row,index)=>({row,index,keys:keys.map(key=>key(row))}));rows.sort((a,b)=>{for(let i=0;i<sorts.length;i++){const x=a.keys[i],y=b.keys[i];if(x===y)continue;if(x==null)return 1;if(y==null)return -1;const cmp=typeof x==='string'&&typeof y==='string'?compareSortStrings(x,y):x<y?-1:1;return sorts[i].direction==='Descending'?-cmp:cmp}return a.index-b.index});evaluated.result.rows=rows.map(x=>x.row);return evaluated;
}
async function pythonQuery(model,page,visual,extra,query,api){
 visual=normalizeHierarchySort(normalizeSourceSort(model,visual));
 assertPhysicalFieldsAvailable(model,projections(visual.definition).map(p=>p.field));
 const hiddenSort=await hiddenSortQuery(model,page,visual,extra,query,api);if(hiddenSort)return hiddenSort;
 // Remove post-aggregation predicates before resolving categorical Top N.
 // Their measures remain hidden result fields and are checked after the ranked
 // domain is narrowed; they must never enter the direct-column filter parser.
 const measureFilters=measureFilterPlan(visual);
 if(measureFilters){const evaluated=await pythonQuery(model,page,measureFilters.visual,extra,query,api),count=projections(visual.definition).length;
  if(evaluated.result.truncated)fail('Measure filters require complete grouped results. Narrow the source filters.');
  evaluated.result.rows=evaluated.result.rows.filter(row=>measureFilters.predicates.every(test=>test(row.slice(count)))).map(row=>row.slice(0,count));
  for(const key of ['columns','types'])if(evaluated.result[key])evaluated.result[key]=evaluated.result[key].slice(0,count);
  for(const key of ['labels','formats','roles'])evaluated.compiled[key]=evaluated.compiled[key].slice(0,count);
  return evaluated;
 }
 // SQL Top N remains the fast path. Complex DAX order measures need a complete
 // candidate-domain evaluation before narrowing the visual's grouped query.
 const raw=filterEntries([page.reportFilters,page.filters,visual.filters,...extra]),ranked=raw.filter(e=>topN(e));
 if(ranked.length){
  let needsDax=false;try{resolvedFilters(model,page,visual,extra)}catch(e){if(!/DAX|DIVIDE|aggregation plans/.test(e.message))throw e;needsDax=true}
  if(needsDax){const ordinary=raw.filter(e=>!topN(e)),filters=parseFilters(ordinary),selected=[];
   for(const entry of ranked){const t=topN(entry),result=await api('/api/dax',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:model.id,operation:'topN',category:t.field,by:t.by,count:t.count,descending:t.descending,filters})});
    selected.push({filter:{Where:[{Condition:{In:{Expressions:[t.field],Values:result.values.map(v=>[{Literal:{Value:v===null?'null':sqlValue(v)}}])}}}]}});
   }
   return pythonQuery(model,{...page,reportFilters:[],filters:[]},{...visual,filters:[...ordinary,...selected]},[],query,api);
  }
 }

 if(projections(visual.definition).some(p=>p.field.NativeVisualCalculation))return visualCalculationQuery(model,page,visual,extra,query,api);
 const fields=projections(visual.definition),indices=fields.map((p,i)=>p.field.Column||p.field.GroupRef?i:-1).filter(i=>i>=0);
 const filters=resolvedFilters(model,page,visual,extra);
 let groupRows=[[]],preview=false;
 if(indices.length){
  const anchor=fields.find(p=>p.field.Aggregation);
  const def={...visual.definition,query:{queryState:{Category:{projections:indices.map(i=>fields[i])},...(anchor?{Values:{projections:[anchor]}}:{})}}};
  const plan=buildQuery(model,page,{...visual,type:'tableEx',definition:def,_groupEnumeration:true},extra),result=await query(plan.sql);
  preview=!!result.truncated;groupRows=result.rows.map(row=>row.slice(0,indices.length));
 }
 const groups=groupRows.map(row=>{
  const groupFilters=indices.map((i,j)=>{const c=column(fields[i].field);return {table:c.table,columns:[c.column],sql:colsql(c)+(row[j]===null?' IS NULL':' = '+sqlValue(row[j]))}});
  return {values:Object.fromEntries(indices.map((i,j)=>[i,row[j]])),externalFilters:filters,filters:[...filters,...groupFilters],scope:indices.map(i=>{const c=column(fields[i].field);return [c.table,c.column]}),contexts:{}};
 });
 const result=await api('/api/dax',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:model.id,fields:fields.map(p=>p.field),contexts:{},baseFilters:filters,groups:groups.map(g=>({...g,filters:g.filters.slice(filters.length),externalFilters:undefined}))})});
 const sorts=visual.definition.query?.sortDefinition?.sort||[];
 if(sorts.length){
  const sortPlan=sorts.map(sort=>{const index=fields.findIndex(p=>JSON.stringify(p.field)===JSON.stringify(sort.field));if(index<0)fail('DAX source sort field is not projected.');const c=sort.field.Column||sort.field.GroupRef,table=c?.Expression?.SourceRef?.Entity,by=model.tables?.find(t=>t.name===table)?.columns?.find(x=>x.name===c?.Property)?.sortByColumn,j=indices.indexOf(index),order=by&&j>=0?new Map(groupRows.map(row=>row[j]).filter((v,i,a)=>a.indexOf(v)===i).map((v,i)=>[v,i])):null;return {index,descending:sort.direction==='Descending',order}});
  result.rows.sort((a,b)=>{for(const sort of sortPlan){const x=a[sort.index],y=b[sort.index];let order=sort.order?(sort.order.get(x)??0)-(sort.order.get(y)??0):x===y?0:x===null?-1:y===null?1:typeof x==='string'&&typeof y==='string'?compareSortStrings(x,y):x<y?-1:1;if(order)return sort.descending?-order:order}return 0});
 }
 if(preview)result.truncated=true;
 return {compiled:{_resolvedFilters:filters,labels:fields.map(p=>p.displayName||p.nativeQueryRef||p.queryRef||'Value'),formats:fields.map(p=>fieldFormat(model,p,visual)),roles:projectionRoles(visual.definition),warnings:[...visualWarnings(visual),...(preview?['Showing a preview of the first 10,000 groups. Narrow filters to evaluate and sort the complete result.']:[])]},result};
}

async function visualCalculationQuery(model,page,visual,extra,query,api){
 const fields=projections(visual.definition),base=fields.filter(p=>!p.field.NativeVisualCalculation),copy=structuredClone(visual);
 copy.definition.query={queryState:{Values:{projections:base}}};
 let compiled,result;try{compiled=buildQuery(model,page,copy,extra);result=await query(compiled.sql)}catch(e){if(!/DAX|DIVIDE|fact tables|aggregation plans/.test(e.message))throw e;({compiled,result}=await pythonQuery(model,page,copy,extra,query,api))}
 if(result.truncated)throw Error('Visual calculations require complete results. Narrow filters to avoid the query row limit.');
 const dimensions=base.filter(p=>p.field.Column||p.field.GroupRef);
 if(dimensions.length!==1||base.some(p=>!p.field.Column&&!p.field.GroupRef&&(!p.field.Aggregation||![0,2,5].includes(p.field.Aggregation.Function)||p.field.Aggregation.Function===2&&JSON.stringify(p.field.Aggregation.Expression)!==JSON.stringify(dimensions[0]?.field))))throw Error('Visual calculation support requires one category and additive aggregates or a distinct count of that category.');
 const names=new Map(),cache=new Map(),visiting=new Set();
 fields.forEach(p=>{for(const name of [p.nativeQueryRef,p.displayName,p.field.NativeVisualCalculation?.Name])if(name){if(names.has(name)&&names.get(name)!==p)throw Error('Ambiguous visual calculation field: '+name);names.set(name,p)}});
 base.forEach((p,i)=>cache.set(p,result.rows.map(r=>r[i])));
 function ref(name){if(!names.has(name))throw Error('Unknown visual calculation field: '+name);return names.get(name)}
 function vector(p){
  if(cache.has(p))return cache.get(p);if(visiting.has(p))throw Error('Circular visual calculation dependency.');visiting.add(p);
  const c=p.field.NativeVisualCalculation;if(c.Language?.toLowerCase()!=='dax')throw Error('Unsupported visual calculation language.');
  const text=c.Expression.replace(/\/\/[^\r\n]*/g,'').trim();let m,out;
  if((m=/^RUNNINGSUM\(\s*\[([^\]]+)\]\s*,\s*ORDERBY\(\s*\[([^\]]+)\]\s*,\s*(ASC|DESC)\s*\)\s*\)$/i.exec(text))){
   const values=vector(ref(m[1])),sort=vector(ref(m[2])),order=values.map((_,i)=>i).sort((a,b)=>((sort[a]??0)-(sort[b]??0))*(m[3].toUpperCase()==='DESC'?-1:1)||a-b);let total=0;out=Array(values.length);for(const i of order){total+=Number(values[i]??0);out[i]=total}out.total=total;
  }else if((m=/^DIVIDE\(\s*\[([^\]]+)\]\s*,\s*COLLAPSEALL\(\s*\[([^\]]+)\]\s*,\s*ROWS\s*\)\s*\)$/i.exec(text))){
   const numerator=vector(ref(m[1])),values=vector(ref(m[2])),total=values.total??values.reduce((a,b)=>a+Number(b??0),0);out=numerator.map(v=>v==null||!total?null:v/total);
  }else throw Error('Unsupported DAX visual calculation: '+text);
  visiting.delete(p);cache.set(p,out);return out;
 }
 const values=fields.map(vector);
 return {compiled:{...compiled,labels:fields.map(p=>p.displayName||p.nativeQueryRef||p.queryRef),formats:fields.map(p=>fieldFormat(model,p,visual)),roles:projectionRoles(visual.definition)},result:{...result,columns:fields.map((_,i)=>'v'+i),types:fields.map(p=>p.field.NativeVisualCalculation?'DOUBLE':result.types?.[base.indexOf(p)]),rows:result.rows.map((_,i)=>values.map(v=>v[i]))}};
}

function tooltipPointFilters(source,datum,channels){
 const state=source.definition?.query?.queryState||{},all=projections(source.definition),fields=[];
 if(datum._rowIdentities?.length){
  const ids=datum._rowIdentities.filter(Boolean),first=ids[0];
  if(first&&ids.every(id=>JSON.stringify(id.fields)===JSON.stringify(first.fields))){const lit=x=>({Literal:{Value:x===null?'null':typeof x==='number'||typeof x==='boolean'?String(x):"'"+String(x).replaceAll("'","''")+"'"}});return [{filter:{Where:[{Condition:{In:{Expressions:first.fields.map(f=>f.field||{Column:{Expression:{SourceRef:{Entity:f.table}},Property:f.column}}),Values:ids.map(id=>first.fields.map(f=>lit(id.datum[f.dataField])))}}}]}}]}
 }

 if(datum._rowIdentity){for(const f of datum._rowIdentity.fields){const x=datum._rowIdentity.datum[f.dataField];if(x!==undefined)fields.push({field:f.field||{Column:{Expression:{SourceRef:{Entity:f.table}},Property:f.column}},value:x})}}
 function add(field,dataField){if(field&&(field.Column||field.GroupRef||field.HierarchyLevel)&&datum[dataField]!==undefined)fields.push({field,value:datum[dataField]})}
 if(datum._cardRow){let index=0;for(const [role,q] of Object.entries(state))for(const projection of q.projections||[]){if(projection.active===false)continue;if(['Rows','Category','Group'].includes(role)&&datum._cardRow[index]!==undefined&&(projection.field.Column||projection.field.GroupRef||projection.field.HierarchyLevel))fields.push({field:projection.field,value:datum._cardRow[index]});index++}}
 if(!datum._rowIdentity&&channels){for(const [index,key] of [[channels.country??channels.category??channels.detail,'_categoryValue'],[channels.color,'_dimension']])if(Number.isInteger(index)&&index>=0)add(all[index]?.field,key)}
 else if(!datum._rowIdentity)for(const [role,key] of [['Category','_categoryValue'],['Details','_categoryValue'],['Series','_dimension'],['Legend','_dimension']]){const p=(state[role]?.projections||[]).filter(p=>p.active!==false);if(p.length===1)add(p[0].field,key)}
 if(!fields.length)return [];
 const literal=value=>({Literal:{Value:value===null?'null':typeof value==='number'||typeof value==='boolean'?String(value):"'"+String(value).replaceAll("'","''")+"'"}});
 return [{filter:{Where:[{Condition:{In:{Expressions:fields.map(f=>f.field),Values:[fields.map(f=>literal(f.value))]}}}]}}];
}
function tooltipSourceFilters(source,pointFilters){
 // A source visual's aggregate predicates select result rows. The hovered
 // identity already passed those tests; applying them again at the tooltip's
 // different grain either changes the answer or rejects a valid row filter.
 const resultExpression=node=>node&&typeof node==='object'&&(node.Measure||node.Aggregation||node.Subquery||Object.values(node).some(resultExpression));
 const excluded=Symbol('visual-result-predicate'),pointColumns=new Set(),key=(field,aliases)=>{try{const c=column(field,aliases);return JSON.stringify([c.table.toLowerCase(),c.column.toLowerCase()])}catch{return null}};
 function fixedColumns(condition,aliases){
  if(condition?.And){fixedColumns(condition.And.Left,aliases);fixedColumns(condition.And.Right,aliases);return}
  const values=condition?.In;
  if(!values?.Expressions?.length||!values.Values?.length||values.Table||values.Values.some(row=>!Array.isArray(row)||row.length!==values.Expressions.length))return;
  try{for(const row of values.Values)for(const value of row)literal(value)}catch{return}
  for(const expression of values.Expressions){const field=key(expression,aliases);if(field)pointColumns.add(field)}
 }
 for(const entry of filterEntries(pointFilters)){
  const aliases=Object.fromEntries((entry.filter?.From||[]).map(x=>[x.Name,x.Entity]));
  for(const where of entry.filter?.Where||[])fixedColumns(where.Condition,aliases);
 }
 function rowCondition(condition){
  if(condition?.And){const left=rowCondition(condition.And.Left),right=rowCondition(condition.And.Right);return left===excluded?right:right===excluded?left:left===condition.And.Left&&right===condition.And.Right?condition:{...condition,And:{...condition.And,Left:left,Right:right}}}
  // An OR/NOT containing a result predicate cannot be narrowed to one of its
  // dimension branches without inventing an additional restriction.
  return resultExpression(condition)?excluded:condition;
 }
 const filters=[];
 for(const entry of filterEntries(source.filters)){
  if(!entry.filter){filters.push(entry);continue}
  if(entry.filter.From?.some(x=>x.Expression?.Subquery)){
   // Preserve a Top N domain when the source is scalar or its hovered identity
   // does not fix the ranked field. Never silently widen an unproven domain.
   let ranked;try{ranked=topN(entry)}catch{}
   if(ranked&&pointColumns.has(key(ranked.field,{})))continue;
   filters.push(entry);continue;
  }
  if(!Array.isArray(entry.filter.Where)){filters.push(entry);continue}
  const where=entry.filter.Where.flatMap(item=>{const condition=rowCondition(item.Condition);return condition===excluded?[]:[{...item,Condition:condition}]});
  if(where.length)filters.push({...entry,filter:{...entry.filter,Where:where}});
 }
 return filters;
}
function tooltipContext(page,tip,source,extra=[],pointFilters=[]){
 return {...tip,reportFilters:page.reportFilters,filters:[...filterEntries(tip.filters),...(tip.pageBinding?.acceptsFilterContext==='None'?[]:[...filterEntries(page.filters),...tooltipSourceFilters(source,pointFilters),...filterEntries(extra)]),...filterEntries(pointFilters)]};
}
function captionVisual(visual,objects){
 const projections=[];for(const key of ['title','subTitle',...(['shape','actionButton'].includes(visual.type)?['shapeText']:[])]){const p=objects[key],Style=typeof module!=='undefined'?require('./report-style'):root.ReportStyle;if(Style.value(p?.show)===false)continue;const expression=p?.text?.expr||p?.text;if(expression&&(expression.Measure||expression.Aggregation||key==='shapeText'&&expression.Column))projections.push({field:expression,nativeQueryRef:key})}
 return projections.length?{...visual,type:'card',definition:{query:{queryState:{Values:{projections}}}},_captionKeys:projections.map(p=>p.nativeQueryRef)}:null;
}
function cardImageVisual(visual,model){
 if(visual.type!=='cardVisual')return visual;
 const Style=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,fields=projections(visual.definition),images=[],bindings={};
 fields.forEach((p,i)=>{const settings=Style.cardSettings(model,visual,i).image,field=(settings.imageData||settings.imageUrl)?.expr;if(Style.value(settings.show,model.theme)!==true||!(field?.Measure||field?.Aggregation))return;bindings[i]=fields.length+images.length;images.push({field,nativeQueryRef:'Card image '+i})});
 if(!images.length)return visual;const copy=structuredClone(visual);copy.definition.query.queryState.CardImages={projections:images};copy._cardImageBindings=bindings;return copy;
}
function textboxVisual(visual){
 const objects=visual.definition?.objects||{},projections=[],bindings=[];
 for(const [entryIndex,entry] of (objects.general||[]).entries())for(const [paragraphIndex,p] of (entry.properties?.paragraphs||[]).entries())for(const [runIndex,run] of (p.textRuns||[]).entries()){
  const ref=run.value?.propertyIdentifier;if(!ref)continue;
  const value=(objects[ref.objectName]||[]).find(x=>JSON.stringify(x.selector||{})===JSON.stringify(run.value.selector||{}))?.properties?.[ref.propertyName];
  const field=value?.expr||value;if(!field||!(field.Measure||field.Aggregation))throw Error('Dynamic text requires a scalar model expression.');
  const index=projections.length;projections.push({field,nativeQueryRef:'Text '+index});bindings.push({entryIndex,paragraphIndex,runIndex,index});
 }
 return projections.length?{...visual,type:'card',definition:{query:{queryState:{Values:{projections}}}},_textBindings:bindings}:null;
}
function applyTextboxValues(visual,plan,result){
 if(result.rows.length!==1)throw Error('Dynamic text requires one scalar row.');const copy=structuredClone(visual);
 for(const b of plan._textBindings)copy.definition.objects.general[b.entryIndex].properties.paragraphs[b.paragraphIndex].textRuns[b.runIndex].value=String(result.rows[0][b.index]??'');return copy;
}
function geographicVisual(visual,model){
 if(!model||!['map','pointMap'].includes(visual.type))return visual;
 const state=visual.definition?.query?.queryState||{};if(state.Latitude||state.Longitude)return visual;
 // The map's bound location role establishes geographic intent. Field names
 // may be localized, identifiers, districts or administrative abbreviations.
 // Use the location's own model table instead of guessing from its name.
 const location=(state.Category?.projections||state.Location?.projections||[]).find(p=>p.active!==false)?.field?.Column;
 if(!location)return visual;
 const table=location.Expression?.SourceRef?.Entity,columns=model.tables?.find(t=>t.name===table)?.columns||[];
 const coordinate=(pattern)=>{const matches=columns.filter(c=>pattern.test(c.name));return matches.length===1?matches[0]:null};
 const lat=coordinate(/^(latitude|lat)$/i),lon=coordinate(/^(longitude|lon|lng|long)$/i);if(!lat||!lon)return visual;
 const numeric=c=>!c.type&&!c.dataType||/^(?:U?(?:TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT)|INT\d*|DOUBLE|FLOAT|REAL|DECIMAL|NUMERIC|NUMBER)/i.test(c.type||c.dataType);
 if(!numeric(lat)||!numeric(lon))return visual;
 const copy=structuredClone(visual),q=copy.definition.query.queryState;copy._embeddedCoordinateMeans=true;
 for(const [role,col] of [['Latitude',lat],['Longitude',lon]])q[role]={projections:[{field:{GeoMean:{table,column:col.name,latitude:lat.name,longitude:lon.name}},nativeQueryRef:role}]};
 return copy;
}
function formattingVisual(visual,model){
 visual=geographicVisual(visual,model);
 const valid=field=>!model||!field.Measure||model.measures.some(m=>m.Name.toLowerCase()===field.Measure.Property.toLowerCase()&&(!field.Measure.Expression?.SourceRef?.Entity||m.TableName.toLowerCase()===field.Measure.Expression.SourceRef.Entity.toLowerCase()));
 const fields=[];const known=new Set(Object.values(visual.definition?.query?.queryState||{}).flatMap(s=>(s.projections||[]).map(p=>JSON.stringify(p.field))));
 function add(field,label){if(!field||!(field.Measure||field.Aggregation||(field.Arithmetic||field.SelectRef||field.ScopedEval||field.RangePercent)&&visualExpression(field)))return false;const key=JSON.stringify(field);if(valid(field)&&!known.has(key)){known.add(key);fields.push({field,nativeQueryRef:field.Measure?.Property||label,queryRef:'__format'+fields.length})}return true}
 function inputs(x){if(!x||typeof x!=='object')return;const scoped=x.ScopedEval;if(scoped?.Scope?.length===1&&Object.hasOwn(scoped.Scope[0],'AllRolesRef')&&!visualExpression(scoped.Expression)){add(scoped.Expression,'Formatting input');return}for(const item of Object.values(x))if(item&&typeof item==='object')inputs(item)}
 function scan(x){if(!x||typeof x!=='object')return;if((x.Measure||x.Aggregation||x.Arithmetic||x.SelectRef||x.ScopedEval||x.RangePercent)&&add(x,'Formatting value')){if(visualExpression(x))inputs(x);return}if(x.expr)add(x.expr,'Formatting value');if(x.dynamicLabelDetail?.expr)add(x.dynamicLabelDetail.expr,'Label detail');if(x.FillRule?.Input)add(x.FillRule.Input,'Formatting value');for(const item of Object.values(x))if(item&&typeof item==='object')scan(item)}
 scan(visual.definition?.objects);if(!fields.length)return visual;
 // Axis limits belong to the visual filter context, not each plotted category.
 // Keep a shared expression per-point if another formatting property uses it.
 const uses=new Map();function contexts(x,path=[]){if(!x||typeof x!=='object')return;if(x.expr){const key=JSON.stringify(x.expr),global=path.some(k=>/axis/i.test(k))&&path.some(k=>/^(start|end|min|max|minimum|maximum)$/i.test(k))||path.some(k=>/AxisReferenceLine$/i.test(k))&&path.includes('value');uses.set(key,(uses.get(key)??true)&&global)}for(const [k,v] of Object.entries(x))if(v&&typeof v==='object')contexts(v,[...path,k])}contexts(visual.definition?.objects);
 for(const p of fields)if(uses.get(JSON.stringify(p.field))===true)p.formattingScope='visual';
 const copy=structuredClone(visual);copy.definition.query.queryState.Formatting={projections:fields};return copy;
}
function tableTotalPlan(visual){
 const copy=structuredClone(visual),indices=[],state={};let i=0;
 for(const [role,q] of Object.entries(copy.definition?.query?.queryState||{})){const projections=[];for(const p of q.projections||[]){if(p.active===false)continue;if(p.field?.Measure||p.field?.Aggregation||p.field?.ScopedEval){indices.push(i);projections.push(p)}i++}if(projections.length)state[role]={...q,projections}}
 if(!indices.length)return null;copy.definition.query={queryState:state};return {visual:copy,indices};
}
const api={activeProjection,assertTableAvailable,measureFilterPlan,parameterQuery,optionalFormatting,dynamicFormats,nonEmptyVisual,tableTotalPlan,cardImageVisual,textboxVisual,applyTextboxValues,geographicVisual,tooltipPointFilters,tooltipContext,captionVisual,formattingVisual,resolvedFilters,underlyingPlan,pythonQuery,fieldFormat,literal,parseFilters,whereFor,buildQuery,filterEntries};
if(typeof module!=='undefined')module.exports=api;root.ReportEngine=api;
})(globalThis);

