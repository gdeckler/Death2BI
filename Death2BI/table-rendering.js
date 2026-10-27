/* Table formatting and local sorting operate on the current visual result cache. */
(function(root){
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function projections(v){return Object.values(v.definition?.query?.queryState||{}).flatMap(s=>(s.projections||[]).filter(p=>p.active!==false))}
function aliases(p,label){const f=p?.field||{},c=f.Measure||f.Column||f.Aggregation?.Expression?.Column||f.GroupRef;return [label,p?.queryRef,p?.nativeQueryRef,p?.displayName,c?.Property,c?.Expression?.SourceRef?.Entity&&c.Property?c.Expression.SourceRef.Entity+'.'+c.Property:null].filter(Boolean)}
function datumFor(visual,labels,row){const ps=projections(visual),datum={};labels.forEach((label,i)=>aliases(ps[i],label).forEach(key=>datum[key]=row[i]));Object.defineProperty(datum,'__formatExpressions',{value:new Map(ps.flatMap((p,i)=>p.field?[[JSON.stringify(p.field),row[i]]]:[])),enumerable:false,configurable:true});return datum}
function cellDatumFor(visual,labels,row,index,base=datumFor(visual,labels,row),metadata={}){const datum={...base,...metadata},p=projections(visual)[index],bindings=new Map([...(base.__formatExpressions||[]),...(metadata.__formatExpressions||[])]);for(const key of aliases(p,labels[index]))datum[key]=row[index];if(p?.field)bindings.set(JSON.stringify(p.field),row[index]);Object.defineProperty(datum,'__formatExpressions',{value:bindings,enumerable:false,configurable:true});if(metadata.__formatScope)Object.defineProperty(datum,'__formatScope',{value:metadata.__formatScope,enumerable:false});return datum}
function matchesColumn(entry,visual,labels,index){return !entry.selector?.metadata||aliases(projections(visual)[index],labels[index]).includes(entry.selector.metadata)}
function sortIndexes(rows,column,descending=false){return rows.map((_,i)=>i).sort((a,b)=>{const x=rows[a][column],y=rows[b][column];if(x==null||y==null)return x==null&&y==null?a-b:x==null?1:-1;let cmp=typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),undefined,{numeric:true,sensitivity:'base'});return cmp?(descending?-cmp:cmp):a-b})}
function rowColors(values,theme,S,index,diagnostics){
 const primary=S.color(values.backColorPrimary||values.backColor,theme)||theme.background||'#ffffff';
 const explicit=S.color(values.backColorSecondary,theme);
 // Power BI's default table style bands rows even when the PBIX omits default properties.
 const enabled=S.value(values.bandedRows,theme)!==false&&S.value(values.alternateRows,theme)!==false;
 let alternate=explicit;
 const token=S.value(values.backColorSecondary,theme),rgb=x=>/^#[0-9a-f]{6}$/i.test(x||'')?x.slice(1).match(/../g).map(n=>parseInt(n,16)/255):null;
 const luminance=x=>{const c=rgb(x);return c?c.map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4).reduce((s,n,i)=>s+n*[.2126,.7152,.0722][i],0):null},fg=luminance(S.color(values.fontColorSecondary||values.fontColorPrimary||values.fontColor,theme)||theme.foreground),bg=luminance(explicit);
 if(theme._inheritedStructuralColors?.includes(token)&&fg!==null&&bg!==null&&(Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05)<3){alternate=null;if(diagnostics&&!diagnostics.some(x=>x.path==='values.backColorSecondary'))diagnostics.push({path:'values.backColorSecondary',source:'readability-fallback',original:explicit,reason:'Inherited base-theme stripe has insufficient contrast with report text.'})}

 if(!alternate){const hex=/^#([\da-f]{6})$/i.exec(primary);alternate=hex?'#'+hex[1].match(/../g).map(x=>Math.round(parseInt(x,16)*.94+128*.06).toString(16).padStart(2,'0')).join(''):'#f2f2f2'}
 return index%2&&enabled?alternate:primary;
}
function barColor(source,theme,S,datum,fallback){
 const token=S.value(source,theme,datum);
 return S.color(source,theme,datum)||({maxColor:theme.maximum||theme.dataColors?.[0]||'#118DFF',minColor:theme.minimum||'#DEEFFF',foreground:theme.foreground||'#252423',background:theme.background||'#FFFFFF'}[token])||fallback;
}
function barMatches(settings,isTotal,S,theme){return S.conditionalApplies?S.conditionalApplies(settings,theme,{isTotal}):(S.value(settings.totalMatchingOption,theme)===1?!isTotal:S.value(settings.totalMatchingOption,theme)===2?isTotal:true)}
function dataBar(value,settings,domain,theme,S,datum={}){
 if(typeof value!=='number'||!Number.isFinite(value)||S.value(settings.show,theme)===false)return null;
 const nums=domain.filter(x=>typeof x==='number'&&Number.isFinite(x));
 const minSetting=S.value(settings.minValue,theme,datum),maxSetting=S.value(settings.maxValue,theme,datum);
 const min=typeof minSetting==='number'&&Number.isFinite(minSetting)?minSetting:Math.min(0,...nums),max=typeof maxSetting==='number'&&Number.isFinite(maxSetting)?maxSetting:Math.max(0,...nums);
 if(max<min)return null;
 const point=x=>max===min?0:Math.max(0,Math.min(1,(x-min)/(max-min)))*100,zero=point(0),end=point(value),reverse=S.value(settings.reverseDirection,theme)===true;
 const left=Math.min(zero,end),right=Math.max(zero,end);
 return {left:reverse?100-right:left,width:right-left,axis:reverse?100-zero:zero,showAxis:min<0,color:value<0?barColor(settings.negativeColor,theme,S,datum,'#D64554'):barColor(settings.positiveColor,theme,S,datum,theme.dataColors?.[0]||'#118DFF'),axisColor:barColor(settings.axisColor,theme,S,datum,theme.foreground||'#252423'),hideText:S.value(settings.hideText,theme)===true,min,max};
}
function paintBar(td,spec,label){
 if(!spec)return;
 td.querySelector(':scope > .pbi-data-bar')?.remove();
 // A separate visual layer leaves banding, conditional colors and raw data intact.
 const layer=document.createElement('span');layer.className='pbi-data-bar';layer.setAttribute('aria-hidden','true');layer.style.cssText='position:absolute;inset:3px 4px;pointer-events:none;z-index:0';
 const bar=document.createElement('span');bar.className='pbi-data-bar-fill';bar.style.cssText='position:absolute;top:0;bottom:0';bar.style.left=spec.left+'%';bar.style.width=spec.width+'%';bar.style.backgroundColor=spec.color;layer.appendChild(bar);
 if(spec.showAxis){const axis=document.createElement('span');axis.className='pbi-data-bar-axis';axis.style.cssText='position:absolute;top:0;bottom:0;width:1px';axis.style.left=spec.axis+'%';axis.style.backgroundColor=spec.axisColor;layer.appendChild(axis)}
 let text=td.querySelector(':scope > .pbi-data-bar-text');if(!text){text=document.createElement('span');text.className='pbi-data-bar-text';while(td.firstChild)text.appendChild(td.firstChild);td.appendChild(text)}
 text.style.cssText='position:relative;z-index:1';if(spec.hideText)text.style.visibility='hidden';td.style.position='relative';td.style.isolation='isolate';td.setAttribute('aria-label',label);td.title=label;td.prepend(layer);
}
function iconMarkup(name){
 const match=/^(Circle|Sign|Arrow|Flag|Star)(High|Medium|Low)$/.exec(String(name||''));if(!match)return null;
 const [,kind,level]=match,color={High:'#27a844',Medium:'#efbb20',Low:'#d83b35'}[level],label=({High:'Green',Medium:'Yellow',Low:'Red'}[level])+' '+({Circle:'circle',Sign:level==='High'?'check':level==='Low'?'cross':'warning',Arrow:'arrow',Flag:'flag',Star:'star'}[kind]);let body;
 if(kind==='Circle')body='<circle cx="10" cy="10" r="8" fill="'+color+'"/>';
 if(kind==='Sign')body='<circle cx="10" cy="10" r="9" fill="'+color+'"/><path d="'+({High:'M5 10L8 13L15 6',Low:'M6 6L14 14M14 6L6 14',Medium:'M10 4V11M10 14V15'}[level])+'" stroke="white" stroke-width="2" fill="none"/>';
 if(kind==='Arrow')body='<path d="M8 18V8H3L10 1L17 8H12V18Z" fill="'+color+'" transform="rotate('+({High:0,Medium:90,Low:180}[level])+' 10 10)"/>';
 if(kind==='Flag')body='<path d="M4 19V2M5 2H16L13 6L16 10H5" fill="'+color+'" stroke="'+color+'" stroke-width="2"/>';
 if(kind==='Star')body='<path d="M10 1L13 7H19L14 12L16 19L10 15L4 19L6 12L1 7H7Z" fill="'+color+'"/>';
 return '<svg class="pbi-cell-icon" role="img" aria-label="'+esc(label)+'" viewBox="0 0 20 20" style="display:inline-block;width:1.2em;height:1.2em;vertical-align:middle"><title>'+esc(label)+'</title>'+body+'</svg>';
}
function pinTotals(table,fallback='#ffffff'){
 let bottom=0;for(const row of [...table.querySelectorAll('tfoot tr,tr[data-pbi-total="true"]')].reverse()){
  for(const cell of row.cells){cell.style.position='sticky';cell.style.bottom=bottom+'px';cell.style.zIndex='2';const bg=cell.style.backgroundColor;if(!bg||bg==='transparent'||bg==='rgba(0, 0, 0, 0)')cell.style.backgroundColor=fallback;cell.style.boxShadow='0 -1px 0 rgba(0,0,0,.12)'}bottom+=row.getBoundingClientRect().height;
 }
}
function pinHeaders(table){
 const head=table.tHead||table.querySelector('thead');if(!head)return;
 head.style.position='sticky';head.style.top='0px';head.style.zIndex='3';
 // Header cells keep their imported colors; this fills any gaps between cells.
 head.style.backgroundColor='inherit';
}
function tableValues(source,preset){const values={...source};
 if(preset==='None'&&!values.backColorPrimary&&!values.backColor)values.backColorPrimary='transparent';
 if(preset==='None'&&values.bandedRows===undefined&&values.alternateRows===undefined)values.bandedRows=false;
 return values;
}
function styleTable(el,model,visual,labels,rows,S){
 const o=S.objects(model,visual),theme=model.theme||{},header=S.props(o,'columnHeaders'),values={...S.props(o,'values')},grid=S.props(o,'grid'),table=el.querySelector('table');if(!table)return;pinHeaders(table);
 const preset=S.value(S.props(visual.definition?.visualContainerObjects,'stylePreset').name,theme);Object.assign(values,tableValues(values,preset));
 const entries=name=>Array.isArray(o[name])?o[name]:[],value=x=>S.value(x,theme),color=(x,datum)=>S.color(x,theme,datum),align=x=>/^(left|center|right)$/i.test(value(x)||'')?value(x).toLowerCase():undefined;
 table.style.fontFamily=value(values.fontFamily)||theme.textClasses?.label?.fontFace||'Segoe UI';
 const headers=[...table.querySelectorAll('th')],body=table.querySelector('tbody'),cached=[...table.querySelectorAll('tbody tr')].map((element,i)=>({element,row:rows[i],sourceIndex:i}));
 if(visual._footerRow){const footer=table.querySelector('tfoot tr');if(footer)cached.push({element:footer,row:visual._footerRow,sourceIndex:rows.length})}
 const rowData=new Map(cached.map(entry=>[entry,datumFor(visual,labels,entry.row)])),formatRows=[...rowData.values()],cellData=new Map(),conditionalDomains=new Map(),gradientDomains=new Map(),gradientRules=new Map();
 for(const datum of formatRows)datum.__formatRows=formatRows;
 function cellFor(entry,index){let cells=cellData.get(entry);if(!cells){cells=new Map();cellData.set(entry,cells)}if(!cells.has(index))cells.set(index,cellDatumFor(visual,labels,entry.row,index,rowData.get(entry),visual._cellData?.[entry.sourceIndex]?.[index]||{}));return cells.get(index)}
 const projected=projections(visual),projectionKey=index=>projected[index]?.field?JSON.stringify(projected[index].field):'column:'+index;
 function applies(entry,tr,datum){const p=entry.properties||entry;if(S.conditionalApplies&&!S.conditionalApplies(p,theme,{isTotal:tr.dataset?.pbiTotal==='true'||datum.__formatScope?.isTotal===true,isSubtotal:tr.dataset?.pbiSubtotal==='true'||datum.__formatScope?.isSubtotal===true}))return false;return !(entry.selector?.data||[]).map(s=>s.scopeId).filter(Boolean).some(c=>!S.value(c,theme,datum))}
 function domainFor(rule,column){if(!conditionalDomains.has(rule))conditionalDomains.set(rule,new Map());const domains=conditionalDomains.get(rule),key=projectionKey(column);if(!domains.has(key)){const domain=[];for(const entry of cached)for(let index=0;index<labels.length;index++)if(projectionKey(index)===key&&matchesColumn(rule,visual,labels,index)){const datum=cellFor(entry,index);if(applies(rule,entry.element,datum))domain.push(datum)}domains.set(key,domain)}return domains.get(key)}
 function gradientsFor(rule,column){
  if(!S.prepareGradientColor)return undefined;
  if(!gradientRules.has(rule)){const rules=new Set();function visit(node){if(!node||typeof node!=='object')return;if(node.FillRule?.Input)rules.add(node.FillRule);for(const child of Object.values(node))if(child&&typeof child==='object')visit(child)}visit(rule.properties||rule);gradientRules.set(rule,[...rules])}
  const rules=gradientRules.get(rule);if(!rules.length)return undefined;
  if(!gradientDomains.has(rule))gradientDomains.set(rule,new Map());const domains=gradientDomains.get(rule),key=projectionKey(column);
  if(!domains.has(key)){const rows=domainFor(rule,column);domains.set(key,new Map(rules.map(gradient=>[gradient,S.prepareGradientColor(gradient,rows.map(datum=>S.value(gradient.Input,theme,datum)),theme)])))}return domains.get(key);
 }
 const barEntries=['values','columnFormatting','cellElements'].flatMap(entries).filter(e=>(e.properties||e).dataBars),barDomains=new Map(barEntries.map(entry=>{
  const settings=(entry.properties||entry).dataBars,indices=labels.flatMap((_,i)=>matchesColumn(entry,visual,labels,i)?[i]:[]);
  return [entry,cached.filter(e=>barMatches(settings,e.element.dataset?.pbiTotal==='true',S,theme)).flatMap(e=>indices.map(i=>e.row[i]))];
 }));
 function paint(rowEntry,rowIndex){const {element:tr,row}=rowEntry,datum=rowData.get(rowEntry);
  for(const [ci,td] of [...tr.cells].entries()){
   td.querySelector(':scope > .pbi-data-bar')?.remove();
   const secondary=rowIndex%2===1;
   td.style.color=color(secondary?(values.fontColorSecondary||values.fontColorPrimary||values.fontColor):(values.fontColorPrimary||values.fontColor),datum)||theme.foreground||'#333';
   td.style.background=rowColors(values,theme,S,rowIndex,(model.formattingProvenance||={fallbacks:[]}).fallbacks);
   if(tr.dataset?.pbiTotal==='true'||tr.dataset?.pbiSubtotal==='true'){const total=S.props(o,tr.dataset?.pbiTotal==='true'?'total':'subTotals');td.style.background=color(total.backColor,datum)||td.style.background;td.style.color=color(total.fontColor,datum)||td.style.color;if(value(total.bold)!==false)td.style.fontWeight='bold'}
   td.style.fontSize=S.px(values.fontSize,theme,12)+'px';td.style.padding=Math.max(0,Number(value(grid.rowPadding))||4)+'px';td.style.textAlign=align(values.alignment)|| (typeof row[ci]==='number'?'right':'left');
   if(value(values.bold)!==undefined)td.style.fontWeight=value(values.bold)?'bold':'normal';if(value(values.wordWrap))td.style.whiteSpace='normal';if(value(grid.gridHorizontal)===false)td.style.borderBottom='none';else if(value(grid.gridHorizontal)===true)td.style.borderBottom=(Number(value(grid.gridHorizontalWeight))||1)+'px solid '+(color(grid.gridHorizontalColor)||theme.backgroundLight||'#ddd');if(value(grid.gridVertical))td.style.borderRight='1px solid '+(color(grid.gridVerticalColor)||theme.backgroundLight||'#ddd');
   for(const name of ['values','columnFormatting','cellElements'])for(const entry of entries(name)){
    if(name==='values'&&!entry.selector?.metadata&&!entry.selector?.data)continue;
    if(!matchesColumn(entry,visual,labels,ci))continue;const cellDatum=cellFor(rowEntry,ci);if(!applies(entry,tr,cellDatum))continue;
    const p=entry.properties||entry;cellDatum.__formatRows=domainFor(entry,ci);Object.defineProperty(cellDatum,'__formatGradients',{value:gradientsFor(entry,ci),configurable:true});const bg=color(p.backColor||p.backgroundColor||p.backColorPrimary,cellDatum),fg=color(p.fontColor||p.fontColorPrimary,cellDatum);if(bg)td.style.background=bg;if(fg)td.style.color=fg;if(align(p.alignment))td.style.textAlign=align(p.alignment);
    if(p.icon){const vertical=value(p.icon.verticalAlignment);if(/^(top|middle|bottom)$/i.test(vertical||''))td.style.verticalAlign=vertical.toLowerCase();const icon=iconMarkup(S.value(p.icon.value,theme,cellDatum));if(icon){const node=document.createElement('span');node.innerHTML=icon;if(value(p.icon.layout)==='IconOnly'){td.replaceChildren(node);td.title=node.textContent;td.setAttribute('aria-label',labels[ci]+': '+node.textContent)}else if(!td.querySelector('.pbi-cell-icon'))td.prepend(node)}}
   }
   for(const barEntry of barEntries){if(!matchesColumn(barEntry,visual,labels,ci))continue;const settings=(barEntry.properties||barEntry).dataBars;if(!barMatches(settings,tr.dataset?.pbiTotal==='true',S,theme))continue;
    const conditions=(barEntry.selector?.data||[]).map(x=>x.scopeId).filter(Boolean);if(conditions.some(x=>!S.value(x,theme,datum)))continue;
    const spec=dataBar(row[ci],settings,barDomains.get(barEntry),theme,S,datum);paintBar(td,spec,td.querySelector('.pbi-data-bar-text')?.textContent||td.textContent);
   }
  }
  // Local sorting repaints conditional icons and data bars. Their native
  // titles must stay suppressed when the visual owns tooltip presentation.
  root.ChartInteractionAPI?.suppressNativeTableTooltips(table,[tr]);
 }
 cached.forEach(paint);
 const ps=projections(visual);for(const [i,th] of headers.entries())if(i>=ps.length){th.hidden=true;for(const {element:tr} of cached)if(tr.cells[i])tr.cells[i].hidden=true}for(const entry of entries('columnWidth')){const width=Number(value((entry.properties||entry).value));if(Number.isFinite(width))for(const [i,th] of headers.entries())if(matchesColumn(entry,visual,labels,i)){th.style.width=width+'px';th.style.minWidth=width+'px';for(const {element:tr} of cached)if(tr.cells[i]){tr.cells[i].style.width=width+'px';tr.cells[i].style.minWidth=width+'px'}}}
 const sourceSort=visual.definition?.query?.sortDefinition?.sort?.[0];let current=sourceSort?{column:ps.findIndex(p=>JSON.stringify(p.field)===JSON.stringify(sourceSort.field)),descending:sourceSort.direction==='Descending'}:null;
 function indicators(){headers.forEach((th,i)=>{th.setAttribute('aria-sort',current?.column===i?(current.descending?'descending':'ascending'):'none');th.querySelector('.pbi-sort-indicator')?.remove();if(current?.column===i){const arrow=document.createElement('span');arrow.className='pbi-sort-indicator';arrow.setAttribute('aria-hidden','true');arrow.textContent=current.descending?' ▼':' ▲';th.appendChild(arrow)}})}
 headers.forEach((th,i)=>{
  th.style.background=color(header.backColor||header.backgroundColor)||(preset==='None'?'transparent':theme.background||'#ffffff');th.style.color=color(header.fontColor)||theme.foregroundNeutralSecondary||theme.foreground||'#333';th.style.fontFamily=value(header.fontFamily)||table.style.fontFamily;th.style.fontSize=S.px(header.fontSize,theme,12)+'px';th.style.textAlign=align(header.alignment)||'left';if(value(header.bold)!==undefined)th.style.fontWeight=value(header.bold)?'bold':'normal';if(value(header.wordWrap))th.style.whiteSpace='normal';
  th.tabIndex=0;th.scope='col';th.style.cursor='pointer';th.title='Sort loaded rows by '+labels[i]+' (no database query)';
  const sort=()=>{current={column:i,descending:current?.column===i?!current.descending:false};sortIndexes(rows,i,current.descending).forEach((index,position)=>{const entry=cached[index];body.appendChild(entry.element);paint(entry,position)});indicators()};th.onclick=sort;th.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();sort()}};
 });indicators();
 // Preserve URL/image cells after formatting; they are retained when rows move.
 cached.forEach(({element:tr,row})=>[...tr.cells].forEach((td,i)=>{if(td.querySelector('.pbi-cell-icon'))return;const target=S.url(row[i],model);if(!target)return;const image=/^data:image\//i.test(target)||/\.(png|jpe?g|gif|webp|avif|bmp|svg)(?:[?#]|$)/i.test(target),node=document.createElement(image?'img':'a');if(image){node.src=target;node.alt='Report image';node.style.cssText='max-width:100%;object-fit:contain';node.style.width=(Number(value(grid.imageWidth))||160)+'px';node.style.height=(Number(value(grid.imageHeight))||90)+'px';node.onerror=()=>node.remove()}else{node.href=target;node.target='_blank';node.rel='noopener noreferrer';node.textContent=td.textContent}node.referrerPolicy='no-referrer';td.replaceChildren(node)}));
 pinTotals(table,theme.background||'#ffffff');
 root.ChartInteractionAPI?.suppressNativeTableTooltips(table);
}
const api={tableValues,pinTotals,pinHeaders,styleTable,sortIndexes,datumFor,cellDatumFor,matchesColumn,iconMarkup,rowColors,dataBar,barMatches};if(typeof module!=='undefined')module.exports=api;root.TablePresentation=api;
})(globalThis);
