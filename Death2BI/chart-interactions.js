(function(root){
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function bindings(visual,channels){
 const facetFields=[];let facetIndex=0;for(const [role,q] of Object.entries(visual.definition?.query?.queryState||{}))if(['Rows','Columns','SmallMultiples','SmallMultiple'].includes(role)&&visual.definition.query.queryState.Category)for(const p of q.projections||[]){if(p.active===false)continue;const c=p.field?.Column||p.field?.GroupRef;if(c)facetFields.push({table:c.Expression.SourceRef.Entity,column:c.Property,dataField:'_facet'+facetIndex,label:c.Property});facetIndex++}
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
  return fields.some(f=>f.dataField==='_categoryValue')?[...fields,...facetFields]:[];
 }
 const fields=[];
 for(const [role,dataField] of [['Category','_categoryValue'],['Group','_categoryValue'],['Series','_dimension'],['Legend','_dimension']]){
  const projections=(state[role]?.projections||[]).filter(p=>p.active!==false);
  if(!projections.length)continue;
  // A collapsed hierarchy or multiple category fields needs a richer identity.
  if(projections.length!==1)return [];
  const c=projections[0].field?.Column||projections[0].field?.GroupRef;
  if(!c?.Expression?.SourceRef?.Entity||!c.Property)return [];
  fields.push({table:c.Expression.SourceRef.Entity,column:c.Property,dataField,label:c.Property});
 }
 if(!fields.some(f=>f.dataField==='_categoryValue'))return [];
 return [...fields,...facetFields];
}
function compoundIdentity(visual,row){
 const ps=Object.entries(visual.definition?.query?.queryState||{}).flatMap(([role,q])=>(q.projections||[]).filter(p=>p.active!==false).map(p=>({...p,role}))),fields=[],datum={};
 ps.forEach((p,i)=>{const c=p.field?.Column||p.field?.GroupRef,h=p.field?.HierarchyLevel;if(!c&&!h||/^formatting$|^tooltips?$/i.test(p.role)||row[i]===undefined)return;const key='_identity'+i;fields.push({...(c?{table:c.Expression?.SourceRef?.Entity,column:c.Property}:{}),field:p.field,dataField:key,label:p.displayName||p.nativeQueryRef||c?.Property||h.Level});datum[key]=row[i]});
 return fields.length?{fields,datum}:null;
}
// Use only unaggregated model columns as row identities; measure values are not filters.
function rowIdentity(visual,row,{matrix=false,path=[]}={}){
 const state=visual.definition?.query?.queryState||{},projections=matrix?(state.Rows?.projections||[]).slice(0,path.length):Object.values(state).flatMap(s=>(s.projections||[]).filter(p=>p.active!==false));
 const fields=[],datum={};
 for(const [i,p] of projections.entries()){
  const c=p.field?.Column||p.field?.GroupRef;
  if(!c?.Expression?.SourceRef?.Entity||!c.Property){if(matrix)return null;continue}
  const key='v'+i,value=matrix?path[i]:row[i];
  if(value===undefined||value!==null&&!['string','number','boolean'].includes(typeof value))return null;
  fields.push({table:c.Expression.SourceRef.Entity,column:c.Property,dataField:key,label:p.displayName||p.nativeQueryRef||c.Property});datum[key]=value;
 }
 return fields.length?{fields,datum}:null;
}
// A matrix cell carries both its row ancestors and its column ancestors.
// Keep the authored field expression so hierarchy levels retain their semantics.
function matrixTooltipIdentity(visual,path=[],columnPath=[]){
 const state=visual.definition?.query?.queryState||{},fields=[],datum={};
 for(const [role,values] of [['Rows',path],['Columns',columnPath]]){
  const projections=(state[role]?.projections||[]).filter(p=>p.active!==false||role==='Rows');
  for(const [i,value] of values.entries()){
   const p=projections[i],c=p?.field?.Column||p?.field?.GroupRef,h=p?.field?.HierarchyLevel;
   if(!c&&!h||value===undefined||value!==null&&!['string','number','boolean'].includes(typeof value)||typeof value==='number'&&!Number.isFinite(value))return null;
   const key='_'+role.toLowerCase()+i;
   fields.push({...(c?{table:c.Expression?.SourceRef?.Entity,column:c.Property}:{}),field:p.field,dataField:key,label:p.displayName||p.nativeQueryRef||c?.Property||h?.Level});datum[key]=value;
  }
 }
 return {fields,datum};
}
// Hover is independent of selection, including read-only report views. An array
// of cell identities lets a pivoted value include its own column context.
function suppressNativeTableTooltips(table,rows){
 if(!table?._pbiSuppressNativeTooltips)return;
 for(const tr of rows||table.querySelectorAll('tbody tr,tfoot tr')){
  tr.removeAttribute?.('title');for(const cell of tr.cells||[])cell.removeAttribute?.('title');
  // Conditional-formatting icons retain role/aria-label when their native
  // browser tooltip is replaced by a report or sentence tooltip.
  for(const title of tr.querySelectorAll?.('svg title')||[])title.remove();
 }
}
function bindRowTooltips(el,identities,{onHover,onLeave,tooltip}={}){
 const table=el.querySelector('table');if(!table)return;
 for(const binding of table._pbiRowTooltipBindings||[]){
  if(binding.row){const {row,show,leave,blur}=binding;if(row.onmousemove===show)row.onmousemove=null;if(row.onmouseleave===leave)row.onmouseleave=null;row.removeEventListener?.('focusin',show);row.removeEventListener?.('focusout',blur)}
  else binding.wrap.removeEventListener?.('scroll',binding.leave);
 }
 table._pbiRowTooltipBindings=[];
 table._pbiSuppressNativeTooltips=typeof onHover==='function'||tooltip===false;
 suppressNativeTableTooltips(table);
 if(typeof onHover!=='function'||tooltip===false)return;
 for(const [i,tr] of [...table.querySelectorAll('tbody tr')].entries()){
  const identitiesForRow=identities[i];if(!identitiesForRow)continue;
  if(tr.tabIndex<0)tr.tabIndex=0;
  const show=event=>{
   if(event.target?.closest?.('button,a,input,select,textarea')){onLeave?.();return}
   const cell=event.target?.closest?.('td,th'),index=cell?[...tr.cells].indexOf(cell):0;
   const identity=Array.isArray(identitiesForRow)?identitiesForRow[Math.max(0,index)]:identitiesForRow;
   if(!identity){onLeave?.();return}
   const rect=tr.getBoundingClientRect?.(),point=Number.isFinite(event.clientX)&&Number.isFinite(event.clientY)?event:{clientX:rect?.left+rect?.width/2||0,clientY:rect?.top+rect?.height/2||0};
   onHover({_rowIdentity:identity},point);
  };
  const leave=()=>onLeave?.(),blur=event=>{if(!tr.contains(event.relatedTarget))onLeave?.()};
  tr.onmousemove=show;tr.onmouseleave=leave;tr.addEventListener('focusin',show);tr.addEventListener('focusout',blur);
  table._pbiRowTooltipBindings.push({row:tr,show,leave,blur});
 }
 const wrap=el.querySelector('.tablewrap');if(wrap){const leave=()=>onLeave?.();wrap.addEventListener('scroll',leave,{passive:true});table._pbiRowTooltipBindings.push({wrap,leave})}
}
function attachRows(el,identities,{selection,onSelect}={}){
 const table=el.querySelector('table');if(!table||!onSelect)return;
 table.setAttribute('aria-multiselectable','true');
 for(const [i,tr] of [...table.querySelectorAll('tbody tr')].entries()){
  const identity=identities[i];if(!identity)continue;
  const active=!!selection&&equal(selection.fields,identity.fields)&&selection.tuples.some(t=>identity.fields.every((f,j)=>equal(t[j],identity.datum[f.dataField])));
  tr.tabIndex=0;tr.setAttribute('aria-selected',String(active));tr.style.cursor='pointer';tr.title='Select row to filter other visuals. Ctrl/Cmd-click adds or removes a row.';
  if(active){tr.style.outline='2px solid #246b55';tr.style.outlineOffset='-2px'}
  const pick=event=>{if(event.target.closest('button,a,input,select,textarea'))return;onSelect(identity,event)};
  tr.onclick=pick;tr.onkeydown=event=>{if((event.key==='Enter'||event.key===' ')&&event.target===tr){event.preventDefault();pick(event)}};
 }
 suppressNativeTableTooltips(table);
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
 filtersFor(report,page,target,mode='filter'){
  const targetVisual=page.visuals?.find(v=>v.id===target),canHighlight=/^(?:clustered|stacked|hundredPercent)?(?:Bar|Column|Area)Chart$|^(?:bar|column|line|area|pie|donut)Chart$/.test(targetVisual?.type||'');
  return this.entries(report,page.id).filter(s=>this.allowed(page,s.source,target)).filter(s=>{const highlight=canHighlight&&(page.visualInteractions||[]).some(r=>r.source===s.source&&r.target===target&&r.type==='HighlightFilter');return mode==='all'||(mode==='highlight'?highlight:!highlight)}).map(s=>({filter:{Where:[{Condition:{In:{Expressions:s.fields.map(f=>f.field||({Column:{Expression:{SourceRef:{Entity:f.table}},Property:f.column}})),Values:s.tuples.map(t=>t.map(literal))}}}]}}));
 }
 selected(report,page,source){return this.entries(report,page).find(s=>s.source===source)}
 matchesDatum(selection,datum){datum=datum?._rowIdentity?.datum||datum;return !selection||selection.tuples.some(t=>selection.fields.every((f,i)=>equal(t[i],datum[f.dataField])))}
}
const api={compoundIdentity,ChartInteractions,bindings,rowIdentity,matrixTooltipIdentity,suppressNativeTableTooltips,bindRowTooltips,attachRows,literal};if(typeof module!=='undefined')module.exports=api;root.ChartInteractionAPI=api;
})(globalThis);
