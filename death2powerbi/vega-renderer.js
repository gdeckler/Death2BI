/* Power BI query results -> locally hosted Vega-Lite specifications. */
(function(root){
const Formats=typeof module!=='undefined'?require('./model-formats.js'):root.ModelFormats;
const Advanced=typeof module!=='undefined'?require('./advanced-charts.js'):root.AdvancedCharts;
const types=['clusteredColumnChart','clusteredBarChart','columnChart','barChart','stackedColumnChart','stackedBarChart','hundredPercentStackedColumnChart','hundredPercentStackedBarChart','lineChart','areaChart','stackedAreaChart','pieChart','donutChart','scatterChart','lineClusteredColumnComboChart','lineStackedColumnComboChart','heatmap','heatmapChart','histogram','histogramChart','boxplot','boxPlot','waterfallChart','funnel','funnelChart',...Advanced.types.filter(t=>t!=='scatterChart')];
const palette=['#337b60','#9dbd67','#4e8fa6','#c89849','#8b6aa8','#ca7b70','#568475','#889ab5'];
function dataLabelOptions(definition={}){
 const entries=[...(definition.objects?.labels||[]),...(definition.objects?.dataLabels||[])];
 const properties=Object.assign({},...entries.filter(e=>!e.selector).map(e=>e.properties||{}));
 const value=x=>{if(x?.expr)x=x.expr;const literal=x?.Literal?.Value;if(literal!==undefined){if(literal==='true'||literal==='false')return literal==='true';if(/^[-+]?\d+(?:\.\d+)?[dDlLmM]?$/.test(literal))return Number(literal.replace(/[dDlLmM]$/,''));return String(literal).replace(/^'|'$/g,'').replaceAll("''", "'")}return typeof x==='object'?undefined:x};
 const color=value(properties.color?.solid?.color)||value(properties.color);
 return {show:value(properties.show)===true,fontSize:value(properties.fontSize),fontFamily:value(properties.fontFamily),color:typeof color==='string'?color:undefined,precision:value(properties.labelPrecision??properties.decimalPlaces),units:value(properties.labelDisplayUnits??properties.displayUnits),position:value(properties.labelPosition??properties.position)};
}
function labelText(value,format,settings){
 if(value==null)return '';
 const percent=Formats.d3(format)?.endsWith('%');
 const units=!percent&&Number(settings.units)>1?Number(settings.units):1;
 const precision=Number.isInteger(settings.precision)&&settings.precision>=0&&settings.precision<=20?settings.precision:null;
 const text=precision===null?Formats.text(value/units,format):new Intl.NumberFormat('en-US',{minimumFractionDigits:precision,maximumFractionDigits:precision,useGrouping:true,style:percent?'percent':'decimal'}).format(value/units);
 return text+({1000:'K',1000000:'M',1000000000:'B',1000000000000:'T'}[units]||'');
}

function buildSpec(type,labels,rows,roles=[],options={}){
 const spec=buildRaw(type,labels,rows,roles,options);
 function walk(node){if(!node||typeof node!=='object')return;
  if(node.type==='quantitative'&&node.title){const i=labels.indexOf(node.title),f=Formats.d3(options.formats?.[i]);if(f){node.format=f;if(node.axis!==null)node.axis={...node.axis,format:f};if(node.legend!==null)node.legend={...node.legend,format:f}}}
  for(const value of Object.values(node))if(value&&typeof value==='object')walk(value);
 }
 walk(spec);return spec;
}
function buildRaw(type,labels,rows,roles=[],options={}){
 if(!types.includes(type))throw Error('No Vega-Lite mapping for '+type);
 const width=Math.max(80,options.width||500),height=Math.max(80,options.height||280);
 const spec={$schema:'https://vega.github.io/schema/vega-lite/v6.json',width,height,autosize:{type:'fit',contains:'padding',resize:true},background:'transparent',config:{view:{stroke:null},font:'DM Sans, sans-serif',axis:{labelColor:'#627668',titleColor:'#344e40',gridColor:'#e6ece3',labelLimit:110,labelOverlap:'greedy',labelSeparation:4,titleFontSize:11,labelFontSize:10},axisQuantitative:{format:'~s'},legend:{orient:'bottom',labelColor:'#627668',title:null,labelLimit:150},range:{category:palette}},data:{values:[]}};
 if(!rows.length){spec.data.values=[{label:'No data for the current filters.'}];spec.mark={type:'text',color:'#788884'};spec.encoding={text:{field:'label'}};return spec}
 const numeric=labels.map((_,i)=>i).filter(i=>rows.some(r=>typeof r[i]==='number'&&Number.isFinite(r[i])));
 if(Advanced.types.includes(type))return Advanced.build(spec,type,labels,rows,roles,options);
 const distribution=['histogram','histogramChart','boxplot','boxPlot'].includes(type);
 let ci=roles.findIndex(r=>['Category','Rows','X'].includes(r));
 if(ci<0)ci=distribution?(labels.length>1?labels.findIndex((_,i)=>!numeric.includes(i)):-1):0;
 let si=roles.findIndex(r=>['Series','Legend','Columns'].includes(r));
 if(si===ci)si=-1;
 let vi=numeric.filter(i=>i!==ci&&i!==si);
 if(!vi.length&&distribution)vi=numeric.slice(0,1);
 if(!vi.length&&rows.length)throw Error('The chart query did not return a numeric value field.');
 // Empty results still get a valid quantitative field and clear empty-state UI.
 if(!vi.length)vi=[Math.max(0,labels.length-1)];
 const values=[];
 for(const row of rows)for(const i of vi){
  if(row[i]!==null&&row[i]!==undefined&&typeof row[i]!=='number')throw Error('Chart value fields must be numeric.');
  values.push({_category:ci>=0?row[ci]??'(Blank)':'All',_categoryValue:ci>=0?row[ci]:undefined,_dimension:si>=0?row[si]:undefined,_value:row[i],_formattedValue:Formats.text(row[i],options.formats?.[i]),_label:labelText(row[i],options.formats?.[i],options.dataLabels||{}),_series:(si>=0?String(row[si]??'(Blank)')+(vi.length>1?' · ':''):'')+(vi.length>1||si<0?labels[i]:''),_role:roles[i]||'Y'});
 }
 spec.data.values=values;
 const categories=[...new Set(values.map(r=>r._category))],series=[...new Set(values.map(r=>r._series))];
 const temporal=ci>=0&&['lineChart','areaChart','stackedAreaChart'].includes(type)&&(/DATE|TIMESTAMP/.test(options.fieldTypes?.[ci]||'')||rows.every(r=>r[ci]==null||typeof r[ci]==='string'&&/^\d{4}-\d\d-\d\d(?:$|[ T])/.test(r[ci])));
 const category={field:'_category',type:temporal?'temporal':'nominal',title:ci>=0?labels[ci]:null,...(temporal?{}:{sort:categories})};
 const quantity={field:'_value',type:'quantitative',title:vi.length===1?labels[vi[0]]:null};
 const color={field:'_series',type:'nominal',sort:series,legend:series.length>1?{}:null};
 const tooltip=[{field:'_category',type:'nominal',title:ci>=0?labels[ci]:'Category'},{field:'_series',type:'nominal',title:'Series'},{field:'_formattedValue',type:'nominal',title:'Value'}];
 if(['histogram','histogramChart'].includes(type)){
  if(vi.length!==1)throw Error('Histograms require one numeric field.');
  spec.mark={type:'bar',tooltip:true};spec.encoding={x:{field:'_value',type:'quantitative',bin:{maxbins:20},title:labels[vi[0]]},y:{aggregate:'count',type:'quantitative',title:'Query row count'},tooltip:[{field:'_value',bin:true,type:'quantitative',title:labels[vi[0]]},{aggregate:'count',type:'quantitative',title:'Count'}]};return spec;
 }
 if(['boxplot','boxPlot'].includes(type)){
  spec.mark={type:'boxplot',extent:1.5,tooltip:true};spec.encoding={y:quantity};
  if(ci>=0)spec.encoding.x=category;if(series.length>1)spec.encoding.color=color;return spec;
 }
 if(['heatmap','heatmapChart'].includes(type)){
  spec.mark={type:'rect',tooltip:true};spec.encoding={x:category,y:{field:'_series',type:'nominal',title:si>=0?labels[si]:'Series'},color:{field:'_value',type:'quantitative',title:quantity.title,scale:{scheme:'greens'}},tooltip};return spec;
 }
 if(['pieChart','donutChart'].includes(type)){
  if(series.length>1)throw Error('Pie/donut charts require one numeric series.');
  if(values.some(v=>v._value<0))throw Error('Pie/donut charts cannot represent negative values.');
  spec.mark={type:'arc',innerRadius:type==='donutChart'?Math.min(width,height)*.22:0,tooltip:true};spec.encoding={theta:{...quantity,stack:true},color:{field:'_category',type:'nominal',sort:categories},order:{field:'_category',sort:'ascending'},tooltip};return spec;
 }
 if(['waterfallChart','funnel','funnelChart'].includes(type)){
  if(series.length>1)throw Error('This chart needs one value series; breakdowns need further mapping.');
  let total=0;spec.data.values=values.map(v=>{const n=v._value||0,start=type==='waterfallChart'?total:-n/2,end=type==='waterfallChart'?total+n:n/2;total+=n;return {...v,_start:start,_end:end,_kind:n<0?'Decrease':'Increase'}});
  if(type==='waterfallChart'){
   spec.mark={type:'bar',tooltip:true};spec.encoding={x:category,y:{field:'_start',type:'quantitative',title:quantity.title},y2:{field:'_end'},color:{field:'_kind',type:'nominal',scale:{domain:['Increase','Decrease'],range:['#337b60','#c46c5f']}},tooltip};
  }else{
   if(values.some(v=>v._value<0))throw Error('Funnel charts require nonnegative values.');
   spec.mark={type:'bar',tooltip:true};spec.encoding={y:category,x:{field:'_start',type:'quantitative',axis:null},x2:{field:'_end'},color:{field:'_category',type:'nominal',legend:null},tooltip};
  }return spec;
 }
 const combo=/ComboChart$/.test(type),horizontal=/BarChart$/.test(type)||type==='barChart',line=['lineChart','areaChart','stackedAreaChart'].includes(type);
 const stacked=/stacked/i.test(type)||['columnChart','barChart'].includes(type),normalize=/hundredPercent/.test(type);
 if(combo){
  if(!values.some(r=>r._role==='Y2')||!values.some(r=>r._role!=='Y2'))throw Error('Combination charts need column and line value roles.');
  const bar={transform:[{filter:"datum._role !== 'Y2'"}],mark:{type:'bar',tooltip:true},encoding:{x:category,y:{...quantity,stack:stacked?'zero':null},color,tooltip}};
  if(!stacked)bar.encoding.xOffset={field:'_series',type:'nominal'};
  const curve={transform:[{filter:"datum._role === 'Y2'"}],mark:{type:'line',point:true,tooltip:true},encoding:{x:category,y:{...quantity,axis:{orient:'right'}},color,tooltip}};
  spec.layer=[bar,curve];spec.resolve={scale:{y:'independent'}};return spec;
 }
 spec.mark={type:line?(type==='lineChart'?'line':'area'):'bar',tooltip:true,...(line?{point:type==='lineChart'}:{})};
 spec.encoding=horizontal?{y:category,x:{...quantity,stack:stacked?(normalize?'normalize':'zero'):null},color,tooltip}:{x:category,y:{...quantity,stack:stacked?(normalize?'normalize':'zero'):null},color,tooltip};
 if(!stacked&&!line&&series.length>1)spec.encoding[horizontal?'yOffset':'xOffset']={field:'_series',type:'nominal'};
 if(line&&!stacked)spec.encoding.y.stack=null;
 if(!line&&options.dataLabels?.show){
  const settings=options.dataLabels,bar={mark:spec.mark,encoding:spec.encoding};
  const labelEncoding={...spec.encoding,text:{field:'_label',type:'nominal'}};delete labelEncoding.color;
  const mark={type:'text',color:settings.color||'#344e40',fontSize:Math.max(1,Math.min(160,(Number(settings.fontSize)||9)*4/3)),...(settings.fontFamily?{font:settings.fontFamily}:{}),tooltip:true};
  const inside=/inside/i.test(settings.position||'');
  if(stacked){
   spec.transform=[{stack:'_value',groupby:['_category'],sort:[{field:'_series',order:'ascending'}],offset:normalize?'normalize':'zero',as:['_stackStart','_stackEnd']},{calculate:'(datum._stackStart + datum._stackEnd)/2',as:'_labelPosition'}];
   bar.encoding[horizontal?'x':'y']={...quantity,field:'_stackEnd',stack:null};bar.encoding[horizontal?'x2':'y2']={field:'_stackStart'};
   labelEncoding[horizontal?'x':'y']={...quantity,field:'_labelPosition',stack:null};
   if(normalize){spec.transform.push({calculate:"datum._value == null ? '' : format(abs(datum._stackEnd-datum._stackStart), '."+(Number.isInteger(settings.precision)?Math.max(0,Math.min(20,settings.precision)):0)+"%')",as:'_label'});bar.encoding[horizontal?'x':'y'].axis={format:'.0%'}}
   mark.align='center';mark.baseline='middle';
  }else if(horizontal){mark.align={expr:inside?"datum._value < 0 ? 'left' : 'right'":"datum._value < 0 ? 'right' : 'left'"};mark.dx={expr:(inside?'-':'')+"(datum._value < 0 ? -4 : 4)"};mark.baseline='middle'}
  else{mark.baseline={expr:inside?"datum._value < 0 ? 'bottom' : 'top'":"datum._value < 0 ? 'top' : 'bottom'"};mark.dy={expr:(inside?'-':'')+"(datum._value < 0 ? 4 : -4)"}}
  spec.layer=[bar,{transform:[{filter:'isValid(datum._value)'}],mark,encoding:labelEncoding}];delete spec.mark;delete spec.encoding;
 }

 return spec;
}
const mapViews=new Map(),mapTypes=new Set(['map','pointMap','filledMap','choroplethMap']);
function mountMapControls(element,view,initial,key,item){
 let state=Advanced.mapViewport(initial),drag=null,frame=0;
 const svg=element.querySelector('svg'),controls=document.createElement('div'),status=document.createElement('output');
 if(!svg)return;
 element.style.position='relative';element.tabIndex=0;element.setAttribute('aria-label','Interactive map. Plus and minus zoom, arrow keys pan, Home resets.');
 controls.className='map-controls';controls.setAttribute('role','group');controls.setAttribute('aria-label','Map navigation');
 controls.style.cssText='position:absolute;top:6px;right:6px;z-index:2;display:flex;flex-wrap:wrap;gap:3px;align-items:center;max-width:calc(100% - 12px);padding:4px;background:rgba(255,255,255,.94);border:1px solid #dfe7e3;border-radius:6px;box-shadow:0 1px 4px #193a3718';
 status.setAttribute('aria-label','Map zoom');status.setAttribute('aria-live','polite');status.style.cssText='font:11px system-ui;min-width:36px;text-align:center;color:#193a37';
 const buttons={};
 function apply(next){
  state=Advanced.mapViewport(next);status.textContent=Math.round(state.zoom*100)+'%';
  buttons.plus.disabled=state.zoom>=32;buttons.minus.disabled=state.zoom<=1;
  if(key){mapViews.delete(key);mapViews.set(key,{...state});if(mapViews.size>200)mapViews.delete(mapViews.keys().next().value)}
  if(!frame)frame=requestAnimationFrame(()=>{frame=0;if(element.isConnected)view.signal('mapZoom',state.zoom).signal('mapPanX',state.x).signal('mapPanY',state.y).runAsync().catch(()=>{})});
 }
 function zoom(factor){const next=Math.max(1,Math.min(32,state.zoom*factor)),ratio=next/state.zoom;apply({zoom:next,x:state.x*ratio,y:state.y*ratio})}
 function button(text,label,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-label',label);b.title=label;b.style.cssText='width:26px;height:26px;padding:0;line-height:1;font:16px system-ui;border:1px solid #dfe7e3;border-radius:4px;background:white;color:#193a37';b.onclick=event=>{event.stopPropagation();action()};controls.appendChild(b);return b}
 buttons.plus=button('+','Zoom in map',()=>zoom(2));buttons.minus=button('−','Zoom out map',()=>zoom(.5));controls.appendChild(status);
 button('↺','Reset map view',()=>apply({zoom:1,x:0,y:0}));
 button('←','Pan map left',()=>apply({...state,x:state.x+.15}));button('→','Pan map right',()=>apply({...state,x:state.x-.15}));
 button('↑','Pan map up',()=>apply({...state,y:state.y+.15}));button('↓','Pan map down',()=>apply({...state,y:state.y-.15}));
 element.appendChild(controls);svg.style.touchAction='none';svg.style.cursor='grab';
 function down(event){if(event.button!==0||!event.isPrimary)return;drag={id:event.pointerId,px:event.clientX,py:event.clientY,x:state.x,y:state.y};item.suppressClick=false}
 function move(event){if(!drag||drag.id!==event.pointerId)return;const dx=event.clientX-drag.px,dy=event.clientY-drag.py;if(!item.suppressClick&&Math.hypot(dx,dy)<4)return;item.suppressClick=true;try{svg.setPointerCapture(event.pointerId)}catch{}svg.style.cursor='grabbing';const box=svg.getBoundingClientRect();apply({...state,x:drag.x+dx/Math.max(1,box.width),y:drag.y+dy/Math.max(1,box.height)})}
 function up(event){if(drag?.id!==event.pointerId)return;drag=null;svg.style.cursor='grab';try{if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId)}catch{}}
 function keyboard(event){if(event.target!==element&&event.target!==svg)return;const actions={'+':()=>zoom(2),'=':()=>zoom(2),'-':()=>zoom(.5),'ArrowLeft':()=>apply({...state,x:state.x+.15}),'ArrowRight':()=>apply({...state,x:state.x-.15}),'ArrowUp':()=>apply({...state,y:state.y+.15}),'ArrowDown':()=>apply({...state,y:state.y-.15}),'Home':()=>apply({zoom:1,x:0,y:0})};if(actions[event.key]){event.preventDefault();event.stopPropagation();actions[event.key]()}}
 svg.addEventListener('pointerdown',down);svg.addEventListener('pointermove',move);svg.addEventListener('pointerup',up);svg.addEventListener('pointercancel',up);element.addEventListener('keydown',keyboard);
 item.cleanup=()=>{if(frame)cancelAnimationFrame(frame);controls.remove();svg.removeEventListener('pointerdown',down);svg.removeEventListener('pointermove',move);svg.removeEventListener('pointerup',up);svg.removeEventListener('pointercancel',up);element.removeEventListener('keydown',keyboard)};
 status.textContent=Math.round(state.zoom*100)+'%';buttons.plus.disabled=state.zoom>=32;buttons.minus.disabled=state.zoom<=1;
}

const active=new Set();
function disposeAll(){for(const item of active){item.observer?.disconnect();item.cleanup?.();item.view.finalize()}active.clear()}
async function mount(element,type,labels,rows,roles,options={}){
 if(!root.vegaEmbed)throw Error('Local Vega libraries did not load. Restart the updated server and refresh the page.');
 const width=Math.max(80,element.clientWidth),height=Math.max(80,element.clientHeight);
 const mapState=mapViews.get(options.mapKey)||options.mapViewport;
 const spec=buildSpec(type,labels,rows,roles,{...options,width,height,mapViewport:mapState});
 if(options.onSelect){
  for(const datum of spec.data.values)datum._selected=options.matchesDatum?options.matchesDatum(datum):true;
  const opacity={condition:{test:'datum._selected',value:1},value:.25};
  if(spec.encoding)spec.encoding.opacity=opacity;
  for(const layer of spec.layer||[])if(!layer.data){layer.encoding=layer.encoding||{};layer.encoding.opacity=opacity}
 }
 const result=await root.vegaEmbed(element,spec,{actions:false,renderer:'svg',tooltip:true});
 if(!element.isConnected){result.view.finalize();return}
 const item={view:result.view};active.add(item);
 if(mapTypes.has(type)&&spec.projection)mountMapControls(element,result.view,mapState,options.mapKey,item);
 if(options.onSelect){
  const activeItem=item;
  element.style.cursor='pointer';
  result.view.addEventListener('click',(event,item)=>{
   if(mapTypes.has(type)&&activeItem.suppressClick){activeItem.suppressClick=false;return}
   const role=item?.mark?.role||'';
   if(role.startsWith('axis')||role.startsWith('legend'))return;
   if(item?.datum&&Object.prototype.hasOwnProperty.call(item.datum,'_categoryValue'))options.onSelect(item.datum,event);
   else if(!item||['frame','scope'].includes(role))options.onClear?.();
  });
 }
 if(root.ResizeObserver){item.observer=new ResizeObserver(entries=>{if(!element.isConnected){item.observer.disconnect();item.cleanup?.();item.view.finalize();active.delete(item);return}const {width,height}=entries[0].contentRect;if(width>0&&height>0)item.view.width(Math.max(80,width)).height(Math.max(80,height)).resize().runAsync().catch(()=>{})});item.observer.observe(element)}
 return result.view;
}
const api={types,buildSpec,mount,disposeAll,dataLabelOptions};if(typeof module!=='undefined')module.exports=api;root.VegaRenderer=api;
})(globalThis);
