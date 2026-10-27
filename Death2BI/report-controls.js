/* Source-driven field parameters and range slicers. No imported code executes. */
(function(root){
function field(v){const state=v.definition?.query?.queryState||{};return (state.Values?.projections||Object.values(state).flatMap(s=>s.projections||[])).find(p=>p.active!==false)?.field}
function column(v){return field(v)?.Column}
function selected(filters){const f=filters?.[0]?.filter,where=f?.Where?.[0];return {value:filters?.selected,reference:where?.Condition?.In?.Values?.[0]?.[0]?.Literal?.Value??where?.Condition?.Comparison?.Right?.Literal?.Value,label:where?.Annotations?.filterExpressionMetadata?.valueMap?.[0]?.['0']}}
function parameterFieldIndex(meta){
 const valid=i=>i>=0&&meta.rows.length&&meta.rows.every(r=>typeof r[i]==='string'&&/^(?:'(?:[^']|'')+'|[^\[]+)\[[^\]]+(?:\]\][^\]]*)*\]$/.test(r[i]));
 const declared=meta.columns.indexOf(meta.fieldColumn);if(valid(declared))return declared;
 const matches=meta.columns.map((_,i)=>i).filter(valid);return matches.length===1?matches[0]:-1;
}
function selectionLabel(model,v,filters){const pick=selected(filters),c=column(v),meta=model.fieldParameters?.[c?.Expression?.SourceRef?.Entity];if(!meta)return pick.value??pick.label;const ref=pick.reference?.replace(/^'|'$/g,'').replaceAll("''", "'");const row=meta.rows.find(r=>r[parameterFieldIndex(meta)]===ref);return pick.value??pick.label??row?.[meta.columns.indexOf(c.Property)]}
async function resolveAsync(model,page,visual,getFilters,allowed,loadRows){
 const tables=[...new Set(Object.values(visual.definition?.query?.queryState||{}).flatMap(s=>(s.fieldParameters||[]).map(p=>p.parameterExpr?.Column?.Expression?.SourceRef?.Entity)).filter(t=>model.fieldParameters?.[t]))];
 if(!tables.length)return visual;
 const selectedRows={};for(const table of tables)selectedRows[table]=await loadRows(table);
 return resolve(model,page,visual,getFilters,allowed,selectedRows);
}
function resolve(model,page,visual,getFilters,allowed=()=>true,selectedRows={}){
 const copy=structuredClone(visual);for(const state of Object.values(copy.definition?.query?.queryState||{}))for(const p of [...(state.fieldParameters||[])].sort((a,b)=>(b.index||0)-(a.index||0))){
  const c=p.parameterExpr?.Column,t=c?.Expression?.SourceRef?.Entity,meta=model.fieldParameters?.[t];if(!meta)continue;
  const slicer=page.visuals.find(v=>v.type==='slicer'&&column(v)?.Expression?.SourceRef?.Entity===t&&allowed(v.id,visual.id)),fi=parameterFieldIndex(meta);
  let rows=selectedRows[t];
  const labelColumn=meta.columns.indexOf(slicer?column(slicer).Property:c.Property);
  if(!rows){
   if(!slicer)continue;
   const filters=getFilters(slicer),pick=selected(filters),ref=pick.reference?.replace(/^'|'$/g,'').replaceAll("''", "'"),chosen=selectedValues(filters);
   rows=meta.rows.filter(r=>r[labelColumn]===(pick.value??pick.label)||r[fi]===ref||chosen.some(value=>value===r[labelColumn]||value===r[fi]));
  }
  if(!rows?.length)continue;
  const order=meta.columns.findIndex(name=>/order|orden/i.test(name));if(order>=0)rows=rows.slice().sort((a,b)=>a[order]-b[order]);
  const replacements=[];
  for(const row of rows){
   const match=/^(?:'((?:[^']|'')+)'|([^\[]+))\[([^\]]+(?:\]\][^\]]*)*)\]$/.exec(row[fi]);if(!match)continue;
   const table=(match[1]||match[2]).replaceAll("''","'"),name=match[3].replaceAll(']]',']');
   const measure=model.measures.some(m=>(m.Name||m.name||m.MeasureName)===name&&(!m.TableName||m.TableName===table));
   const expr={[measure?'Measure':'Column']:{Expression:{SourceRef:{Entity:table}},Property:name}};
   replacements.push({field:expr,queryRef:table+'.'+name,nativeQueryRef:row[labelColumn]??name,displayName:row[labelColumn]??name,active:true});
  }
  if(!replacements.length)continue;
  const replaced=state.projections.slice(p.index||0,(p.index||0)+(p.length||1)).map(x=>JSON.stringify(x.field));
  for(const sort of copy.definition.query.sortDefinition?.sort||[])if(replaced.includes(JSON.stringify(sort.field))){sort.field=replacements[0].field;if(p.sortDirection)sort.direction=p.sortDirection}
  state.projections.splice(p.index||0,p.length||1,...replacements);p.length=replacements.length;
 }
 return copy;
}
function rangeFilter(expression,low,high){const lit=(v,end=false)=>({Literal:{Value:typeof v==='number'?String(v):/^\d{4}-\d{2}-\d{2}$/.test(v)?"datetime'"+v+(end?"T23:59:59.9999999'":"T00:00:00'"):"'"+String(v).replaceAll("'","''")+"'"}});const result=[{filter:{Where:[{Condition:{And:{Left:{Comparison:{ComparisonKind:2,Left:expression,Right:lit(low)}},Right:{Comparison:{ComparisonKind:4,Left:expression,Right:lit(high,true)}}}}}]}}];result.range=[low,high];return result}
function mode(v){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,data=S.props(v.definition?.objects,'data'),explicit=S.value(data.mode);if(explicit)return explicit;
 // Numeric Single is omitted as the default in some legacy slicers. A saved
 // scalar start plus an equality filter identifies that mode, not a range.
 const filter=S.props(v.definition?.objects,'general').filter;let equality=false;function scan(x){if(!x||typeof x!=='object')return;if(x.Comparison?.ComparisonKind===0)equality=true;Object.values(x).forEach(scan)}scan(filter);
 if(data.numericStart!==undefined&&data.numericEnd===undefined&&equality)return 'Single';
}

