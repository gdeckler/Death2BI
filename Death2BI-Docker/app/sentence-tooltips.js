/* Native sentence templates use rendered query values, never another model query. */
(function(root){
const Style=typeof module!=='undefined'?require('./report-style'):root.ReportStyle;
const Formats=typeof module!=='undefined'?require('./model-formats'):root.ModelFormats;
const own=(object,key)=>object!=null&&Object.hasOwn(object,key),escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sourceRank=['theme-global','theme-global-preset','theme-visual','theme-visual-preset','visual','container'];
function properties(model,visual){
 const merged={},ranks={};
 // Legacy tooltip and modern visualTooltip are aliases; authored properties
 // take precedence over theme defaults regardless of which alias was used.
 for(const name of ['tooltip','visualTooltip']){
  const resolved=Style.resolveProperties(model,visual,name);
  for(const [key,value] of Object.entries(resolved.properties)){const rank=sourceRank.indexOf(resolved.sources[key]);if(!own(ranks,key)||rank>=ranks[key]){merged[key]=value;ranks[key]=rank}}
 }
 return merged;
}
function settings(model,visual){
 const p=properties(model,visual),theme=model.theme||{},read=key=>Style.value(p[key],theme),template=read('sentenceTemplate');
 if(read('show')===false||read('showSentenceFormat')!==true||typeof template!=='string'||!template.trim())return null;
 const titleColor=Style.color(p.themedTitleFontColor,theme)||Style.color(theme.foreground,theme)||'#252423';
 return {template,showValuesInBold:read('showValuesInBold')===true,showTooltipFieldsOnly:read('showTooltipFieldsOnly'),showChartSpecificTooltips:read('showChartSpecificTooltips'),showActionsInTooltips:read('showActionsInTooltips'),titleColor,valueColor:Style.color(p.themedValueFontColor,theme)||titleColor,background:Style.color(p.themedBackground,theme)||Style.color(theme.background,theme)||'#FFFFFF'};
}
function projections(visual,compiled){
 const state=visual.definition?.query?.queryState||{},flat=Object.values(state).flatMap(slot=>(slot.projections||[]).filter(p=>p.active!==false)),offsets={};
 return compiled.labels.map((_,index)=>{const role=compiled.roles?.[index],list=state[role]?.projections?.filter(p=>p.active!==false),offset=offsets[role]||0;offsets[role]=offset+1;return list?.[offset]||flat[index]||{}});
}
function aliases(projection,label){
 const field=projection.field||{},node=field.Measure||field.Column||field.GroupRef||field.Aggregation?.Expression?.Column,table=node?.Expression?.SourceRef?.Entity;
 return [[label,0],...[projection.displayName,projection.nativeQueryRef,projection.queryRef].map(name=>[name,1]),[node?.Property,2],...(table&&node?.Property?[[table+'.'+node.Property,2],["'"+table.replaceAll("'","''")+"'["+node.Property+']',2]]:[]),...(projection.queryRef?.includes('.')?[[projection.queryRef.slice(projection.queryRef.indexOf('.')+1),2]]:[])].filter(([name])=>typeof name==='string'&&name!=='');
}
function create(model,visual,compiled,result={}){
 const options=settings(model,visual);if(!options)return null;
 const labels=compiled.labels||[],fields=projections(visual,{...compiled,labels}),names=new Map(),folded=new Map(),rows=result.rows||[],rowIndices=new Map(rows.map((row,index)=>[row,index]));
 function add(map,key,index,rank){const old=map.get(key);if(!old||rank<old.rank)map.set(key,{rank,indices:new Set([index])});else if(rank===old.rank)old.indices.add(index)}
 const fieldAliases=fields.map((field,index)=>aliases(field,labels[index]));
 fieldAliases.forEach((list,index)=>list.forEach(([name,rank])=>{add(names,name,index,rank);add(folded,name.toLowerCase(),index,rank)}));
 const indexFor=name=>{const found=names.get(name)||folded.get(name.toLowerCase());return found?.indices.size===1?[...found.indices][0]:undefined};
 const parts=[];let position=0;for(const match of options.template.matchAll(/\{([^{}]+)\}/g)){if(match.index>position)parts.push({text:options.template.slice(position,match.index)});parts.push({token:match[0],name:match[1].trim(),index:indexFor(match[1].trim())});position=match.index+match[0].length}if(position<options.template.length)parts.push({text:options.template.slice(position)});
 const formatVisual={...visual,definition:{...visual.definition,query:{queryState:{Values:{projections:fields}}}}},expressionIndices=new Map(fields.flatMap((p,index)=>p.field?[[JSON.stringify(p.field),index]]:[]));
 function fromRaw(raw,index){
  if(!raw||typeof raw!=='object')return {present:false};const key=fields[index]?.field&&JSON.stringify(fields[index].field);
  if(key&&raw.__formatExpressions?.has(key))return {present:true,value:raw.__formatExpressions.get(key)};
  for(const [name] of fieldAliases[index])if(indexFor(name)===index&&own(raw,name))return {present:true,value:raw[name]};
  return {present:false};
 }
 function context(datum){
  const explicit=Array.isArray(datum)?datum:Array.isArray(datum?._rowValues)?datum._rowValues:Array.isArray(datum?._cardRow)?datum._cardRow:null,raw=datum?._raw||datum,values=labels.map((_,index)=>explicit&&own(explicit,index)?{present:true,value:explicit[index]}:fromRaw(raw,index));
  const identity=datum?._rowIdentity;
  for(const field of identity?.fields||[]){const expression=field.field||{Column:{Expression:{SourceRef:{Entity:field.table}},Property:field.column}},index=expressionIndices.get(JSON.stringify(expression));if(index!==undefined&&own(identity.datum,field.dataField)&&!values[index].present)values[index]={present:true,value:identity.datum[field.dataField]}}
  for(const [roles,key] of [[['Category','Group','Rows','Location'],'_categoryValue'],[['Series','Legend','Columns'],'_dimension']]){const indices=(compiled.roles||[]).flatMap((role,index)=>roles.includes(role)?[index]:[]);if(indices.length===1&&own(datum,key)&&!values[indices[0]].present)values[indices[0]]={present:true,value:datum[key]}}
  let rowIndex=explicit?(rowIndices.get(explicit)??-1):-1;
  // Legacy callbacks can carry only a category identity. Recover additional
  // values only if it identifies exactly one cached result row.
  if(rowIndex<0){const constraints=values.flatMap((entry,index)=>entry.present&&entry.value!==undefined?[index]:[]);if(constraints.length||rows.length===1){const matches=[];for(let index=0;index<rows.length;index++)if(constraints.every(column=>Object.is(rows[index][column],values[column].value)||rows[index][column]===values[column].value))matches.push(index);if(matches.length===1)rowIndex=matches[0]}}
  if(rowIndex>=0)labels.forEach((_,index)=>{if(!values[index].present&&own(rows[rowIndex],index))values[index]={present:true,value:rows[rowIndex][index]}});
  return {values,formats:datum?._rowFormats||result.rowFormats?.[rowIndex]};
 }
 return {settings:options,render(datum){
  const {values,formats}=context(datum),unresolved=[],text=[],html=[];
  for(const part of parts){if(part.token===undefined){text.push(part.text);html.push(escape(part.text));continue}const entry=part.index===undefined?null:values[part.index];
   if(!entry?.present||entry.value===undefined||typeof entry.value==='number'&&!Number.isFinite(entry.value)){text.push(part.token);html.push(escape(part.token));if(!unresolved.includes(part.name))unresolved.push(part.name);continue}
   const format=Formats.resolve(model,formatVisual,part.index,{dynamicFormat:formats?.[part.index]??compiled.formats?.[part.index]}),formatted=Formats.text(entry.value,format.format,format),tag=options.showValuesInBold?'strong':'span';
   text.push(formatted);html.push('<'+tag+' style="color:'+escape(options.valueColor)+'">'+escape(formatted)+'</'+tag+'>');
  }
  return {text:text.join(''),html:'<div class="pbi-sentence-tooltip" style="white-space:pre-wrap;overflow-wrap:anywhere;color:'+escape(options.titleColor)+'">'+html.join('')+'</div>',style:{background:options.background,color:options.titleColor},unresolved};
 }};
}
const api={properties,settings,create};if(typeof module!=='undefined')module.exports=api;root.SentenceTooltips=api;
})(globalThis);
