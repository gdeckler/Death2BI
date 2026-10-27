/* Matrix groups are evaluated at their own grain; totals are never summed from child measures. */
(function(root){
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state=v=>v?.definition?.query?.queryState||{};
function plan(visual,depth=0,path=[]){
 const v=structuredClone(visual),s=state(v),rows=s.Rows?.projections||[];
 v.filters=Array.isArray(v.filters)?v.filters:v.filters?[v.filters]:[];
 rows.forEach((p,i)=>p.active=i<=depth);
 for(let i=0;i<path.length;i++){
  const x=path[i],literal={Literal:{Value:x===null?'null':typeof x==='number'?String(x):typeof x==='boolean'?String(x):"'"+String(x).replaceAll("'","''")+"'"}};
  (v.filters||=[]).push({filter:{Where:[{Condition:{In:{Expressions:[rows[i].field],Values:[[literal]]}}}]}});
 }
 const fields=Object.values(s).flatMap(r=>(r.projections||[]).filter(p=>p.active!==false).map(p=>JSON.stringify(p.field)));
 if(v.definition.query.sortDefinition)v.definition.query.sortDefinition.sort=(v.definition.query.sortDefinition.sort||[]).filter(x=>fields.includes(JSON.stringify(x.field)));
 return v;
}
function sparklineSettings(model={},visual={},projection={},datum={}){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,theme=model.theme||{},context={...datum,_projectionRef:projection.queryRef};
 const properties=S.resolveProperties(model,visual,'sparklines',{datum:context}).properties;
 const chartType=String(S.value(properties.chartType,theme,context)||'line').toLowerCase(),width=Number(S.value(properties.strokeWidth,theme,context));
 return {chartType:chartType==='column'?'column':'line',color:S.color(properties.dataColor,theme,context._raw||context)||S.color(theme.dataColors?.[0],theme)||'currentColor',strokeWidth:Number.isFinite(width)?Math.max(0,Math.min(12,width)):1.5};
}
function sparklineMarkup(value,options={}){
 if(!value||!Array.isArray(value.sparkline))return null;
 const settings=sparklineSettings(options.model,options.visual,options.projection,options.datum),slots=value.sparkline.filter(p=>Array.isArray(p)&&p.length>=2),points=slots.filter(p=>Number.isFinite(p[1]));if(!points.length)return '<span>No data</span>';
 const ys=points.map(p=>p[1]),lo=Math.min(...ys),hi=Math.max(...ys),column=settings.chartType==='column';let marks='';
 if(column){
  const bottom=Math.min(0,lo),top=Math.max(0,hi),range=top-bottom||1,y=value=>28-26*(value-bottom)/range,zero=y(0),step=116/slots.length,width=step*.75;
  marks=slots.map((point,index)=>{if(!Number.isFinite(point[1]))return '';const position=y(point[1]);return '<rect x="'+(2+index*step+(step-width)/2).toFixed(2)+'" y="'+Math.min(position,zero).toFixed(2)+'" width="'+width.toFixed(2)+'" height="'+Math.abs(zero-position).toFixed(2)+'" fill="'+esc(settings.color)+'"/>'}).join('');
 }else{
  const numeric=slots.every(p=>Number.isFinite(p[0])),xs=slots.map((p,i)=>numeric?p[0]:i),minX=Math.min(...xs),maxX=Math.max(...xs),x=i=>2+116*(xs[i]-minX)/(maxX-minX||1),y=value=>28-26*(value-lo)/(hi-lo||1);let open=false;
  const path=slots.map((point,index)=>{if(!Number.isFinite(point[1])){open=false;return ''}const segment=(open?'L':'M')+x(index).toFixed(2)+','+y(point[1]).toFixed(2);open=true;return segment}).filter(Boolean).join(' ');
  marks='<path d="'+path+'" fill="none" stroke="'+esc(settings.color)+'" stroke-width="'+settings.strokeWidth+'"/>';
  if(points.length===1){const index=slots.findIndex(point=>Number.isFinite(point[1]));marks+='<circle cx="'+x(index).toFixed(2)+'" cy="'+y(points[0][1]).toFixed(2)+'" r="1.5" fill="'+esc(settings.color)+'"/>'}
 }
 return '<svg role="img" data-pbi-sparkline-type="'+settings.chartType+'" aria-label="'+esc((column?'Column sparkline: ':'Trend: ')+points.length+' points, minimum '+lo+', maximum '+hi)+'" viewBox="0 0 120 32" style="width:120px;height:32px;max-width:100%;vertical-align:middle">'+marks+'</svg>';
}
function groups(result,compiled,depth,visual=compiled._visual){
 const ri=compiled.roles.flatMap((r,i)=>r==='Rows'?[i]:[]),ci=compiled.roles.flatMap((r,i)=>r==='Columns'?[i]:[]),vi=compiled.roles.flatMap((r,i)=>r==='Values'?[i]:[]),nodes=new Map(),columns=new Map();
 const T=typeof module!=='undefined'?require('./table-rendering'):root.TablePresentation,E=typeof module!=='undefined'?require('./report-engine'):root.ReportEngine,source=visual&&compiled.roles.includes('Formatting')&&!state(visual).Formatting?E.formattingVisual(visual):visual,offsets={},ps=compiled.roles.map(role=>{const list=state(source)[role]?.projections||[],active=['Rows','Columns'].includes(role)?list:list.filter(p=>p.active!==false),index=offsets[role]||0;offsets[role]=index+1;return active[index]||{}}),bindingVisual={definition:{query:{queryState:{Values:{projections:ps}}}}};
 for(const [rowIndex,row] of result.rows.entries()){const path=ri.map(i=>row[i]),key=JSON.stringify(path),column=ci.map(i=>row[i]),ck=JSON.stringify(column);columns.set(ck,column);if(!nodes.has(key))nodes.set(key,{path,depth,label:path.length?path.at(-1):'Total',cells:new Map(),formats:new Map(),raw:new Map()});nodes.get(key).cells.set(ck,vi.map(i=>row[i]));nodes.get(key).raw.set(ck,T?T.datumFor(bindingVisual,compiled.labels||compiled.roles,row):Object.fromEntries((compiled.labels||compiled.roles).map((l,i)=>[l,row[i]])));nodes.get(key).formats.set(ck,vi.map(i=>result.rowFormats?.[rowIndex]?.[i]??compiled.formats?.[i]))}
 // A missing pivot tuple has blank values for every measure and formatting
 // input. Never inherit sibling measures from a different displayed column.
 for(const node of nodes.values())for(const [key,column] of columns)if(!node.raw.has(key)){
  const row=compiled.roles.map(()=>null);ri.forEach((index,i)=>row[index]=node.path[i]);ci.forEach((index,i)=>row[index]=column[i]);
  node.raw.set(key,T?T.datumFor(bindingVisual,compiled.labels||compiled.roles,row):Object.fromEntries((compiled.labels||compiled.roles).map((label,i)=>[label,row[i]])));
 }
 return {nodes:[...nodes.values()],columns,vi,ci,ri};
}
function sortNodes(nodes,sort){
 if(!sort)return nodes;
 const data=nodes.map(n=>[sort.columnKey===null?n.label:n.cells.get(sort.columnKey)?.[sort.measure]??null]);
 return root.TablePresentation.sortIndexes(data,0,sort.descending).map(i=>nodes[i]);
}
function sourceExpansionPaths(visual){
 const S=typeof module!=='undefined'?require('./report-style'):root.ReportStyle,paths=[];
 function visit(node,parent=[]){if(!node)return;const path=[...parent,...(node.identityValues||[]).map(v=>S.value(v))];if(node.isToggled===true&&path.length&&path.every(v=>v===null||['string','number','boolean'].includes(typeof v)))paths.push(JSON.stringify(path));for(const child of node.children||[])visit(child,path)}
 for(const state of visual.definition?.expansionStates||[])if(state.roles?.includes('Rows'))visit(state.root);
 return paths;
}
function title(model,visual){return root.ReportStyle.authoredTitle(model,visual)}
async function mount(el,model,visual,initial,load,{format,style,interactions,tooltips,state:saved={},isConnected=()=>el.isConnected}={}){
 const allRows=state(visual).Rows?.projections||[],rootData=groups(initial.result,initial.compiled,0,visual),columns=rootData.columns,compiled=initial.compiled;
 const valueIndices=rootData.vi,children=new Map(),expanded=new Set(saved.expanded||sourceExpansionPaths(visual)),loading=new Set(),errors=new Map();let totals=[],totalError='';
 const Style=root.ReportStyle,theme=model.theme||{},objects=Style.objects(model,visual),subtotalSettings=Style.props(objects,'subTotals'),rowHeaders=Style.props(objects,'rowHeaders'),columnFields=state(visual).Columns?.projections||[];
 async function withColumnTotals(queryVisual,data){
  if(!columnFields.length||Style.value(subtotalSettings.columnSubtotals,theme)===false)return data;
  const target=groups(data.result,data.compiled,0,queryVisual),leaves=[...target.columns.values()];
  for(let depth=columnFields.length-1;depth>=0;depth--){const q=structuredClone(queryVisual);(q.definition.query.queryState.Columns?.projections||[]).forEach((p,i)=>p.active=i<depth);
   const total=await load(q),summary=groups(total.result,total.compiled,0,q);
   for(const node of target.nodes){const sum=summary.nodes.find(n=>JSON.stringify(n.path)===JSON.stringify(node.path));if(!sum)continue;for(const [ck,path] of summary.columns){const key='__columnSubtotal__'+JSON.stringify(path);node.cells.set(key,sum.cells.get(ck));node.formats.set(key,sum.formats.get(ck));node.raw.set(key,sum.raw.get(ck));target.columns.set(key,[...path,'Total'])}}
  }
  const rank=([key,path])=>{const total=key.startsWith('__columnSubtotal__'),prefix=total?path.slice(0,-1):path;const index=leaves.findIndex(p=>prefix.every((v,i)=>JSON.stringify(p[i])===JSON.stringify(v)));return (index<0?leaves.length:index)+(total?leaves.filter(p=>prefix.every((v,i)=>JSON.stringify(p[i])===JSON.stringify(v))).length-.001*prefix.length:0)};
  target.columns=new Map([...target.columns].sort((a,b)=>rank(a)-rank(b)));
  return {matrixGroups:target,...data};
 }

 const readGroups=(data,depth)=>data.matrixGroups||groups(data.result,data.compiled,depth,visual);
 const heading=el.querySelector('h3'),note=initial.result.truncated?'<small>Matrix preview limited to 10,000 groups per level. Narrow filters for complete results.</small>':'';
 let sort=saved.sort||null;
 const sourceSort=visual.definition?.query?.sortDefinition?.sort?.[0],sourceField=JSON.stringify(sourceSort?.field),measureFields=(state(visual).Values?.projections||[]).filter(p=>p.active!==false),measureIndex=measureFields.findIndex(p=>JSON.stringify(p.field)===sourceField);
 if(sourceSort&&!saved.sort){if(allRows.some(p=>JSON.stringify(p.field)===sourceField))sort={columnKey:null,measure:0,descending:sourceSort.direction==='Descending'};else if(measureIndex>=0&&columns.size)sort={columnKey:columns.keys().next().value,measure:measureIndex,descending:sourceSort.direction==='Descending'}}
 function draw(){
  if(!isConnected())return;saved.expanded=[...expanded];saved.sort=sort;
  let rows=[],display=[];const count=Math.max(1,valueIndices.length),columnKeys=[...columns.keys()];
  function visit(nodes){for(const node of sortNodes(nodes,sort)){const key=JSON.stringify(node.path),canExpand=node.depth<allRows.length-1,open=expanded.has(key),label=node.label==null?'(Blank)':node.label;
   const cells=columnKeys.flatMap(ck=>valueIndices.length?valueIndices.map((vi,i)=>node.cells.get(ck)?.[i]??null):[null]);
   rows.push([label,...(open&&Style.value(subtotalSettings.rowSubtotals,theme)===false?cells.map(()=>null):cells)]);display.push(node);
   if(open)visit(children.get(key)||[]);
  }}visit(rootData.nodes);for(const node of totals){rows.push(['Total',...columnKeys.flatMap(ck=>valueIndices.map((vi,i)=>node.cells.get(ck)?.[i]??null))]);display.push(node)}
  const headers=['',...columnKeys.flatMap(ck=>valueIndices.length?valueIndices.map(vi=>[...(columnFields.length?[]:columns.get(ck)),compiled.labels[vi]].filter(x=>x!==null&&x!=='').join(' / ')):[columns.get(ck).join(' / ')])];
  const controls=[...el.querySelectorAll(':scope > .pbi-export,:scope > .pbi-filters')];
  el.innerHTML='<div class="tablewrap" style="overflow:auto;max-height:100%"><table class="pbi-matrix" aria-label="Matrix"><thead><tr>'+headers.map((h,i)=>'<th scope="col">'+esc(i?h:(allRows[0]?.displayName||allRows[0]?.nativeQueryRef||'Rows'))+'</th>').join('')+'</tr></thead><tbody>'+rows.map((row,index)=>{
   const node=display[index],key=JSON.stringify(node.path),canExpand=node.depth>=0&&node.depth<allRows.length-1;
   return '<tr data-pbi-total="'+(node.depth<0)+'" data-pbi-subtotal="'+(expanded.has(key)&&node.depth>=0)+'"><td style="padding-left:'+(node.depth*16+4)+'px">'+(canExpand?'<button type="button" data-matrix-node="'+index+'" aria-label="'+esc((expanded.has(key)?'Collapse ':'Expand ')+row[0])+'" aria-expanded="'+expanded.has(key)+'" style="padding:0 4px;margin-right:4px;border:0;background:transparent;color:inherit">'+(loading.has(key)?'…':expanded.has(key)?'−':'+')+'</button>':'')+esc(row[0])+(errors.has(key)?'<small role="alert"> '+esc(errors.get(key))+'</small>':'')+'</td>'+row.slice(1).map((x,i)=>'<td>'+(sparklineMarkup(x,{model,visual,projection:measureFields[i%count],datum:{_raw:node.raw.get(columnKeys[Math.floor(i/count)])||{}}})??esc(valueIndices.length?format(x,node.formats?.get(columnKeys[Math.floor(i/count)])?.[i%count]??compiled.formats?.[valueIndices[i%count]],{locale:model.reportSettings?.locale,dialect:typeof measureFields[i%count]?.format==='string'?'dotnet':'vba'}):x))+'</td>').join('')+'</tr>';
  }).join('')+'</tbody></table></div>'+note+(totalError?'<small role="note">Total unavailable: '+esc(totalError)+'</small>':'');
  if(heading)el.prepend(heading);for(const control of controls)el.appendChild(control);
  const styleVisual=structuredClone(visual);styleVisual._cellData=display.map(node=>[{},...columnKeys.flatMap(ck=>valueIndices.map(()=>{const raw=node.raw.get(ck)||{},datum={...raw};Object.defineProperty(datum,'__formatExpressions',{value:raw.__formatExpressions});Object.defineProperty(datum,'__formatScope',{value:{isSubtotal:ck.startsWith('__columnSubtotal__')}});return datum}))]);
  styleVisual.definition.query.queryState={Values:{projections:[allRows[0]||{},...columnKeys.flatMap(()=>measureFields.length?measureFields:[{}])]}};
  style(el,headers,rows,styleVisual);
  if(interactions)root.ChartInteractionAPI.attachRows(el,display.map(node=>node.depth<0?null:root.ChartInteractionAPI.rowIdentity(visual,null,{matrix:true,path:node.path})),interactions);
  // Sort siblings independently. Descendants follow their parent; totals stay at the bottom.
  for(const [i,th] of [...el.querySelectorAll('th')].entries()){
   th.querySelector('.pbi-sort-indicator')?.remove();
   const columnKey=i?columnKeys[Math.floor((i-1)/count)]:null,measure=i?(i-1)%count:0,active=sort?.columnKey===columnKey&&sort?.measure===measure;
   th.setAttribute('aria-sort',active?(sort.descending?'descending':'ascending'):'none');th.tabIndex=0;th.style.cursor='pointer';th.title='Sort loaded Matrix groups by '+th.textContent+' (no database query)';
   if(active){const arrow=document.createElement('span');arrow.className='pbi-sort-indicator';arrow.setAttribute('aria-hidden','true');arrow.textContent=sort.descending?' ▼':' ▲';th.appendChild(arrow)}
   const apply=()=>{sort={columnKey,measure,descending:active?!sort.descending:false};draw()};th.onclick=apply;th.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();apply()}};
  }
  for(const [i,tr] of [...el.querySelectorAll('tbody tr')].entries()){const cell=tr.cells[0];cell.style.textAlign='left';cell.style.paddingLeft=(Style.value(rowHeaders.steppedLayout,theme)===false?4:Math.max(0,display[i].depth)*16+4)+'px';if(display[i].depth<0)tr.style.fontWeight='bold';const S=root.ReportStyle,projection=allRows[Math.max(0,display[i].depth)],p=S?.resolveProperties(model,visual,'rowHeaders',{datum:{_projectionRef:projection?.queryRef,_raw:display[i].raw?.values().next().value||{}}}).properties;if(p){cell.style.color=S.color(p.fontColor,model.theme)||cell.style.color;cell.style.background=S.color(p.backColor,model.theme)||cell.style.background;cell.style.fontSize=(Number(S.value(p.fontSize,model.theme))>0?Number(S.value(p.fontSize,model.theme))*4/3:12)+'px'}}
  const head=el.querySelector('thead'),levels=Math.max(0,...[...columns.values()].map(p=>p.length));
  if(columnFields.length&&levels){const rows=[];for(let level=0;level<levels;level++){const tr=document.createElement('tr'),blank=document.createElement('th');blank.textContent=level===0?(allRows[0]?.nativeQueryRef||'Rows'):'';tr.append(blank);let previous,cell;for(const ck of columnKeys){const path=columns.get(ck),identity=JSON.stringify(path.slice(0,level+1));if(previous===identity){cell.colSpan+=count;continue}previous=identity;cell=document.createElement('th');cell.colSpan=count;cell.scope='colgroup';cell.textContent=String(path[level]??'');cell.style.background=Style.color(Style.props(objects,'columnHeaders').backColor,theme)||theme.background||'#fff';cell.style.color=Style.color(Style.props(objects,'columnHeaders').fontColor,theme)||theme.foreground||'#333';tr.append(cell)}rows.push(tr)}for(const row of rows.reverse())head.prepend(row)}
  for(const button of el.querySelectorAll('[data-matrix-node]'))button.onclick=async()=>{
   const node=display[+button.dataset.matrixNode],key=JSON.stringify(node.path);if(loading.has(key))return;
   if(expanded.has(key)){expanded.delete(key);draw();return}
   errors.delete(key);
   if(!children.has(key)){loading.add(key);draw();try{const query=plan(visual,node.depth+1,node.path),data=await withColumnTotals(query,await load(query));if(!isConnected())return;const next=readGroups(data,node.depth+1);for(const nextNode of next.nodes)nextNode.depth=node.depth+1;children.set(key,next.nodes);for(const [ck,col] of next.columns)columns.set(ck,col)}catch(e){if(e.name!=='AbortError')errors.set(key,e.message);return}finally{loading.delete(key);draw()}}
   expanded.add(key);draw();
  };
  if(Style.value(rowHeaders.steppedLayout,theme)===false&&allRows.length>1){
   const header=el.querySelector('thead tr:last-child'),first=header.cells[0],anchor=first.nextSibling;
   first.textContent=allRows[0]?.nativeQueryRef||allRows[0]?.displayName||'Rows';
   for(let level=1;level<allRows.length;level++){const th=document.createElement('th');th.textContent=allRows[level]?.nativeQueryRef||allRows[level]?.displayName||'Level '+(level+1);th.scope='col';th.style.cssText=first.style.cssText;th.onclick=first.onclick;th.onkeydown=first.onkeydown;header.insertBefore(th,anchor)}
   for(const [i,row] of [...el.querySelectorAll('tbody tr')].entries()){const cell=row.cells[0],anchor=cell.nextSibling;cell.remove();for(let level=0;level<allRows.length;level++){const td=level===Math.max(0,display[i].depth)?cell:document.createElement('td');td.style.paddingLeft='4px';row.insertBefore(td,anchor)}}
   for(const row of el.querySelectorAll('thead tr:not(:last-child)'))row.cells[0].colSpan=allRows.length;
  }
  if(tooltips){
   const identity=(node,column=[])=>root.ChartInteractionAPI.matrixTooltipIdentity(visual,node.depth<0?[]:node.path,column);
   const rowHeaderCount=Style.value(rowHeaders.steppedLayout,theme)===false&&allRows.length>1?allRows.length:1;
   root.ChartInteractionAPI.bindRowTooltips(el,display.map(node=>[
    ...Array.from({length:rowHeaderCount},()=>identity(node)),
    ...columnKeys.flatMap(key=>{const path=columns.get(key)||[],column=key.startsWith('__columnSubtotal__')?path.slice(0,-1):path;return Array.from({length:count},()=>identity(node,column))})
   ]),tooltips);
  }
 }draw();
 // Keep a selected descendant visible when cross-filtering redraws the page.
 const selection=interactions?.selection;
 if(saved.expanded?.length||selection&&selection.fields.length>1){
  const paths=new Map((saved.expanded||[]).map(key=>[key,JSON.parse(key)]));for(const tuple of selection?.tuples||[])for(let depth=1;depth<tuple.length;depth++)paths.set(JSON.stringify(tuple.slice(0,depth)),tuple.slice(0,depth));
  for(const [key,path] of [...paths].sort((a,b)=>a[1].length-b[1].length).slice(0,100)){
   const nodes=path.length===1?rootData.nodes:children.get(JSON.stringify(path.slice(0,-1)))||[];
   if(!nodes.some(node=>JSON.stringify(node.path)===key))continue;
   try{const query=plan(visual,path.length,path),data=await withColumnTotals(query,await load(query));if(!isConnected())return;const next=readGroups(data,path.length);for(const nextNode of next.nodes)nextNode.depth=path.length;children.set(key,next.nodes);for(const [ck,col] of next.columns)columns.set(ck,col);expanded.add(key)}catch(e){if(e.name!=='AbortError')errors.set(key,e.message)}
  }draw();
 }
 if(columnFields.length){try{const enhanced=await withColumnTotals(plan(visual),initial),groups=readGroups(enhanced,0);rootData.nodes=groups.nodes;columns.clear();for(const [key,col] of groups.columns)columns.set(key,col);draw()}catch(error){totalError='Column totals: '+error.message;draw()}}
 const S=root.ReportStyle,settings=S?.props(S.objects(model,visual),'subTotals')||{};
 if(valueIndices.length&&allRows.length&&S?.value(settings.rowSubtotals,model.theme)!==false){try{const query=plan(visual,-1),total=await withColumnTotals(query,await load(query));totals=readGroups(total,-1).nodes;for(const node of totals)node.depth=-1;draw()}catch(e){if(e.name!=='AbortError'){totalError=e.message;draw()}}}
}
const api={sourceExpansionPaths,sparklineSettings,sparklineMarkup,plan,groups,mount,sortNodes,title};if(typeof module!=='undefined')module.exports=api;root.MatrixRenderer=api;
})(globalThis);