function isFilterVisual(model,visual){return visual.type==='slicer'||!!root.CustomVisuals?.isFilterVisual(visual.type,model)}
function filtersFor(model,page,target,getFilters,allowed){return page.visuals.filter(v=>isFilterVisual(model,v)&&v.id!==target&&(!target||allowed(v.id,target))).flatMap(v=>getFilters(v)||[])}

const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function singleValuePlan(model,v,values,filters=[]){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,theme=model.theme||{},domain=[...new Set(values.filter(Number.isFinite))].sort((a,b)=>a-b);
 if(!domain.length)throw Error('Single Value slicer needs a numeric domain.');
 const kind=mode(v),bounds=[];function scan(x){if(!x||typeof x!=='object')return;if(x.Comparison)bounds.push(x.Comparison);Object.values(x).forEach(scan)}filters.forEach(scan);const boundary=bounds.find(c=>c.ComparisonKind===(kind==='Before'?4:2)),bound=boundary?S.value(boundary.Right,theme):undefined;const saved=selectedValues(filters)[0]??bound??S.value(S.props(S.objects(model,v),'data').numericStart,theme)??(kind==='Before'?domain.at(-1):domain[0]),nearest=x=>domain.reduce((a,b)=>Math.abs(b-x)<Math.abs(a-x)?b:a,domain[0]);
 const c=column(v),format=v.definition?.columnProperties?.[v.definition?.query?.queryState?.Values?.projections?.[0]?.queryRef]?.formatString||model.tables?.find(t=>t.name===c?.Expression?.SourceRef?.Entity)?.columns.find(x=>x.name===c.Property)?.formatString||'';
 const scale=format.includes('%')?100:1,step=domain.length>1?Math.min(...domain.slice(1).map((x,i)=>x-domain[i])):1;
 return {domain,selected:nearest(Number(saved)),nearest,scale,step:Number((step*scale).toPrecision(12)),format};
}
function singleValueSlicer(el,model,v,values,filters,onChange){
 values=orderedValues(v,values);
 const S=root.ReportStyle,theme=model.theme||{},o=S.objects(model,v),plan=singleValuePlan(model,v,values,filters),p=S.props(o,'numericInputStyle'),slider=S.props(o,'slider');
 const wrapper=document.createElement('div');wrapper.style.cssText='display:flex;flex-direction:column;gap:8px;min-height:0;width:100%';el.appendChild(wrapper);
 const input=document.createElement('input');input.type='number';input.setAttribute('aria-label','Single value');input.min=Number((plan.domain[0]*plan.scale).toPrecision(12));input.max=Number((plan.domain.at(-1)*plan.scale).toPrecision(12));input.step=plan.step;input.value=Number((plan.selected*plan.scale).toPrecision(12));input.style.cssText='width:100%;min-width:0;box-sizing:border-box;text-align:center';if(S.value(p.bold,theme))input.style.fontWeight='bold';wrapper.appendChild(input);
 if(plan.scale===100){const unit=document.createElement('span');unit.textContent='%';unit.style.cssText='align-self:flex-end;font-size:12px';wrapper.appendChild(unit)}
 const range=document.createElement('input');range.type='range';range.setAttribute('aria-label','Single value slider');range.min=0;range.max=plan.domain.length-1;range.step=1;range.value=plan.domain.indexOf(plan.selected);range.style.width='100%';if(S.value(slider.show,theme)!==false)wrapper.appendChild(range);
 range.style.accentColor=S.color(slider.color,theme)||theme.dataColors?.[0]||'#4c3f7a';
 if(S.color(p.fontColor,theme)&&S.color(p.fontColor,theme)===S.color(p.background,theme))input.style.border='none';
 const commit=n=>{if(!Number.isFinite(n)||n<plan.domain[0]-1e-10||n>plan.domain.at(-1)+1e-10){input.setCustomValidity('Choose a value within the available range.');input.reportValidity();return}input.setCustomValidity('');onChange(mode(v)==='Before'?rangeFilter(field(v),plan.domain[0],plan.nearest(n)):mode(v)==='After'?rangeFilter(field(v),plan.nearest(n),plan.domain.at(-1)):categoricalFilter(field(v),[plan.nearest(n)]))};
 range.oninput=()=>{input.value=Number((plan.domain[Number(range.value)]*plan.scale).toPrecision(12))};range.onchange=()=>commit(plan.domain[Number(range.value)]);const commitInput=()=>{const n=Number(input.value)/plan.scale;if(input.value.trim()!==''&&Math.abs(n-plan.selected)>1e-12)commit(n)};input.onchange=commitInput;input.onblur=commitInput;input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();commitInput()}};
}
function slicerSettings(model,v){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,o=S.objects(model,v),theme=model.theme||{},selection=S.props(o,'selection'),general=S.props(o,'general'),data=S.props(o,'data'),settings=S.props(o,'slicerSettings');
 const sourceMode=S.value(data.dropdownMode,theme)===true?'dropdown':String(S.value(data.mode??settings.style,theme)||'Basic').toLowerCase(),orientation=S.value(general.orientation,theme);
 const button=v.originalType==='advancedSlicerVisual'||v.type==='advancedSlicerVisual'||v.definition?.visualType==='advancedSlicerVisual';
 const layout=button||/tile|horizontal/.test(sourceMode)||sourceMode==='basic'&&(orientation===1||/horizontal/i.test(String(orientation)))?'tiles':/dropdown/.test(sourceMode)?'dropdown':'list';
 return {layout,single:S.value(selection.strictSingleSelect??selection.singleSelect,theme)===true,strict:S.value(selection.strictSingleSelect,theme)===true,ctrl:S.value(selection.multiSelectWithCtrl,theme)!==false,selectAll:S.value(selection.selectAllCheckboxEnabled,theme)===true,search:S.value(general.selfFilterEnabled,theme)===true,button,orientation:S.value(S.props(o,'layout').orientation,theme)};
}
function categoricalFilter(expression,values){
 const lit=v=>({Literal:{Value:v===null?'null':typeof v==='number'||typeof v==='boolean'?String(v):"'"+String(v).replaceAll("'","''")+"'"}});
 const filters=[{filter:{Where:[{Condition:{In:{Expressions:[expression],Values:values.map(v=>[lit(v)])}}}]}}];filters.selectedValues=[...values];if(values.length===1)filters.selected=values[0];return filters;
}
function selectedValues(filters){
 if(Array.isArray(filters?.selectedValues))return filters.selectedValues;
 if(filters?.selected!==undefined)return [filters.selected];
 const values=[];const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle;
 function visit(x){if(!x||typeof x!=='object'||x.Not)return;if(x.In?.Values)for(const tuple of x.In.Values)if(tuple.length===1)values.push(S.value(tuple[0]));if(x.Comparison?.ComparisonKind===0&&x.Comparison.Right?.Literal)values.push(S.value(x.Comparison.Right));for(const [key,value] of Object.entries(x))if(!['In','Comparison'].includes(key))visit(value)}visit(filters);return values;
}
let popup,cleanup;
function closePopup(){popup?.remove();popup=null;cleanup?.();cleanup=null}
function orderedValues(v,values){const sort=v.definition?.query?.sortDefinition;if(sort?.isDefaultSort===true&&sort.sort?.some(s=>s.field?.Aggregation)&&values.every(x=>x==null||typeof x==='number'))return [...values].sort((a,b)=>a==null?1:b==null?-1:a-b);return values}
function slicerImagePlan(model,v,values){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,settings=slicerSettings(model,v);if(!settings.button)return null;
 const theme=model.theme||{},objects=S.objects(model,v),p=S.resolveProperties(model,v,'image',{datum:{_projectionRef:v.definition?.query?.queryState?.Values?.projections?.[0]?.queryRef}}).properties;
 if(S.value(p.show,theme)===false)return null;
 const c=column(v),metadata=model.tables?.find(t=>t.name===c?.Expression?.SourceRef?.Entity)?.columns.find(x=>x.name===c?.Property),declared=Object.keys(p).length||/imageurl/i.test(metadata?.dataCategory||'');
 const urls=values.map(value=>typeof value==='string'&&(declared||/^data:image\//i.test(value))?S.url(value,model):null);if(!urls.some(Boolean))return null;
 const layout=S.props(objects,'layout'),number=(x,fallback)=>Number.isInteger(Number(S.value(x,theme)))&&Number(S.value(x,theme))>0?Math.min(100,Number(S.value(x,theme))):fallback,columns=Math.max(1,Math.min(values.length,number(layout.columnCount,1))),rows=Math.max(1,Math.min(Math.ceil(values.length/columns),number(layout.rowCount,Math.ceil(values.length/columns))));
 const fit=String(S.value(p.enhancedFit??p.imageFit??p.fit,theme)||'Fit').toLowerCase();
 return {urls,columns,rows,fit:/stretch/.test(fit)?'fill':/fill/.test(fit)?'cover':/normal/.test(fit)?'none':'contain',position:String(S.value(p.position,theme)||'Top').toLowerCase(),showValues:S.value(S.props(objects,'value').show,theme)===true};
}
function buttonSlicerStyle(model,v,value,selected){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,theme=model.theme||{},datum={_categoryValue:value,_projectionRef:v.definition?.query?.queryState?.Values?.projections?.[0]?.queryRef},state=selected?'selection:selected':'selection:unselected',read=group=>S.resolveProperties(model,v,group,{state,datum}).properties;
 const fill=read('fillCustom'),outline=read('outline'),text=read('value');
 return {background:S.value(fill.show,theme)===false?'transparent':S.color(fill.fillColor??fill.color,theme)|| (selected?theme.dataColors?.[0]||'#246b55':'transparent'),color:S.color(text.fontColor??text.color,theme)||theme.foreground||'#222',fontFamily:S.value(text.fontFamily,theme)||theme.textClasses?.label?.fontFace||'Segoe UI',fontSize:Math.max(1,Number(S.value(text.fontSize,theme))||10)*4/3,fontWeight:S.value(text.bold,theme)===true?'bold':S.value(text.bold,theme)===false?'normal':undefined,border:S.value(outline.show,theme)===true?'1px solid '+(S.color(outline.lineColor??outline.color,theme)||theme.foreground||'#888'):'none',showValue:S.value(text.show,theme)!==false};
}
function categoricalSlicer(el,model,v,values,{filters=[],label='Values',parameter=false,onChange,onHover,onLeave}={}){
 values=orderedValues(v,values);
 const S=root.ReportStyle,theme=model.theme||{},o=S.objects(model,v),items={...S.props(o,'items'),...S.props(o,'value')},settings=slicerSettings(model,v),rawChosen=selectedValues(filters),rawLabel=x=>x===null?'(Blank)':String(x),has=x=>chosen.some(y=>same(x,y));let chosen=rawChosen;if(parameter){const table=column(v)?.Expression?.SourceRef?.Entity,meta=model.fieldParameters?.[table],fi=meta?parameterFieldIndex(meta):-1,li=meta?.columns.indexOf(column(v)?.Property);if(meta&&rawChosen.length>1)chosen=rawChosen.map(x=>meta.rows.find(row=>row[fi]===x||row[li]===x)?.[li]??x);else{const label=selectionLabel(model,v,filters);if(label!==undefined)chosen=[label]}}
 const font=S.value(items.fontFamily,theme)||theme.textClasses?.label?.fontFace||'Segoe UI',size=((S.value(items.textSize||items.fontSize,theme)||10)*4/3)+'px',color=S.color(items.fontColor,theme)||theme.foreground||'#222',background=S.color(items.background,theme)||'transparent';
 const container=document.createElement('div');container.className='pbi-slicer-options';container.style.cssText='min-height:0;max-height:100%;overflow:auto;pointer-events:auto';el.appendChild(container);
 // Keep the mounted control current while its parent asynchronously rerenders.
 const repaint=[];const commit=next=>{chosen=next===null?[]:[...next];for(const paint of repaint)paint();closePopup();onChange(next===null?null:categoricalFilter(field(v),next))};
 if(settings.layout==='dropdown'){
  const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',label);button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-expanded','false');button.dataset.snapshotSlicer='true';button.textContent=(chosen.length?chosen.map(rawLabel).join(', '):Array.isArray(filters?.selectedValues)&&!filters.selectedValues.length?'None':filters.length?'Saved selection':'All')+' ▾';button.style.cssText='width:100%;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:5px;border-radius:2px';button.style.fontFamily=font;button.style.fontSize=size;button.style.color=color;button.style.background=background;container.appendChild(button);
  button.onclick=()=>{
   if(popup){closePopup();return}let draft=[...chosen];const box=document.createElement('div');popup=box;box.className='pbi-slicer-popup';box.setAttribute('role','dialog');box.setAttribute('aria-label',label+' choices');
   const rect=button.getBoundingClientRect();box.style.cssText='position:fixed;z-index:100001;box-shadow:0 4px 20px #0003;border:1px solid #b6c6bb;border-radius:5px;padding:10px;background:white;color:#193a37;overflow:auto;max-height:60vh;min-width:220px';box.style.width=Math.max(220,Math.min(420,rect.width))+'px';box.style.left=Math.max(8,Math.min(innerWidth-430,rect.left))+'px';box.style.top=Math.min(innerHeight-240,rect.bottom+3)+'px';box.style.fontFamily=font;box.style.fontSize=size;
   (root.ReportFullscreen?.overlayHost?.()||document.body).appendChild(box);const actions=document.createElement('div');actions.style.cssText='display:flex;gap:6px;margin-bottom:8px';box.appendChild(actions);
   const clear=document.createElement('button');clear.type='button';clear.textContent='Clear selection';if(!parameter)actions.appendChild(clear);clear.onclick=()=>commit(null);
   if(!settings.single){const apply=document.createElement('button');apply.type='button';apply.textContent='Apply';actions.appendChild(apply);apply.onclick=()=>commit(draft.length===values.length?null:draft)}
   let search;if(settings.search){search=document.createElement('input');search.type='search';search.placeholder='Search';search.setAttribute('aria-label','Search '+label);search.style.cssText='width:100%;margin-bottom:8px;padding:6px';box.appendChild(search)}
   const list=document.createElement('div');box.appendChild(list);
   function row(text,value,all=false){const line=document.createElement('label');line.style.cssText='display:flex;align-items:center;gap:8px;padding:5px;cursor:pointer';line.dataset.label=text.toLowerCase();const input=document.createElement('input');input.type=settings.single?'radio':'checkbox';input.name='slicer-'+v.id;input.checked=all?draft.length===values.length:draft.some(x=>same(x,value));input.setAttribute('aria-label',text);line.append(input,document.createTextNode(text));list.appendChild(line);input.onchange=()=>{if(settings.single){commit([value]);return}if(all)draft=input.checked?[...values]:[];else draft=input.checked?[...draft.filter(x=>!same(x,value)),value]:draft.filter(x=>!same(x,value));for(const [i,n] of [...list.querySelectorAll('input')].entries())n.checked=n.dataset.all==='true'?draft.length===values.length:draft.some(x=>same(x,values[settings.selectAll?i-1:i]));};if(all)input.dataset.all='true'}
   if(settings.selectAll&&!settings.single)row('Select all',null,true);for(const value of values)row(rawLabel(value),value);
   if(search)search.oninput=()=>{for(const line of list.children)line.style.display=line.dataset.label.includes(search.value.toLowerCase())?'flex':'none'};
   const outside=e=>{if(!box.contains(e.target)&&e.target!==button)closePopup()},keys=e=>{if(e.key==='Escape')closePopup()};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',keys);cleanup=()=>{button.setAttribute('aria-expanded','false');document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',keys)};button.setAttribute('aria-expanded','true');(search||box.querySelector('input')||clear).focus();
  };return;
 }
 container.setAttribute('role','group');container.setAttribute('aria-label',label);container.style.display='flex';container.style.flexDirection=settings.layout==='tiles'?'row':'column';container.style.flexWrap=settings.layout==='tiles'?'wrap':'nowrap';container.style.gap='4px';if(settings.button){container.style.flexDirection=settings.orientation===1?'column':'row';container.style.flexWrap=settings.orientation===1?'nowrap':'wrap';container.style.flex='1 1 0';container.style.width='100%';container.style.minHeight='0';container.style.alignItems='stretch';container.style.alignContent='stretch'};
 const images=slicerImagePlan(model,v,values);if(images){container.style.display='grid';container.style.gridTemplateColumns='repeat('+images.columns+',minmax(0,1fr))';container.style.gridTemplateRows='repeat('+images.rows+',minmax(0,1fr))';container.style.gridAutoRows='minmax(40px,1fr)';container.style.flex='1';container.style.width='100%';container.style.height='100%'}
 if(settings.selectAll&&!settings.single){const clear=document.createElement('button');clear.type='button';clear.textContent=settings.selectAll?'Select all':'Clear selection';clear.style.cssText='padding:3px 6px;font-size:10px';clear.onclick=()=>commit(null);container.appendChild(clear)}
 for(const [index,value] of values.entries()){const button=document.createElement('button');button.type='button';button.textContent=rawLabel(value);button.dataset.snapshotSlicer='true';button.setAttribute('aria-label',rawLabel(value));button.style.cssText='padding:5px 8px;border:0;border-radius:2px;text-align:left;flex-shrink:0';button.style.fontFamily=font;button.style.fontSize=size;
  const paint=()=>{button.setAttribute('aria-pressed',String(has(value)));button.style.color=has(value)?'#fff':color;button.style.background=has(value)?(theme.dataColors?.[0]||'#246b55'):background;if(settings.button){const style=buttonSlicerStyle(model,v,value,has(value));Object.assign(button.style,{fontFamily:style.fontFamily,fontSize:style.fontSize+'px',color:style.color,background:style.background,border:style.border,fontWeight:style.fontWeight||''});if(!images?.urls[index])button.textContent=style.showValue?rawLabel(value):''}};repaint.push(paint);paint();
  if(settings.button){button.style.flex='1 1 0';button.style.minWidth='0';button.style.minHeight='0';button.style.alignSelf='stretch'}
  if(images?.urls[index]){button.textContent='';button.setAttribute('aria-label',label+' '+(index+1));button.style.cssText+=';display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:0;min-height:0;overflow:hidden;padding:0;width:100%;height:100%';const image=document.createElement('img');image.src=images.urls[index];image.alt='';image.referrerPolicy='no-referrer';image.loading='eager';image.style.cssText='width:100%;height:100%;min-width:0;min-height:0;flex:1;object-fit:'+images.fit;image.onerror=()=>{image.title='Image could not be loaded from its source URL.'};button.appendChild(image);if(images.showValues){const text=document.createElement('span');text.textContent=rawLabel(value);text.style.cssText='flex:none;overflow-wrap:anywhere';images.position==='bottom'?button.prepend(text):button.appendChild(text)}}
  container.appendChild(button);if(onHover){button.onmouseenter=event=>onHover(value,event);button.onmousemove=event=>onHover(value,event);button.onmouseleave=()=>onLeave?.()}button.onclick=e=>{if(settings.single||settings.ctrl&&!e.ctrlKey&&!e.metaKey){commit(has(value)&&chosen.length===1&&!parameter&&!settings.strict?null:[value]);return}const next=has(value)?chosen.filter(x=>!same(x,value)):[...chosen,value];commit(next.length?next:null)}}
}

