(function(root){
function fail(message){throw Error(message)}
function projections(visual){const Engine=typeof module!=='undefined'?require('./report-engine'):root.ReportEngine;return Object.entries(visual.definition?.query?.queryState||{}).flatMap(([role,state])=>(state.projections||[]).filter(p=>Engine?.activeProjection?Engine.activeProjection(p,visual.definition):p.active!==false).map(p=>({...p,role})))}
function objectValue(value){
 if(Array.isArray(value))return value.map(objectValue);
 if(!value||typeof value!=='object')return value;
 if(value.Literal){const s=value.Literal.Value;if(s==='true'||s==='false')return s==='true';if(s==='null')return null;if(/^[-+]?\d+(?:\.\d+)?[dDlLmM]?$/.test(s))return Number(s.replace(/[dDlLmM]$/,''));if(s?.startsWith("'")&&s.endsWith("'"))return s.slice(1,-1).replaceAll("''","'")}
 if(value.expr)return objectValue(value.expr);
 return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,objectValue(v)]));
}
function objects(source){const result={};for(const [name,entries] of Object.entries(source||{})){
 const base=Array.isArray(entries)?entries.filter(e=>!e.selector).map(e=>e.properties||{}):[entries];
 result[name]=Object.assign({},...base.map(objectValue));
}return result}
function filterProperties(pkg){return Object.entries(pkg?.capabilities?.objects||{}).flatMap(([objectName,object])=>Object.entries(object.properties||{}).filter(([,property])=>property?.type?.filter===true).map(([propertyName])=>({objectName,propertyName})))}
function filterColumns(visual){return projections(visual).flatMap(p=>{const c=p.field?.Column;return c?.Expression?.SourceRef?.Entity&&c.Property?[{table:c.Expression.SourceRef.Entity,column:c.Property}]:[]})}
function normalizeJsonFilters(visual,input){
 const values=input==null?[]:Array.isArray(input)?input:[input],allowed=filterColumns(visual),scalar=x=>x===null||typeof x==='boolean'||typeof x==='string'&&x.length<=10000||typeof x==='number'&&Number.isFinite(x);
 if(values.length>16||JSON.stringify(values).length>64000)fail('Custom visual filters exceed their size limit.');
 return values.map(filter=>{
  const target=filter?.target;if(!target||Object.keys(target).some(k=>!['table','column'].includes(k))||!allowed.some(c=>c.table===target.table&&c.column===target.column))fail('Custom visual filters must target a bound model column.');
  const common={target:{table:target.table,column:target.column}};
  if(['In','NotIn'].includes(filter.operator)&&Array.isArray(filter.values)&&filter.values.length<=10000&&filter.values.every(scalar))return {...common,operator:filter.operator,values:[...filter.values],filterType:1};
  const operators=['Is','IsNot','IsBlank','IsNotBlank','LessThan','LessThanOrEqual','GreaterThan','GreaterThanOrEqual'];
  if(['And','Or'].includes(filter.logicalOperator)&&Array.isArray(filter.conditions)&&filter.conditions.length>0&&filter.conditions.length<=16&&filter.conditions.every(c=>c&&operators.includes(c.operator)&&(['IsBlank','IsNotBlank'].includes(c.operator)||scalar(c.value))))return {...common,logicalOperator:filter.logicalOperator,conditions:filter.conditions.map(c=>({operator:c.operator,...(!['IsBlank','IsNotBlank'].includes(c.operator)?{value:c.value}:{})})),filterType:0};
  fail('This custom visual filter type is not supported.');
 });
}
function jsonFilters(visual,source){
 const output=[];
 function visit(entry){
  if(!entry)return;if(Array.isArray(entry)){entry.forEach(visit);return}if(Array.isArray(entry.filters)){entry.filters.forEach(visit);return}
  if(entry.target){output.push(entry);return}
  const f=entry.filter;if(!f)return;const aliases=Object.fromEntries((f.From||[]).map(x=>[x.Name,x.Entity]));
  const column=field=>{const c=field?.Column,ref=c?.Expression?.SourceRef;return c&&{table:ref?.Entity||aliases[ref?.Source],column:c.Property}};
  const value=x=>{const v=objectValue(x);if(v&&typeof v==='object')fail('Unsupported custom visual filter value.');return v};
  for(const where of f.Where||[]){const negated=where.Condition?.Not,condition=negated?.Expression||negated||where.Condition;
   if(condition?.In?.Expressions?.length===1){const node=condition.In;if(node.Values.some(row=>!Array.isArray(row)||row.length!==1))fail('Custom visual tuple filters are not supported.');output.push({target:column(node.Expressions[0]),operator:negated?'NotIn':'In',values:node.Values.map(row=>value(row[0]))});continue}
   const operators={0:'Is',1:'GreaterThan',2:'GreaterThanOrEqual',3:'LessThan',4:'LessThanOrEqual',5:'IsNot'},logicalOperator=condition?.Or?'Or':'And',conditions=[];let target;
   function comparison(node){if(node?.[logicalOperator]){comparison(node[logicalOperator].Left);comparison(node[logicalOperator].Right);return}const c=node?.Comparison,t=column(c?.Left);if(!c||!operators[c.ComparisonKind]||target&&JSON.stringify(t)!==JSON.stringify(target))fail('This saved custom visual filter type is not supported.');target=t;conditions.push({operator:operators[c.ComparisonKind],value:value(c.Right)})}
   if(!negated&&(condition?.Comparison||condition?.And||condition?.Or)){comparison(condition);output.push({target,logicalOperator,conditions});continue}
   fail('This saved custom visual filter type is not supported.');
  }
 }
 visit(source);return normalizeJsonFilters(visual,output);
}
function reportFilters(visual,filters){
 const literal=value=>({Literal:{Value:value===null?'null':typeof value==='number'||typeof value==='boolean'?String(value):"'"+String(value).replaceAll("'","''")+"'"}});
 return normalizeJsonFilters(visual,filters).map(filter=>{
  const field={Column:{Expression:{SourceRef:{Entity:filter.target.table}},Property:filter.target.column}};let condition;
  if(filter.values){condition={In:{Expressions:[field],Values:filter.values.map(value=>[literal(value)])}};if(filter.operator==='NotIn')condition={Not:{Expression:condition}}}
  else{const kinds={Is:0,IsNot:5,LessThan:3,LessThanOrEqual:4,GreaterThan:1,GreaterThanOrEqual:2,IsBlank:0,IsNotBlank:5};const conditions=filter.conditions.map(item=>{
   if(Object.hasOwn(kinds,item.operator))return {Comparison:{ComparisonKind:kinds[item.operator],Left:field,Right:literal(['IsBlank','IsNotBlank'].includes(item.operator)?null:item.value)}};
   fail('Text-search custom visual filters are not supported by the shared filter engine.');
  });condition=conditions.reduce((left,right)=>left?{[filter.logicalOperator]:{Left:left,Right:right}}:right,null)}
  return {filter:{Version:2,Where:[{Condition:condition}]}};
 });
}
function build(pkg,visual,result,compiled,overrides={}){
 const ps=projections(visual),caps=pkg.capabilities||{},roles=caps.dataRoles||[];
 if(ps.length!==result.columns.length)fail('Custom visual query columns do not match its projections.');
 const counts=Object.fromEntries(roles.map(role=>[role.name,ps.filter(p=>p.role===role.name).length]));
 const mappings=(caps.dataViewMappings||[]).filter(m=>!m.conditions?.length||m.conditions.some(condition=>Object.entries(condition).every(([role,limit])=>(counts[role]||0)>=(limit.min||0)&&(counts[role]||0)<=(limit.max??Infinity))));
 const mapping=mappings.find(m=>m.table||m.categorical||m.single);
 if(!mapping)fail('This visual needs an unsupported data mapping or role combination (matrix/tree mappings are not implemented).');
 const columns=ps.map((p,i)=>{
  const t=String(result.types?.[i]||''),role=roles.find(r=>r.name===p.role),numeric=/INT|DOUBLE|DECIMAL|FLOAT|REAL|HUGEINT/.test(t),dateTime=/DATE|TIMESTAMP/.test(t);
  const filterColumn=filterProperties(pkg).length&&p.field.Column;
  return {displayName:filterColumn?.Property||compiled.labels[i],queryName:p.queryRef||(filterColumn?filterColumn.Expression.SourceRef.Entity+'.'+filterColumn.Property:p.nativeQueryRef)||'field'+i,index:i,roles:{[p.role]:true},isMeasure:!!(p.field.Measure||p.field.Aggregation||role?.kind===1||role?.kind==='Measure'),type:dateTime?{dateTime:true}:numeric?{numeric:true,integer:/INT/.test(t)}:/BOOL/.test(t)?{bool:true}:{text:true},format:compiled.formats?.[i]||undefined};
 });
 const rows=result.rows.map(row=>row.map((value,i)=>value!=null&&columns[i].type.dateTime?new Date(value):value));
 const identity=(indices,key)=>({key,rows:indices});
 const view={metadata:{columns,objects:{...objects(visual.definition?.objects),...overrides}},table:{columns,rows,identity:rows.map((_,i)=>identity([i],'row:'+i))}};
 const roleIndex=role=>ps.flatMap((p,i)=>p.role===role?[i]:[]);
 function roleNames(def){if(!def)return [];if(def.for)return [def.for.in];if(def.bind)return [def.bind.to];if(def.select)return def.select.flatMap(roleNames);return []}
 if(mapping.single){const index=roleIndex(mapping.single.role)[0];if(index===undefined)fail('The custom visual scalar role has no field.');if(rows.length>1)fail('The custom visual scalar mapping requires one row.');view.single={value:rows[0]?.[index]??null}}
 if(mapping.categorical){
  // A GroupingOrMeasure role can be bound to both channels (for example a
  // Deneb dataset). Physical group columns belong to categories; measures
  // belong to values. Duplicating both in both channels loses their grain.
  const mixed=role=>[2,'GroupingOrMeasure'].includes(roles.find(r=>r.name===role)?.kind),mapped=(def,measure)=>roleNames(def).flatMap(role=>roleIndex(role).filter(i=>!mixed(role)||columns[i].isMeasure===measure));
  const cat=mapping.categorical,categoryIndices=mapped(cat.categories,false),group=cat.values?.group,seriesIndices=group?roleIndex(group.by):[];
  if(group&&seriesIndices.length>1)fail('Grouped custom visuals support at most one series/time field.');
  const measureIndices=mapped(group?{select:group.select}:cat.values,true);
  if(!categoryIndices.length&&rows.length>1)fail('This categorical mapping has no supported category field.');
  const keyFor=(row,indices)=>JSON.stringify(indices.map(i=>row[i]));
  const categories=new Map();rows.forEach((row,index)=>{const key=keyFor(row,categoryIndices);if(!categories.has(key))categories.set(key,{row,indices:[]});categories.get(key).indices.push(index)});
  const categoryRows=[...categories.values()],series=new Map();
  rows.forEach((row,index)=>{const key=keyFor(row,seriesIndices);if(!series.has(key))series.set(key,{name:seriesIndices.length?row[seriesIndices[0]]:undefined,indices:[]});series.get(key).indices.push(index)});
  view.categorical={categories:categoryIndices.map(i=>({source:columns[i],values:categoryRows.map(c=>c.row[i]),identity:categoryRows.map((c,j)=>identity(c.indices,'category:'+j))})),values:[]};
  const values=view.categorical.values;
  for(const [seriesKey,s] of series){for(const index of measureIndices){
   const output=categoryRows.map(c=>{const matches=c.indices.filter(i=>s.indices.includes(i));if(matches.length>1)fail('Custom categorical mapping has duplicate category/series cells; its report query needs a unique grain.');return matches.length?rows[matches[0]][index]:null});
   values.push({source:{...columns[index],...(group&&seriesIndices.length?{groupName:s.name}:{})},values:output,identity:identity(s.indices,'series:'+seriesKey)});
  }}
  if(group&&seriesIndices.length){values.source=columns[seriesIndices[0]];values.identityFields=[]}
 }
 if(visual._nativeKpi&&pkg.guid===root.NativeKPI?.guid)root.NativeKPI.orderMonths(view);
 return view;
}
function selectionFields(visual,rows,indices){
 const ps=projections(visual),columns=ps.flatMap((p,i)=>{const c=p.field.Column||p.field.GroupRef;return c?.Expression?.SourceRef?.Entity&&c.Property?[{table:c.Expression.SourceRef.Entity,column:c.Property,index:i}]:[]});
 return {fields:columns.map(c=>({...c,dataField:'v'+c.index,label:c.column})),tuples:indices.map(index=>columns.map(c=>rows[index][c.index]))};
}
const api={build,objects,projections,selectionFields,filterProperties,filterColumns,normalizeJsonFilters,jsonFilters,reportFilters};if(typeof module!=='undefined')module.exports=api;root.CustomDataView=api;
})(globalThis);
