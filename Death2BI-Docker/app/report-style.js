/* Resolve Power BI presentation properties without executing imported code. */
(function(root){
const fallback=['#118DFF','#12239E','#E66C37','#6B007B','#E044A7','#744EC2','#D9B300','#D64550','#197278','#1AAB40'];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=(v,min,max,otherwise)=>Number.isFinite(Number(v))?Math.max(min,Math.min(max,Number(v))):otherwise;
function literal(x){if(typeof x!=='string')return x;if(x==='true'||x==='false')return x==='true';if(x==='null')return null;if(/^[-+]?\d+(?:\.\d+)?[dDlLmM]?$/.test(x))return Number(x.replace(/[dDlLmM]$/,''));return x.replace(/^'|'$/g,'').replaceAll("''", "'")}
function value(x,theme={},datum={}){
 if(x==null||typeof x!=='object')return x;
 if(x.expr)return value(x.expr,theme,datum);
 // Presentation expressions may reference a rendered series rather than a
 // model column. Exact materialized bindings also retain an explicit BLANK.
 if(datum.__formatExpressions?.has(JSON.stringify(x)))return datum.__formatExpressions.get(JSON.stringify(x));
 if(x.Literal)return literal(x.Literal.Value);
 if(x.solid)return value(x.solid.color,theme,datum);
 // Palette neutral swatches are white/black; named structural colors such as
 // foreground/background are independent and may be inverted by dark themes.
 if(x.ThemeDataColor){const t=x.ThemeDataColor,p=theme.dataColors?.length?theme.dataColors:fallback;let c=t.ColorId===0?'#FFFFFF':t.ColorId===1?'#000000':p[(((t.ColorId-2)%p.length)+p.length)%p.length];const pct=Number(t.Percent)||0;if(/^#[0-9a-f]{6}$/i.test(c)&&pct){const rgb=c.slice(1).match(/../g).map(n=>parseInt(n,16));c='#'+rgb.map(n=>Math.round(pct>0?n+(255-n)*Math.min(1,pct):n*(1+Math.max(-1,pct))).toString(16).padStart(2,'0')).join('')}return c}
 if(x.Measure||x.Column||x.Aggregation){const n=x.Measure||x.Column||x.Aggregation?.Expression?.Column;return datum[n?.Property]??datum[(n?.Expression?.SourceRef?.Entity||'')+'.'+n?.Property]}
 if(x.Comparison){const q=x.Comparison,a=value(q.Left,theme,datum),b=value(q.Right,theme,datum);if((q.Left?.RangePercent||q.Left?.ScopedEval)&&a==null||(q.Right?.RangePercent||q.Right?.ScopedEval)&&b==null)return false;const equal=typeof a==='string'&&typeof b==='string'?a.toLowerCase()===b.toLowerCase():a===b;return ({0:()=>equal,1:()=>a>b,2:()=>a>=b,3:()=>a<b,4:()=>a<=b,5:()=>!equal}[q.ComparisonKind]||(()=>false))()}
 if(x.And)return !!value(x.And.Left,theme,datum)&&!!value(x.And.Right,theme,datum);
 if(x.Or)return !!value(x.Or.Left,theme,datum)||!!value(x.Or.Right,theme,datum);
 if(x.Not)return !value(x.Not.Expression,theme,datum);
 if(x.RangePercent){const r=x.RangePercent,low=value(r.Min,theme,datum),high=value(r.Max,theme,datum),percent=value(r.Percent,theme,datum);return [low,high,percent].every(Number.isFinite)?low+(high-low)*percent:undefined}
 if(x.FillRule){const input=value(x.FillRule.Input,theme,datum),prepared=datum.__formatGradients?.get(x.FillRule);if(prepared)return prepared(input);const rows=datum.__formatRows||[datum];return gradientColor(x.FillRule,input,rows.map(row=>value(x.FillRule.Input,theme,row)),theme)}
 if(x.Conditional){for(const c of x.Conditional.Cases||[])if(value(c.Condition,theme,datum))return value(c.Value,theme,datum);return value(x.Conditional.Else,theme,datum)}
 return undefined;
}
function color(x,theme={},datum){let c=value(x,theme,datum);const seen=new Set();while(typeof c==='string'&&Object.hasOwn(theme,c)&&!seen.has(c)){seen.add(c);c=value(theme[c],theme,datum)}return typeof c==='string'&&(/^(#[\da-f]{3,8}|rgba?\([\d.,%\s]+\)|hsla?\([\d.,%\s]+\)|transparent|black|white|red|green|blue|yellow|gray|grey|orange|purple)$/i.test(c))?c:undefined}
function url(x,model){
 if(x?.expr)return url(x.expr,model);
 if(x?.ResourcePackageItem){const r=x.ResourcePackageItem;return model.assets?.[r.ItemName]||Object.entries(model.assets||{}).find(([k])=>k.endsWith('/'+r.ItemName))?.[1]}
 let v=value(x,model.theme);if(typeof v!=='string')return null;
 if(/^data:image\/(png|jpeg|gif|webp|avif|bmp);base64,[a-z\d+/=]+$/i.test(v))return v;
 if(/^data:image\/svg\+xml(?:;[^,]*)?,/i.test(v)){
  const comma=v.indexOf(','),header=v.slice(0,comma+1),body=v.slice(comma+1);
  if(/;base64,/i.test(header))return v;
  // Raw SVG measures frequently contain color hashes, which URL parsers treat as fragments.
  const raw=body.includes('<')?body.replace(/(?:%[\da-f]{2})+/gi,part=>{try{return decodeURIComponent(part)}catch{return part}}):null;
  return header+(raw!==null?encodeURIComponent(raw):body.replaceAll('#','%23'));
 }
 try{const u=new URL(v);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null}catch{return null}
}
function entries(source,key){return Array.isArray(source?.[key])?source[key]:[]}
function props(source,key){return Object.assign({},...entries(source,key).filter(e=>(!e.selector||e.selector.id==='default')&&(!e.$id||e.$id==='default')).map(e=>e.properties||Object.fromEntries(Object.entries(e).filter(([k])=>k!=='$id'))))}
function combine(a,b){const out={...a};for(const [k,v] of Object.entries(b||{}))out[k]=Array.isArray(v)?[...(out[k]||[]),...v]:v;return out}
function objects(model,v){const theme=model.theme||{},styles=theme.visualStyles||{},type=v.originalType||v.type||v.definition?.visualType,all=styles['*']||{},specific=styles[type]||{},preset=value(props(v.definition?.visualContainerObjects,'stylePreset').name,theme)||value(props(v.definition?.objects,'stylePreset').name,theme)||value(props(v.definition?.objects,'general').style,theme)||value(props(specific['*'],'stylePreset').name,theme)||value(props(all['*'],'stylePreset').name,theme)||'*';let out={};for(const part of [all['*'],preset!=='*'&&all[preset],specific['*'],preset!=='*'&&specific[preset],v.definition?.objects,v.definition?.visualContainerObjects])out=combine(out,part);return out}
// Resolve without mutating source definitions. Omitted, null and false remain distinct.
function resolveProperties(model,v,name,{datum={},state='default',inheritDefault=true}={}){
 const theme=model.theme||{},styles=theme.visualStyles||{},all=styles['*']||{},specific=styles[v.originalType||v.type]||{};
 const preset=value(props(v.definition?.visualContainerObjects,'stylePreset').name,theme)??value(props(v.definition?.objects,'stylePreset').name,theme)??value(props(v.definition?.objects,'general').style,theme)??value(props(specific['*'],'stylePreset').name,theme)??'*';
 const result={},sources={};
 for(const [source,part] of [['theme-global',all['*']],['theme-global-preset',all[preset]],['theme-visual',specific['*']],['theme-visual-preset',specific[preset]],['visual',v.definition?.objects],['container',v.definition?.visualContainerObjects]]){
  if(source.endsWith('preset')&&preset==='*')continue;
  const list=entries(part,name).filter(e=>{const id=e.selector?.id??e.$id;return (!id||id==='default'&&(inheritDefault||state==='default')||id===state)&&(!e.selector?.data&&!e.selector?.metadata||selectorMatches(e.selector,datum))});
  list.sort((a,b)=>{const rank=e=>((e.selector?.id??e.$id)===state&&(state!=='default'||!inheritDefault)?4:0)+(e.selector?.metadata?2:e.selector?.data?1:0);return rank(a)-rank(b)});
  for(const e of list)for(const [key,x] of Object.entries(e.properties||Object.fromEntries(Object.entries(e).filter(([k])=>!['$id','selector'].includes(k))))){result[key]=x;sources[key]=source}
 }
 return {properties:result,sources};
}
function resolveProperty(model,v,name,key,options={}){const r=resolveProperties(model,v,name,options);return Object.hasOwn(r.properties,key)?{value:value(r.properties[key],model.theme,options.datum),raw:r.properties[key],source:r.sources[key]}:{value:options.fallback,source:options.fallback===undefined?'omitted':'fallback'}}
function bookmarkScope(bookmark){return bookmark.options?.applyOnlyToTargetVisuals===true?bookmark.options.targetVisualNames||[]:[]}
function bookmarkPlan(model,bookmark,{activePageId,allowHidden=false}={}){
 const state=bookmark.explorationState,options=bookmark.options||{},scope=bookmarkScope(bookmark);if(!state)return null;
 const active=model.pages.find(p=>p.id===state.activeSection);if(!options.suppressActiveSection&&(!active||active.hidden&&!allowHidden))return null;
 const pages=model.pages.map(p=>structuredClone(p)),resetSlicers=[],clearPages=[];
 if(!(options.applyOnlyToTargetVisuals===true&&!scope.length))for(const page of pages){
  if(page.hidden&&!allowHidden)continue;
  const section=state.sections?.[page.id];
  if(!options.suppressData&&!scope.length&&state.filters?.byExpr)page.reportFilters=state.filters.byExpr.filter(f=>f.filter);
  if(!section)continue;
  if(!options.suppressData){
   if(!scope.length&&section.filters?.byExpr)page.filters=section.filters.byExpr.filter(f=>f.filter);
   for(const v of page.visuals){if(scope.length&&!scope.includes(v.id)&&!(v.groupChain||[]).some(id=>scope.includes(id)))continue;const saved=section.visualContainers?.[v.id];if(!saved)continue;
    if(saved.filters?.byExpr)v.filters=saved.filters.byExpr.filter(f=>f.filter);
    const visual=saved.singleVisual;if(visual?.orderBy?.length&&v.definition?.query)v.definition.query.sortDefinition={sort:visual.orderBy.map(s=>({field:s.Expression,direction:s.Direction===2?'Descending':'Ascending'}))};
    if(visual?.objects?.merge)v.definition.objects={...v.definition.objects,...visual.objects.merge};
    if(visual)for(const [role,fields] of Object.entries(visual.projections||visual.activeProjections||{})){const slot=v.definition?.query?.queryState?.[role];if(slot){const prior=slot.projections||[];slot.projections=fields.map(field=>({...prior.find(p=>JSON.stringify(p.field)===JSON.stringify(field)),field,nativeQueryRef:prior.find(p=>JSON.stringify(p.field)===JSON.stringify(field))?.nativeQueryRef||field.Measure?.Property||field.Column?.Property||field.Aggregation?.Expression?.Column?.Property,active:true}))}}
    resetSlicers.push({pageId:page.id,visualId:v.id});
   }
   if(!scope.length)clearPages.push(page.id);
  }
  if(!options.suppressDisplay)applyBookmarkDisplay(page,section,scope);
  page.activeBookmark=bookmark.name;
 }
 return {pages,targetPageId:options.suppressActiveSection?activePageId:state.activeSection,resetSlicers,clearPages};
}
function px(x,theme,base=10){const n=value(x,theme);return Number.isFinite(Number(n))?finite(n,1,200,base)*4/3:base}
function opacity(n){return 1-finite(n,0,100,0)/100}
function paint(c,transparency){if(!c)return 'transparent';const n=opacity(transparency);if(/^#[\da-f]{6}$/i.test(c))return c+Math.round(n*255).toString(16).padStart(2,'0');return c}
// Canvas image scaling Fit is the legacy serialized Stretch mode.
function backgroundSize(mode){const fit=String(mode||'').toLowerCase();return /^(fit|stretch)$/.test(fit)?'100% 100%':/contain|uniform/.test(fit)?'contain':/normal/.test(fit)?'auto':'cover'}
function imageBackground(el,properties,model){
 el.querySelector(':scope > .pbi-background-image')?.remove();el.style.backgroundImage='none';
 const source=properties.image||properties.imageUrl||properties.url,u=url(source?.image?.url||source?.url||source,model);if(!u)return;
 const image=document.createElement('div');image.className='pbi-background-image';image.setAttribute('aria-hidden','true');image.style.cssText='position:absolute;inset:0;pointer-events:none;z-index:-1';
 image.style.backgroundImage='url('+JSON.stringify(u)+')';const fit=value(properties.imageFit||properties.scaling||source?.image?.scaling,model.theme);image.style.backgroundSize=backgroundSize(fit);image.style.backgroundPosition='center';image.style.backgroundRepeat='no-repeat';image.style.opacity=String(opacity(value(properties.transparency,model.theme)));el.style.position='relative';el.style.isolation='isolate';el.prepend(image);
}
function pageStyle(canvas,workspace,model,page){const theme=model.theme||{},p=page.objects||{},pageTheme=objects(model,{type:'page',definition:{objects:p}}),base=props(model.reportObjects,'background'),background={...props(pageTheme,'background'),...base,...props(p,'background')},out={...props(pageTheme,'outspace'),...props(model.reportObjects,'outspace'),...props(p,'outspace'),...props(p,'wallpaper')};canvas.style.background=paint(color(background.color||background.fill,theme)||theme.background||'#ffffff',value(background.transparency,theme));canvas.style.border='none';canvas.style.boxShadow='none';imageBackground(canvas,background,model);workspace.style.background=paint(color(out.color,theme)||'#f2f4f0',value(out.transparency,theme));imageBackground(workspace,out,model)}
function container(el,model,v){const theme=model.theme||{},o=objects(model,v),bg=props(o,'background'),border=props(o,'border'),pad=props(o,'padding'),shadow=props(o,'dropShadow');el.classList.add('pbi-visual');el.style.zIndex=String(v.layerOrder??v.z??0);el.style.background=value(bg.show,theme)===false?'transparent':paint(color(bg.color,theme)||(value(bg.show,theme)===true?(theme.background||'#FFFFFF'):undefined),value(bg.transparency,theme));el.style.border=value(border.show,theme)?finite(value(border.width,theme),0,12,1)+'px '+(/dash/i.test(value(border.style,theme)||'')?'dashed':'solid')+' '+(color(border.color,theme)||theme.foreground||'#888'):'none';el.style.borderRadius=finite(value(border.radius,theme),0,100,0)+'px';el.style.padding=['top','right','bottom','left'].map(k=>finite(value(pad[k],theme),0,100,0)+'px').join(' ');if(value(shadow.show,theme))el.style.boxShadow='0 3px 8px '+(color(shadow.color,theme)||'#00000033');return o}
function titleVisible(model,v){const show=value(props(objects(model,v),'title').show,model.theme);return ['card','cardVisual','multiRowCard'].includes(v.type)?show===true:show!==false}
function authoredTitle(model,v){const p=props(objects(model,v),'title');return titleVisible(model,v)?value(p.text,model.theme)||'':''}
function styleTitle(el,model,v){
 const o=objects(model,v),theme=model.theme||{},title=props(o,'title'),subtitle=props(o,'subTitle');
 let heading=el.querySelector(':scope > h3');
 for(const [key,p,tag,existing] of [['title',title,'h3',heading],['subTitle',subtitle,'div',el.querySelector(':scope > .pbi-subtitle')]]){
  const content=v._captionValues&&Object.hasOwn(v._captionValues,key)?v._captionValues[key]:value(p.text,theme);
  if(key==='title'&&!titleVisible(model,v)||value(p.show,theme)===false||key==='subTitle'&&(content==null||content==='')){existing?.remove();if(key==='title')heading=null;continue}
  if(!existing&&(content==null||content===''))continue;
  const node=existing||document.createElement(tag);node.className=key==='subTitle'?'pbi-subtitle':'pbi-title';
  if(content!=null)node.textContent=String(content);
  const textClass=theme.textClasses?.[key==='title'?'title':'label']||{};
  node.style.background=color(p.background||(key==='subTitle'?title.background:null),theme)||'transparent';node.style.color=color(p.fontColor||p.color,theme)||textClass.color||theme.foreground||'#222';node.style.fontSize=px(p.fontSize??textClass.fontSize,theme,key==='title'?12:10)+'px';node.style.fontFamily=value(p.fontFamily,theme)||textClass.fontFace||'Segoe UI, sans-serif';node.style.fontWeight=value(p.bold,theme)?'700':'normal';node.style.fontStyle=value(p.italic,theme)?'italic':'normal';node.style.textDecoration=value(p.underline,theme)?'underline':'none';node.style.textAlign=value(p.alignment,theme)||'left';node.style.margin=color(title.background,theme)?'0':'0 0 4px';node.style.flexShrink='0';node.style.lineHeight='1.25';node.style.whiteSpace=value(p.titleWrap??p.wordWrap,theme)===false?'pre':'pre-wrap';node.style.overflowWrap='anywhere';node.style.position='relative';node.style.zIndex='1';
  if(key==='title'){if(!existing)el.prepend(node);heading=node}else if(!existing){if(heading)heading.after(node);else el.prepend(node)}
 }
}
function slicerHeadingPlan(model,v,label){const o=objects(model,v),theme=model.theme||{},head=props(o,'header');return {show:value(head.show,theme)??!(v.originalType==='advancedSlicerVisual'||v.type==='advancedSlicerVisual'||v.definition?.visualType==='advancedSlicerVisual'),text:value(head.text,theme)??label,fontFamily:value(head.fontFamily,theme)||theme.textClasses?.header?.fontFace||'Segoe UI',fontSize:px(head.textSize??head.fontSize,theme,10),color:color(head.fontColor??head.color,theme)||theme.foreground||'#222',background:color(head.background,theme)||'transparent',bold:value(head.bold,theme),alignment:value(head.alignment,theme)||'left'}}
function styleSlicerHeadings(el,model,v,label){
 const old=el.querySelector(':scope > h3');if(old&&!old.classList.contains('pbi-title'))old.remove();
 const p=slicerHeadingPlan(model,v,label);let header=el.querySelector(':scope > .pbi-slicer-header');
 if(!p.show)header?.remove();else{if(!header){header=document.createElement('div');header.className='pbi-slicer-header';el.prepend(header)}header.textContent=String(p.text??'');header.style.fontFamily=p.fontFamily;header.style.fontSize=p.fontSize+'px';header.style.color=p.color;header.style.background=p.background;header.style.textAlign=p.alignment;header.style.fontWeight=p.bold===true?'bold':p.bold===false?'normal':'600';header.style.flexShrink='0';header.style.margin='0 0 4px';header.style.lineHeight='1.25'}
 styleTitle(el,model,v);
}
function action(model,v){const o=objects(model,v),a={...props(o,'action'),...props(o,'visualLink')},theme=model.theme||{};if(value(a.show,theme)===false)return null;let type=String(value(a.type||a.actionType,theme)||'');if(/page|navigation/i.test(type))return {type:'page',target:value(a.navigationSection||a.page||a.destination||a.pageName,theme)};if(/back/i.test(type))return {type:'back'};if(/web|url/i.test(type))return {type:'url',target:url(a.webUrl||a.url,model)};if(/bookmark/i.test(type))return {type:'bookmark',target:value(a.bookmark,theme)};return null}
function tooltipPage(model,v){const o=objects(model,v),p={...props(o,'tooltip'),...props(o,'visualTooltip')};if(value(p.show,model.theme)===false)return;return value(p.section||p.page||p.pageName||p.tooltipPage,model.theme)}
function shapeMarkup(model,v){const o=objects(model,v),theme=model.theme||{},shape=props(o,'shape'),fill=props(o,'fill'),line=props(o,'outline');const name=String(value(shape.tileShape||shape.shapeType,theme)||'rectangle').toLowerCase(),paths={triangle:'M50 2L98 98H2Z',diamond:'M50 1L99 50L50 99L1 50Z',pentagon:'M50 1L98 37L80 98H20L2 37Z',hexagon:'M25 2H75L99 50L75 98H25L1 50Z',parallelogram:'M25 2H99L75 98H1Z',trapezoid:'M25 2H75L99 98H1Z',rightarrow:'M1 25H65V2L99 50L65 98V75H1Z',leftarrow:'M99 25H35V2L1 50L35 98V75H99Z',uparrow:'M25 99V35H2L50 1L98 35H75V99Z',downarrow:'M25 1V65H2L50 99L98 65H75V1Z',chevron:'M1 2H65L99 50L65 98H1L35 50Z',heart:'M50 95C-20 50 0-15 50 20C100-15 120 50 50 95Z',star5:'M50 1L62 36H99L70 59L81 96L50 74L19 96L30 59L1 36H38Z'};let body;
 if(/rectangle|square|round/.test(name))body='<rect x="1" y="1" width="98" height="98" rx="'+(/round/.test(name)?finite(value(shape.rectangleRoundedCurve,theme),0,49,8):0)+'" ry="'+(/round/.test(name)?finite(value(shape.rectangleRoundedCurve,theme),0,49,8)*(v.width||100)/(v.height||100):0)+'"/>';
 else if(/ellipse|oval|circle/.test(name))body='<ellipse cx="50" cy="50" rx="49" ry="49"/>';
 else if(/line/.test(name))body='<path d="M1 50H99" fill="none"/>';
 else if(paths[name])body='<path d="'+paths[name]+'"/>';
 else return null;
 const stroke=value(line.show,theme)===false?'none':color(line.lineColor||line.color,theme)||'none',fc=value(fill.show,theme)===false?'none':color(fill.fillColor||fill.color,theme)||theme.tableAccent||'#118DFF';
 return '<svg class="pbi-shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" style="width:100%;height:100%;display:block;overflow:visible"><g transform="rotate('+finite(value(props(o,'rotation').shapeAngle,theme),-360,360,0)+' 50 50)" fill="'+esc(fc)+'" fill-opacity="'+opacity(value(fill.transparency,theme))+'" stroke="'+esc(stroke)+'" stroke-opacity="'+opacity(value(line.transparency,theme))+'" stroke-width="'+finite(value(line.weight||line.width,theme),0,30,1)+'" vector-effect="non-scaling-stroke">'+body.replace(/<(rect|ellipse|path)/g,'<$1 vector-effect="non-scaling-stroke"')+'</g></svg>';
}
function layoutTextIcons(canvas,page){
 const texts=[...canvas.querySelectorAll('.pbi-richtext')],used=new Set();
 for(const [index,v] of (page.visuals||[]).entries()){
  if(v.hidden||!['image','actionButton'].includes(v.type)||v.width<8||v.height<8||v.width>64||v.height>64)continue;
  const original=canvas.querySelector('#visual'+index),source=original?.querySelector('img');if(!source)continue;
  const box=original.getBoundingClientRect(),scale=box.width/v.width,cx=box.x+box.width/2,cy=box.y+box.height/2;
  let best=null,score=Infinity;
  for(const text of texts){const bounds=text.parentElement.getBoundingClientRect();if(cx<bounds.left||cx>bounds.right||cy<bounds.top||cy>bounds.bottom)continue;
   for(const slot of text.querySelectorAll('[data-pbi-space]')){if(used.has(slot))continue;const r=slot.getBoundingClientRect(),dx=Math.abs(cx-r.x-r.width/2),dy=Math.abs(cy-r.y-r.height/2);
    if(dx>Math.max(40*scale,box.width*1.5)||dy>box.height*1.3)continue;
    const distance=dx+dy*2;if(distance<score){best=slot;score=distance}
   }
  }
  if(!best)continue;used.add(best);const width=best.getBoundingClientRect().width/scale,icon=source.cloneNode(false);
  best.textContent='';best.style.cssText='display:inline-block;vertical-align:-.15em;height:1.1em;width:'+Math.max(8,width)+'px;line-height:1';icon.style.cssText='display:block;width:100%;height:100%;object-fit:contain';best.appendChild(icon);
  if(original.classList.contains('pbi-action')){best.setAttribute('role','button');best.tabIndex=0;best.setAttribute('aria-label',original.getAttribute('aria-label')||'Report navigation');best.style.cursor='pointer';best.onclick=event=>{event.preventDefault();event.stopPropagation();original.click()};best.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();original.click()}}}
  original.style.visibility='hidden';original.setAttribute('aria-hidden','true');original.tabIndex=-1;
 }
}
function textboxMarkup(model,v){
 const o=objects(model,v),theme=model.theme||{},paragraphs=props(o,'general').paragraphs||[];
 if(!paragraphs.length)return null;
 const size=(x,fallback)=>/^\d+(?:\.\d+)?(?:pt|px)$/.test(String(x||''))?String(x):fallback;
 let result='',list='';
 for(const p of paragraphs){
  const first=(p.textRuns||[]).find(r=>String(r.value||'').trim())?.textStyle||{};
  const base=size(p.textStyle?.fontSize||first.fontSize,finite(theme.textClasses?.label?.fontSize,1,200,10)+'pt');
  const align=['left','right','center','justify'].includes(p.horizontalTextAlignment)?p.horizontalTextAlignment:'left';
  const kind=/bullet/i.test(p.listType||'')?'ul':/number|decimal|ordered/i.test(p.listType||'')?'ol':'';
  if(kind!==list){if(list)result+='</'+list+'>';if(kind)result+='<'+kind+' style="margin:0;padding:0 0 0 20px;list-style-position:outside">';list=kind}
  const tag=kind?'li':'p',level=finite(p.listLevel??p.level??0,0,8,0);
  const spacing=n=>finite(Number.parseFloat(n),0,200,0);
  result+='<'+tag+' style="margin:'+spacing(p.spaceBefore||p.spacingBefore)+'px 0 '+spacing(p.spaceAfter||p.spacingAfter)+'px '+(level*16)+'px;padding:0;font-size:'+base+';font-family:'+esc(first.fontFamily||theme.textClasses?.label?.fontFace||'Segoe UI, sans-serif')+';line-height:1.15;text-align:'+align+';color:'+esc(color(first.color,theme)||theme.foreground||'#222')+';white-space:pre-wrap;overflow-wrap:break-word;tab-size:4">';
  result+=(p.textRuns||[]).map(r=>{
   const t=r.textStyle||{},fontSize=size(t.fontSize,base),weight=/^(normal|bold|[1-9]00)$/.test(String(t.fontWeight))?t.fontWeight:(/bold/i.test(t.fontFamily||'')?'700':'normal');
   const style='font-family:'+esc(t.fontFamily||first.fontFamily||'Segoe UI, sans-serif')+';font-size:'+fontSize+';color:'+esc(color(t.color,theme)||color(first.color,theme)||theme.foreground||'#222')+';font-weight:'+weight+';font-style:'+(t.fontStyle==='italic'?'italic':'normal')+';text-decoration:'+(t.textDecoration==='underline'?'underline':'none');
   let content=String(r.value??'').split(/( {2,}|\t+)/).map(part=>/^( {2,}|\t+)$/.test(part)?'<span data-pbi-space>'+esc(part)+'</span>':esc(part)).join('');if(r.url){try{const link=new URL(r.url);if(['http:','https:','mailto:'].includes(link.protocol)&&!link.username&&!link.password)content='<a href="'+esc(link.href)+'" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:inherit">'+content+'</a>'}catch{}}
   return '<span style="'+style+'">'+content+'</span>';
  }).join('')||'<br>';
  result+='</'+tag+'>';
 }
 if(list)result+='</'+list+'>';
 return '<div class="pbi-richtext" style="line-height:1.15">'+result+'</div>';
}
function hasCaptionContent(model,v){const o=objects(model,v);return ['title','subTitle'].some(key=>{const p=props(o,key);if(key==='title'&&!titleVisible(model,v)||value(p.show,model.theme)===false)return false;const text=v._captionValues&&Object.hasOwn(v._captionValues,key)?v._captionValues[key]:value(p.text,model.theme);return text!=null&&String(text).trim()!==''})}
function hasVisibleDecoration(model,v){
 const theme=model.theme||{},authored=(resolved,keys)=>keys.some(key=>['visual','container'].includes(resolved.sources[key]));
 const visible=c=>{if(typeof c!=='string'||!c||c.toLowerCase()==='transparent')return false;if(/^#[\da-f]{4}$/i.test(c))return c.slice(-1)!=='0';if(/^#[\da-f]{8}$/i.test(c))return c.slice(-2)!=='00';if(/^(rgba|hsla)\(/i.test(c)&&c.split(',').length===4)return Number.parseFloat(c.slice(c.lastIndexOf(',')+1))>0;return true};
 const background=resolveProperties(model,v,'background'),bg=background.properties,bgColor=color(bg.color,theme)||(value(bg.show,theme)===true?theme.background||'#FFFFFF':undefined);
 if(authored(background,['show','color','transparency'])&&value(bg.show,theme)!==false&&opacity(value(bg.transparency,theme))>0&&visible(bgColor))return true;
 const border=resolveProperties(model,v,'border'),b=border.properties;
 if(authored(border,['show','width','color'])&&value(b.show,theme)===true&&finite(value(b.width,theme),0,12,1)>0&&visible(color(b.color,theme)||theme.foreground||'#888'))return true;
 const shadow=resolveProperties(model,v,'dropShadow'),s=shadow.properties;
 return authored(shadow,['show','color','transparency'])&&value(s.show,theme)===true&&opacity(value(s.transparency,theme))>0&&visible(color(s.color,theme)||'#00000033');
}
function shapeTextMarkup(model,v){
 const theme=model.theme||{},o=objects(model,v),p=props(o,'text');if(value(p.show,theme)===false)return '';const text=v._captionValues&&Object.hasOwn(v._captionValues,'shapeText')?v._captionValues.shapeText:value(p.text,theme);if(text==null||text==='')return '';
 const horizontal=String(value(p.horizontalAlignment,theme)||'center').toLowerCase(),vertical=String(value(p.verticalAlignment,theme)||'middle').toLowerCase(),align={left:'flex-start',center:'center',right:'flex-end'}[horizontal]||'center',justify={top:'flex-start',middle:'center',center:'center',bottom:'flex-end'}[vertical]||'center';
 return '<div class="pbi-shape-text" style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:'+justify+';align-items:'+align+';padding:6px;overflow:hidden;pointer-events:none;box-sizing:border-box"><div style="max-width:100%;min-width:0;white-space:'+(value(p.textWrap??p.wordWrap,theme)===false?'nowrap':'pre-wrap')+';overflow-wrap:anywhere;overflow:hidden;text-align:'+(/^(left|center|right)$/.test(horizontal)?horizontal:'center')+';font-family:'+esc(value(p.fontFamily,theme)||theme.textClasses?.label?.fontFace||'Segoe UI')+';font-size:'+px(p.fontSize,theme,12)+'px;color:'+esc(color(p.fontColor??p.color,theme)||theme.foreground||'#222')+';font-weight:'+(value(p.bold,theme)?'700':'normal')+';font-style:'+(value(p.italic,theme)?'italic':'normal')+';text-decoration:'+(value(p.underline,theme)?'underline':'none')+';line-height:1.2">'+esc(text)+'</div></div>';
}
function navigatorPages(model,v,allowHidden=false){
 const o=objects(model,v),theme=model.theme||{},defaults=props(o,'pages');
 return (model.pages||[]).filter(page=>{
  const overrides=Object.assign({},...entries(o,'pages').filter(e=>e.selector?.id===page.id).map(e=>e.properties||{})),explicit=value(overrides.showPage,theme);
  if(page.hidden&&!allowHidden)return false;
  if(explicit!==undefined)return explicit===true;
  if(value(defaults.showByDefault,theme)===false)return false;
  if((page.isTooltip||page.tooltip||String(page.pageType).toLowerCase()==='tooltip')&&value(defaults.showTooltipPages,theme)!==true)return false;
  return !page.hidden||value(defaults.showHiddenPages,theme)===true;
 });
}
function navigatorBookmarks(model,v){
 const group=value(props(objects(model,v),'bookmarks').bookmarkGroup,model.theme||{}),all=model.bookmarks||[];
 if(!group)return all;
 const groups=new Map((model.bookmarkGroups||[]).map(g=>[g.name,g])),bookmarks=new Map(all.map(b=>[b.name,b])),result=[],seen=new Set();
 function visit(id){if(seen.has(id))return;seen.add(id);if(groups.has(id)){for(const child of groups.get(id).children||[])visit(typeof child==='string'?child:child.name)}else if(bookmarks.has(id))result.push(bookmarks.get(id))}
 visit(group);return result;
}
const imageControllers=new WeakMap();
function imagePlan(model,v,state='default'){
 // All is the common base. Default is a sibling of Hover and Press, not their base.
 const options={state,inheritDefault:false},p={...resolveProperties(model,v,'general',options).properties,...resolveProperties(model,v,'image',options).properties},theme=model.theme||{},source=url(p.imageUrl||p.sourceUrl||p.source||p.url||p.sourceFile?.image?.url,model)||null,fit=String(value(p.imageFit||p.fit,theme)||'').trim().toLowerCase();
 return {source,alt:value(p.altText,theme)||value(props(objects(model,v),'altText').text,theme)||'Report image',opacity:opacity(value(p.transparency,theme)),objectFit:v.navigationIcon?'contain':({fill:'cover',stretch:'fill',fit:'contain',center:'none',normal:'none'}[fit]||'contain')};
}
function bindImageStates(el,model,v,img){
 if(typeof el.addEventListener!=='function')return;
 const interactive=[v.definition?.objects,v.definition?.visualContainerObjects].some(source=>['general','image'].some(name=>entries(source,name).some(entry=>['hover','press'].includes(entry.selector?.id??entry.$id)))),originalPointerEvents=el.style.pointerEvents,originalTabIndex=el.tabIndex,listeners=[],document=el.ownerDocument;
 // Decorative visual layers normally allow clicks through to charts underneath.
 // Authored image states require their own hit area even when Default is invisible.
 if(interactive)el.style.pointerEvents='auto';
 let hover=interactive&&el.matches?.(':hover')===true,keyboardFocus=false,pointer=null,key=null,watching=false;
 const read=()=>imagePlan(model,v,pointer!==null||key!==null?'press':hover||keyboardFocus?'hover':'default');
 function paint(){const plan=read();img.hidden=!plan.source;if(plan.source){if(img.getAttribute('src')!==plan.source)img.setAttribute('src',plan.source)}else img.removeAttribute('src');img.alt=plan.alt;img.style.opacity=String(plan.opacity);img.style.objectFit=plan.objectFit;img.style.objectPosition='center';img.dataset.pbiImageState=pointer!==null||key!==null?'press':hover||keyboardFocus?'hover':'default'}
 function unwatch(){if(!watching)return;document.removeEventListener('pointerup',release,true);document.removeEventListener('pointercancel',cancel,true);watching=false}
 function release(event){if(pointer===null||event.pointerId!==undefined&&event.pointerId!==pointer)return;pointer=null;unwatch();if(!el.contains(event.target))hover=false;paint()}
 function cancel(){pointer=null;key=null;hover=false;unwatch();paint()}
 function listen(name,fn){el.addEventListener(name,fn);listeners.push([name,fn])}
 listen('pointerenter',event=>{if(event.pointerType!=='touch')hover=true;paint()});
 listen('pointerleave',()=>{pointer=null;hover=false;unwatch();paint()});
 listen('pointerdown',event=>{if(event.isPrimary===false||event.button!==undefined&&event.button!==0)return;pointer=event.pointerId??0;keyboardFocus=false;if(document?.addEventListener&&!watching){document.addEventListener('pointerup',release,true);document.addEventListener('pointercancel',cancel,true);watching=true}paint()});
 listen('pointerup',release);listen('pointercancel',cancel);listen('lostpointercapture',cancel);
 listen('focus',()=>{keyboardFocus=pointer===null;paint()});listen('blur',()=>{keyboardFocus=false;key=null;pointer=null;hover=false;unwatch();paint()});
 listen('keydown',event=>{if(!['Enter',' '].includes(event.key)||event.altKey||event.ctrlKey||event.metaKey)return;key=event.key;event.preventDefault();paint()});
 listen('keyup',event=>{if(event.key!==key)return;key=null;paint()});
 // Additive listeners leave the application's navigation/click handlers intact.
 if(interactive&&el.tabIndex<0)el.tabIndex=0;
 imageControllers.set(el,()=>{unwatch();for(const [name,fn] of listeners)el.removeEventListener(name,fn);if(interactive){el.style.pointerEvents=originalPointerEvents;el.tabIndex=originalTabIndex}});paint();
}
function staticVisual(el,model,v,options={}){const o=objects(model,v),theme=model.theme||{};
 if(v.type==='group')return false;
 if(v.type==='pageNavigator'||v.type==='bookmarkNavigator'){
  const text=props(o,'text'),fill=props(o,'fill'),layout=props(o,'layout'),items=v.type==='pageNavigator'?navigatorPages(model,v,options.allowHidden===true):navigatorBookmarks(model,v);
  const orientation=String(value(layout.orientation,theme)??'').trim().toLowerCase();
  el.style.display='flex';el.style.flexDirection=orientation==='1'||orientation==='vertical'?'column':'row';el.style.alignItems='stretch';el.style.gap=(Number(value(layout.cellPadding,theme))||0)+'px';el.style.padding='0';
  el.innerHTML=items.map(p=>'<button type="button" data-report-'+(v.type==='pageNavigator'?'page':'bookmark')+'="'+esc(p.id||p.name)+'" style="flex:1;min-width:0;min-height:0;border:0;border-radius:0;padding:4px;background:'+esc(value(fill.show,theme)===false?'transparent':color(fill.fillColor,theme)||'transparent')+';color:'+esc(color(text.fontColor,theme)||theme.foreground||'#222')+';font-family:'+esc(value(text.fontFamily,theme)||'Segoe UI')+';font-size:'+px(text.fontSize,theme,12)+'px">'+esc(p.displayName||p.name)+'</button>').join('');return !!items.length;
 }

 if(v.type==='shape'){const markup=shapeMarkup(model,v);if(!markup)return false;el.innerHTML=markup+shapeTextMarkup(model,v);return true}
 if(v.type==='image'){imageControllers.get(el)?.();imageControllers.delete(el);const plan=imagePlan(model,v);if(!plan.source&&!['hover','press'].some(state=>imagePlan(model,v,state).source))return false;
  el.innerHTML='<img alt="'+esc(plan.alt)+'" referrerpolicy="no-referrer" loading="eager" style="width:100%;height:100%;opacity:'+plan.opacity+';object-fit:'+plan.objectFit+';object-position:center"'+(plan.source?' src="'+esc(plan.source)+'"':' hidden')+'>';const img=el.querySelector('img');img.onerror=event=>{event.target.title='Image could not be loaded from its source URL.'};bindImageStates(el,model,v,img);return true}
 if(v.type==='textbox'){const hasBody=(props(o,'general').paragraphs||[]).some(p=>(p.textRuns||[]).some(r=>String(r.value??'').trim()!=='')),markup=hasBody?textboxMarkup(model,v):'';if(!markup&&!hasCaptionContent(model,v)&&!hasVisibleDecoration(model,v))return false;const padding=props(o,'padding');if(!['top','right','bottom','left'].some(k=>padding[k]!==undefined))el.style.padding='5px';el.innerHTML=markup||'';el.style.display='flex';el.style.flexDirection='column';el.style.justifyContent='flex-start';return true}
 if(v.type==='actionButton'){const p=props(o,'text'),icon=props(o,'icon'),a=action(model,v),text=value(p.show,theme)===false?'':v._captionValues&&Object.hasOwn(v._captionValues,'shapeText')?v._captionValues.shapeText:value(p.text,theme);const symbol={back:'←',leftArrow:'←',rightArrow:'→',home:'⌂',reset:'↻',information:'ⓘ',help:'?'}[value(icon.shapeType,theme)],image=url(icon.image?.image?.url||icon.image?.url,model);if(!text&&!symbol&&!image&&!a)return false;el.innerHTML='<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:'+px(p.fontSize,theme,14)+'px;color:'+esc(color(p.fontColor,theme)||'#222')+'">'+(image?'<img alt="" src="'+esc(image)+'" referrerpolicy="no-referrer" style="'+(v.navigationIcon?'width:100%;height:100%;':'')+'max-width:100%;max-height:100%;object-fit:contain">':'')+esc(text||symbol||'')+'</div>';const f=props(o,'fill');if(value(f.show,theme)!==false&&color(f.fillColor,theme))el.style.background=paint(color(f.fillColor,theme),value(f.transparency,theme));return true}

 return null;
}
function selectorMatches(selector,datum){if(!selector||selector.id==='default')return true;if(selector.id)return false;const wanted=[];function walk(x){if(!x||typeof x!=='object')return;if(x.Comparison){const c=x.Comparison;if(c.Right?.Literal)wanted.push(literal(c.Right.Literal.Value))}for(const [k,v] of Object.entries(x))if(k!=='Comparison')Array.isArray(v)?v.forEach(walk):walk(v)}walk(selector);if(selector.metadata&&selector.metadata!==datum._projectionRef)wanted.push(selector.metadata.replace(/^[A-Za-z]+\((.*)\)$/,'$1').split('.').pop());const roleMatch=selector.data?.some(s=>Array.isArray(s.roles)&&s.roles.length&&s.roles.every(role=>datum._roles?.includes(role)||role==='Category'&&Object.hasOwn(datum,'_categoryValue')&&datum._categoryValue!==undefined));return (wanted.length>0||selector.metadata===datum._projectionRef&&!!selector.metadata||selector.data?.some(s=>s.dataViewWildcard)||roleMatch)&&wanted.every(w=>[datum._sourceMeasure,datum._categoryValue,datum._dimension,datum._category,datum._series,...Object.values(datum._raw||{})].some(v=>String(v)===String(w)||String(v).endsWith(' · '+String(w))))}
function stableColor(key,theme,domain=[]){const palette=theme.dataColors?.length?theme.dataColors:fallback;let index=domain.map(String).indexOf(String(key));if(index<0){let hash=2166136261;for(const c of String(key)){hash^=c.charCodeAt(0);hash=Math.imul(hash,16777619)}index=hash>>>0}return palette[index%palette.length]}
function formatColor(model,v,datum,defaultColor,source){const o=source||objects(model,v),theme=model.theme||{};let result=(source?undefined:datum._pbiGradient)||color(props(o,'dataPoint').fill||props(o,'dataColors').defaultColor,theme,datum._raw||datum)||defaultColor;for(const entry of [...entries(o,'dataPoint'),...entries(o,'dataColors')])if(selectorMatches(entry.selector,datum)){const c=color(entry.properties?.fill||entry.properties?.defaultColor||entry.properties?.color,theme,datum._raw||datum);if(c)result=c}return result}
function seriesColorObjects(source,seriesProjection,categoryFields,values,theme){
 const series=seriesProjection?.field?.Column||seriesProjection?.field?.GroupRef;if(!series)return source;
 const same=(a,b)=>a&&b&&String(a.Property).toLowerCase()===String(b.Property).toLowerCase()&&String(a.Expression?.SourceRef?.Entity||'').toLowerCase()===String(b.Expression?.SourceRef?.Entity||'').toLowerCase();
 function targets(selector,fields,roles){let found=false;function walk(x){if(!x||typeof x!=='object')return;if(Array.isArray(x.roles)&&x.roles.some(role=>roles.includes(role))||fields.some(f=>same(x.Column||x.GroupRef,f)))found=true;for(const child of Object.values(x))if(child&&typeof child==='object')Array.isArray(child)?child.forEach(walk):walk(child)}walk(selector);return found}
 const all=[...entries(source,'dataPoint'),...entries(source,'dataColors')],seriesTarget=entry=>targets(entry.selector,[series],['Series','Legend','Columns'])||!!entry.selector?.metadata&&[seriesProjection.queryRef,seriesProjection.nativeQueryRef].filter(Boolean).includes(entry.selector.metadata),categoryTarget=entry=>targets(entry.selector,categoryFields,['Category','Rows','X','Location','Group']);
 const paintOf=entry=>entry.properties?.fill??entry.properties?.defaultColor??entry.properties?.color,categoryOwned=all.some(entry=>paintOf(entry)!==undefined&&!seriesTarget(entry)&&categoryTarget(entry));
 function applies(entry){
  if(seriesTarget(entry))return true;
  // A legend column owns dynamic-series colors. Legacy single-series defaults
  // and Category selectors may remain in a report after a Series is added;
  // applying those to every segment destroys its native palette assignment.
  if(categoryTarget(entry)||categoryOwned)return false;
  const paint=paintOf(entry);
  if(!/"(?:Conditional|Measure|Column|Aggregation|FillRule)"\s*:/.test(JSON.stringify(paint)||''))return false;
  // Retain existing field-value series colors when they define one color per
  // Series. Per-point colors need an explicit Series-bound selector instead.
  const colors=new Map();for(const d of values){const key=JSON.stringify(d._dimension),c=color(paint,theme,d._raw||d);if(colors.has(key)&&colors.get(key)!==c)return false;colors.set(key,c)}return true;
 }
 return {...source,dataPoint:entries(source,'dataPoint').filter(applies),dataColors:entries(source,'dataColors').filter(applies)};
}
function conditionalApplies(settings,theme,{isTotal=false,isSubtotal=false}={}){const option=value(settings.totalMatchingOption,theme);if(option===1&&(isTotal||isSubtotal)||option===2&&!isTotal&&!isSubtotal)return false;if(isTotal&&value(settings.applyToTotals,theme)===false||isSubtotal&&value(settings.applyToSubtotals,theme)===false)return false;return true}
function prepareGradientColor(rule,numbers,theme){
 const empty=()=>undefined,g=rule.FillRule?.linearGradient3||rule.FillRule?.linearGradient2;if(!g)return empty;
 const asZero=value(g.nullColoringStrategy?.strategy,theme)==='asZero';let minimum=Infinity,maximum=-Infinity;
 for(let n of numbers){if(n==null&&asZero)n=0;if(Number.isFinite(n)){minimum=Math.min(minimum,n);maximum=Math.max(maximum,n)}}if(minimum===Infinity)return empty;
 const low=value(g.min?.value,theme)??minimum,high=value(g.max?.value,theme)??maximum,mid=value(g.mid?.value,theme)??(low+high)/2;
 const stops=[[low,color(g.min?.color,theme)],...(g.mid?[[mid,color(g.mid.color,theme)]]:[]),[high,color(g.max?.color,theme)]];
 if(stops.some(s=>!Number.isFinite(s[0])||!/^#[\da-f]{6}$/i.test(s[1]||'')))return empty;
 stops.sort((a,b)=>a[0]-b[0]);const rgb=stops.map(stop=>stop[1].slice(1).match(/../g).map(n=>parseInt(n,16)));
 // Prepared only for the current render's immutable domain. Painting and local
 // sorting reuse these stops without rescanning all rows for each cell.
 return input=>{if(input==null&&asZero)input=0;if(!Number.isFinite(input))return;
  const upper=stops.findIndex(s=>s[0]>=input);if(upper<=0)return upper===0?stops[0][1]:stops.at(-1)[1];
  const a=stops[upper-1],b=stops[upper],t=b[0]===a[0]?0:(input-a[0])/(b[0]-a[0]);
  return '#'+rgb[upper-1].map((n,i)=>Math.round(n+(rgb[upper][i]-n)*t).toString(16).padStart(2,'0')).join('');
 };
}
function gradientColor(rule,input,numbers,theme){return prepareGradientColor(rule,numbers,theme)(input)}
function axisSource(model,v,secondary=false,datum={}){
 const read=name=>resolveProperties(model,v,name,{datum}).properties;
 if(!secondary)return read('valueAxis');
 const secondaryProperties=source=>Object.fromEntries(Object.entries(source).filter(([key])=>/^sec[A-Z]/.test(key)).map(([key,x])=>[key[3].toLowerCase()+key.slice(4),x]));
 const legacy=read('valueAxis'),classic=read('valueAxis2'),modern=read('y2Axis');
 return {...secondaryProperties(legacy),...classic,...secondaryProperties(classic),...modern,...secondaryProperties(modern)};
}
function axisProperties(source,theme){const out={};const aliases={fontSize:'labelFontSize',fontFamily:'labelFont',labelColor:'labelColor',color:'labelColor',titleColor:'titleColor',titleFontSize:'titleFontSize',titleFontFamily:'titleFont',gridlineColor:'gridColor',gridlineThickness:'gridWidth'};for(const [key,dest] of Object.entries(aliases)){const x=/Color|^color$/.test(key)?color(source[key],theme):value(source[key],theme);if(x!==undefined)out[dest]=/FontSize/.test(dest)?px(source[key],theme):x}if(value(source.show,theme)===false)out.labels=out.ticks=out.domain=false;if(value(source.showAxisTitle,theme)===false)out.title=null;else{const title=value(source.titleText??source.title,theme);if(typeof title==='string')out.title=title}if(value(source.gridlineShow,theme)!==undefined)out.grid=value(source.gridlineShow,theme);const position=value(source.position,theme);if(/^(left|right|top|bottom)$/i.test(position||''))out.orient=position.toLowerCase();if(value(source.labelAngle,theme)!==undefined)out.labelAngle=finite(value(source.labelAngle,theme),-90,90,0);return out}
function applySpec(spec,model,v,labels,rows,roles){const theme=model.theme||{},o=objects(model,v);spec.config=spec.config||{};spec.config.font=value(props(o,'general').fontFamily,theme)||theme.textClasses?.label?.fontFace||'Segoe UI, sans-serif';const text=theme.foreground||'#333';spec.config.axis={...spec.config.axis,labelColor:text,titleColor:text};spec.config.legend={...spec.config.legend,labelColor:text,titleColor:text};const legend=props(o,'legend');if(value(legend.fontSize,theme)!==undefined)spec.config.legend.labelFontSize=px(legend.fontSize,theme);if(color(legend.labelColor||legend.color,theme))spec.config.legend.labelColor=color(legend.labelColor||legend.color,theme);const position=String(value(legend.position,theme)||'').toLowerCase();const positions={top:'top',bottom:'bottom',left:'left',right:'right',topright:'top',topleft:'top',bottomright:'bottom',bottomleft:'bottom',topcenter:'top',bottomcenter:'bottom',leftcenter:'left',rightcenter:'right'};if(positions[position])spec.config.legend.orient=positions[position];if(value(legend.showTitle,theme)===false)spec.config.legend.title=null;else if(value(legend.titleText,theme))spec.config.legend.title=value(legend.titleText,theme);
 const catIndex=roles.findIndex(r=>['Category','Rows','X','Location','Group'].includes(r)),seriesIndex=roles.findIndex(r=>['Series','Legend','Columns'].includes(r));const state=v.definition?.query?.queryState||{};const axisProjections=Object.values(state).flatMap(s=>(s.projections||[]).filter(p=>p.active!==false)),field=axisProjections.map(p=>p.field);function domain(index){const c=field[index]?.Column||field[index]?.GroupRef;return model.colorDomains?.[(c?.Expression?.SourceRef?.Entity||'')+'\u0000'+c?.Property]||[]}
 // Selector columns identify the series receiving a static override; they
 // are not row-dependent color expressions. A direct fill would replace
 // Vega's series grouping and merge distinct areas that share a color.
 // Location and Size buckets do not imply a map color legend. Keep native
 // category legends and explicit color/gradient opt-ins, including View as
 // rebuilds, without disabling the separate optional Size legend.
 const implicitMapLegend=(!!spec.projection||['map','pointMap','filledMap','choroplethMap'].includes(v.type))&&value(legend.show,theme)!==true&&value(legend.showGradientLegend,theme)!==true&&!roles.some(role=>['Series','Legend','Columns'].includes(role));
 const values=spec.data?.values||[],legendCarriers=new Map(),rawRows=new Map(rows.map(row=>[JSON.stringify(row.slice(0,labels.length)),row]));for(const d of values){const row=d._raw?(labels.every(label=>Object.hasOwn(d._raw,label))?rawRows.get(JSON.stringify(labels.map(label=>d._raw[label]))):undefined):rows.find(r=>String(r[catIndex])===String(d._categoryValue)&& (seriesIndex<0||String(r[seriesIndex])===String(d._dimension)));d._raw=d._raw||Object.fromEntries(labels.flatMap((l,i)=>{const c=field[i]?.Column||field[i]?.Measure||field[i]?.Aggregation?.Expression?.Column;return [[l,row?.[i]],...(c?[[c.Property,row?.[i]],[(c.Expression?.SourceRef?.Entity||'')+'.'+c.Property,row?.[i]]]:[])]}));Object.defineProperty(d._raw,'__formatExpressions',{value:new Map(row?field.flatMap((f,i)=>f?[[JSON.stringify(f),row[i]]]:[]):[]),enumerable:false,configurable:true})}
 const formattingRows=values.map(d=>d._raw);for(const d of values)Object.defineProperty(d._raw,'__formatRows',{value:formattingRows,enumerable:false,configurable:true});
 const formattingGradients=new Map();for(const entry of entries(o,'dataPoint')){const rule=entry.properties?.fill?.solid?.color?.expr?.FillRule;if(!rule)continue;formattingGradients.set(rule,prepareGradientColor(rule,values.map(d=>value(rule.Input,theme,d._raw)),theme))}if(formattingGradients.size)for(const d of values)Object.defineProperty(d._raw,'__formatGradients',{value:formattingGradients,enumerable:false,configurable:true});
 for(const d of values)d._roles=roles;
 const colorObjects=seriesIndex>=0?seriesColorObjects(o,axisProjections[seriesIndex],field.filter((_,i)=>['Category','Rows','X','Location','Group'].includes(roles[i])).map(f=>f?.Column||f?.GroupRef).filter(Boolean),values,theme):o;
 const dynamicColor=/"(?:Conditional|Measure|Column|Aggregation|FillRule)"\s*:/.test(JSON.stringify([...entries(colorObjects,'dataPoint'),...entries(colorObjects,'dataColors')].map(entry=>entry.properties||{})));
 const sourceSeriesDomain=seriesIndex>=0?domain(seriesIndex):[],seriesDomain=sourceSeriesDomain.length?sourceSeriesDomain:[...new Set(values.map(d=>d._dimension))];
 function walk(node){if(!node||typeof node!=='object')return;if(node.mark){if(typeof node.mark==='string')node.mark={type:node.mark};const mark=node.mark;if(v.type==='scatterChart'&&['point','circle','square'].includes(mark.type)){const bubbles=props(o,'bubbles'),shape=String(value(bubbles.markerShape,theme)||'').toLowerCase(),shapes={circle:'circle',square:'square',diamond:'diamond',triangle:'triangle-up',triangleup:'triangle-up',triangledown:'triangle-down',cross:'cross',plus:'cross',x:'cross',star:'M0,-1L0.2245,-0.309L0.9511,-0.309L0.3633,0.118L0.5878,0.809L0,0.382L-0.5878,0.809L-0.3633,0.118L-0.9511,-0.309L-0.2245,-0.309Z'};if(shapes[shape])mark.shape=shapes[shape];const size=value(bubbles.bubbleSize,theme);if(Number.isFinite(size)){const area=Math.pow(Math.max(2,8+size*.42),2);if(node.encoding?.size?.field&&size!==0)node.encoding.size.scale={...node.encoding.size.scale,range:[Math.max(1,area*.025),area]};else if(!node.encoding?.size?.field)mark.size=area}if(shape==='x')mark.angle=45;mark.opacity=opacity(value(bubbles.transparency??props(o,'dataPoint').fillTransparency,theme)??15)}const lines=props(o,'lineStyles'),shapes=props(o,'shapes');if(['line','area'].includes(mark.type)){const width=value(lines.strokeWidth||lines.lineWidth||shapes.strokeWidth,theme);if(width!==undefined)mark.strokeWidth=finite(width,0,20,2);const interpolation=value(lines.interpolationSmooth,theme);if(['linear','monotoneX','monotoneY','step','stepBefore','stepAfter'].includes(interpolation))mark.interpolate=({monotoneX:'monotone',monotoneY:'monotone',stepBefore:'step-before',stepAfter:'step-after'}[interpolation]||interpolation);const dash=String(value(lines.lineStyle,theme)||'');if(/dash/i.test(dash))mark.strokeDash=[6,4];if(/dot/i.test(dash))mark.strokeDash=[2,3];if(value(shapes.showMarker||lines.showMarker,theme)!==undefined)mark.point=!!value(shapes.showMarker||lines.showMarker,theme);if(mark.type==='area'){mark.fillOpacity=opacity(value(props(o,'fill').transparency,theme)??60);mark.line=true}}if(mark.type==='arc'&&v.type==='donutChart'){const radius=value(props(o,'slices').innerRadiusRatio||props(o,'shapes').innerRadius,theme);if(radius!==undefined)mark.innerRadius=Math.min(spec.width,spec.height)*finite(radius,0,95,50)/200}
  if(mark.type==='bar'){const radius=value(props(o,'bars').roundedCorners,theme);if(radius!==undefined)mark.cornerRadius=finite(radius,0,30,0)}}
  if(node.mark?.type==='bar'){const bar={...props(o,'shapes'),...props(o,'bars'),...props(o,'columns')},thickness=value(bar.barThickness??bar.maximumSize??bar.maxBarSize,theme);if(Number.isFinite(thickness)&&thickness>0)node.mark.size=Math.min(300,thickness)}
  if(node.encoding){const e=node.encoding;for(const channel of ['x','y']){const f=e[channel];if(!f)continue;const category=f.field==='_category'||v.type==='scatterChart'&&channel==='x',a=category?props(o,'categoryAxis'):axisSource(model,v,f.axis?.orient==='right',{_projectionRef:axisProjections[labels.indexOf(f.title)]?.queryRef});if(value(a.show,theme)===false)f.axis=null;else if(f.axis!==null)f.axis={...f.axis,...axisProperties(a,theme)};if(category&&value(a.innerPadding,theme)!==undefined)f.scale={...f.scale,paddingInner:finite(value(a.innerPadding,theme),0,100,20)/100};if(f.type==='quantitative'){const min=value(a.start??a.minimum??a.min,theme),max=value(a.end??a.maximum??a.max,theme);f.scale={...f.scale};if(['lineChart','scatterChart'].includes(v.type))f.scale.zero=false;if(Number.isFinite(min)){f.scale.domainMin=min;f.scale.zero=false;f.scale.nice=false}if(Number.isFinite(max)){const barValue=!category&&(['clusteredBarChart','clusteredColumnChart','barChart','columnChart','stackedBarChart','stackedColumnChart','hundredPercentStackedBarChart','hundredPercentStackedColumnChart'].includes(v.type)||/ComboChart$/.test(v.type)&&node.mark?.type==='bar');f.scale.domainMax=max;f.scale.zero=barValue&&max>=0&&!Number.isFinite(min);f.scale.nice=false}if(Number.isFinite(min)&&Number.isFinite(max))f.scale.domain=[min,max];if(value(a.invertAxis,theme)!==undefined)f.scale.reverse=value(a.invertAxis,theme)===true;if(value(a.logAxisScale,theme)===true){f.scale.type='log';delete f.scale.zero}if(value(a.showAxisTitle,theme)===false)f.title=null}}
   if(v.type==='scatterChart'&&['point','circle','square'].includes(node.mark?.type)){for(const d of values)d._pbiColor=formatColor(model,v,d,color(props(colorObjects,'dataPoint').fill,theme,d._raw)||theme.dataColors?.[0]||'#337b60',colorObjects);if(dynamicColor||seriesIndex<0&&entries(colorObjects,'dataPoint').length)e.fill={field:'_pbiColor',type:'nominal',scale:null,legend:null}}
   const c=e.color;if(c?.type==='nominal'&&c.field){const keys=[...new Set(values.map(d=>d[c.field]))],isCat=['_category','_categoryValue'].includes(c.field),baseDomain=isCat?domain(catIndex):seriesIndex>=0?seriesDomain:labels.filter((_,i)=>rows.some(r=>typeof r[i]==='number'));c.scale={domain:keys,range:keys.map(key=>{const d=values.find(d=>d[c.field]===key)||{};return formatColor(model,v,d,stableColor(isCat?key:seriesIndex>=0?d._dimension:key,theme,baseDomain),colorObjects)})};if(value(legend.show,theme)===false)c.legend=null;
    else if(c.legend!==null&&seriesIndex>=0&&c.field==='_series')c.legend={...c.legend,title:value(legend.showTitle,theme)===false?null:value(legend.titleText,theme)??labels[seriesIndex]};
    if(node.mark?.type==='line'&&entries(o,'lineStyles').some(entry=>entry.selector?.data)){e.strokeDash={field:c.field,type:'nominal',legend:null,scale:{domain:keys,range:keys.map(key=>{const d=values.find(d=>d[c.field]===key)||{};const props=Object.assign({},...entries(o,'lineStyles').filter(entry=>selectorMatches(entry.selector,d)).map(entry=>entry.properties));const dash=String(value(props.lineStyle,theme)||'');return /dash/i.test(dash)?[6,4]:/dot/i.test(dash)?[2,3]:[1,0]})}}}

    if((dynamicColor||seriesIndex<0&&c.field==='_series'&&entries(colorObjects,'dataPoint').some(entry=>entry.selector?.data))&&['bar','rect','arc','point','circle','square','area'].includes(node.mark?.type)){for(const d of values)d._pbiColor=formatColor(model,v,d,stableColor(isCat?d[c.field]:seriesIndex>=0?d._dimension:d[c.field],theme,baseDomain),colorObjects);e.fill={field:'_pbiColor',type:'nominal',scale:null,legend:null}}
   }
   // Preserve series identity independently of its paint color, including
   // connected areas and lines with duplicate colors. Constant group colors
   // belong on the existing nominal scale, retaining its authored legend.
   if((['line','area'].includes(node.mark?.type)||['scatterChart','map','pointMap','filledMap','choroplethMap'].includes(v.type)&&seriesIndex>=0||['bar','rect','arc','point','circle','square'].includes(node.mark?.type)&&e.color?.legend!==null&&value(legend.show,theme)!==false)&&e.color?.type==='nominal'&&e.fill?.field==='_pbiColor'){
    const groups=new Map();for(const d of values){const key=d[e.color.field];if(!groups.has(key))groups.set(key,new Set());groups.get(key).add(d._pbiColor)}
    if([...groups.values()].every(colors=>colors.size===1)){e.color.scale={domain:[...groups.keys()],range:[...groups.values()].map(colors=>[...colors][0])};delete e.fill}
   }
   for(const channel of ['color','size','fill','stroke','shape','opacity','strokeDash','strokeWidth','fillOpacity','strokeOpacity','angle'])if(e[channel]&&(value(legend.show,theme)===false||implicitMapLegend&&channel!=='size'))e[channel].legend=null;
   if(['bar','rect','arc','point','circle','square'].includes(node.mark?.type)&&e.color?.type==='nominal'&&e.fill?.field==='_pbiColor'){
    // Vega-Lite drops color (and its legend) when a direct fill is present.
    // Retain the series grain independently, keeping every authored point
    // color. A tiny separate layer owns only the existing nominal legend.
    const c=e.color,details=Array.isArray(e.detail)?e.detail:e.detail?[e.detail]:[];
    if(!details.some(d=>d.field===c.field))details.push({field:c.field,type:c.type});e.detail=details;delete e.color;
    if(c.legend!==null){const key=JSON.stringify(c);if(!legendCarriers.has(key)){const color=structuredClone(c);color.legend={...c.legend,symbolOpacity:c.legend?.symbolOpacity??spec.config.legend?.symbolOpacity??1,symbolSize:c.legend?.symbolSize??spec.config.legend?.symbolSize??100,symbolType:c.legend?.symbolType??spec.config.legend?.symbolType??'square'};legendCarriers.set(key,{data:{values:[...new Set(values.map(d=>d[c.field]))].map(key=>({[c.field]:key}))},mark:{type:'point',filled:true,opacity:0,size:0,aria:false,tooltip:false},encoding:{color}})}}
   }
   if(e.color?.type==='quantitative'){const p=props(o,'dataPoint');const rule=entries(o,'dataPoint').map(e=>e.properties?.fill?.solid?.color?.expr?.FillRule?.FillRule?.linearGradient2).find(Boolean),low=color(rule?.min?.color||p.minColor,theme)||theme.minimum,high=color(rule?.max?.color||p.maxColor,theme)||theme.maximum;if(low&&high)e.color.scale={...e.color.scale,range:[low,high]}}
  }
  for(const [key,x] of Object.entries(node))if(key!=='data'&&key!=='config'&&x&&typeof x==='object'){if(Array.isArray(x))x.forEach(walk);else walk(x)}
 }walk(spec);
 if(legendCarriers.size){const carriers=[...legendCarriers.values()].map((layer,i)=>({name:'pbi_conditional_legend_'+i,...layer}));if(spec.layer)spec.layer.push(...carriers);else{const layer={mark:spec.mark,encoding:spec.encoding};delete spec.mark;delete spec.encoding;spec.layer=[layer,...carriers]}}
 if(v.type==='scatterChart'&&value(props(o,'categoryLabels').show,theme)===true){const p=props(o,'categoryLabels');if(spec.data.values.some(d=>d._detail!=null)){const {mark,encoding,params,...rest}=spec;spec={...rest,layer:[{mark,encoding,params},{mark:{type:'text',dy:-9,clip:true,fontSize:px(p.fontSize,theme,10),font:value(p.fontFamily,theme)||spec.config.font,color:color(p.color||p.fontColor,theme)||theme.foreground||'#333',tooltip:true},encoding:{x:encoding.x,y:encoding.y,text:{field:'_detail',type:'nominal'},tooltip:encoding.tooltip}}]}}}
 return spec;
}
function styleTable(el,model,v,labels,rows){return (typeof module!=='undefined'?require('./table-rendering.js'):root.TablePresentation).styleTable(el,model,v,labels,rows,{objects,props,value,color,px,url,conditionalApplies,prepareGradientColor})}
function resolveTheme(source,theme){if(!source||typeof source!=='object')return source;if(source.ThemeDataColor){const c=value(source,theme);return {Literal:{Value:"'"+c+"'"}}}return Array.isArray(source)?source.map(x=>resolveTheme(x,theme)):Object.fromEntries(Object.entries(source).map(([k,x])=>[k,resolveTheme(x,theme)]))}
function applyBookmarkDisplay(page,section,scope=[]){
 const saved={...section.visualContainers};
 function groups(entries){for(const [id,state] of Object.entries(entries||{})){saved[id]={...saved[id],...state};groups(state.children)}}
 groups(section.visualContainerGroups);
 for(const v of page.visuals){if(scope.length&&!scope.includes(v.id)&&!(v.groupChain||[]).some(id=>scope.includes(id)))continue;const state=saved[v.id];if(!state)continue;if(state.isHidden!==undefined)v.ownHidden=!!state.isHidden;else if(state.singleVisual)v.ownHidden=state.singleVisual.display?.mode==='hidden';else if(v.type==='group')v.ownHidden=false}
 const byid=new Map(page.visuals.map(v=>[v.id,v]));for(const v of page.visuals)v.hidden=!!v.ownHidden||(v.groupChain||[]).some(id=>byid.get(id)?.ownHidden)
}
function cardSettings(model,v,index=0){
 const o=objects(model,v),ps=Object.values(v.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false)),projection=ps[index];
 const resolved=key=>resolveProperties(model,v,key,{datum:{_sourceMeasure:projection?.queryRef?.split('.').pop(),_raw:{queryRef:projection?.queryRef}}}),selected=key=>resolved(key).properties;
 const pad=resolved('padding'),padding={...pad.properties};
 if(v.type==='cardVisual'){
  // Native card layout padding takes precedence over inherited general visual
  // padding. Keep explicitly authored card/container padding overrides.
  const layout=resolved('layout'),sources=['theme-global','theme-global-preset','theme-visual','theme-visual-preset','visual','container'];
  for(const key of ['paddingUniform','paddingIndividual','topMargin','rightMargin','bottomMargin','leftMargin','top','right','bottom','left'])if(Object.hasOwn(layout.properties,key)){
   const own=sources.indexOf(pad.sources[key]),native=sources.indexOf(layout.sources[key]);
   if(!Object.hasOwn(padding,key)||native>own||native===own&&own<4)padding[key]=layout.properties[key];
  }
 }
 return {border:selected('border'),padding,fill:selected('fillCustom'),callout:selected('cardCalloutArea'),image:selected('image'),value:{...selected('labels'),...(v.type==='cardVisual'?selected('value'):{})},category:{...selected('categoryLabels'),...(v.type==='cardVisual'?selected('label'):{})}};
}
function cardValue(model,v,index,n,format){
 const F=typeof module!=='undefined'?require('./model-formats'):root.ModelFormats,p=cardSettings(model,v,index).value,theme=model.theme||{},precision=value(p.labelPrecision??p.precision??p.decimalPlaces,theme),authored=value(p.labelDisplayUnits??p.displayUnits,theme);
 let units=authored;if((authored===0||authored===undefined&&v.type==='cardVisual'&&model.reportSettings?.defaultDisplayUnitsToNone!==true)&&!String(format).includes('%')){const abs=Math.abs(n);units=abs>=1e12?1e12:abs>=1e9?1e9:abs>=1e6?1e6:abs>=1e3?1e3:1}
 const resolved=F.resolve(model,v,index,{element:p,dynamicFormat:format});return F.text(n,resolved.format||'#,0.##',{...resolved,precision:precision??(v.type==='cardVisual'&&units>1&&!format?2:undefined),units});
}
function cardMarkup(model,v,labels,formattedValues,indices,images=[]){
 const title=v._suppressCardTitle?'':authoredTitle(model,v);
 return (title?'<h3>'+esc(title)+'</h3>':'')+formattedValues.map((formatted,i)=>{
  const index=indices?.[i]??i,settings=cardSettings(model,v,index),image=settings.image,src=value(image.show,model.theme)===true?url(images[i]??image.imageData??image.imageUrl,model):null;
  const imageOnly=value(settings.value.show,model.theme)===false&&value(settings.category.show,model.theme)===false,fit=String(value(image.fit,model.theme)||'Fit'),position=String(value(image.position,model.theme)||'Top').toLowerCase(),inline=['left','right'].includes(position),im=src?'<img class="card-image" alt="" referrerpolicy="no-referrer" src="'+esc(src)+'" style="object-fit:'+(/stretch/i.test(fit)?'fill':/fill/i.test(fit)?'cover':'contain')+';max-width:100%;'+(imageOnly?'width:100%;height:100%;min-height:0':inline?'width:48px;max-height:48px':'height:40px;max-width:100%')+'">':'';
  const above=String(value(settings.category.position,model.theme)||'').toLowerCase()==='abovevalue';
  const text='<div style="min-width:0;flex:1;width:100%;display:flex;flex-direction:'+(above?'column-reverse':'column')+'">'+(value(settings.value.show,model.theme)===false?'':'<div class="big">'+esc(formatted)+'</div>')+(value(settings.category.show,model.theme)===false?'':'<small class="card-category">'+esc(labels[i]??'')+'</small>')+'</div>';
  return '<div class="card-item"'+(v._nativeTooltip?' title="'+esc(v._nativeTooltip)+'"':'')+' data-card-index="'+index+'" style="max-width:100%;'+(imageOnly?'height:100%;min-height:0;':'')+'display:flex;align-items:center;justify-content:center;gap:8px;flex-direction:'+(inline?'row':'column')+'">'+(['bottom','right'].includes(position)?text+im:im+text)+'</div>';
 }).join('');
}
// Multi-card Arrangement uses layout.orientation: 0 grid, 1 vertical, 2 horizontal.
// Horizontal is the Power BI default when the property is omitted.
function cardLayout(model,v,count){
 const o=props(objects(model,v),'layout'),theme=model.theme||{},raw=value(o.orientation,theme),orientation=String(raw??2).toLowerCase();
 let columns=orientation==='1'||orientation==='vertical'?1:count;
 if(orientation==='0'||orientation==='grid'){
  const authored=Number(value(o.columnCount,theme)),rows=Number(value(o.rowCount,theme));
  columns=authored>0?authored:rows>0?Math.ceil(count/rows):Math.ceil(Math.sqrt(count));
 }
 columns=Math.max(1,Math.min(count,Math.floor(columns)||1));
 return '<div class="card-layout card-metrics" style="display:grid;width:100%;min-width:0;grid-template-columns:repeat('+columns+',minmax(0,1fr));gap:'+finite(value(o.cellPadding,theme),0,100,0)+'px">';
}
function cardResultMarkup(model,v,compiled,result,{defaultTooltip=true}={}){
 const groupIndices=(compiled.roles||[]).flatMap((role,i)=>(['Rows','Category','Group'].includes(role)||v.type==='multiRowCard'&&!result.rows.some(row=>typeof row[i]==='number')&&Object.values(v.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false))[i]?.field?.Column)?[i]:[]),metrics=compiled.labels.map((_,i)=>i).filter(i=>!groupIndices.includes(i)&&!['CardImages','Formatting','Tooltips','Tooltip'].includes(compiled.roles?.[i]));
 const tip={...props(objects(model,v),'tooltip'),...props(objects(model,v),'visualTooltip')},tipEnabled=defaultTooltip&&value(tip.show,model.theme)!==false&&!tooltipPage(model,v),render=row=>cardMarkup(model,{...v,_suppressCardTitle:true,_nativeTooltip:tipEnabled?(compiled.roles||[]).flatMap((role,i)=>/^tooltips?$/i.test(role)&&row[i]!=null?[compiled.labels[i]+': '+cardValue(model,v,i,row[i],compiled.formats?.[i])]:[]).join('\n'):''},metrics.map(i=>compiled.labels[i]),metrics.map(i=>cardValue(model,v,i,row[i],result.rowFormats?.[result.rows.indexOf(row)]?.[i]??compiled.formats?.[i])),metrics,metrics.map(i=>row[v._cardImageBindings?.[i]]));
 const title=authoredTitle(model,v),head=title?'<h3>'+esc(title)+'</h3>':'';
 if(result.rows.length===1&&!groupIndices.length)return head+(v.type==='cardVisual'?cardLayout(model,v,metrics.length)+render(result.rows[0])+'</div>':render(result.rows[0]));
 if(!groupIndices.length||!['cardVisual','multiRowCard'].includes(v.type))throw Error('Card needs one scalar row.');
 const layout=props(objects(model,v),'smallMultiplesLayout'),horizontal=v.type==='cardVisual'&&Number(value(layout.orientation,model.theme))===2;
 const ordered=[...result.rows];if(v.definition?.query?.sortDefinition?.isDefaultSort===true)ordered.sort((a,b)=>{for(const i of groupIndices){const cmp=typeof a[i]==='number'&&typeof b[i]==='number'?a[i]-b[i]:String(a[i]??'').localeCompare(String(b[i]??''));if(cmp)return cmp}return 0});
 return head+'<div class="card-layout" style="display:grid;width:100%;min-height:0;grid-template-columns:repeat('+(horizontal?ordered.length:1)+',minmax(0,1fr));gap:8px">'+ordered.map((row,rowIndex)=>'<section data-card-row="'+result.rows.indexOf(row)+'" class="card-group" style="width:100%;min-width:0;flex:none"><h4 style="margin:6px 0">'+esc(groupIndices.map(i=>row[i]??'(Blank)').join(' / '))+'</h4>'+cardLayout(model,v,metrics.length)+render(row)+'</div></section>').join('')+'</div>';
}
function bindCardTooltips(el,handlers,rows){
 if(handlers.onHover||handlers.tooltip===false)for(const node of el.querySelectorAll?.('.card-item[title],.card-item [title]')||[])node.removeAttribute?.('title');
 if(handlers.tooltip===false||!handlers.onHover)return;
 const items=el.querySelectorAll?.('.card-item')||[],scalarItem=rows.length===1&&items.length===1&&!items[0].closest('[data-card-row]')?items[0]:null;
 el.addEventListener('mousemove',event=>{
  if(event.target.closest('button,a,input,select')){handlers.onLeave?.();return}
  const item=event.target.closest('.card-item')||scalarItem;if(!item||!el.contains(item))return;
  const group=item.closest('[data-card-row]'),index=Number(group?.dataset.cardRow??0);
  handlers.onHover({_cardIndex:Number(item.dataset.cardIndex??0),_cardRow:rows[index]},event);
 });
 el.addEventListener('mouseleave',()=>handlers.onLeave?.());
}
function styleCard(el,model,v){
 for(const raw of v._formatRows||[])Object.defineProperty(raw,'__formatRows',{value:v._formatRows,enumerable:false,configurable:true});
 const o=objects(model,v),theme=model.theme||{},title=props(o,'title');if(!authoredTitle(model,v))el.querySelector(':scope > h3')?.remove();
 for(const [i,item] of [...el.querySelectorAll('.card-item')].entries()){
  const raw=v._formatRows?.[Number(item.closest('[data-card-row]')?.dataset.cardRow||0)]||{},settings=cardSettings(model,v,Number(item.dataset.cardIndex??i)),p=settings.value,category=settings.category,n=item.querySelector('.big');
  if(n){n.style.fontSize=px(p.fontSize??(v.type==='cardVisual'?theme.textClasses?.callout?.fontSize:undefined),theme,28)+'px';n.style.color=color(p.color||p.fontColor,theme,raw)||theme.foreground||'#222';n.style.fontFamily=value(p.fontFamily,theme)||'Segoe UI, sans-serif';n.style.fontWeight=value(p.bold,theme)?'700':'normal';n.style.lineHeight='1.1';n.style.margin='0';n.style.maxWidth='100%';n.style.minWidth='0';n.style.whiteSpace=value(p.textWrap,theme)===false?'nowrap':'pre-wrap';n.style.overflowWrap='anywhere';n.style.overflow='hidden';n.style.textOverflow='ellipsis'}
  const label=item.querySelector('.card-category');if(value(category.show,theme)===false)label?.remove();else if(label){label.style.display='block';label.style.marginTop=String(value(category.position,theme)||'').toLowerCase()==='abovevalue'?'0':'5px';label.style.fontSize=px(category.fontSize,theme,9)+'px';label.style.color=color(category.color||category.fontColor,theme,raw)||theme.textClasses?.label?.color||'#666666';label.style.fontFamily=value(category.fontFamily,theme)||'Segoe UI, sans-serif';label.style.whiteSpace='normal';label.style.overflowWrap='anywhere';label.style.lineHeight='1.25'}
  item.style.textAlign=value(p.horizontalAlignment||p.alignment||props(o,'general').alignment,theme)||(v.type==='cardVisual'?'left':'center');
  if(v.type==='cardVisual'){const fill=settings.fill,callout=settings.callout,shape=props(o,'shapeCustomRectangle'),border=props(o,'borderCustom');item.style.background=value(fill.show??fill.backgroundShow,theme)===false?'transparent':paint(color(fill.fillColor??fill.color,theme,raw)||(value(callout.show,theme)!==false?color(callout.backgroundFillColor,theme,raw):undefined)||color(props(o,'background').color,theme)||theme.background||'#FFFFFF',value(fill.transparency,theme));item.style.borderRadius=finite(value(shape.rectangleRoundedCurve,theme),0,100,8)+'px';item.style.border=value(settings.border.show,theme)===false||value(border.show,theme)===false?'none':finite(value(border.borderWeight,theme),0,12,1)+'px solid '+(color(border.borderColor,theme,raw)||'#E6E6E6');const pad=settings.padding,individual=value(pad.paddingIndividual,theme),uniform=value(pad.paddingUniform,theme);item.style.padding=individual===true?['top','right','bottom','left'].map(k=>finite(value(pad[k+'Margin']??pad[k],theme),0,100,0)+'px').join(' '):uniform!==undefined?finite(uniform,0,100,0)+'px':'4px 12px';item.style.width='100%';item.style.boxSizing='border-box';item.style.minWidth='0';item.style.maxWidth='100%';item.style.overflow='hidden';item.style.alignItems='stretch';item.style.justifyContent='center'}
 }
 // Transparent cards can deliberately hide both their callout and category
 // and serve as tooltip targets. Keep their grid inside the authored bounds
 // while giving its empty content a real hover area.
 const metrics=el.querySelector(':scope > .card-metrics'),items=[...el.querySelectorAll('.card-item')];
 if(metrics&&items.length&&items.every((item,i)=>{const settings=cardSettings(model,v,Number(item.dataset.cardIndex??i));return value(settings.value.show,theme)===false&&value(settings.category.show,theme)===false})){metrics.style.flex='1 0 0';metrics.style.alignSelf='stretch';metrics.style.minHeight='0'}
 el.dataset.singleScalarCard=String(v.type==='card'&&el.querySelectorAll('.card-item').length===1&&!el.querySelector('.card-group'));el.style.display='flex';el.style.flexDirection='column';el.style.justifyContent=el.querySelector('.card-group')?'flex-start':'center';el.style.pointerEvents='auto';el.style.minHeight='0';el.tabIndex=0;el.setAttribute('role','region');el.setAttribute('aria-label','Scrollable cards');for(const child of el.children)child.style.flexShrink='0';for(const h of el.querySelectorAll('.card-group > h4')){const header=props(o,'smallMultiplesHeader');h.style.textAlign=value(header.alignment,theme)||'left';h.style.fontFamily=value(header.fontFamily,theme)||theme.textClasses?.header?.fontFace||'Segoe UI';h.style.fontSize=px(header.fontSize,theme,12)+'px';h.style.margin='2px 12px';}el.style.textAlign='center';el.style.alignItems='center';
}

function tooltipSize(page,bounds=[],viewportWidth=1024,viewportHeight=768){
 const width=Math.max(page.width||350,...bounds.map(b=>b.x+b.width)),height=Math.max(page.height||240,...bounds.map(b=>b.y+b.height));
 return {width,height,scale:Math.min(1,Math.max(1,viewportWidth-24)/width,Math.max(1,viewportHeight-24)/height)};
}
function positionTooltip(box,point){const r=box.getBoundingClientRect(),root=typeof document!=='undefined'?document.documentElement:null,width=root?.clientWidth||innerWidth,height=root?.clientHeight||innerHeight;box.style.left=Math.max(6,Math.min(width-r.width-6,(point.clientX||0)+16))+'px';box.style.top=Math.max(6,Math.min(height-r.height-6,(point.clientY||0)+16))+'px'}
function fitTooltip(canvas,box,page,point){
 const bounds=[];
 for(const el of canvas.children){
  for(const wrap of el.querySelectorAll('.tablewrap')){wrap.style.overflow='visible';wrap.style.maxHeight='none';wrap.style.height='auto';wrap.style.flex='none';const table=wrap.querySelector('table');if(table){table.style.width='max-content';table.style.minWidth='100%'}}
  // Chart pages keep their authored chart boxes. Only tabular content grows to
  // reveal rows; stretching a chart here overlaps adjacent tooltip visuals.
  for(const chart of el.querySelectorAll('.vega-chart'))chart.style.overflow='visible';
  const x=(parseFloat(el.style.left)||0)*(el.style.left.endsWith('%')?page.width/100:1),y=(parseFloat(el.style.top)||0)*(el.style.top.endsWith('%')?page.height/100:1);
  const width=Math.max(el.offsetWidth,el.scrollWidth),height=Math.max(el.offsetHeight,el.scrollHeight);
  el.style.left=x+'px';el.style.top=y+'px';el.style.width=width+'px';el.style.height=height+'px';el.style.overflow='visible';bounds.push({x,y,width,height});
 }
 const size=tooltipSize(page,bounds,innerWidth,innerHeight);canvas.style.width=size.width+'px';canvas.style.height=size.height+'px';canvas.style.zoom=size.scale;canvas.style.overflow='visible';box.style.overflow='hidden';positionTooltip(box,point);return size;
}
const api={imagePlan,axisSource,navigatorBookmarks,navigatorPages,conditionalApplies,gradientColor,prepareGradientColor,bookmarkPlan,resolveProperties,resolveProperty,bookmarkScope,bindCardTooltips,cardLayout,shapeTextMarkup,backgroundSize,slicerHeadingPlan,styleSlicerHeadings,hasCaptionContent,tooltipSize,fitTooltip,positionTooltip,titleVisible,cardResultMarkup,cardSettings,cardValue,selectorMatches,cardMarkup,authoredTitle,layoutTextIcons,textboxMarkup,applyBookmarkDisplay,styleCard,resolveTheme,value,color,url,objects,props,container,pageStyle,styleTitle,action,tooltipPage,staticVisual,shapeMarkup,stableColor,applySpec,styleTable,formatColor};if(typeof module!=='undefined')module.exports=api;root.ReportStyle=api;
})(globalThis);

