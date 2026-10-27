/* Shared report behavior: synchronization, binding resolution, and exploration state. */
(function(root){
const clone=x=>structuredClone(x),key=f=>JSON.stringify(f),ps=v=>Object.values(v.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false));
function binding(page){return page.pageBinding||page.definition?.pageBinding||{}}
function bindingFields(page){const filters=Array.isArray(page.filters)?page.filters:page.filters?.filters||[];return (binding(page).parameters||[]).map(p=>p.fieldExpr||p.expression||filters.find(f=>f.name===p.boundFilter)?.expression||filters.find(f=>f.name===p.boundFilter)?.field).filter(Boolean)}
function compatible(a,b){while(a?.Aggregation)a=a.Aggregation.Expression;while(b?.Aggregation)b=b.Aggregation.Expression;return key(a)===key(b)}
function resolveTooltip(model,visual){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,o=S.objects(model,visual),settings={...S.props(o,'tooltip'),...S.props(o,'visualTooltip')};
 if(S.value(settings.show,model.theme)===false)return;
 const explicit=S.value(settings.section||settings.page||settings.pageName||settings.tooltipPage,model.theme),pages=[...model.pages,...(model.tooltipPages||[])];
 if(explicit)return pages.find(p=>p.id===explicit||p.name===explicit);
 if(String(S.value(settings.type,model.theme)||'').toLowerCase()==='default')return;
 const fields=ps(visual).map(p=>p.field),candidates=pages.filter(p=>(p.isTooltip||binding(p).type==='Tooltip')&&bindingFields(p).length&&bindingFields(p).some(f=>fields.some(x=>compatible(x,f))));
 return candidates.sort((a,b)=>bindingFields(b).filter(f=>fields.some(x=>compatible(x,f))).length-bindingFields(a).filter(f=>fields.some(x=>compatible(x,f))).length||String(a.id).localeCompare(String(b.id)))[0];
}
function syncInfo(visual){return visual.definition?.syncGroup||visual.syncGroup}
function setSlicerField(model,visual,field){
 const source=ps(visual)[0];if(!source)return;source.field=clone(field);const group=syncInfo(visual);if(!group?.groupName||group.fieldChanges===false)return;
 for(const page of model.pages)for(const peer of page.visuals||[]){const target=syncInfo(peer);if(peer.type==='slicer'&&target?.groupName===group.groupName&&target.fieldChanges!==false&&ps(peer)[0])ps(peer)[0].field=clone(field)}
}
function setSlicer(model,page,visual,state,filters){
 const stateKey=(p,v)=>model.id+':'+p.id+':'+v.id;state.set(stateKey(page,visual),filters);
 const group=syncInfo(visual);if(!group?.groupName||group.filterChanges===false)return;
 for(const peerPage of model.pages)for(const peer of peerPage.visuals||[]){const target=syncInfo(peer);if(peer.type!=='slicer'||target?.groupName!==group.groupName||target.filterChanges===false||peer.id===visual.id&&peerPage.id===page.id)continue;
  const sourceField=ps(visual)[0]?.field,peerField=ps(peer)[0]?.field;
  const replacement=clone(filters);function map(node){if(!node||typeof node!=='object')return;if(node.In?.Expressions)node.In.Expressions=node.In.Expressions.map(f=>compatible(f,sourceField)?clone(peerField):f);if(node.Comparison&&compatible(node.Comparison.Left,sourceField))node.Comparison.Left=clone(peerField);Object.values(node).forEach(map)}
  if(!compatible(sourceField,peerField)&&group.fieldChanges!==false&&target.fieldChanges!==false){peer.definition.query.queryState=clone(visual.definition.query.queryState)}else map(replacement);
  state.set(stateKey(peerPage,peer),replacement);
 }
}
function drillTargets(model,identity,{allowHidden=false}={}){
 const fields=identity?.fields?.map(f=>f.field||{Column:{Expression:{SourceRef:{Entity:f.table}},Property:f.column}})||[];
 return model.pages.filter(p=>(!p.hidden||allowHidden)&&(p.pageType==='Drillthrough'||binding(p).type==='Drillthrough')&&bindingFields(p).length&&bindingFields(p).some(f=>fields.some(x=>compatible(x,f))));
}
function drillFilters(page,identity,context=[]){
 const C=typeof module!=='undefined'?require('./chart-interactions'):root.ChartInteractionAPI,fields=identity.fields,expressions=fields.map(f=>f.field||{Column:{Expression:{SourceRef:{Entity:f.table}},Property:f.column}}),wanted=bindingFields(page),indices=expressions.flatMap((f,i)=>wanted.some(w=>compatible(w,f))?[i]:[]);
 if(indices.length<wanted.length)throw Error('Drillthrough requires all target fields.');
 const point={filter:{Where:[{Condition:{In:{Expressions:indices.map(i=>expressions[i]),Values:[indices.map(i=>C.literal(identity.datum[fields[i].dataField]))]}}}]}};
 return [...(binding(page).acceptsFilterContext==='None'?[]:context),point];
}
class ExplorationState{
 constructor(){this.states=new Map();this.pageFilters=new Map()}
 key(model,page,v){return [model.id,page.id,v.id].join(':')}
 get(model,page,v){
  const q=v.definition?.query?.queryState||{},signature=JSON.stringify(Object.values(q).flatMap(q=>(q.projections||[]).map(p=>p.field))),saved=this.states.get(this.key(model,page,v));if(saved&&saved.signature===signature)return saved;
  const role=['Category','Rows'].find(r=>q[r]?.projections?.length>1)||'Category',fields=q[role]?.projections||[];
  // Projection activity is the authored global drill state. Expansion states
  // describe individual nodes and are only a fallback when activity is absent.
  if(fields.some(p=>typeof p.active==='boolean')){const active=fields.flatMap((p,i)=>p.active!==false?[i]:[]),depth=active.length?active.at(-1):0;return {depth,path:[],expanded:active.length>1,signature,_authoredActive:active}}
  const levels=v.definition?.expansionStates?.find(x=>x.roles?.includes(role))?.levels||[],depth=Math.min(Math.max(0,levels.filter(x=>x.isCollapsed===false).length),Math.max(0,fields.length-1));return {depth,path:[],expanded:depth>0,signature}
 }
 set(model,page,v,state){const signature=JSON.stringify(Object.values(v.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).map(p=>p.field))),next=clone(state);delete next._authoredActive;this.states.set(this.key(model,page,v),{...next,signature})}
 plan(model,page,visual){const state=this.get(model,page,visual),v=clone(visual),q=v.definition?.query?.queryState,role=['Category','Rows'].find(r=>q?.[r]?.projections?.length>1);if(!role||v.type==='pivotTable'||v.type==='slicer')return v;
  const fields=q[role].projections;fields.forEach((p,i)=>p.active=Array.isArray(state._authoredActive)?state._authoredActive.includes(i):state.expanded?i<=state.depth:i===state.depth);v.filters=Array.isArray(v.filters)?v.filters:v.filters?[v.filters]:[];
  state.path.forEach((value,i)=>v.filters.push({filter:{Where:[{Condition:{In:{Expressions:[fields[i].field],Values:[[(typeof module!=='undefined'?require('./chart-interactions'):root.ChartInteractionAPI).literal(value)]]}}}]}}));
  v._hierarchy={role,depth:state.depth,levels:fields.length};return v;
 }
}
const api={binding,bindingFields,compatible,resolveTooltip,syncInfo,setSlicerField,setSlicer,drillTargets,drillFilters,ExplorationState};if(typeof module!=='undefined')module.exports=api;root.ReportBehavior=api;
})(globalThis);
