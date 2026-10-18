(function(root){
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function bindings(visual,channels){
 const state=visual.definition?.query?.queryState||{};
 if(channels){
  const projections=Object.values(state).flatMap(v=>(v.projections||[]).filter(p=>p.active!==false));
  const first=channels.country??channels.category??channels.detail;
  const fields=[];
  for(const [index,dataField] of [[first,'_categoryValue'],[channels.color,'_dimension']]){
   if(!Number.isInteger(index)||index<0)continue;
   const c=projections[index]?.field?.Column||projections[index]?.field?.GroupRef;
   if(c?.Expression?.SourceRef?.Entity&&c.Property)fields.push({table:c.Expression.SourceRef.Entity,column:c.Property,dataField,label:c.Property});
  }
  return fields.some(f=>f.dataField==='_categoryValue')?fields:[];
 }
 const fields=[];
 for(const [role,dataField] of [['Category','_categoryValue'],['Series','_dimension'],['Legend','_dimension']]){
  const projections=(state[role]?.projections||[]).filter(p=>p.active!==false);
  if(!projections.length)continue;
  // A collapsed hierarchy or multiple category fields needs a richer identity.
  if(projections.length!==1)return [];
  const c=projections[0].field?.Column||projections[0].field?.GroupRef;
  if(!c?.Expression?.SourceRef?.Entity||!c.Property)return [];
  fields.push({table:c.Expression.SourceRef.Entity,column:c.Property,dataField,label:c.Property});
 }
 if(!fields.some(f=>f.dataField==='_categoryValue'))return [];
 return fields;
}
function literal(value){
 if(value===null)return {Literal:{Value:'null'}};
 if(typeof value==='number'&&Number.isFinite(value))return {Literal:{Value:String(value)}};
 if(typeof value==='boolean')return {Literal:{Value:String(value)}};
 if(typeof value==='string')return {Literal:{Value:"'"+value.replaceAll("'","''")+"'"}};
 throw Error('Unsupported selection value.');
}
class ChartInteractions{
 constructor(){this.pages=new Map()}
 key(report,page){return report+':'+page}
 entries(report,page){return [...(this.pages.get(this.key(report,page))?.values()||[])]}
 select(report,page,source,fields,datum,multi=false){
  if(!fields.length||fields.some(f=>!Object.prototype.hasOwnProperty.call(datum,f.dataField)))return false;
  const tuple=fields.map(f=>datum[f.dataField]);tuple.forEach(literal);
  const key=this.key(report,page),map=this.pages.get(key)||new Map(),old=map.get(source);
  let tuples=old&&equal(old.fields,fields)?old.tuples:[];
  const index=tuples.findIndex(t=>equal(t,tuple));
  if(multi)tuples=index<0?[...tuples,tuple]:tuples.filter((_,i)=>i!==index);
  else tuples=tuples.length===1&&index===0?[]:[tuple];
  if(tuples.length)map.set(source,{source,fields,tuples});else map.delete(source);
  if(map.size)this.pages.set(key,map);else this.pages.delete(key);
  return true;
 }
 clear(report,page,source){const key=this.key(report,page),map=this.pages.get(key);if(!map)return false;if(source)map.delete(source);else map.clear();if(!map.size)this.pages.delete(key);return true}
 removeReport(report){for(const key of this.pages.keys())if(key.startsWith(report+':'))this.pages.delete(key)}
 allowed(page,source,target){return source!==target&&!(page.visualInteractions||[]).some(r=>r.source===source&&r.target===target&&r.type==='NoFilter')}
 filtersFor(report,page,target){
  return this.entries(report,page.id).filter(s=>this.allowed(page,s.source,target)).map(s=>({filter:{Where:[{Condition:{In:{Expressions:s.fields.map(f=>({Column:{Expression:{SourceRef:{Entity:f.table}},Property:f.column}})),Values:s.tuples.map(t=>t.map(literal))}}}]}}));
 }
 selected(report,page,source){return this.entries(report,page).find(s=>s.source===source)}
 matchesDatum(selection,datum){return !selection||selection.tuples.some(t=>selection.fields.every((f,i)=>equal(t[i],datum[f.dataField])))}
}
const api={ChartInteractions,bindings,literal};if(typeof module!=='undefined')module.exports=api;root.ChartInteractionAPI=api;
})(globalThis);
