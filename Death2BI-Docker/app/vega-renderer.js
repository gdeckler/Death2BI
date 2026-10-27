/* Power BI query results -> locally hosted Vega-Lite specifications. */
(function(root){
const Style=typeof module!=='undefined'?require('./report-style.js'):root.ReportStyle;
const Formats=typeof module!=='undefined'?require('./model-formats.js'):root.ModelFormats;
const Advanced=typeof module!=='undefined'?require('./advanced-charts.js'):root.AdvancedCharts;
const types=['gauge','hundredPercentStackedAreaChart','treemap','ribbonChart','violinPlot','clusteredColumnChart','clusteredBarChart','columnChart','barChart','stackedColumnChart','stackedBarChart','hundredPercentStackedColumnChart','hundredPercentStackedBarChart','lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart','pieChart','donutChart','scatterChart','lineClusteredColumnComboChart','lineStackedColumnComboChart','heatmap','heatmapChart','histogram','histogramChart','boxplot','boxPlot','waterfallChart','funnel','funnelChart',...Advanced.types.filter(t=>t!=='scatterChart')];
const palette=['#337b60','#9dbd67','#4e8fa6','#c89849','#8b6aa8','#ca7b70','#568475','#889ab5'];
// VegaEmbed skips installing a handler for false, leaving Vega's native title tooltip active.
function suppressDefaultTooltip(){}
function dataLabelOptions(definition={},theme={}){
 const properties={...Style.props(definition.objects,'labels'),...Style.props(definition.objects,'dataLabels')},value=x=>Style.value(x,theme),color=Style.color(properties.color||properties.fontColor,theme);
 return {show:value(properties.show??properties.enableValueDataLabel)===true,showSpecified:value(properties.show??properties.enableValueDataLabel)!==undefined,labelStyle:value(properties.labelStyle),fontSize:value(properties.fontSize??properties.detailFontSize),fontFamily:value(properties.fontFamily),color,precision:value(properties.labelPrecision??properties.decimalPlaces??properties.detailLabelPrecision),units:value(properties.labelDisplayUnits??properties.displayUnits),position:value(properties.labelPosition??properties.position)};
}
function autoUnits(n,currency=false){return n>=(currency?1e11:1e12)?1e12:n>=(currency?1e8:1e9)?1e9:n>=(currency?1e5:1e6)?1e6:n>=1e3?1e3:1}
function labelText(value,format,settings){
 if(value==null)return '';
 format=settings.format??format;const adjusted={...settings};if(adjusted.units>1&&adjusted.precision===undefined&&/\.[0#]*#/.test(format||'#,0.##'))adjusted.precision=2;return Formats.text(value,format||'#,0.##',adjusted);
}

function visibleRows(rows,roles,options={}){
 const projections=Object.values(options.visual?.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false));
 const valueRoles=new Set(['Y','Y2','Values','Value','ColumnY','LineY','Size','X']);
 const measures=projections.map((p,i)=>valueRoles.has(roles[i])&&(p.field?.Measure||p.field?.Aggregation)?i:-1).filter(i=>i>=0);
 if(measures.length&&!projections.some(p=>p.showAll===true||p.showItemsWithNoData===true))rows=rows.filter(row=>measures.some(i=>row[i]!==null&&row[i]!==undefined));
 return rows;
}
function buildSpec(type,labels,rows,roles=[],options={}){
 options={...options,_rowFormatMap:options._rowFormatMap||new Map(rows.map((row,i)=>[row,options.rowFormats?.[i]]))};
 rows=visibleRows(rows,roles,options);
 const spec=buildRaw(type,labels,rows,roles,options);if(options.model?.reportSettings?.defaultDisplayUnitsToNone){spec.config=spec.config||{};spec.config.axisQuantitative={...spec.config.axisQuantitative,format:',.6~f'}}
 const projections=Object.values(options.visual?.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false));
 function walk(node,secondary=false){if(!node||typeof node!=='object')return;if(node.name==='pbi_secondary_y'||node.axis?.orient==='right')secondary=true;else if(node.name==='pbi_primary_y')secondary=false;
  if(node.type==='quantitative'&&(node.title||node.field==='_value')){let i=labels.indexOf(node.title);if(i<0&&node.field==='_value')i=roles.findIndex(role=>secondary?['Y2','LineY'].includes(role):['Y','Value','Values','ColumnY'].includes(role));const f=Formats.d3(options.formats?.[i]),theme=options.model?.theme||{},axis=options.visual?(roles[i]==='X'?Style.props(Style.objects(options.model||{},options.visual),'categoryAxis'):Style.axisSource(options.model||{},options.visual,secondary||['Y2','LineY'].includes(roles[i]),{_projectionRef:projections[i]?.queryRef})):{};
   if(f){node.format=f;if(node.axis!==null)node.axis={...node.axis,format:f};if(node.legend!==null)node.legend={...node.legend,format:f}}
   const precision=Style.value(axis.labelPrecision,theme);if(String(options.formats?.[i]).includes('%')&&Number.isInteger(precision)&&node.axis!==null)node.axis={...node.axis,format:'.'+Math.max(0,Math.min(20,precision))+'%'};
   if(i>=0&&['X','Y','Y2','Value','Values','ColumnY','LineY'].includes(roles[i])&&!String(options.formats?.[i]).includes('%')&&node.axis!==null){const authored=Style.value(axis.labelDisplayUnits,theme),currency=(options.formats?.[i]||'').match(/[$€£¥]/)?.[0]||'',largest=Math.max(0,...rows.map(r=>Math.abs(r[i]||0))),extent=Math.max(largest,Math.abs(Number(Style.value(axis.end??axis.maximum??axis.max,theme)))||0),step=extent?10**Math.floor(Math.log10(extent)):1,rounded=Math.ceil(extent/step)*step,units=authored>0?authored:authored===undefined&&options.model?.reportSettings?.defaultDisplayUnitsToNone?1:options._axisUnits||autoUnits(rounded,!!currency),digits=precision??(units>1?1:undefined);if(units>1){const suffix={1000:'K',1000000:'M',1000000000:'B',1000000000000:'T'}[units]||'';node.axis={...node.axis,tickCount:3,labelExpr:JSON.stringify(currency)+' + format(datum.value / '+units+', '+JSON.stringify('.'+(digits??1)+'f')+') + '+JSON.stringify(suffix)}}}
  }
  for(const value of Object.values(node))if(value&&typeof value==='object')walk(value,secondary);
 }
 walk(spec);let styled=options.model&&options.visual?Style.applySpec(spec,options.model,options.visual,labels,rows,roles):spec;
 fitXAxisLabels(styled,type,options);
 styled=applyErrors(styled,type,labels,rows,roles,options);styled=applyBarLabels(styled,type,labels,options);styled=applyLineLabels(styled,type,options);styled=applyPlotImage(styled,options);styled=applyReferenceBands(styled,type,options);styled=applyTrends(styled,type,options);fitLegends(styled,type,options);if(options._multipleDomain&&!styled.usermeta?.secondaryAxes){const apply=n=>{if(!n||typeof n!=='object')return;for(const channel of ['x','y']){const e=n.encoding?.[channel];if(['_value','_stackEnd'].includes(e?.field)&&e.type==='quantitative'&&!e.scale?.domain&&!Number.isFinite(e.scale?.domainMin)&&!Number.isFinite(e.scale?.domainMax))e.scale={...e.scale,domain:options._multipleDomain,nice:false}};Object.values(n).forEach(x=>x&&typeof x==='object'&&apply(x))};apply(styled)}if(type==='hundredPercentStackedAreaChart'){const fix=n=>{if(!n||typeof n!=='object')return;if(n.encoding?.y?.field==='_value'&&n.encoding.y.axis!==null)n.encoding.y.axis={...n.encoding.y.axis,format:'.0%'};Object.values(n).forEach(x=>x&&typeof x==='object'&&fix(x))};fix(styled)}return styled;
}
function fitXAxisLabels(spec,type,options={}){
 // Vega's categorical default is vertical even for two short labels. Compare
 // the actual neighbouring label widths with category spacing instead. Width
 // expressions keep this choice responsive when an existing view is resized.
 let context;
 try{context=typeof document!=='undefined'?document.createElement('canvas').getContext?.('2d'):null}catch{}
 const measured=new Map(),seen=new Set(),config=spec.config||{},height=Number(spec.height)||Number(options.height)||280;
 function walk(node,inherited){
  if(!node||typeof node!=='object')return;
  const values=node.data?.values||inherited||[],field=node.encoding?.x;
  if(field&&['nominal','ordinal'].includes(field.type)&&field.field&&field.axis!==null&&!seen.has(field)){
   seen.add(field);const axis=field.axis||{},defaults={...config.axis,...config.axisX};
   // Authored/theme angles and hidden labels remain authoritative.
   if(axis.labelAngle===undefined&&defaults.labelAngle===undefined&&axis.labels!==false){
    const scale=field.scale||{},domain=Array.isArray(scale.domain)?scale.domain:Array.isArray(field.sort)?field.sort:[...new Set(values.map(d=>d[field.field]))];
    if(domain.length){
     const font=Number(axis.labelFontSize??defaults.labelFontSize)||10,family=axis.labelFont??defaults.labelFont??config.font??'sans-serif',weight=axis.labelFontWeight??defaults.labelFontWeight??'normal',style=axis.labelFontStyle??defaults.labelFontStyle??'normal',limit=Number(axis.labelLimit??defaults.labelLimit??180),gap=Math.max(4,Number(axis.labelSeparation??defaults.labelSeparation)||0)+2;
     if(context)context.font=style+' '+weight+' '+font+'px '+family;
     const measure=text=>{const key=[font,family,weight,style,text].join('\u0000');if(!measured.has(key)){const width=Math.max(0,...text.split('\n').map(line=>context?context.measureText(line).width:[...line].reduce((sum,c)=>sum+(/[^\u0000-\u00ff]/.test(c)?1:/[ilI1.,'`|! ]/.test(c)?.3:/[MW@%]/.test(c)?.9:.58)*font,0)));measured.set(key,width)}return Math.min(measured.get(key),limit>0?limit:Infinity)};
     const texts=domain.map(value=>String(value??'')),widths=texts.map(measure),lineHeight=Number(axis.labelLineHeight??defaults.labelLineHeight)||font*1.15,budget=Math.max(font*1.5,Math.min(90,height*.25));
     // Wrap at word boundaries into at most two lines before rotating. Keep
     // custom label expressions intact, and do not trade away a short plot.
     const wrapping=axis.labelExpr===undefined&&defaults.labelExpr===undefined&&budget>=lineHeight*2&&texts.some(text=>/\S\s+\S/.test(text));
     const metrics=texts.map((text,i)=>{const words=text.trim().split(/\s+/),middle=Math.ceil(words.length/2),lines=wrapping&&words.length>1?[words.slice(0,middle).join(' '),words.slice(middle).join(' ')]:[text];return {width:wrapping?Math.max(...lines.map(measure)):widths[i],height:lines.length*lineHeight}});
     const mark=typeof node.mark==='string'?node.mark:node.mark?.type,point=scale.type==='point'||scale.type!=='band'&&(/line|area|ribbon|strip/i.test(type)||['point','circle','square','tick'].includes(mark)),padding=Number(scale.padding??(point?0.5:0.1)),inner=Number(scale.paddingInner??padding),outer=Number(scale.paddingOuter??(point?padding:inner/2)),steps=point?Math.max(1,domain.length-1+2*padding):Math.max(1,domain.length-inner+2*outer);
     const maxHeight=Math.max(...metrics.map(m=>m.height)),diagonalLimit=Math.max(font,(budget-maxHeight*Math.SQRT1_2/2)/Math.SQRT1_2);
     const threshold=(items,cos,sin,cap,centered=false)=>Math.ceil(steps*items.reduce((max,item,i)=>i?Math.max(max,(centered?(Math.min(item.width,cap)+Math.min(items[i-1].width,cap))/2:Math.max(Math.min(item.width,cap),Math.min(items[i-1].width,cap)))*cos+(item.height+items[i-1].height)*sin/2+gap):max,0));
     const horizontal=threshold(widths.map(width=>({width,height:lineHeight})),1,0,Infinity,true),wrapped=threshold(metrics,1,0,Infinity,true),diagonal=threshold(metrics,Math.SQRT1_2,Math.SQRT1_2,diagonalLimit),expression=domain.length===1?'0':'width >= '+horizontal+' ? 0 : '+(wrapping?'width >= '+wrapped+' ? 0 : ':'')+'width >= '+diagonal+' ? -45 : -90';
     const top=(axis.orient??defaults.orient)==='top';
     const liveBudget='max('+font+', min(90, height * 0.35))',cap=limit>0?limit:1000000,liveDiagonal='max('+font+', ('+liveBudget+' - '+maxHeight*Math.SQRT1_2/2+') / '+Math.SQRT1_2+')';
     field.axis={...axis,labelAngle:{expr:expression},labelAlign:axis.labelAlign??defaults.labelAlign??{expr:'('+expression+') === 0 ? "center" : '+JSON.stringify(top?'left':'right')},labelBaseline:axis.labelBaseline??defaults.labelBaseline??{expr:'('+expression+') === 0 ? '+JSON.stringify(top?'bottom':'top')+' : "middle"'},labelLimit:{expr:'('+expression+') === 0 ? '+(limit>0?limit:0)+' : min('+cap+', ('+expression+') === -45 ? '+liveDiagonal+' : '+liveBudget+')'},labelOverlap:axis.labelOverlap??defaults.labelOverlap??'greedy',labelSeparation:axis.labelSeparation??defaults.labelSeparation??4};
     if(wrapping){const words='split(trim(datum.label), /\\s+/)',middle='ceil(length('+words+') / 2)';field.axis.labelExpr='width >= '+horizontal+' || length('+words+') < 2 ? datum.label : [join(slice('+words+', 0, '+middle+'), " "), join(slice('+words+', '+middle+'), " ")]';field.axis.labelLineHeight=lineHeight}
    }
   }
  }
  for(const child of node.layer||[])walk(child,values);
  if(node.spec)walk(node.spec,values);
  for(const key of ['concat','hconcat','vconcat'])for(const child of node[key]||[])walk(child,values);
 }
 walk(spec,[]);return spec;
}
function applyErrors(spec,type,labels,rows,roles,options){
 if(!['clusteredBarChart','clusteredColumnChart','barChart','columnChart'].includes(type)||!options.visual||!options.model)return spec;
 const theme=options.model.theme||{},o=Style.objects(options.model,options.visual),ps=Object.values(options.visual.definition?.query?.queryState||{}).flatMap(q=>q.projections||[]);
 const index=f=>{const p=ps.find(p=>JSON.stringify(p.field)===JSON.stringify(f));return p?labels.indexOf(p.displayName??p.nativeQueryRef??p.queryRef):-1};
 const ci=roles.findIndex(r=>['Category','Group','Rows','X'].includes(r)),horizontal=/Bar/.test(type),axis=horizontal?'x':'y',cat=horizontal?'y':'x';
 const base=spec.layer?.find(l=>l.encoding?.[axis]?.field==='_value')||spec,encoding=base.encoding;if(!encoding)return spec;
 const layers=[],groups=new Map();for(const entry of o.error||[]){const key=entry.selector?.metadata||'';groups.set(key,{selector:entry.selector,properties:{...groups.get(key)?.properties,...entry.properties}})}
 for(const entry of groups.values()){const p=entry.properties||{},range=p.errorRange?.explicit;if(Style.value(p.enabled,theme)!==true||!range)continue;
  const projection=ps.find(x=>x.queryRef===entry.selector?.metadata),metric=projection?labels.indexOf(projection.displayName??projection.nativeQueryRef??projection.queryRef):-1;
  const lo=range.lowerBound?index(range.lowerBound.expr):metric,hi=range.upperBound?index(range.upperBound.expr):metric;if(lo<0||hi<0)continue;
  const data=rows.filter(r=>Number.isFinite(r[lo])&&Number.isFinite(r[hi])).map(r=>({_category:r[ci],_categoryValue:r[ci],_low:r[lo],_high:r[hi]}));
  const coordinates={[cat]:{...encoding[cat]},[axis]:{...encoding[axis],field:'_low',stack:null}},color=Style.value(p.barMatchSeriesColor,theme)===true?Style.color((o.dataPoint||[]).find(x=>x.selector?.metadata===projection?.queryRef)?.properties?.fill,theme)||'#888':Style.color(p.barColor,theme)||'#888';
  if(Style.value(p.barShow,theme)!==false)layers.push({data:{values:data},mark:{type:'rule',clip:true,color,strokeWidth:Number(Style.value(p.barWidth,theme))||1},encoding:{...coordinates,[axis+'2']:{field:'_high'}}});
  if(Style.value(p.markerShow,theme)===true||Style.value(p.markerShow,theme)!==false&&p.markerShape)for(const field of ['_low','_high'])layers[range.lowerBound&&range.upperBound?'unshift':'push']({data:{values:data},mark:{type:'point',filled:true,opacity:1,clip:true,color,shape:Style.value(p.markerShape,theme)||'circle',size:(Number(Style.value(p.markerSize,theme))||8)**2},encoding:{...coordinates,[axis]:{...coordinates[axis],field}}});
 }
 if(!layers.length&&!(o.dataPoint||[]).some(e=>e.properties?.fillTransparency!==undefined))return spec;
 for(const d of spec.data?.values||[]){const p=Style.resolveProperties(options.model,options.visual,'dataPoint',{datum:d}).properties,transparency=Number(Style.value(p.fillTransparency,theme,d._raw||d));d._barOpacity=1-Math.max(0,Math.min(100,Number.isFinite(transparency)?transparency:0))/100}
 if(spec.layer){for(const l of spec.layer)if(l.mark?.type==='bar')l.encoding.opacity={field:'_barOpacity',type:'quantitative',scale:null,legend:null}}
 else if(spec.mark?.type==='bar')spec.encoding.opacity={field:'_barOpacity',type:'quantitative',scale:null,legend:null};
 if(!layers.length)return spec;
 const {mark,encoding:enc,layer,params,...rest}=spec;return {...rest,layer:[...(layer||[{mark,encoding:enc,params}]),...layers.filter(l=>l.mark.type==='rule'),...layers.filter(l=>l.mark.type!=='rule')]};
}
function applyBarLabels(spec,type,labels,options){
 const supported=['clusteredBarChart','clusteredColumnChart','barChart','columnChart','stackedBarChart','stackedColumnChart','hundredPercentStackedBarChart','hundredPercentStackedColumnChart'];
 if(!supported.includes(type)||!options.model||!options.visual)return spec;
 const model=options.model,v=options.visual,theme=model.theme||{},objects=Style.objects(model,v),names=['labels','dataLabels'];
 // Ordinary unscoped labels retain the existing layout. This path resolves
 // authored metric/category selectors and field-valued label overrides.
 if(!names.some(name=>(objects[name]||[]).some(e=>e.selector?.metadata||e.selector?.data||e.properties?.dynamicLabelValue!==undefined)))return spec;
 const values=spec.data?.values||[],layers=spec.layer||[{mark:spec.mark,encoding:spec.encoding,...(spec.params?{params:spec.params}:{})}],bar=layers.find(l=>l.mark?.type==='bar');
 if(!values.length||!bar?.encoding)return spec;
 // Merge aliases within each source, then let the shared resolver preserve
 // theme/authored and default/metric/category-selector precedence together.
 const aliases=part=>part?{...part,labels:[...(part.labels||[]),...(part.dataLabels||[])]}:part,labelStyles=Object.fromEntries(Object.entries(theme.visualStyles||{}).map(([type,presets])=>[type,Object.fromEntries(Object.entries(presets).map(([name,part])=>[name,aliases(part)]))])),labelModel={...model,theme:{...theme,visualStyles:labelStyles}},labelVisual={...v,definition:{...v.definition,objects:aliases(v.definition?.objects),visualContainerObjects:aliases(v.definition?.visualContainerObjects)}};
 const properties=datum=>Style.resolveProperties(labelModel,labelVisual,'labels',{datum}).properties;
 const retained=layers.filter(l=>!(l.mark?.type==='text'&&l.encoding?.text?.field==='_label')),global=properties({});
 const finish=extra=>{const {mark,encoding,params,...rest}=spec;return {...rest,layer:[...retained,...extra]}};
 const globalShow=Style.value(global.show,theme);
 if(globalShow===false||globalShow===undefined&&options.dataLabels?.show===false&&options.dataLabels?.showSpecified===true)return finish([]);
 const horizontal=/BarChart$/.test(type)||type==='barChart',axis=horizontal?'x':'y',cat=horizontal?'y':'x',stacked=/stacked/i.test(type)||['barChart','columnChart'].includes(type),normalize=/hundredPercent/.test(type),series=[...new Set(values.map(d=>d._series))],categories=new Set(values.map(d=>d._category)),groups=new Map();
 const ps=Object.values(v.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false)),projectionIndex=new Map(ps.map((p,i)=>[p.queryRef,i])),largest=new Map();
 for(const d of values)largest.set(d._projectionRef,Math.max(largest.get(d._projectionRef)||0,Math.abs(d._value||0)));
 const read=(p,key,d)=>Style.value(p[key],theme,d._raw||d),slots=Math.max(1,categories.size*(stacked?1:series.length));
 for(const d of values){
  const p=properties(d),show=read(p,'show',d)??options.dataLabels?.show??false;
  if(show!==true||read(p,'showSeries',d)===false||!Number.isFinite(d._value))continue;
  const index=projectionIndex.get(d._projectionRef)??labels.indexOf(d._sourceMeasure),resolved=Formats.resolve(model,v,index,{element:p,dynamicFormat:d._sourceLabelFormat??options.formats?.[index]}),settings={...resolved,...Object.fromEntries(Object.entries(options.dataLabels||{}).filter(([,value])=>value!==undefined))};
  for(const [key,source] of Object.entries({precision:p.labelPrecision??p.decimalPlaces??p.detailLabelPrecision,units:p.labelDisplayUnits??p.displayUnits})){const value=Style.value(source,theme,d._raw);if(value!==undefined)settings[key]=value}
  if(settings.units===0||settings.units===undefined&&/[$€£¥]/.test(resolved.format||''))settings.units=autoUnits(largest.get(d._projectionRef)||0,/[$€£¥]/.test(resolved.format||''));
  const dynamic=Object.hasOwn(p,'dynamicLabelValue'),dynamicValue=dynamic?read(p,'dynamicLabelValue',d):undefined,parts=[],valueEnabled=read(p,'enableValueDataLabel',d)!==false,separator=read(p,'labelContentLayout',d)==='MultiLine'?'\n':' ';
  if(read(p,'enableTitleDataLabel',d)===true)parts.push(String(read(p,'dynamicLabelTitle',d)??d._series));
  const prefix=parts.length?parts.join(separator)+separator:'',normal=normalize&&!dynamic&&valueEnabled;
  if(valueEnabled){const value=dynamic?dynamicValue:d._value;if(value!==undefined&&value!==null){if(dynamic&&typeof value!=='number')parts.push(String(value));else parts.push(labelText(value,resolved.format,settings))}}
  const detail=read(p,'dynamicLabelDetail',d);if(read(p,'enableDetailDataLabel',d)===true&&detail!=null)parts.push(String(detail));
  const text=parts.join(separator);if(text==='')continue;
  let position=String(read(p,'labelPosition',d)??read(p,'position',d)??options.dataLabels?.position??'Auto').toLowerCase();position=/base/.test(position)?'base':/center|middle/.test(position)?'center':/outside/.test(position)?'outside':/inside/.test(position)?'inside':'auto';
  const key=position+':'+normal;if(!groups.has(key))groups.set(key,{id:'g'+groups.size,position,normal});const group=groups.get(key);
  d._pbiBarLabel=text;d._pbiBarLabelStyle=group.id;d._pbiBarLabelPrefix=prefix;d._pbiBarLabelSuffix=read(p,'enableDetailDataLabel',d)===true&&detail!=null?separator+String(detail):'';d._pbiBarLabelPrecision=Number.isInteger(settings.precision)?Math.max(0,Math.min(20,settings.precision)):0;
  d._pbiBarLabelColor=Style.color(p.color??p.fontColor,theme,d._raw)||options.dataLabels?.color||theme.foreground||'#344e40';d._pbiBarLabelFont=read(p,'fontFamily',d)||options.dataLabels?.fontFamily||spec.config?.font||'Segoe UI';d._pbiBarLabelWeight=read(p,'bold',d)?'bold':'normal';d._pbiBarLabelFontStyle=read(p,'italic',d)?'italic':'normal';
  const chars=Math.max(1,...text.split('\n').map(t=>t.length)),size=(Number(read(p,'fontSize',d)??read(p,'detailFontSize',d)??options.dataLabels?.fontSize)||9)*4/3,fit=horizontal?Math.min(spec.height/slots*.85,spec.width*(dynamic?.95:.35)/(chars*.6)):spec.width/slots*.82/(chars*.6);d._pbiBarLabelFontSize=Math.min(Math.max(1,Math.min(160,size)),Math.max(6,fit));
 }
 if(!groups.size)return finish([]);
 const offset=bar.encoding[cat+'Offset'];if(offset){const reversed=Style.value(Style.props(objects,'layout').seriesOrderReversed,theme)===true;offset.sort=reversed?[...series].reverse():series}
 let quantity=bar.encoding[axis];
 if(stacked&&!spec.transform?.some(t=>t.stack==='_value')){
  spec.transform=[...(spec.transform||[]),{stack:'_value',groupby:['_category'],sort:[{field:'_series',order:'ascending'}],offset:normalize?'normalize':'zero',as:['_stackStart','_stackEnd']},{calculate:'(datum._stackStart + datum._stackEnd)/2',as:'_labelPosition'}];
  bar.encoding[axis]={...quantity,field:'_stackEnd',stack:null};bar.encoding[axis+'2']={field:'_stackStart'};
 }
 const output=[];
 for(const g of groups.values()){
  const encoding=structuredClone(bar.encoding);for(const key of ['color','fill','stroke','opacity',axis+'2'])delete encoding[key];
  const outside=g.position==='outside'||g.position==='auto'&&(!stacked||horizontal&&series.length===1),base=g.position==='base',center=g.position==='center'||g.position==='auto'&&stacked&&!outside;
  encoding[axis]={...quantity,field:stacked?(center?'_labelPosition':base?'_stackStart':'_stackEnd'):'_value',stack:null};
  const transform=[{filter:'datum._pbiBarLabelStyle === '+JSON.stringify(g.id)}],mark={type:'text',clip:false,tooltip:true,color:{expr:'datum._pbiBarLabelColor'},font:{expr:'datum._pbiBarLabelFont'},fontSize:{expr:'datum._pbiBarLabelFontSize'},fontWeight:{expr:'datum._pbiBarLabelWeight'},fontStyle:{expr:'datum._pbiBarLabelFontStyle'},lineBreak:'\n'};
  if(center){if(!stacked)transform.push({calculate:'datum._value / 2',as:'_pbiBarLabelCenter'});if(!stacked)encoding[axis].field='_pbiBarLabelCenter';mark.align='center';mark.baseline='middle'}
  else if(horizontal){if(base&&!stacked)encoding.x={...quantity,datum:0,stack:null},delete encoding.x.field;mark.align={expr:outside||base?"datum._value < 0 ? 'right' : 'left'":"datum._value < 0 ? 'left' : 'right'"};mark.dx={expr:(outside||base?'':'-')+"(datum._value < 0 ? -4 : 4)"};mark.baseline='middle'}
  else{if(base&&!stacked)encoding.y={...quantity,datum:0,stack:null},delete encoding.y.field;mark.baseline={expr:outside||base?"datum._value < 0 ? 'top' : 'bottom'":"datum._value < 0 ? 'bottom' : 'top'"};mark.dy={expr:(outside||base?'':'-')+"(datum._value < 0 ? 4 : -4)"}}
  if(g.normal)transform.push({calculate:"datum._pbiBarLabelPrefix + format(abs(datum._stackEnd-datum._stackStart), '.' + datum._pbiBarLabelPrecision + '%') + datum._pbiBarLabelSuffix",as:'_pbiBarLabel'});
  encoding.text={field:'_pbiBarLabel',type:'nominal'};output.push({name:'pbi_bar_labels_'+g.id,transform,mark,encoding});
 }
 return finish(output);
}
function applyLineLabels(spec,type,options){
 if(!['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart'].includes(type)||!options.model||!options.visual)return spec;
 if(spec.usermeta?.secondaryAxes){spec.layer=spec.layer.map(group=>{if(!['pbi_primary_y','pbi_secondary_y'].includes(group.name))return group;const secondary=group.name==='pbi_secondary_y',data={values:spec.data.values.filter(row=>['Y2','LineY'].includes(row._role)===secondary)},local=applyLineLabels({...spec,data,layer:group.layer,usermeta:{...spec.usermeta,secondaryAxes:false}},type,options);return {...group,layer:local.layer}});return spec}
 const model=options.model,v=options.visual,theme=model.theme||{},objects=Style.objects(model,v),values=spec.data?.values||[],layers=[],base=spec.layer?.find(l=>l.encoding?.x&&l.encoding?.y)||spec;
 if(!base.encoding?.x||!base.encoding?.y)return spec;
 const props=(key,d)=>Object.assign({},Style.props(objects,key),...(objects[key]||[]).filter(e=>e.selector&&(e.selector.data?.some(s=>s.dataViewWildcard)||Style.selectorMatches(e.selector,d))).map(e=>e.properties||{}));
 const coordinates={x:base.encoding.x,y:base.encoding.y};
 function textLayer(data,p,series){const right=series&&String(Style.value(p.seriesPosition,theme)||'Right').toLowerCase()==='right',left=series&&String(Style.value(p.seriesPosition,theme)).toLowerCase()==='left';
  return {data:{values:data},mark:{type:'text',clip:false,tooltip:true,align:right?'left':left?'right':'center',baseline:'bottom',dx:right?10:left?-10:0,dy:series?0:-8,fontSize:(Number(Style.value(p.textSize||p.detailFontSize||p.fontSize,theme))||10)*4/3,font:Style.value(p.fontFamily,theme)||spec.config?.font,color:Style.color(p.color||p.fontColor,theme)||theme.foreground||'#333',fontWeight:Style.value(p.bold,theme)?'bold':'normal'},encoding:{...coordinates,text:{field:'_pbiLabel',type:'nominal'},tooltip:base.encoding.tooltip}};
 }
 for(const d of values){const p=props('labels',d);if(Style.value(p.show,theme)!==true||Style.value(p.showSeries,theme)===false)continue;
  const detail=Style.value(p.dynamicLabelDetail,theme,d._raw),parts=[];
  if(Style.value(p.enableTitleDataLabel,theme)===true)parts.push(d._series);
  if(Style.value(p.enableValueDataLabel,theme)!==false)parts.push(d._label);
  if(Style.value(p.enableDetailDataLabel,theme)===true&&detail!=null)parts.push(String(detail));
  if(parts.length)layers.push(textLayer([{...d,_pbiLabel:parts.join(Style.value(p.labelContentLayout,theme)==='MultiLine'?'\n':' ')}],p,false));
 }
 const series=new Map();for(const d of values){const p=props('seriesLabels',d);if(Style.value(p.show,theme)!==true)continue;const prior=series.get(d._series),left=String(Style.value(p.seriesPosition,theme)).toLowerCase()==='left';if(!prior||(left?d._category<prior.d._category:d._category>prior.d._category))series.set(d._series,{d,p})}
 for(const {d,p} of series.values())layers.push(textLayer([{...d,_pbiLabel:d._series}],p,true));
 if(!layers.length)return spec;
 const {mark,encoding,layer,params,...rest}=spec;return {...rest,layer:[...(layer||[{mark,encoding,...(params?{params}:{})}]),...layers.filter(l=>l.mark.type==='rule'),...layers.filter(l=>l.mark.type!=='rule')]};
}
// Plot-area artwork belongs inside the axes, beneath marks, not behind the container.
function applyPlotImage(spec,options){
 if(!options.model||!options.visual)return spec;
 const model=options.model,theme=model.theme||{},p=Style.props(Style.objects(model,options.visual),'plotArea'),image=p.image?.image||p.image;
 const source=Style.url(image?.url||image||p.imageUrl,model);if(!source)return spec;
 const fit=String(Style.value(p.imageFit||p.scaling||image?.scaling,theme)||'Fit').toLowerCase(),width=Number(spec.width),height=Number(spec.height);
 if(!(width>0&&height>0))return spec;
 // Natural-size artwork can extend beyond the plot. Keep its layer inside the
 // plot rectangle so it cannot paint over axes, labels or legends.
 const background={data:{values:[{url:source}]},mark:{type:'image',clip:true,align:'center',baseline:'middle',aspect:!/fill|stretch/.test(fit),...(fit==='normal'?{}:{width:{expr:'width'},height:{expr:'height'}}),opacity:1-Math.max(0,Math.min(100,Number(Style.value(p.transparency,theme))||0))/100},encoding:{url:{field:'url',type:'nominal'},x:{value:{expr:'width/2'}},y:{value:{expr:'height/2'}}}};
 const {mark,encoding,layer,params,...rest}=spec;
 return {...rest,layer:[background,...(layer?layer.map((l,i)=>i===0&&params?{...l,params:[...(l.params||[]),...params]}:l):[{mark,encoding,...(params?{params}:{})}]) ]};
}
function applyReferenceBands(spec,type,options){
 if(!options.visual||!options.model)return spec;
 const theme=options.model.theme||{},objects=Style.objects(options.model,options.visual),behind=[],front=[];
 for(const [key,axis] of type==='scatterChart'?[['xAxisReferenceLine','x'],['y1AxisReferenceLine','y']]:[])for(const entry of objects[key]||[]){
  const p=entry.properties||entry,value=x=>Style.value(x,theme,spec.data?.values?.[0]?._raw||{}),at=value(p.value);if(value(p.show)!==true||typeof at!=='number'||!Number.isFinite(at))continue;
  const color=Style.color(p.lineColor,theme)||'#777',encoding=axis==='x'?{x:{datum:at,type:'quantitative',axis:null}}:{y:{datum:at,type:'quantitative',axis:null}},target=value(p.position)==='front'?front:behind;
  if(value(p.shadeShow)===true){const before=value(p.shadeRegion)!=='after',bound=spec.encoding?.[axis]?.scale?.domain||[0,1],lo=before?bound[0]:at,hi=before?at:bound[1];target.push({data:{values:[{}]},mark:{type:'rect',color:value(p.shadeColorMatchStroke)===false?(Style.color(p.shadeColor,theme)||color):color,opacity:1-Number(value(p.shadeTransparency)||0)/100},encoding:axis==='x'?{x:{datum:lo,type:'quantitative',axis:null},x2:{datum:hi},y:{value:0},y2:{value:spec.height}}:{y:{datum:lo,type:'quantitative',axis:null},y2:{datum:hi},x:{value:0},x2:{value:spec.width}}})}
  target.push({data:{values:[{}]},mark:{type:'rule',color,opacity:1-Number(value(p.transparency)||0)/100,strokeWidth:Number(value(p.width)||1),...(value(p.style)==='dashed'?{strokeDash:[4,4]}:{})},encoding});
 }
 const supported=['barChart','columnChart','clusteredBarChart','clusteredColumnChart','stackedBarChart','stackedColumnChart','hundredPercentStackedBarChart','hundredPercentStackedColumnChart','lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart'];
 if(supported.includes(type)&&!spec.usermeta?.secondaryAxes){
  const ps=Object.values(options.visual.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false)),axis=/BarChart$/.test(type)||type==='barChart'?'x':'y';
  for(const entry of objects.referenceLine||[]){
   const p=entry.properties||entry,value=x=>Style.value(x,theme,spec.data?.values?.[0]?._raw||{});if(value(p.show)!==true)continue;
   const points=spec.data?.values||[],numbers=points.map(d=>Style.value(p.value,theme,d._raw||{})),at=numbers[0];
   // A reference line needs one scalar for its axis. A per-point conditional
   // value must not silently become a line for an arbitrary first category.
   if(typeof at!=='number'||!Number.isFinite(at)||numbers.some(n=>n!==at))continue;
   const color=Style.color(p.lineColor??p.color,theme,points[0]?._raw)||'#777',style=String(value(p.style??p.lineStyle)||'').toLowerCase(),width=Number(value(p.width??p.lineWidth)),transparency=Number(value(p.transparency)),encoding={[axis]:{datum:at,type:'quantitative',axis:null}},target=String(value(p.position)||'').toLowerCase()==='front'?front:behind;
   target.push({name:'pbi_reference_'+(behind.length+front.length),data:{values:[{}]},mark:{type:'rule',clip:true,color,opacity:1-Math.max(0,Math.min(100,Number.isFinite(transparency)?transparency:0))/100,strokeWidth:Number.isFinite(width)?Math.max(0,Math.min(20,width)):1,...(/dash/.test(style)?{strokeDash:[4,4]}:/dot/.test(style)?{strokeDash:[2,3]}:{})},encoding});
   if(value(p.dataLabelShow)===true){const index=ps.findIndex(q=>q.queryRef===entry.selector?.metadata),text=Formats.text(at,options.formats?.[index]||'#,0.##',{precision:value(p.decimalPoints??p.dataLabelDecimalPoints),units:value(p.dataLabelDisplayUnits)});target.push({data:{values:[{label:text}]},mark:{type:'text',align:axis==='y'?'right':'left',baseline:axis==='y'?'bottom':'top',dx:axis==='x'?3:-3,dy:axis==='y'?-3:3,fontSize:Math.max(1,Math.min(160,Number(value(p.dataLabelTextSize))||9))*4/3,color:Style.color(p.dataLabelColor,theme,points[0]?._raw)||color},encoding:{...encoding,[axis==='x'?'y':'x']:{value:axis==='x'?0:spec.width},text:{field:'label',type:'nominal'}}})}
  }
 }
 if(behind.length||front.length){const {mark,encoding,layer,params,...rest}=spec;return {...rest,layer:[...behind,...(layer||[{mark,encoding,params}]),...front]}}
 return spec;
}
function linearFit(points){
 if(points.length<2)return null;
 const mx=points.reduce((sum,p)=>sum+p.x,0)/points.length,my=points.reduce((sum,p)=>sum+p.y,0)/points.length;
 let xx=0,xy=0;for(const p of points){xx+=(p.x-mx)**2;xy+=(p.x-mx)*(p.y-my)}if(!xx)return null;
 const slope=xy/xx;return x=>my+slope*(x-mx);
}
function applyTrends(spec,type,options){
 if(!options.visual||!options.model||!['lineChart','areaChart','scatterChart','clusteredColumnChart','columnChart'].includes(type))return spec;
 if(spec.usermeta?.secondaryAxes){let trendLines=0;spec.layer=spec.layer.map(group=>{if(!['pbi_primary_y','pbi_secondary_y'].includes(group.name))return group;const secondary=group.name==='pbi_secondary_y',data={values:spec.data.values.filter(row=>['Y2','LineY'].includes(row._role)===secondary)},local=applyTrends({...spec,data,layer:group.layer,usermeta:{...spec.usermeta,secondaryAxes:false,trendLines:0}},type,options);trendLines+=local.usermeta?.trendLines||0;return {...group,layer:local.layer.map(layer=>layer.name?.startsWith('pbi_trend_')?{...layer,name:group.name+'_'+layer.name}:layer)}});if(trendLines)spec.usermeta.trendLines=trendLines;return spec}
 const model=options.model,theme=model.theme||{},objects=Style.objects(model,options.visual),entries=objects.trend||[];
 const base=spec.layer?.find(layer=>layer.encoding?.x&&layer.encoding?.y)||spec,x=base.encoding?.x,y=base.encoding?.y;
 if(!x?.field||!y?.field)return spec;
 const data=spec.data?.values||[],categories=Array.isArray(x.sort)?x.sort:[...new Set(data.map(d=>d[x.field]))],ranks=new Map(categories.map((v,i)=>[JSON.stringify(v),i]));
 const number=d=>d[x.field]==null?NaN:x.type==='temporal'?Date.parse(d[x.field]):x.type==='quantitative'?Number(d[x.field]):ranks.get(JSON.stringify(d[x.field]));
 const behind=[],front=[];
 for(const entry of entries){const p=entry.properties||entry;if(Style.value(p.show,theme)!==true)continue;
  const combined=Style.value(p.combineSeries,theme)!==false,groups=new Map();
  for(const d of data){const nx=number(d),ny=d[y.field];if(!Number.isFinite(nx)||!Number.isFinite(ny))continue;const key=combined?'all':String(d._series??d._color??'all');if(!groups.has(key))groups.set(key,[]);groups.get(key).push({x:nx,y:ny,raw:d[x.field]})}
  for(const [key,points] of groups){const full=type==='scatterChart'&&combined?options.scatterStats:undefined,fit=full&&Number.isFinite(full.slope)?x=>full.intercept+full.slope*x:linearFit(points);if(!fit)continue;
   const sorted=[...points].sort((a,b)=>a.x-b.x),ends=[sorted[0],sorted.at(-1)],name=String(Style.value(p.displayName,theme)||'Trend line'),dash=String(Style.value(p.style??p.lineStyle,theme)||'dashed').toLowerCase();
   const values=ends.map(point=>({[x.field]:point.raw,_trendY:fit(point.x),_trendName:name+(combined?'':' · '+key)}));
   const layer={name:'pbi_trend_'+(behind.length+front.length),data:{values},mark:{type:'line',clip:true,point:false,tooltip:true,color:Style.color(p.lineColor??p.color,theme)||'#000000',opacity:Math.max(0,Math.min(1,1-(Number(Style.value(p.transparency,theme))||0)/100)),strokeWidth:Math.max(.5,Math.min(20,Number(Style.value(p.lineWidth??p.strokeWidth,theme))||2)),...(/dot/.test(dash)?{strokeDash:[2,3]}:/dash/.test(dash)?{strokeDash:[6,4]}:{})},encoding:{x:{...x},y:{...y,field:'_trendY',stack:null},tooltip:[{field:'_trendName',type:'nominal',title:'Trend'},{field:'_trendY',type:'quantitative',title:y.title||'Value',format:y.axis?.format}]}};
   (/back|behind/i.test(String(Style.value(p.position,theme)||''))?behind:front).push(layer);
  }
 }
 if(!behind.length&&!front.length)return spec;
 const {mark,encoding,params,...rest}=spec;
 return {...rest,layer:[...behind,...(spec.layer||[{mark,encoding,params}]),...front],usermeta:{...spec.usermeta,trendLines:behind.length+front.length}};
}
function fitLegends(spec,type,options={}){
 const legend=spec.config.legend,width=Number(spec.width)||500,height=Number(spec.height)||280;
 const horizontal=['top','bottom'].includes(legend.orient||'bottom');let count=0,chars=0;
 function visit(node){if(node.encoding)for(const channel of ['color','fill','stroke']){const e=node.encoding[channel];if(e?.type==='nominal'&&e.legend!==null){const keys=[...new Set((spec.data.values||[]).map(d=>d[e.field]))];count=Math.max(count,keys.length);chars=Math.max(chars,...keys.map(x=>String(x??'').length))}}for(const layer of node.layer||[])visit(layer)}visit(spec);
 const font=legend.labelFontSize||10,cell=Math.min(width,Math.max(70,chars*font*.64+28));
 if(horizontal&&count){legend.columns=Math.max(1,Math.floor((width-12)/cell));legend.columnPadding=10;legend.rowPadding=4;legend.gridAlign='all';legend.labelLimit=Math.max(20,Math.floor((width-12)/legend.columns)-28);legend.symbolLimit=Math.max(count,1)}
 if(['pieChart','donutChart'].includes(type)){
  const budget=count?(horizontal?Math.ceil(count/(legend.columns||1))*(font+7)+20:Math.min(width*.45,cell)+15):0;
  const diameter=horizontal?Math.min(width,height-budget):Math.min(width-budget,height),radius=Math.max(12,diameter*.36);
  const layers=spec.layer||[{mark:spec.mark}],inside=/inside/i.test(options.dataLabels?.position||'');
  for(const layer of layers)if(layer.mark?.type==='arc'){layer.mark.outerRadius=radius;layer.mark.innerRadius=type==='donutChart'?radius*.5:0}else if(layer.mark?.type==='text')layer.mark.radius=inside?radius*.7:radius+12;
  const text=spec.layer?.find(l=>l.encoding?.text?.field==='_pieLabel');if(text)text.transform=[{filter:"datum._pieLabel !== ''"}];
  if(text&&!inside){
   const plotHeight=Math.max(30,height-(horizontal?budget:0)-12),total=spec.data.values.reduce((s,d)=>s+(d._magnitude??d._value??0),0);let angle=0;
   for(const d of [...spec.data.values].sort((a,b)=>a._category<b._category?-1:a._category>b._category?1:0)){const step=total?(d._magnitude??d._value??0)/total*Math.PI*2:0,mid=angle+step/2;angle+=step;d._pieSide=Math.sin(mid)>=0?1:-1;d._pieEdgeX=Math.sin(mid)*radius;d._pieEdgeY=-Math.cos(mid)*radius;d._pieY=-Math.cos(mid)*(radius+12);d._pieX=d._pieSide*(radius+16)}
   const sides=[-1,1].map(side=>spec.data.values.filter(d=>d._pieSide===side&&d._pieLabel).sort((a,b)=>a._pieY-b._pieY)),maxRows=Math.max(1,...sides.map(s=>s.length)),font=Math.min(text.mark.fontSize,Math.max(7,plotHeight/maxRows-2)),gap=font+2,limit=plotHeight/2;
   text.mark.fontSize=font;
   for(const side of sides){for(let i=0;i<side.length;i++)side[i]._pieY=Math.max(-limit+font/2,side[i]._pieY,i?side[i-1]._pieY+gap:-Infinity);if(side.length&&side.at(-1)._pieY>limit-font/2){side.at(-1)._pieY=limit-font/2;for(let i=side.length-2;i>=0;i--)side[i]._pieY=Math.min(side[i]._pieY,side[i+1]._pieY-gap)}}
   delete text.mark.radius;delete text.encoding.theta;delete text.encoding.order;
   text.mark.x={expr:'width / 2 + datum._pieX'};text.mark.y={expr:'height / 2 + datum._pieY'};text.mark.align={expr:"datum._pieSide > 0 ? 'left' : 'right'"};
   spec.layer.splice(spec.layer.indexOf(text),0,{name:'pbi_pie_label_leaders',transform:[{filter:"datum._pieLabel !== ''"}],mark:{type:'rule',stroke:text.mark.color||'#666666',strokeWidth:1,opacity:.8,aria:false},encoding:{x:{value:{expr:'width / 2 + datum._pieEdgeX'}},y:{value:{expr:'height / 2 + datum._pieEdgeY'}},x2:{value:{expr:'width / 2 + datum._pieX - datum._pieSide * 3'}},y2:{value:{expr:'height / 2 + datum._pieY'}}}});
  }
 }
}
function buildRaw(type,labels,rows,roles=[],options={}){
 if(!types.includes(type))throw Error('No Vega-Lite mapping for '+type);
 const width=Math.max(80,options.width||500),height=Math.max(80,options.height||280);
 const spec={$schema:'https://vega.github.io/schema/vega-lite/v6.json',width,height,autosize:{type:'fit',contains:'padding',resize:false},background:'transparent',config:{view:{stroke:null},font:'DM Sans, sans-serif',axis:{labelColor:'#627668',titleColor:'#344e40',gridColor:'#e6ece3',labelLimit:110,labelOverlap:'greedy',labelSeparation:4,titleFontSize:11,labelFontSize:10},axisQuantitative:{format:'~s'},legend:{orient:'bottom',labelColor:'#627668',title:null,labelLimit:150},range:{category:palette}},data:{values:[]}};
 if(!rows.length){spec.data.values=[{label:'No data for the current filters.'}];spec.mark={type:'text',color:'#788884'};spec.encoding={text:{field:'label'}};return spec}
 if(type==='gauge'){
  spec.autosize={type:'none',contains:'padding'};spec.padding=0;
  const pick=(names,fallback)=>{const i=roles.findIndex(r=>names.includes(r));return i>=0?rows[0][i]:fallback},value=pick(['Y','Value'],rows[0][0]),o=options.model&&options.visual?Style.objects(options.model,options.visual):{},axis=Style.props(o,'gaugeAxis'),theme=options.model?.theme||{};
  const min=Number(pick(['MinValue','Minimum'],Style.value(axis.min,theme)??Math.min(0,value))),max=Number(pick(['MaxValue','Maximum'],Style.value(axis.max,theme)??Math.max(1,value*2))),target=pick(['TargetValue','Target'],Style.value(axis.target,theme));
  if(!Number.isFinite(value)||!Number.isFinite(min)||!Number.isFinite(max)||max<=min)throw Error('Gauge requires a numeric value and an increasing range.');
  const angle=x=>-Math.PI/2+Math.PI*Math.max(0,Math.min(1,(x-min)/(max-min))),radius=Math.max(20,Math.min(width/2-16,height-65)),color=Style.color(Style.props(o,'dataPoint').fill,theme)||palette[0],mark={type:'arc',innerRadius:radius*.72,outerRadius:radius,x:width/2,y:height-42,tooltip:true};
  spec.data.values=[{value,label:labelText(value,options.formats?.[roles.findIndex(r=>['Y','Value'].includes(r))]||options.formats?.[0],{}),min,max}];
  spec.layer=[{mark:{...mark,color:'#e4e7e8'},encoding:{theta:{datum:-Math.PI/2,scale:null},theta2:{datum:Math.PI/2}}},{mark:{...mark,color},encoding:{theta:{datum:-Math.PI/2,scale:null},theta2:{datum:angle(value)},tooltip:[{field:'value',type:'quantitative'},{field:'min',type:'quantitative'},{field:'max',type:'quantitative'}]}},{mark:{type:'text',x:width/2,y:height-65,fontSize:26,color:theme.foreground||'#333'},encoding:{text:{field:'label'}}}];
  for(const [x,n,align] of [[width/2-radius,min,'left'],[width/2+radius,max,'right']])spec.layer.push({data:{values:[{label:labelText(n,options.formats?.[0],{})}]},mark:{type:'text',x,y:height-30,align,fontSize:11,baseline:'bottom'},encoding:{text:{field:'label'}}});
  if(Number.isFinite(target)){const a=angle(target);spec.layer.push({mark:{type:'rule',color:'#333',strokeWidth:2,x:width/2+Math.sin(a)*radius*.68,x2:width/2+Math.sin(a)*radius*1.03,y:height-42-Math.cos(a)*radius*.68,y2:height-42-Math.cos(a)*radius*1.03},encoding:{}})}
  return spec;
 }
 const numeric=labels.map((_,i)=>i).filter(i=>rows.some(r=>typeof r[i]==='number'&&Number.isFinite(r[i])));
 if(Advanced.types.includes(type)){const bubble=type==='filledMap'&&options.visual&&Style.value(Style.props(Style.objects(options.model||{},options.visual),'bubbleLayer').show,options.model?.theme)===true;return Advanced.build(spec,bubble?'pointMap':type,labels,rows,roles,options);}
 const distribution=['violinPlot','histogram','histogramChart','boxplot','boxPlot'].includes(type);
 let ci=roles.findIndex(r=>['Category','Group','Rows','X'].includes(r));
 if(ci<0)ci=distribution?(labels.length>1?labels.findIndex((_,i)=>!numeric.includes(i)):-1):roles.some(r=>['Y','Y2','Values','Value','ColumnY','LineY'].includes(r))?-1:0;
 let si=roles.findIndex(r=>['Series','Legend','Columns'].includes(r));
 if(si===ci)si=-1;
 const categoryIndices=roles.flatMap((role,i)=>role==='Category'?[i]:[]);
 let vi=numeric.filter(i=>!categoryIndices.includes(i)&&i!==ci&&i!==si&&!['formatting','tooltips','tooltip'].includes(String(roles[i]).toLowerCase()));
 if(!vi.length&&distribution)vi=numeric.slice(0,1);
 if(!vi.length&&rows.length)throw Error('The chart query did not return a numeric value field.');
 // Empty results still get a valid quantitative field and clear empty-state UI.
 if(!vi.length)vi=[Math.max(0,labels.length-1)];
 const labelSettings={...options.dataLabels};
 if(labelSettings.units===undefined&&options.model?.reportSettings?.defaultDisplayUnitsToNone)labelSettings.units=1;
 if(labelSettings.units===0||labelSettings.units===undefined&&vi.some(i=>/[$€£¥]/.test(options.formats?.[i]||''))){const largest=Math.max(0,...rows.flatMap(row=>vi.map(i=>Math.abs(row[i]||0))));labelSettings.units=autoUnits(largest,vi.some(i=>/[$€£¥]/.test(options.formats?.[i]||'')))}
 const rowFormatMap=options._rowFormatMap||new Map(rows.map((row,i)=>[row,options.rowFormats?.[i]]));
 const values=[];
 for(const row of rows)for(const i of vi){
  if(row[i]!==null&&row[i]!==undefined&&typeof row[i]!=='number')throw Error('Chart value fields must be numeric.');
  const projection=Object.values(options.visual?.definition?.query?.queryState||{}).flatMap(q=>q.projections||[]).find(p=>(p.displayName??p.nativeQueryRef)===labels[i]);
  values.push({_rowValues:options._rowValueMap?.get(row)??row,_rowFormats:options._sourceRowFormatMap?.has(row)?options._sourceRowFormatMap.get(row):rowFormatMap.get(row),_projectionRef:projection?.queryRef,_rowIdentity:options.visual?(typeof module!=='undefined'?require('./chart-interactions'):root.ChartInteractionAPI).compoundIdentity(options.visual,row):null,_sourceMeasure:projection?.field?.Measure?.Property||projection?.field?.Aggregation?.Expression?.Column?.Property,_category:categoryIndices.length>1?categoryIndices.map(i=>row[i]??'(Blank)').join(' / '):ci>=0?row[ci]??'(Blank)':'All',_categoryValue:ci>=0?row[ci]:undefined,_dimension:si>=0?row[si]:undefined,_value:row[i],_formattedValue:Formats.text(row[i],rowFormatMap.get(row)?.[i]??options.formats?.[i],{locale:options.model?.reportSettings?.locale}),_label:labelText(row[i],rowFormatMap.get(row)?.[i]??options.formats?.[i],{...(options.model&&options.visual?Formats.resolve(options.model,options.visual,i,{element:Style.resolveProperties(options.model,options.visual,'labels',{datum:{_sourceMeasure:projection?.field?.Measure?.Property||projection?.field?.Aggregation?.Expression?.Column?.Property,_projectionRef:projection?.queryRef}}).properties,dynamicFormat:rowFormatMap.get(row)?.[i]??options.formats?.[i]}):{}),...Object.fromEntries(Object.entries(labelSettings).filter(([,v])=>v!==undefined))}),_series:(si>=0?(typeof row[si]==='boolean'?(row[si]?'True':'False'):String(row[si]??'(Blank)'))+(vi.length>1?' · ':''):'')+(vi.length>1||si<0?labels[i]:''),_role:roles[i]||'Y',...Object.fromEntries(roles.flatMap((role,index)=>/^tooltips?$/i.test(role)?[['_tooltip'+index,Formats.text(row[index],options.formats?.[index])]]:[]))});
  Object.defineProperty(values[values.length-1],'_sourceLabelFormat',{value:rowFormatMap.get(row)?.[i]??options.formats?.[i]});
 }
 if(['funnel','funnelChart'].includes(type)&&ci<0&&si<0&&vi.length>1)for(const value of values){value._category=value._series;value._categoryValue=undefined;value._series='Value'}
 spec.data.values=values;
 const categories=options._multipleCategories||[...new Set(values.map(r=>r._category))],series=[...new Set(values.map(r=>r._series))];
 const orderedCategories=()=>{if(categories.length<=128)return categories;const order=new Map(categories.map((name,i)=>[name,i]));for(const d of values)d._categoryOrder=order.get(d._category);return {field:'_categoryOrder',op:'min',order:'ascending'}};
 if(type==='treemap'){
  const leaves=values.filter(d=>d._value>0).sort((a,b)=>b._value-a._value);
  if(values.some(d=>d._value<0))spec.usermeta={mappingWarnings:['Treemap areas omit negative values; use a bar chart to compare signed values.']};
  function layout(items,x,y,w,h){if(!items.length)return;if(items.length===1){Object.assign(items[0],{_x:x,_y:y,_x2:x+w,_y2:y+h,_cx:x+w/2,_cy:y+h/2,_treeLabel:w>55&&h>25?String(items[0]._category):''});return}
   const sum=items.reduce((s,d)=>s+d._value,0);let subtotal=0,i=0;while(i<items.length-1&&subtotal<sum/2){subtotal+=items[i++]._value}const ratio=subtotal/sum;
   if(w>=h){layout(items.slice(0,i),x,y,w*ratio,h);layout(items.slice(i),x+w*ratio,y,w*(1-ratio),h)}else{layout(items.slice(0,i),x,y,w,h*ratio);layout(items.slice(i),x,y+h*ratio,w,h*(1-ratio))}
  }
  layout(leaves,0,0,width,height);spec.data.values=leaves;
  const encoding={x:{field:'_x',type:'quantitative',axis:null,scale:{domain:[0,width],nice:false}},x2:{field:'_x2'},y:{field:'_y',type:'quantitative',axis:null,scale:{domain:[0,height],reverse:true,nice:false}},y2:{field:'_y2'},color:{field:'_category',type:'nominal',legend:null},tooltip:[{field:'_category',title:labels[ci]},{field:'_formattedValue',title:labels[vi[0]]}]};
  spec.layer=[{mark:{type:'rect',stroke:'white',strokeWidth:1,tooltip:true},encoding}];
  const categoryObjects=options.visual&&options.model?Style.objects(options.model,options.visual):{},categoryProps=Object.assign({},Style.props(categoryObjects,'categoryLabels'),...(categoryObjects.categoryLabels||[]).filter(e=>e.selector?.data?.some(s=>s.dataViewWildcard)).map(e=>e.properties||{})),theme=options.model?.theme||{},categoryShow=Style.value(categoryProps.show,theme)!==false,dataShow=options.dataLabels?.show===true;
  const labelLayer=(field,settings,dy)=>({mark:{type:'text',color:settings.color||'white',font:settings.fontFamily||'Segoe UI',fontSize:settings.fontSize||12,dy,tooltip:true},encoding:{x:{...encoding.x,field:'_cx'},y:{...encoding.y,field:'_cy'},text:{field},tooltip:encoding.tooltip}});
  if(categoryShow)spec.layer.push(labelLayer('_treeLabel',{color:Style.color(categoryProps.color||categoryProps.fontColor,theme),fontSize:Style.value(categoryProps.fontSize,theme),fontFamily:Style.value(categoryProps.fontFamily,theme)},dataShow?-9:0));
  if(dataShow){for(const d of leaves)d._treeDataLabel=d._treeLabel?d._label:'';spec.layer.push(labelLayer('_treeDataLabel',options.dataLabels,categoryShow?9:0))}

  return spec;
 }
 if(type==='ribbonChart'){
  for(const category of categories){let start=0;for(const d of values.filter(d=>d._category===category).sort((a,b)=>b._value-a._value)){d._ribbonStart=start;start+=Math.max(0,d._value||0);d._ribbonEnd=start}}
  spec.mark={type:'area',interpolate:'monotone',tooltip:true,opacity:.85};spec.encoding={x:{field:'_category',type:'ordinal',sort:orderedCategories(),scale:{padding:0},title:labels[ci]},y:{field:'_ribbonEnd',type:'quantitative',stack:null,title:labels[vi[0]]},y2:{field:'_ribbonStart'},color:{field:'_series',type:'nominal',legend:series.length>1?{}:null},detail:{field:'_series'},tooltip:[{field:'_category',title:labels[ci]},{field:'_series',title:'Series'},{field:'_formattedValue',title:'Value'}]};return spec;
 }

 const axisType=options.model&&options.visual?Style.value(Style.props(Style.objects(options.model,options.visual),'categoryAxis').axisType,options.model.theme):undefined;
 // Multiple active levels form a compound category even when each level is
 // numeric (for example Year / Month). A numeric scale cannot plot its label.
 const categorical=categoryIndices.length>1||String(axisType||'').toLowerCase()==='categorical';
 const temporal=!categorical&&ci>=0&&['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart'].includes(type)&&(/DATE|TIMESTAMP/.test(options.fieldTypes?.[ci]||'')||rows.every(r=>r[ci]==null||typeof r[ci]==='string'&&/^\d{4}-\d\d-\d\d(?:$|[ T])/.test(r[ci])));
 const continuous=!categorical&&ci>=0&&['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart'].includes(type)&&numeric.includes(ci);
 const query=options.visual?.definition?.query,categoryField=query?Object.values(query.queryState||{}).flatMap(s=>(s.projections||[]).filter(p=>p.active!==false))[ci]?.field:undefined;
 const categorySort=categoryField&&query.sortDefinition?.sort?.find(s=>JSON.stringify(s.field)===JSON.stringify(categoryField));
 if(categoryIndices.length<=1&&categorical&&numeric.includes(ci)&&query?.sortDefinition?.isDefaultSort===true&&!categorySort&&['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart'].includes(type))categories.sort((a,b)=>a-b);
 const categoryTitle=categoryIndices.length>1?categoryIndices.map(i=>labels[i]).join(' / '):ci>=0?labels[ci]:null;
 const category={...(categoryIndices.length<=1&&categorical&&numeric.includes(ci)?{axis:{labelAngle:0}}:{}),field:'_category',type:temporal?'temporal':continuous?'quantitative':categorical?'ordinal':'nominal',title:categoryTitle,...(temporal||continuous?{scale:{...(continuous?{zero:false,nice:false}:{}),...(categorySort?.direction==='Descending'?{reverse:true}:{})},...(continuous&&rows.every(r=>r[ci]==null||Number.isInteger(r[ci]))?{axis:{format:'d'}}:{})}:{sort:orderedCategories(),scale:/line|area/i.test(type)?{padding:0}:{paddingOuter:0,paddingInner:/BarChart$/.test(type)||type==='barChart'?.4:.1}})};
 if(options._multipleCategories?.length){category.scale={...category.scale,...(temporal||continuous?{domain:(()=>{const ordered=options._multipleCategories.filter(x=>x!=null).slice().sort((a,b)=>continuous?a-b:String(a).localeCompare(String(b)));return ordered.length?[ordered[0],ordered.at(-1)]:undefined})()}:{domain:options._multipleCategories})}}
 const quantity={field:'_value',type:'quantitative',title:vi.length===1?labels[vi[0]]:null};
 const color={field:'_series',type:'nominal',sort:series,legend:series.length>1?{}:null};
 const tooltip=[{field:'_category',type:'nominal',title:categoryTitle||'Category'},{field:'_series',type:'nominal',title:'Series'},{field:'_formattedValue',type:'nominal',title:'Value'},...roles.flatMap((role,index)=>/^tooltips?$/i.test(role)?[{field:'_tooltip'+index,type:'nominal',title:labels[index]}]:[])];
 if(type==='violinPlot'){
  spec.data.values=values.filter(d=>Number.isFinite(d._value));spec.transform=[{density:'_value',as:['_value','_density']}];spec.mark={type:'area',orient:'horizontal',color:options.model?Style.color(Style.props(Style.objects(options.model,options.visual),'dataColours').defaultFillColour,options.model.theme):'#337b60',clip:true};spec.encoding={x:{field:'_density',type:'quantitative',stack:'center',axis:null},y:{field:'_value',type:'quantitative',axis:null,scale:{zero:false}},tooltip:[{field:'_value',type:'quantitative',title:labels[vi[0]]}]};return spec;
 }
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
  if(ci<0||series.length>1)for(const d of values)d._category=ci>=0?String(d._category)+' · '+d._series:d._series;
  if(values.some(v=>v._value<0))spec.usermeta={...spec.usermeta,mappingWarnings:['Negative slice values use absolute magnitudes for area; labels, tooltips and exported data retain their original signs.']};
  for(const d of values)d._magnitude=Math.abs(d._value||0);
  const settings=options.dataLabels||{},largest=new Set(values.map((d,i)=>({d,i})).sort((a,b)=>b.d._magnitude-a.d._magnitude||a.i-b.i).slice(0,12).map(x=>x.d)),total=values.reduce((sum,d)=>sum+d._magnitude,0),style=String(settings.labelStyle||'Data value');
  for(const d of values){const pct=total?new Intl.NumberFormat(options.model?.reportSettings?.locale||'en-US',{style:'percent',minimumFractionDigits:Number.isInteger(settings.precision)?Math.max(0,Math.min(20,settings.precision)):0,maximumFractionDigits:Number.isInteger(settings.precision)?Math.max(0,Math.min(20,settings.precision)):1}).format(d._magnitude/total):'0%';d._pieLabel=largest.has(d)?[/category/i.test(style)?d._category:null,/data value|value/i.test(style)?d._label:null,/percent/i.test(style)?pct:null].filter(x=>x!==null).join(' · ')||d._label:''}
  const encoding={theta:{...quantity,field:'_magnitude',stack:true},color:{field:'_category',type:'nominal',sort:[...new Set(values.map(d=>d._category))]},order:{field:'_category',sort:'ascending'},tooltip};
  const arc={mark:{type:'arc',innerRadius:type==='donutChart'?Math.min(width,height)*.22:0,tooltip:true},encoding};
  if(settings.show||settings.showSpecified===false||settings.show===undefined){spec.layer=[arc,{mark:{type:'text',radius:100,fontSize:Math.max(7,Math.min(40,(Number(settings.fontSize)||8)*4/3)),color:settings.color||options.model?.theme?.foreground||'#333',...(settings.fontFamily?{font:settings.fontFamily}:{}),tooltip:true},encoding:{theta:encoding.theta,order:encoding.order,text:{field:'_pieLabel',type:'nominal'},tooltip}}]}else{spec.mark=arc.mark;spec.encoding=encoding}return spec;
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
 const combo=/ComboChart$/.test(type),horizontal=/BarChart$/.test(type)||type==='barChart',line=['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart'].includes(type);
 const stacked=/stacked/i.test(type)||['columnChart','barChart'].includes(type),normalize=/hundredPercent/.test(type);if(horizontal)category.axis={...category.axis,labelAngle:0,labelLimit:Math.min(400,width*.45)};
 const secondary=role=>['Y2','LineY'].includes(role),axisQuantity=(isSecondary=false)=>({...quantity,title:vi.filter(i=>secondary(roles[i])===isSecondary).map(i=>labels[i]).join(' / ')||null,...(isSecondary?{axis:{orient:'right',grid:false}}:{axis:{orient:'left'}})});
 if(line&&values.some(row=>secondary(row._role))){
  const primary=values.some(row=>!secondary(row._role)),mark={type:type==='lineChart'?'line':'area',tooltip:true,point:type==='lineChart'},groups=[];
  for(const isSecondary of [false,true]){if(!isSecondary&&!primary)continue;groups.push({name:isSecondary?'pbi_secondary_y':'pbi_primary_y',layer:[{transform:[{filter:isSecondary?"datum._role === 'Y2' || datum._role === 'LineY'":"datum._role !== 'Y2' && datum._role !== 'LineY'"}],mark:{...mark},encoding:{x:structuredClone(category),y:{...axisQuantity(isSecondary),stack:stacked?(normalize?'normalize':'zero'):null},color:structuredClone(color),tooltip:structuredClone(tooltip)}}]})}
  spec.layer=groups;spec.resolve={scale:{y:'independent'}};spec.usermeta={...spec.usermeta,secondaryAxes:true};return spec;
 }
 if(combo){
  const hasLine=values.some(r=>secondary(r._role)),hasBar=values.some(r=>!secondary(r._role));
  const bar={transform:[{filter:"datum._role !== 'Y2' && datum._role !== 'LineY'"}],mark:{type:'bar',tooltip:true},encoding:{x:category,y:{...axisQuantity(),stack:stacked?'zero':null},color,tooltip}};
  if(!stacked)bar.encoding.xOffset={field:'_series',type:'nominal'};
  const curve={transform:[{filter:"datum._role === 'Y2' || datum._role === 'LineY'"}],mark:{type:'line',point:true,tooltip:true},encoding:{x:category,y:axisQuantity(true),color,tooltip}};
  spec.layer=[...(hasBar?[bar]:[]),...(hasLine?[curve]:[])];if(hasBar&&hasLine)spec.resolve={scale:{y:'independent'}};return spec;
 }
 spec.mark={type:line?(type==='lineChart'?'line':'area'):'bar',tooltip:true,...(line?{point:type==='lineChart'}:{})};
 spec.encoding=horizontal?{y:category,x:{...quantity,stack:stacked?(normalize?'normalize':'zero'):null},color,tooltip}:{x:category,y:{...quantity,stack:stacked?(normalize?'normalize':'zero'):null},color,tooltip};
 if(!stacked&&!line&&series.length>1)spec.encoding[horizontal?'yOffset':'xOffset']={field:'_series',type:'nominal'};
 if(line&&!stacked)spec.encoding.y.stack=null;
 if(!line&&options.dataLabels?.show){
  const settings=options.dataLabels,bar={mark:spec.mark,encoding:spec.encoding};
  const labelEncoding={...spec.encoding,text:{field:'_label',type:'nominal'}};delete labelEncoding.color;
  const mark={type:'text',color:settings.color||'#344e40',fontSize:Math.max(1,Math.min(160,(Number(settings.fontSize)||9)*4/3)),...(settings.fontFamily?{font:settings.fontFamily}:{}),tooltip:true};
  const slots=Math.max(1,categories.length*(stacked?1:series.length)),chars=Math.max(1,...values.map(v=>String(v._label||'').length));
  const fit=horizontal?Math.min(height/slots*.7,width*.35/(chars*.6)):width/slots*.82/(chars*.6);
  mark.fontSize=Math.min(mark.fontSize,Math.max(6,fit));
  const inside=/inside/i.test(settings.position||'');const endLabels=horizontal&&stacked&&series.length===1&&!inside;
  if(stacked){
   spec.transform=[{stack:'_value',groupby:['_category'],sort:[{field:'_series',order:'ascending'}],offset:normalize?'normalize':'zero',as:['_stackStart','_stackEnd']},{calculate:'(datum._stackStart + datum._stackEnd)/2',as:'_labelPosition'}];
   bar.encoding[horizontal?'x':'y']={...quantity,field:'_stackEnd',stack:null};bar.encoding[horizontal?'x2':'y2']={field:'_stackStart'};
   labelEncoding[horizontal?'x':'y']={...quantity,field:endLabels?'_stackEnd':'_labelPosition',stack:null};
   if(normalize){spec.transform.push({calculate:"datum._value == null ? '' : format(abs(datum._stackEnd-datum._stackStart), '."+(Number.isInteger(settings.precision)?Math.max(0,Math.min(20,settings.precision)):0)+"%')",as:'_label'});bar.encoding[horizontal?'x':'y'].axis={format:'.0%'}}
   mark.align=endLabels?'left':'center';if(endLabels){mark.dx=6;spec.padding={...spec.padding,right:70}}mark.baseline='middle';
  }else if(horizontal){mark.align={expr:inside?"datum._value < 0 ? 'left' : 'right'":"datum._value < 0 ? 'right' : 'left'"};mark.dx={expr:(inside?'-':'')+"(datum._value < 0 ? -4 : 4)"};mark.baseline='middle'}
  else{mark.baseline={expr:inside?"datum._value < 0 ? 'bottom' : 'top'":"datum._value < 0 ? 'top' : 'bottom'"};mark.dy={expr:(inside?'-':'')+"(datum._value < 0 ? 4 : -4)"}}
  spec.layer=[bar,{transform:[{filter:'isValid(datum._value)'}],mark,encoding:labelEncoding}];delete spec.mark;delete spec.encoding;
 }

 return spec;
}
const mapViews=new Map(),mapTypes=new Set(['map','pointMap','filledMap','choroplethMap']);
function mapFitForView(values,view,width=500,height=280){
 // Vega's fitted projection viewport excludes legend and layout padding.
 // Reading it after a completed layout avoids amplifying that size difference
 // into a large geographic centering error on local maps.
 const actualWidth=typeof view.width==='function'?view.width():undefined,actualHeight=typeof view.height==='function'?view.height():undefined;
 return Advanced.mapFit(values,Number.isFinite(actualWidth)&&actualWidth>0?actualWidth:width,Number.isFinite(actualHeight)&&actualHeight>0?actualHeight:height);
}
async function mountMapControls(element,view,initial,key,item,fit=initial,dataKey,values=[],manual=false){
 fit=mapFitForView(values,view,element.clientWidth,element.clientHeight);
 let state=Advanced.mapViewport(manual?initial:fit),drag=null,frame=0;
 const svg=element.querySelector('svg'),controls=document.createElement('div'),status=document.createElement('output');
 if(!svg)return;
 element.classList.add('interactive-map');element.style.position='relative';element.tabIndex=0;element.setAttribute('aria-label','Interactive map. Scroll wheel zooms, drag pans, click a country to filter. Plus and minus zoom, arrow keys pan, Home fits data.');
 controls.className='map-controls';controls.setAttribute('role','group');controls.setAttribute('aria-label','Map navigation');
 controls.style.cssText='position:absolute;top:6px;right:6px;z-index:2;display:flex;flex-wrap:wrap;gap:3px;align-items:center;max-width:calc(100% - 12px);padding:4px;background:rgba(255,255,255,.94);border:1px solid #dfe7e3;border-radius:6px;box-shadow:0 1px 4px #193a3718';
 status.setAttribute('aria-label','Map zoom');status.setAttribute('aria-live','polite');status.style.cssText='font:11px system-ui;min-width:36px;text-align:center;color:#193a37';
 const buttons={};
 function apply(next,remember=true){
  if(remember)manual=true;state=Advanced.mapViewport(next);status.textContent=Math.round(state.zoom*100)+'%';
  buttons.plus.disabled=state.zoom>=Advanced.mapLimits.maxZoom;buttons.minus.disabled=state.zoom<=Advanced.mapLimits.minZoom;
  if(key&&remember){mapViews.delete(key);mapViews.set(key,{...state,dataKey});if(mapViews.size>200)mapViews.delete(mapViews.keys().next().value)}
  if(!frame)frame=requestAnimationFrame(()=>{frame=0;if(element.isConnected)view.signal('mapZoom',state.zoom).signal('mapPanX',state.x).signal('mapPanY',state.y).runAsync().catch(()=>{})});
 }
 function zoom(factor,anchor={x:0,y:0}){const next=Math.max(Advanced.mapLimits.minZoom,Math.min(Advanced.mapLimits.maxZoom,state.zoom*factor)),ratio=next/state.zoom;apply({zoom:next,x:anchor.x-(anchor.x-state.x)*ratio,y:anchor.y-(anchor.y-state.y)*ratio})}
 function button(text,label,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-label',label);b.title=label;b.style.cssText='width:26px;height:26px;padding:0;line-height:1;font:16px system-ui;border:1px solid #dfe7e3;border-radius:4px;background:white;color:#193a37';b.onclick=event=>{event.stopPropagation();action()};controls.appendChild(b);return b}
 buttons.plus=button('+','Zoom in map',()=>zoom(2));buttons.minus=button('−','Zoom out map',()=>zoom(.5));controls.appendChild(status);
 function reset(){manual=false;if(key)mapViews.delete(key);fit=mapFitForView(values,view,element.clientWidth,element.clientHeight);apply(fit,false)}
 button('↺','Fit map to data',reset);
 item.onResize=(width,height)=>{fit=mapFitForView(values,view,width,height);if(!manual)apply(fit,false)};
 button('←','Pan map left',()=>apply({...state,x:state.x+.15}));button('→','Pan map right',()=>apply({...state,x:state.x-.15}));
 button('↑','Pan map up',()=>apply({...state,y:state.y+.15}));button('↓','Pan map down',()=>apply({...state,y:state.y-.15}));
 element.appendChild(controls);svg.style.touchAction='none';svg.style.cursor='grab';
 function down(event){if(![0,1].includes(event.button)||!event.isPrimary)return;if(event.button===1)event.preventDefault();drag={id:event.pointerId,px:event.clientX,py:event.clientY,x:state.x,y:state.y,zoom:state.zoom,middle:event.button===1};item.suppressClick=false}
 function move(event){if(!drag||drag.id!==event.pointerId)return;const dx=event.clientX-drag.px,dy=event.clientY-drag.py;if(!item.suppressClick&&Math.hypot(dx,dy)<4)return;item.suppressClick=true;try{svg.setPointerCapture(event.pointerId)}catch{}svg.style.cursor='grabbing';const box=svg.getBoundingClientRect();if(drag.middle){const next=Math.max(Advanced.mapLimits.minZoom,Math.min(Advanced.mapLimits.maxZoom,drag.zoom*Math.exp(-dy*.01))),ratio=next/drag.zoom;apply({zoom:next,x:drag.x*ratio,y:drag.y*ratio})}else apply({...state,x:drag.x+dx/Math.max(1,box.width),y:drag.y+dy/Math.max(1,box.height)})}
 function up(event){if(drag?.id!==event.pointerId)return;drag=null;svg.style.cursor='grab';try{if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId)}catch{}}
 function keyboard(event){if(event.target!==element&&event.target!==svg)return;const actions={'+':()=>zoom(2),'=':()=>zoom(2),'-':()=>zoom(.5),'ArrowLeft':()=>apply({...state,x:state.x+.15}),'ArrowRight':()=>apply({...state,x:state.x-.15}),'ArrowUp':()=>apply({...state,y:state.y+.15}),'ArrowDown':()=>apply({...state,y:state.y-.15}),'Home':reset};if(actions[event.key]){event.preventDefault();event.stopPropagation();actions[event.key]()}}
 function wheel(event){event.preventDefault();event.stopPropagation();const box=svg.getBoundingClientRect(),delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?box.height:1);zoom(Math.exp(-Math.max(-500,Math.min(500,delta))*.002),{x:(event.clientX-box.left)/Math.max(1,box.width)-.5,y:(event.clientY-box.top)/Math.max(1,box.height)-.5})}
 svg.addEventListener('wheel',wheel,{passive:false});
 svg.addEventListener('pointerdown',down);svg.addEventListener('pointermove',move);svg.addEventListener('pointerup',up);svg.addEventListener('pointercancel',up);element.addEventListener('keydown',keyboard);
 item.cleanup=()=>{if(frame)cancelAnimationFrame(frame);controls.remove();svg.removeEventListener('wheel',wheel);svg.removeEventListener('pointerdown',down);svg.removeEventListener('pointermove',move);svg.removeEventListener('pointerup',up);svg.removeEventListener('pointercancel',up);element.removeEventListener('keydown',keyboard)};
 status.textContent=Math.round(state.zoom*100)+'%';buttons.plus.disabled=state.zoom>=Advanced.mapLimits.maxZoom;buttons.minus.disabled=state.zoom<=Advanced.mapLimits.minZoom;
 await view.signal('mapZoom',state.zoom).signal('mapPanX',state.x).signal('mapPanY',state.y).runAsync();
}

function contentWidth(type,labels,rows,roles=[],viewport=500,options={}){
 if(options.visual?.tooltipOnly)return viewport;
 const supported=['waterfallChart','columnChart','clusteredColumnChart','stackedColumnChart','hundredPercentStackedColumnChart','lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart','lineClusteredColumnComboChart','lineStackedColumnComboChart','ribbonChart','heatmap','heatmapChart','boxplot','boxPlot'];
 if(!supported.includes(type)||!rows.length)return viewport;
 let ci=roles.findIndex(r=>['Category','Rows','X'].includes(r));if(ci<0)ci=0;
 const categoryIndices=roles.flatMap((role,i)=>role==='Category'?[i]:[]),categories=[...new Set(rows.map(r=>categoryIndices.length>1?categoryIndices.map(i=>r[i]??'(Blank)').join(' / '):r[ci]))],si=roles.findIndex(r=>['Series','Legend','Columns'].includes(r)),numeric=labels.map((_,i)=>i).filter(i=>!categoryIndices.includes(i)&&i!==ci&&i!==si&&!/^(tooltips?|formatting)$/i.test(roles[i]||'')&&rows.some(r=>typeof r[i]==='number'));
 const clustered=type==='clusteredColumnChart'||type==='lineClusteredColumnComboChart',series=clustered?Math.max(1,si>=0?new Set(rows.map(r=>r[si])).size:1)*Math.max(1,numeric.length):1;
 const line=['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart','ribbonChart'].includes(type),labelWidth=Math.min(100,Math.max(0,...categories.map(x=>String(x??'').length))*5.5);
 const axis=options.visual?Style.props(Style.objects(options.model||{},options.visual),'categoryAxis'):{},preferred=Number(Style.value(axis.preferredCategoryWidth,options.model?.theme));
 const theme=options.model?.theme||{},font=(Number(Style.value(axis.fontSize,theme))||10)*4/3,angle=Math.abs(Number(Style.value(axis.labelAngle,theme))||0)*Math.PI/180,label=Style.value(axis.show,theme)===false?0:Math.min(140,labelWidth*Math.cos(angle)+font*Math.sin(angle)),labelsOn=options.dataLabels?.show===true;
 const step=Number.isFinite(preferred)&&preferred>0?preferred:Math.max(line?12:24,clustered?series*Math.max(12,font):0,Math.min(line?60:140,label),labelsOn?font*2:0);
 const o=options.visual?Style.objects(options.model||{},options.visual):{},valueAxis=Style.props(o,'valueAxis'),legend=Style.props(o,'legend'),legendPosition=String(Style.value(legend.position,theme)||'bottom'),axisReserve=Style.value(valueAxis.show,theme)===false?8:Math.max(40,(Number(Style.value(valueAxis.fontSize,theme))||10)*5),legendReserve=Style.value(legend.show,theme)!==false&&/left|right/i.test(legendPosition)?Math.max(80,(Number(Style.value(legend.fontSize,theme))||10)*8):0;
 return Math.max(viewport,Math.ceil(categories.length*step+axisReserve+legendReserve));
}
function highlightSpec(spec,highlight,type){
 if(spec.usermeta?.secondaryAxes){const layer=spec.layer.map(group=>{if(!['pbi_primary_y','pbi_secondary_y'].includes(group.name))return group;const secondary=group.name==='pbi_secondary_y',keep=row=>['Y2','LineY'].includes(row._role)===secondary,sub={...spec,data:{values:spec.data.values.filter(keep)},layer:group.layer,usermeta:{...spec.usermeta,secondaryAxes:false}},hit={...highlight,data:{values:(highlight.data?.values||[]).filter(keep)}};delete sub.resolve;const result=highlightSpec(sub,hit,type);return {...group,layer:result.layer}});return {...spec,layer,usermeta:{...spec.usermeta,crossHighlight:true}}}
 const key=d=>JSON.stringify([d._category,d._series,d._detail,d._x,d._y]);
 const hits=new Map((highlight.data?.values||[]).map(d=>[key(d),d]));
 const values=spec.data.values.map(d=>({...d,_highlightValue:hits.get(key(d))?._value??null}));
 const base={...spec};delete base.$schema;delete base.config;delete base.usermeta;delete base.width;delete base.height;delete base.autosize;delete base.background;
 const overlay=structuredClone(base);const rename=node=>{if(node.name)node.name='pbi_highlight_'+node.name;for(const child of node.layer||[])rename(child)};rename(overlay);base.data={values:values.map(d=>({...d,_crossHighlight:false}))};overlay.data={values:values.filter(d=>d._highlightValue!==null).map(d=>({...d,_rowValues:hits.get(key(d))?._rowValues??d._rowValues,_rowFormats:hits.get(key(d))?._rowFormats,_value:d._highlightValue,_label:hits.get(key(d))?._label??'',_formattedValue:hits.get(key(d))?._formattedValue??'',_crossHighlight:true}))};
 function fade(n){if(n.mark){n.mark=typeof n.mark==='string'?{type:n.mark}:n.mark;n.mark.opacity=.22}for(const l of n.layer||[])fade(l)}fade(base);
 if(/hundredPercent/.test(type)){
  const totals=new Map();for(const d of values)totals.set(d._category,(totals.get(d._category)||0)+Math.abs(d._value||0));
  for(const d of overlay.data.values)d._value=(d._value||0)/(totals.get(d._category)||1);
  const adjust=n=>{for(const channel of Object.values(n.encoding||{}))if(channel?.stack==='normalize')channel.stack='zero';for(const l of n.layer||[])adjust(l)};adjust(overlay);
 }
 if(['pieChart','donutChart'].includes(type)){
  const ordered=values.slice().sort((a,b)=>String(a._category)<String(b._category)?-1:String(a._category)>String(b._category)?1:0),total=ordered.reduce((n,d)=>n+Math.abs(d._value||0),0),positions=new Map();let angle=0;
  for(const d of ordered){const span=total?Math.abs(d._value||0)/total*Math.PI*2:0;positions.set(key(d),[angle,angle+span*Math.min(1,Math.abs(d._highlightValue||0)/(Math.abs(d._value)||1))]);angle+=span}
  for(const d of overlay.data.values)[d._highlightStart,d._highlightEnd]=positions.get(key(d));
  if(overlay.layer)overlay.layer=overlay.layer.filter(n=>n.mark?.type==='arc');
  const arcs=n=>{if(n.mark?.type==='arc'){n.encoding.theta={field:'_highlightEnd',type:'quantitative',stack:null,scale:null};n.encoding.theta2={field:'_highlightStart'}}for(const l of n.layer||[])arcs(l)};arcs(overlay);
 }else if(/stacked/i.test(type)||type==='barChart'){
  const groups=new Map();for(const d of values){if(!groups.has(d._category))groups.set(d._category,[]);groups.get(d._category).push(d)}const positions=new Map();
  for(const group of groups.values()){let positive=0,negative=0;const denominator=/hundredPercent/.test(type)?group.reduce((n,d)=>n+Math.abs(d._value||0),0)||1:1;for(const d of group.slice().sort((a,b)=>String(a._series)<String(b._series)?1:String(a._series)>String(b._series)?-1:0)){const start=(d._value||0)<0?negative:positive;positions.set(key(d),[start/denominator,(start+(d._highlightValue||0))/denominator]);if((d._value||0)<0)negative+=d._value||0;else positive+=d._value||0}}
  for(const d of overlay.data.values)[d._highlightStart,d._highlightEnd]=positions.get(key(d));
  const stacks=n=>{for(const channel of ['x','y'])if(n.encoding?.[channel]?.field==='_value'&&n.encoding[channel].stack!==undefined){n.encoding[channel]={...n.encoding[channel],field:'_highlightEnd',stack:null};if(n.mark?.type==='bar'||n.mark?.type==='area')n.encoding[channel+'2']={field:'_highlightStart'}}for(const l of n.layer||[])stacks(l)};stacks(overlay);
 }
 const result={...spec,layer:[base,overlay]};delete result.mark;delete result.encoding;delete result.params;delete result.data;result.usermeta={...spec.usermeta,crossHighlight:true};return result;
}
const active=new Set();
const mountLeases=new Set(),mountOwners=new WeakMap(),retiredViews=new WeakSet();let mountEpoch=0;
function currentMount(lease){return !!lease&&!lease.cancelled&&!lease.controller.signal.aborted&&lease.epoch===mountEpoch&&mountOwners.get(lease.element)===lease&&lease.element.isConnected}
function cancelMount(lease){
 if(!lease||lease.cancelled)return;
 lease.cancelled=true;lease.controller.abort();lease.external?.removeEventListener('abort',lease.onAbort);mountLeases.delete(lease);if(mountOwners.get(lease.element)===lease)mountOwners.delete(lease.element);
 const view=lease.view;lease.view=null;if(view)retireView(view);
}
async function yieldMount(lease){
 if(!currentMount(lease)){cancelMount(lease);return false}
 // A browser task boundary lets navigation, filter clicks and abort events run
 // before another synchronous spec/compile stage starts. A microtask does not.
 if(typeof root.scheduler?.yield==='function')await root.scheduler.yield();else await new Promise(resolve=>setTimeout(resolve,0));
 if(!currentMount(lease)){cancelMount(lease);return false}return true;
}
function disposeAll(){mountEpoch++;for(const lease of [...mountLeases])cancelMount(lease);for(const item of [...active])retireView(item.view);active.clear()}
function smallMultiplePlan(type,labels,rows,roles,options={}){
 if(options._noMultiples||!roles.includes('Category'))return null;
 const facets=roles.flatMap((r,i)=>['Rows','Columns','SmallMultiples','SmallMultiple'].includes(r)?[i]:[]);if(!facets.length)return null;
 const keep=labels.map((_,i)=>i).filter(i=>!facets.includes(i)),groups=new Map(),rowFormatMap=new Map(),rowValueMap=new Map(),sourceRowFormatMap=new Map();
 for(const [index,row] of rows.entries()){const key=JSON.stringify(facets.map(i=>row[i]));if(!groups.has(key))groups.set(key,{title:facets.map(i=>row[i]??'(Blank)').join(' / '),identity:Object.fromEntries(facets.map((i,j)=>['_facet'+j,row[i]])),rows:[]});const projected=keep.map(i=>row[i]),formats=options._rowFormatMap?.get(row)??options.rowFormats?.[index];groups.get(key).rows.push(projected);rowFormatMap.set(projected,keep.map(i=>formats?.[i]??options.formats?.[i]));rowValueMap.set(projected,options._rowValueMap?.get(row)??row);sourceRowFormatMap.set(projected,options._sourceRowFormatMap?.get(row)??formats)}
 const visual=options.visual?structuredClone(options.visual):undefined;
 if(visual)for(const role of ['Rows','Columns','SmallMultiples','SmallMultiple'])delete visual.definition.query.queryState[role];
 const channels=options.channels&&Object.fromEntries(Object.entries(options.channels).map(([key,value])=>[key,value!==''&&value!=='auto'&&value!=='none'&&value!==undefined?(keep.includes(Number(value))?String(keep.indexOf(Number(value))):'none'):value]));
 const ordered=[...groups.values()];const sorts=options.visual?.definition?.query?.sortDefinition?.sort||[],ps=Object.values(options.visual?.definition?.query?.queryState||{}).flatMap(s=>s.projections||[]);if(!sorts.some(s=>facets.some(i=>JSON.stringify(ps[i]?.field)===JSON.stringify(s.field))))ordered.sort((a,b)=>a.title.localeCompare(b.title,undefined,{numeric:true}));
 return {facets,keep,channels,rowFormatMap,rowValueMap,sourceRowFormatMap,labels:keep.map(i=>labels[i]),roles:keep.map(i=>roles[i]),visual,groups:ordered};
}
async function mountMultiples(element,type,labels,rows,roles,options,plan){
 element.style.cssText+=';overflow:auto;pointer-events:auto;min-height:0';element.setAttribute('tabindex','0');element.setAttribute('role','region');element.setAttribute('aria-label','Scrollable small multiples');
 const p=options.model&&options.visual?Style.props(Style.objects(options.model,options.visual),'smallMultiplesLayout'):{},requested=Number(Style.value(p.columnCount??p.columns,options.model?.theme)),columns=Number.isInteger(requested)&&requested>0?Math.min(12,requested):Math.min(2,plan.groups.length||1),visibleRows=Math.min(3,Math.ceil(plan.groups.length/columns)||1),height=Math.max(200,(element.clientHeight-12*(visibleRows-1))/visibleRows);
 const grid=document.createElement('div');grid.className='small-multiples';grid.style.cssText='display:grid;grid-template-columns:repeat('+columns+',minmax(220px,1fr));gap:12px;min-width:'+columns*220+'px';element.replaceChildren(grid);
 const categoryIndex=plan.roles.indexOf('Category'),categories=[...new Set(plan.groups.flatMap(g=>g.rows.map(r=>r[categoryIndex])))],numbers=plan.groups.flatMap(g=>g.rows.flatMap(r=>plan.roles.flatMap((role,i)=>['Y','Y2'].includes(role)&&Number.isFinite(r[i])?[r[i]]:[]))),shared=/^(?:clustered|stacked|hundredPercent|line|area|column|bar)/.test(type)&&!/Combo/.test(type),domain=/hundredPercent/.test(type)?[0,1]:numbers.length?[numbers.reduce((m,n)=>Math.min(m,n),0),numbers.reduce((m,n)=>Math.max(m,n),1)]:undefined;
 const tasks=[];for(const group of plan.groups){if(!await yieldMount(options._mountLease))break;const cell=document.createElement('section'),head=document.createElement('h4'),chart=document.createElement('div');head.textContent=group.title;const sub=options.visual?Style.props(Style.objects(options.model||{},options.visual),'subheader'):{},theme=options.model?.theme||{};head.style.cssText='margin:0;height:24px;padding-left:24px;text-align:'+(Style.value(sub.alignment??sub.horizontalAlignment,theme)||'left');head.style.fontSize=((Number(Style.value(sub.fontSize,theme))||10.5)*4/3)+'px';head.style.fontFamily=Style.value(sub.fontFamily,theme)||theme.textClasses?.label?.fontFace||'Segoe UI';head.style.fontWeight=Style.value(sub.bold,theme)?'bold':'normal';head.style.color=Style.color(sub.fontColor??sub.color,theme)||theme.foreground||'#252423';cell.style.cssText='min-width:0;height:'+height+'px;overflow:hidden';chart.style.cssText='height:calc(100% - 24px);min-width:0';cell.append(head,chart);grid.append(cell);
  const highlightRows=options.highlightRows?.filter(row=>plan.facets.every((i,j)=>JSON.stringify(row[i])===JSON.stringify(group.identity['_facet'+j]))).map(row=>{const projected=plan.keep.map(i=>row[i]);plan.rowValueMap.set(projected,row);return projected});
  const add=d=>({...d,...group.identity}),pending=mount(chart,type,plan.labels,group.rows,plan.roles,{...options,highlightRows,_noMultiples:true,_rowFormatMap:plan.rowFormatMap,_rowValueMap:plan.rowValueMap,_sourceRowFormatMap:plan.sourceRowFormatMap,channels:plan.channels,_multipleCategories:categories,_multipleDomain:shared&&!/stacked/i.test(type)?domain:/hundredPercent/.test(type)?domain:undefined,visual:plan.visual,formats:plan.keep.map(i=>options.formats?.[i]),fieldTypes:plan.keep.map(i=>options.fieldTypes?.[i]),onSelect:options.onSelect?((d,...args)=>options.onSelect(add(d),...args)):undefined,onHover:options.onHover?((d,...args)=>options.onHover(d?add(d):d,...args)):undefined,matchesDatum:options.matchesDatum?(d=>options.matchesDatum(add(d))):undefined});
  // Later child launches yield browser tasks. Observe an early rejection now;
  // Promise.all below still propagates the original active render error.
  pending.catch(()=>{});tasks.push(pending);
 }return Promise.all(tasks);
}
function barWindow(type,labels,rows,roles,viewport,options={}){
 if(options.visual?.tooltipOnly||options._barWindow||!['barChart','clusteredBarChart','stackedBarChart','hundredPercentStackedBarChart'].includes(type))return null;
 let ci=roles.findIndex(r=>['Category','Group','Rows'].includes(r));if(ci<0)return null;
 const categories=[...new Set(rows.map(r=>r[ci]))],o=options.visual?Style.objects(options.model||{},options.visual):{},theme=options.model?.theme||{},axis=Style.props(o,'categoryAxis'),font=(Number(Style.value(axis.fontSize,theme))||10.5)*4/3,preferred=Number(Style.value(axis.preferredCategoryWidth,theme)),labelsOn=options.dataLabels?.show===true,step=preferred>0?preferred:Math.max(24,font*(labelsOn?2.2:1.8)),legend=Style.props(o,'legend'),legendPosition=String(Style.value(legend.position,theme)||'bottom'),legendHeight=Style.value(legend.show,theme)!==false&&/top|bottom/i.test(legendPosition)?Math.max(20,(Number(Style.value(legend.fontSize,theme))||10)*2):0,reserve=(Style.value(Style.props(o,'valueAxis').show,theme)===false?12:32)+legendHeight,count=Math.max(1,Math.floor((viewport-reserve)/step));
 // Every window start must be reachable, including the final category. A
 // fixed plot reserve can leave less than one row step of actual overflow.
 // Round upward because browser scrollHeight is measured in whole pixels.
 return categories.length>count?{ci,categories,step,count,totalHeight:Math.ceil(Math.max(categories.length*step+48,viewport+(categories.length-count)*step))}:null;
}
function retireView(view){if(!view||retiredViews.has(view))return;retiredViews.add(view);for(const item of active)if(item.view===view){if(item.mountLease){item.mountLease.view=null;cancelMount(item.mountLease)}item.observer?.disconnect();item.cleanup?.();active.delete(item)}view.finalize()}
async function mountScrollingBars(element,type,labels,rows,roles,options,plan){
 element.style.overflow='auto';element.style.pointerEvents='auto';element.tabIndex=0;element.setAttribute('role','region');element.setAttribute('aria-label','Scrollable bar chart');
 const surface=document.createElement('div'),spacer=document.createElement('div');surface.className='bar-window';surface.style.cssText='position:sticky;top:0;z-index:1;width:100%;overflow:hidden;height:'+element.clientHeight+'px';spacer.style.height=Math.max(0,plan.totalHeight-element.clientHeight)+'px';spacer.style.pointerEvents='none';element.replaceChildren(surface,spacer);
 const indices=labels.flatMap((_,i)=>['Y','Y2','Values','Value'].includes(roles[i])?[i]:[]),numbers=rows.flatMap(r=>indices.map(i=>r[i]).filter(Number.isFinite)),currency=indices.some(i=>/[$€£¥]/.test(options.formats?.[i]||'')),units=options.model?.reportSettings?.defaultDisplayUnitsToNone?1:autoUnits(numbers.reduce((m,n)=>Math.max(m,Math.abs(n)),0),currency),totals=new Map();for(const r of rows){const key=r[plan.ci],t=totals.get(key)||[0,0];for(const i of indices)if(Number.isFinite(r[i]))t[r[i]<0?0:1]+=r[i];totals.set(key,t)}const stacked=/stacked/i.test(type)||type==='barChart',domain=/hundredPercent/.test(type)?[0,1]:stacked?[Math.min(0,...[...totals.values()].map(t=>t[0])),Math.max(1,...[...totals.values()].map(t=>t[1]))]:[numbers.reduce((m,n)=>Math.min(m,n),0),numbers.reduce((m,n)=>Math.max(m,n),1)];
 if(!/hundredPercent/.test(type))for(let i=0;i<2;i++){const n=domain[i];if(n){const step=10**Math.floor(Math.log10(Math.abs(n)));domain[i]=Math.sign(n)*Math.ceil(Math.abs(n)/step)*step}}
 let current,pendingTarget,start=-1,serial=0,disposed=false,timer;const controller={mountLease:options._mountLease,view:{finalize(){disposed=true;serial++;clearTimeout(timer);cancelMount(mountOwners.get(pendingTarget));retireView(current)}},cleanup:()=>{element.removeEventListener('scroll',onScroll);element.removeEventListener('keydown',onKey)}};options._mountLease.view=controller.view;active.add(controller);
 async function draw(){if(disposed||!currentMount(options._mountLease))return;const next=Math.max(0,Math.min(plan.categories.length-plan.count,Math.floor(element.scrollTop/plan.step)));if(next===start)return;start=next;const token=++serial,chosen=new Set(plan.categories.slice(start,start+plan.count)),subset=rows.filter(r=>chosen.has(r[plan.ci])),target=document.createElement('div');target.style.cssText='width:100%;height:100%';cancelMount(mountOwners.get(pendingTarget));pendingTarget=target;surface.replaceChildren(target);retireView(current);current=null;
  const view=await mount(target,type,labels,subset,roles,{...options,highlightRows:options.highlightRows?.filter(r=>chosen.has(r[plan.ci])),_barWindow:true,_multipleCategories:undefined,_multipleDomain:domain,_axisUnits:units,dataLabels:{...options.dataLabels,units:options.dataLabels?.units>0?options.dataLabels.units:units}});if(disposed||token!==serial||!currentMount(options._mountLease)){retireView(view);return}current=view;element.dataset.firstCategory=String(plan.categories[start]);element.dataset.lastCategory=String(plan.categories[Math.min(plan.categories.length-1,start+plan.count-1)]);element.dataset.categoryCount=String(plan.categories.length);
 }
 function onScroll(){clearTimeout(timer);timer=setTimeout(()=>draw().catch(console.error),30)}
 function onKey(event){if(event.target!==element||!['Home','End'].includes(event.key))return;event.preventDefault();element.scrollTop=event.key==='End'?element.scrollHeight:0;onScroll()}
 element.addEventListener('scroll',onScroll);element.addEventListener('keydown',onKey);if(root.ResizeObserver){controller.observer=new ResizeObserver(()=>{if(disposed||!element.isConnected)return;surface.style.height=element.clientHeight+'px';const updated=barWindow(type,labels,rows,roles,element.clientHeight,options);plan=updated||{...plan,count:plan.categories.length,totalHeight:element.clientHeight};spacer.style.height=Math.max(0,plan.totalHeight-element.clientHeight)+'px';start=-1;onScroll()});controller.observer.observe(element)}
 await draw();return controller.view;
}
async function mount(element,type,labels,rows,roles,options={}){
 if(options.signal?.aborted||!element.isConnected)return;
 cancelMount(mountOwners.get(element));const lease={element,epoch:mountEpoch,controller:new AbortController(),external:options.signal,cancelled:false,view:null};lease.onAbort=()=>cancelMount(lease);mountOwners.set(element,lease);mountLeases.add(lease);lease.external?.addEventListener('abort',lease.onAbort,{once:true});
 try{
  if(!await yieldMount(lease))return;
  const result=await mountOwned(element,type,labels,rows,roles,{...options,signal:lease.controller.signal,_mountLease:lease});
  if(!currentMount(lease)){if(Array.isArray(result))result.forEach(retireView);else retireView(result);cancelMount(lease);return}return result;
 }catch(error){const stale=!currentMount(lease);cancelMount(lease);if(!stale)throw error}
}
async function mountOwned(element,type,labels,rows,roles,options){
 options={...options,_rowFormatMap:options._rowFormatMap||new Map(rows.map((row,i)=>[row,options.rowFormats?.[i]]))};
 rows=visibleRows(rows,roles,options);
 const multiple=smallMultiplePlan(type,labels,rows,roles,options);if(multiple)return mountMultiples(element,type,labels,rows,roles,options,multiple);
 const windowPlan=barWindow(type,labels,rows,roles,element.clientHeight,options);if(windowPlan)return mountScrollingBars(element,type,labels,rows,roles,options,windowPlan);
 if(!root.vegaEmbed)throw Error('Local Vega libraries did not load. Restart the updated server and refresh the page.');
 const viewportWidth=Math.max(80,element.clientWidth),scrollWidth=contentWidth(type,labels,rows,roles,viewportWidth,options),width=scrollWidth,height=Math.max(80,element.clientHeight-(scrollWidth>viewportWidth?16:0));
 element.style.overflowX='auto';element.style.overflowY='hidden';element.style.pointerEvents='auto';element.setAttribute('tabindex','0');element.setAttribute('role','region');element.setAttribute('aria-label','Scrollable chart');
 const surface=document.createElement('div');surface.className='chart-scroll-surface';surface.style.cssText='height:100%;width:'+width+'px;min-width:100%';element.replaceChildren(surface);
 const cached=mapViews.get(options.mapKey);
 if(!await yieldMount(options._mountLease))return;
 let spec=buildSpec(type,labels,rows,roles,{...options,width,height});
 if(options.highlightRows){const highlight=buildSpec(type,labels,options.highlightRows,roles,{...options,width,height,highlightRows:undefined});spec=highlightSpec(spec,highlight,type)}
 const mapState=cached?.dataKey===spec.usermeta?.mapDataKey?Advanced.mapViewport(cached):spec.usermeta?.mapViewport||options.mapViewport;
 if(mapTypes.has(type)&&mapState)for(const param of spec.params||[])param.value=({mapZoom:mapState.zoom,mapPanX:mapState.x,mapPanY:mapState.y})[param.name]??param.value;
 if(options.onSelect&&!options.highlightRows){
  for(const datum of spec.data?.values||[]){datum._selected=options.matchesDatum?options.matchesDatum(datum):true;if(datum._barOpacity!==undefined)datum._barSelectionOpacity=datum._barOpacity*(datum._selected?1:.25)}
  const baseOpacity=typeof spec.mark==='object'?spec.mark.opacity??1:1;const opacity={condition:{test:'datum._selected',value:baseOpacity},value:baseOpacity*.25};
  if(spec.encoding)spec.encoding.opacity=spec.encoding.opacity?.field==='_barOpacity'?{field:'_barSelectionOpacity',type:'quantitative',scale:null,legend:null}:opacity;
  for(const layer of spec.layer||[])if(!layer.data){layer.encoding=layer.encoding||{};const base=typeof layer.mark==='object'?layer.mark.opacity??1:1;layer.encoding.opacity=layer.encoding.opacity?.field==='_barOpacity'?{field:'_barSelectionOpacity',type:'quantitative',scale:null,legend:null}:{condition:{test:'datum._selected',value:base},value:base*.25}}
 }
 const locale=Formats.vegaLocale(options.model?.reportSettings?.locale);
 if(!await yieldMount(options._mountLease))return;
 const result=await root.vegaEmbed(surface,spec,{actions:false,renderer:'svg',tooltip:options.tooltip===false||options.onHover?suppressDefaultTooltip:true,formatLocale:locale.number,timeFormatLocale:locale.time});
 if(!currentMount(options._mountLease)){retireView(result.view);return}
 const item={view:result.view,mountLease:options._mountLease};options._mountLease.view=result.view;let lastWidth=viewportWidth,lastHeight=element.clientHeight;active.add(item);
 if(mapTypes.has(type)&&spec.projection){
  await mountMapControls(element,result.view,mapState,options.mapKey,item,spec.usermeta?.mapAutoViewport,spec.usermeta?.mapDataKey,spec.data.values,!!options.mapViewport||cached?.dataKey===spec.usermeta?.mapDataKey);
  if(!active.has(item)||!currentMount(options._mountLease))return;
  if(!element.isConnected){retireView(item.view);return}
 }
 const scrollKey=event=>{if(event.target!==element||element.scrollWidth<=element.clientWidth||!['Home','End'].includes(event.key))return;event.preventDefault();event.stopPropagation();element.scrollLeft=event.key==='End'?element.scrollWidth:0};element.addEventListener('keydown',scrollKey);const scrollCleanup=item.cleanup;item.cleanup=()=>{scrollCleanup?.();element.removeEventListener('keydown',scrollKey)};
 if(options.tooltip!==false&&options.onHover){
  const hover=(event,mark)=>{const role=mark?.mark?.role||'';if(mark?.datum&&!/^(axis|legend)/.test(role))options.onHover(mark.datum,event)};
  result.view.addEventListener('mousemove',hover);result.view.addEventListener('mouseover',hover);
  const leave=()=>options.onLeave?.(),focus=event=>{const mark=event.target.__data__,rect=event.target.getBoundingClientRect();hover({clientX:rect.left+rect.width/2,clientY:rect.top+rect.height/2},mark)};
  for(const node of surface.querySelectorAll('svg [role="graphics-symbol"]'))if(node.__data__?.datum?._rowIdentity||node.__data__?.datum?._categoryValue!==undefined)node.setAttribute('tabindex','0');
  element.addEventListener('mouseleave',leave);element.addEventListener('focusin',focus);element.addEventListener('focusout',leave);
  const previous=item.cleanup;item.cleanup=()=>{previous?.();element.removeEventListener('mouseleave',leave);element.removeEventListener('focusin',focus);element.removeEventListener('focusout',leave)};
 }
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
 if(root.ResizeObserver){item.observer=new ResizeObserver(entries=>{if(!active.has(item))return;if(!element.isConnected){retireView(item.view);return}const {width,height}=entries[0].contentRect;if(width>0&&height>0&&(Math.abs(width-lastWidth)>1||Math.abs(height-lastHeight)>1)){lastWidth=width;lastHeight=height;surface.style.width=contentWidth(type,labels,rows,roles,Math.max(80,width),options)+'px';item.view.width(contentWidth(type,labels,rows,roles,Math.max(80,width),options)).height(Math.max(80,height-(contentWidth(type,labels,rows,roles,width,options)>width?16:0))).resize().runAsync().then(()=>{if(active.has(item)&&element.isConnected)item.onResize?.(width,height)}).catch(()=>{})}});item.observer.observe(element)}
 return result.view;
}
const api={highlightSpec,barWindow,autoUnits,labelText,visibleRows,smallMultiplePlan,contentWidth,linearFit,applyTrends,types,buildSpec,mapFitForView,mount,disposeAll,dataLabelOptions};if(typeof module!=='undefined')module.exports=api;root.VegaRenderer=api;
})(globalThis);