function hierarchyFields(v){return (v.definition?.query?.queryState?.Values?.projections||[]).filter(p=>p.active!==false)}
function hierarchyFilter(v,paths){
 const fields=hierarchyFields(v),lit=x=>({Literal:{Value:x===null?'null':typeof x==='number'?String(x):"'"+String(x).replaceAll("'","''")+"'"}});
 const combine=(nodes,key)=>nodes.reduce((a,b)=>a?{[key]:{Left:a,Right:b}}:b,null);
 const condition=combine(paths.map(path=>combine(path.map((value,i)=>({Comparison:{ComparisonKind:0,Left:fields[i].field,Right:lit(value)}})),'And')),'Or');
 const result=condition?[{filter:{Where:[{Condition:condition}]}}]:[];result.selectedPaths=paths;return result;
}
function hierarchyPlan(v,depth=0,path=[]){const copy=structuredClone(v),fields=hierarchyFields(v);copy.definition.query={queryState:{Values:{projections:[fields[depth]]}}};copy.filters=[v.filters,...hierarchyFilter(v,path.length?[path]:[])];return copy}
const hierarchyExpanded=new Map();
async function hierarchySlicer(el,model,v,initial,{filters=[],load,onChange}={}){
 const fields=hierarchyFields(v),S=root.ReportStyle,settings=slicerSettings(model,v),props=S.props(S.objects(model,v),'items'),theme=model.theme||{},key=model.id+':'+v.id,expanded=hierarchyExpanded.get(key)||new Set();hierarchyExpanded.set(key,expanded);
 let paths=filters.selectedPaths||[];const prefix=(a,b)=>a.length<=b.length&&a.every((x,i)=>same(x,b[i]));
 const tree=document.createElement('div');tree.setAttribute('role','tree');tree.style.cssText='overflow:auto;min-height:0;flex:1;width:100%;pointer-events:auto;font-family:'+(S.value(props.fontFamily,theme)||'Segoe UI')+';font-size:'+((S.value(props.textSize||props.fontSize,theme)||10)*4/3)+'px';el.style.pointerEvents='auto';el.append(tree);
 const nodes=[];
 const refresh=()=>{for(const n of nodes){n.input.checked=paths.some(p=>prefix(p,n.path));n.input.indeterminate=!n.input.checked&&paths.some(p=>prefix(n.path,p));}};
 async function populate(parent,values,path){for(const value of values){const next=[...path,value],id=JSON.stringify(next),row=document.createElement('div'),branch=document.createElement('div'),button=document.createElement('button'),input=document.createElement('input'),label=document.createElement('span');row.style.cssText='display:flex;align-items:center;gap:6px;min-height:28px';branch.style.paddingLeft='18px';branch.hidden=true;button.type='button';button.textContent='▸';button.setAttribute('aria-label','Expand '+next.join(' / '));button.setAttribute('aria-expanded','false');button.style.cssText='width:24px;padding:0;min-width:24px';input.type='checkbox';input.setAttribute('aria-label',next.join(' / '));label.textContent=value??'(Blank)';row.append(button,input,label);parent.append(row,branch);const node={input,path:next,children:[]};nodes.push(node);refresh();
  input.onchange=()=>{const ancestor=paths.find(p=>prefix(p,next)&&p.length<next.length);if(ancestor){const siblings=[];for(let depth=ancestor.length;depth<next.length;depth++){const owner=nodes.find(n=>same(n.path,next.slice(0,depth)));if(!owner?.children.length)return;siblings.push(...owner.children.filter(p=>!prefix(p,next)))}paths=paths.filter(p=>!same(p,ancestor));paths.push(...siblings)}if(input.checked){paths=settings.single?[next]:[...paths.filter(p=>!prefix(next,p)),next]}else paths=paths.filter(p=>!prefix(next,p)&&!same(p,next));refresh();onChange(hierarchyFilter(v,paths))};
  if(next.length===fields.length){button.style.visibility='hidden';continue}
  let loaded=false;button.onclick=async()=>{const open=branch.hidden;branch.hidden=!open;button.textContent=open?'▾':'▸';button.setAttribute('aria-expanded',String(open));button.setAttribute('aria-label',(open?'Collapse ':'Expand ')+next.join(' / '));if(open)expanded.add(id);else expanded.delete(id);if(open&&!loaded){loaded=true;button.disabled=true;try{const result=await load(hierarchyPlan(v,next.length,next));if(!el.isConnected)return;node.children=result.result.rows.map(r=>[...next,r[0]]);await populate(branch,result.result.rows.map(r=>r[0]),next);if(result.result.truncated){const note=document.createElement('p');note.textContent='More values are available. Narrow the report filters.';branch.append(note)}}catch(e){loaded=false;const note=document.createElement('p');note.textContent=e.message;branch.replaceChildren(note)}finally{button.disabled=false}}};if(expanded.has(id))await button.onclick();
 }}await populate(tree,initial.rows.map(r=>r[0]),[]);
}

const api={resolveAsync,orderedValues,hierarchyFields,hierarchyFilter,hierarchyPlan,hierarchySlicer,singleValuePlan,singleValueSlicer,isFilterVisual,filtersFor,slicerSettings,categoricalFilter,selectedValues,slicerImagePlan,buttonSlicerStyle,categoricalSlicer,closePopup,field,column,selected,selectionLabel,resolve,rangeFilter,mode};if(typeof module!=='undefined')module.exports=api;root.ReportControls=api;
})(typeof globalThis!=='undefined'?globalThis:this);
