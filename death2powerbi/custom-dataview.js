(function(root){
function fail(message){throw Error(message)}
const projections=visual=>Object.entries(visual.definition?.query?.queryState||{}).flatMap(([role,state])=>(state.projections||[]).filter(p=>p.active!==false).map(p=>({...p,role})));
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
function build(pkg,visual,result,compiled,overrides={}){
 const ps=projections(visual),caps=pkg.capabilities||{},roles=caps.dataRoles||[];
 if(ps.length!==result.columns.length)fail('Custom visual query columns do not match its projections.');
 const counts=Object.fromEntries(roles.map(role=>[role.name,ps.filter(p=>p.role===role.name).length]));
 const mappings=(caps.dataViewMappings||[]).filter(m=>!m.conditions?.length||m.conditions.some(condition=>Object.entries(condition).every(([role,limit])=>(counts[role]||0)>=(limit.min||0)&&(counts[role]||0)<=(limit.max??Infinity))));
 const mapping=mappings.find(m=>m.table||m.categorical||m.single);
 if(!mapping)fail('This visual needs an unsupported data mapping or role combination (matrix/tree mappings are not implemented).');
 const columns=ps.map((p,i)=>{
  const t=String(result.types?.[i]||''),role=roles.find(r=>r.name===p.role),numeric=/INT|DOUBLE|DECIMAL|FLOAT|REAL|HUGEINT/.test(t),dateTime=/DATE|TIMESTAMP/.test(t);
  return {displayName:compiled.labels[i],queryName:p.queryRef||p.nativeQueryRef||'field'+i,index:i,roles:{[p.role]:true},isMeasure:!!(p.field.Measure||p.field.Aggregation||role?.kind===1||role?.kind==='Measure'),type:dateTime?{dateTime:true}:numeric?{numeric:true,integer:/INT/.test(t)}:/BOOL/.test(t)?{bool:true}:{text:true},format:compiled.formats?.[i]||undefined};
 });
 const rows=result.rows.map(row=>row.map((value,i)=>value!=null&&columns[i].type.dateTime?new Date(value):value));
 const identity=(indices,key)=>({key,rows:indices});
 const view={metadata:{columns,objects:{...objects(visual.definition?.objects),...overrides}},table:{columns,rows,identity:rows.map((_,i)=>identity([i],'row:'+i))}};
 const roleIndex=role=>ps.flatMap((p,i)=>p.role===role?[i]:[]);
 function roleNames(def){if(!def)return [];if(def.for)return [def.for.in];if(def.bind)return [def.bind.to];if(def.select)return def.select.flatMap(roleNames);return []}
 if(mapping.single){const index=roleIndex(mapping.single.role)[0];if(index===undefined)fail('The custom visual scalar role has no field.');if(rows.length>1)fail('The custom visual scalar mapping requires one row.');view.single={value:rows[0]?.[index]??null}}
 if(mapping.categorical){
  const cat=mapping.categorical,categoryIndices=roleNames(cat.categories).flatMap(roleIndex),group=cat.values?.group,seriesIndices=group?roleIndex(group.by):[];
  if(group&&seriesIndices.length!==1)fail('Grouped custom visuals require exactly one series/time field.');
  const measureIndices=roleNames(group?{select:group.select}:cat.values).flatMap(roleIndex);
  if(!categoryIndices.length&&rows.length>1)fail('This categorical mapping has no supported category field.');
  const keyFor=(row,indices)=>JSON.stringify(indices.map(i=>row[i]));
  const categories=new Map();rows.forEach((row,index)=>{const key=keyFor(row,categoryIndices);if(!categories.has(key))categories.set(key,{row,indices:[]});categories.get(key).indices.push(index)});
  const categoryRows=[...categories.values()],series=new Map();
  rows.forEach((row,index)=>{const key=keyFor(row,seriesIndices);if(!series.has(key))series.set(key,{name:seriesIndices.length?row[seriesIndices[0]]:undefined,indices:[]});series.get(key).indices.push(index)});
  view.categorical={categories:categoryIndices.map(i=>({source:columns[i],values:categoryRows.map(c=>c.row[i]),identity:categoryRows.map((c,j)=>identity(c.indices,'category:'+j))})),values:[]};
  const values=view.categorical.values;
  for(const [seriesKey,s] of series){for(const index of measureIndices){
   const output=categoryRows.map(c=>{const matches=c.indices.filter(i=>s.indices.includes(i));if(matches.length>1)fail('Custom categorical mapping has duplicate category/series cells; its report query needs a unique grain.');return matches.length?rows[matches[0]][index]:null});
   values.push({source:{...columns[index],...(group?{groupName:s.name}:{})},values:output,identity:identity(s.indices,'series:'+seriesKey)});
  }}
  if(group){values.source=columns[seriesIndices[0]];values.identityFields=[]}
 }
 if(visual._nativeKpi&&pkg.guid===root.NativeKPI?.guid)root.NativeKPI.orderMonths(view);
 return view;
}
function selectionFields(visual,rows,indices){
 const ps=projections(visual),columns=ps.flatMap((p,i)=>{const c=p.field.Column||p.field.GroupRef;return c?.Expression?.SourceRef?.Entity&&c.Property?[{table:c.Expression.SourceRef.Entity,column:c.Property,index:i}]:[]});
 return {fields:columns.map(c=>({...c,dataField:'v'+c.index,label:c.column})),tuples:indices.map(index=>columns.map(c=>rows[index][c.index]))};
}
const api={build,objects,projections,selectionFields};if(typeof module!=='undefined')module.exports=api;root.CustomDataView=api;
})(globalThis);
