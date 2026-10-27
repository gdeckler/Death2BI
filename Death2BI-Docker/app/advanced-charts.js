(function(root){
const types=['scatterChart','stripPlot','stripChart','ternaryChart','ternaryPlot','map','pointMap','filledMap','choroplethMap'];
function channels(type){
 if(type==='scatterChart')return [['x','X',true],['y','Y',true],['size','Size',true,true],['color','Color',false,true],['detail','Point identity',false,true]];
 if(['stripPlot','stripChart'].includes(type))return [['value','Value',true],['category','Category',false,true],['color','Color',false,true]];
 if(['ternaryChart','ternaryPlot'].includes(type))return [['a','Component A',true],['b','Component B',true],['c','Component C',true],['color','Color',false,true],['detail','Point identity',false,true]];
 if(['map','pointMap'].includes(type))return [['country','Country / ISO code',false,true],['latitude','Latitude',true,true],['longitude','Longitude',true,true],['size','Size',true,true],['color','Color',false,true],['detail','Point identity',false,true]];
 return [['country','Country / ISO code',false],['value','Value',true]];
}
const normal=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
function geography(){
 if(!root.Death2Geo&&typeof module!=='undefined')require('./dist/vendor/world-geography.js');
 if(!root.Death2Geo)throw Error('Local map geography did not load. Restart the updated server and refresh.');
 return root.Death2Geo.features;
}
const mapLimits=Object.freeze({minZoom:1,maxZoom:65536,pointZoom:32});
function mapViewport(value={}){
 const finite=(n,fallback)=>Number.isFinite(n)?n:fallback,zoom=Math.max(mapLimits.minZoom,Math.min(mapLimits.maxZoom,finite(value.zoom,mapLimits.minZoom)));
 return {zoom,x:Math.max(-zoom,Math.min(zoom,finite(value.x,0))),y:Math.max(-zoom,Math.min(zoom,finite(value.y,0)))};
}
// Equal Earth coordinates in projection units, matching the locally bundled Vega projection.
function projectEqualEarth(lon,lat){const a1=1.340264,a2=-.081106,a3=.000893,a4=.003796,m=Math.sqrt(3)/2,l=Math.asin(m*Math.sin(lat*Math.PI/180)),l2=l*l,l6=l2*l2*l2;return [lon*Math.PI/180*Math.cos(l)/(m*(a1+3*a2*l2+l6*(7*a3+9*a4*l2))),-l*(a1+a2*l2+l6*(a3+a4*l2))]}
function mapFit(values=[],width=500,height=280){
 width=Number.isFinite(width)?Math.max(1,width):500;height=Number.isFinite(height)?Math.max(1,height):280;
 const points=[];const area=ring=>Math.abs(ring.reduce((sum,p,i)=>{const q=ring[(i+1)%ring.length];return sum+p[0]*q[1]-q[0]*p[1]},0));
 for(const d of values){if(Number.isFinite(d._longitude)&&Number.isFinite(d._latitude))points.push([d._longitude,d._latitude]);else if(d.geometry&&d._value!=null){const polygons=d.geometry.type==='Polygon'?[d.geometry.coordinates]:d.geometry.type==='MultiPolygon'?d.geometry.coordinates:[];const ring=polygons.reduce((best,p)=>!best||area(p[0])>area(best)?p[0]:best,null);if(ring)for(const point of ring)points.push(point)}}
 let loX=Infinity,hiX=-Infinity,loY=Infinity,hiY=-Infinity;
 for(const point of points){if(!Number.isFinite(point[0])||!Number.isFinite(point[1])||Math.abs(point[0])>180||Math.abs(point[1])>90)continue;const [x,y]=projectEqualEarth(...point);if(!Number.isFinite(x)||!Number.isFinite(y))continue;loX=Math.min(loX,x);hiX=Math.max(hiX,x);loY=Math.min(loY,y);hiY=Math.max(hiY,y)}
 if(!Number.isFinite(loX))return {zoom:mapLimits.minZoom,x:0,y:0};
 const scale=Math.max(1,Math.min((width-12)/5.5,(height-12)/2.7)),spanX=hiX-loX,spanY=hiY-loY;
 // Use real nonzero geographic extents, even for a street/city-sized cluster.
 // A collapsed axis imposes no fit constraint. Only a coincident point domain
 // uses a bounded regional default; it must not force every map to that extent.
 const fitX=spanX>1e-12?Math.max(1,width-2*Math.min(24,width/4))/(scale*spanX):Infinity,fitY=spanY>1e-12?Math.max(1,height-2*Math.min(24,height/4))/(scale*spanY):Infinity;
 const zoom=Math.max(mapLimits.minZoom,Math.min(mapLimits.maxZoom,Number.isFinite(Math.min(fitX,fitY))?Math.min(fitX,fitY):mapLimits.pointZoom));
 return mapViewport({zoom,x:-scale*zoom*(hiX+loX)/2/width,y:-scale*zoom*(hiY+loY)/2/height});
}
let countryIndex, indexedFeatures;
let regionFeatures,regionIndex;
function resolveRegion(value,features){
 if(regionFeatures!==features){regionFeatures=features;regionIndex=new Map();for(const f of features)for(const key of [f.properties.continent,f.properties.region,f.properties.subregion].filter(Boolean)){const n=normal(key);if(!regionIndex.has(n))regionIndex.set(n,new Set());regionIndex.get(n).add(f)}}
 const key=normal(value),aliases={eastasia:'easternasia',southeastasia:'southeasternasia',southasia:'southernasia',australasiaoceania:'oceania',easterneurope:'easterneurope',easteurope:'easterneurope'};
 const regions={middleeastnorthafrica:['westernasia','northernafrica'],centralamericacaribbean:['centralamerica','caribbean'],westerneurope:['westerneurope','northerneurope','southerneurope'],subsaharanafrica:['easternafrica','middleafrica','southernafrica','western africa']};
 return [...new Set((regions[key]||[aliases[key]||key]).flatMap(n=>[...(regionIndex.get(normal(n))||[])]))];
}
const countryPoints=new WeakMap();
function resolveCountry(value,features){
 if(indexedFeatures!==features){countryIndex=new Map();indexedFeatures=features;for(const feature of features)for(const key of feature.properties.keys){const normalized=normal(key),matches=countryIndex.get(normalized)||new Set();matches.add(feature);countryIndex.set(normalized,matches)}}
 const key=normal(value),aliases={micronesiafedsts:'fsm',syrianarabrepublic:'syr',bahamasthe:'bhs',congodemrep:'cod',congorep:'cog',egyptarabrep:'egy',gambiathe:'gmb',iranislamicrep:'irn',korearep:'kor',koreadempeoplesrep:'prk',laopdr:'lao',kyrgyzrepublic:'kgz',slovakrepublic:'svk',venezuelarb:'ven',yemenrep:'yem',hongkongsarchina:'hkg',macaosarchina:'mac',westbankandgaza:'pse',uk:'unitedkingdom',turkiye:'turkey',ivorycoast:'cotedivoire',congokinshasa:'cod',congobrazzaville:'cog',southkorea:'kor',northkorea:'prk',russianfederation:'rus',unitedstatesofamerica:'usa',vaticancity:'vat',easttimor:'tls'};
 const matches=countryIndex.get(aliases[key]||key)||countryIndex.get(key);
 if(!matches){const region=resolveRegion(value,features);if(region.length){const polygons=region.flatMap(f=>f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates);return {feature:{type:'Feature',properties:{name:String(value)},geometry:{type:'MultiPolygon',coordinates:polygons}}}}}
 if(['congo','korea'].includes(key)||matches?.size>1)return {reason:'ambiguous'};
 return matches?.size===1?{feature:[...matches][0]}:{reason:'unmatched'};
}
function countryPoint(feature){
 if(countryPoints.has(feature))return countryPoints.get(feature);
 // Representative interior point of the largest polygon, not a street/capital lookup.
 const polygons=feature.geometry.type==='Polygon'?[feature.geometry.coordinates]:feature.geometry.coordinates;
 const area=ring=>Math.abs(ring.reduce((sum,p,i)=>{const q=ring[(i+1)%ring.length];return sum+p[0]*q[1]-q[0]*p[1]},0));
 const polygon=polygons.reduce((best,p)=>area(p[0])>area(best[0])?p:best),ring=polygon[0];
 let sum=0,x=0,y=0;for(let i=0;i<ring.length;i++){const p=ring[i],q=ring[(i+1)%ring.length],cross=p[0]*q[1]-q[0]*p[1];sum+=cross;x+=(p[0]+q[0])*cross;y+=(p[1]+q[1])*cross}
 let point=sum?[x/(3*sum),y/(3*sum)]:ring[0];
 const insideRing=(p,r)=>{let inside=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside}return inside};
 const inside=p=>insideRing(p,ring)&&!polygon.slice(1).some(hole=>insideRing(p,hole));
 if(!inside(point)){
  const xs=ring.map(p=>p[0]),ys=ring.map(p=>p[1]),left=Math.min(...xs),right=Math.max(...xs),bottom=Math.min(...ys),top=Math.max(...ys);let best,score=Infinity;
  for(let i=1;i<40;i++)for(let j=1;j<40;j++){const candidate=[left+(right-left)*i/40,bottom+(top-bottom)*j/40],distance=(candidate[0]-point[0])**2+(candidate[1]-point[1])**2;if(distance<score&&inside(candidate)){best=candidate;score=distance}}
  point=best||ring[0];
 }
 countryPoints.set(feature,point);return point;
}
// Stable endpoint-preserving standard sampling over valid rows only.
function sampleScatter(rows,x,y,size=-1,limit=3500,categoricalX=false){
 const valid=rows.filter(r=>(categoricalX?typeof r[x]==='string'||Number.isFinite(r[x]):Number.isFinite(r[x]))&&(y<0||Number.isFinite(r[y]))&&(size<0||Number.isFinite(r[size])&&r[size]>=0));
 if(valid.length<=limit)return valid;
 return Array.from({length:limit},(_,i)=>valid[Math.floor(i*(valid.length-1)/(limit-1))]);
}
function build(spec,type,labels,rows,roles=[],options={}){
 const numeric=labels.map((_,i)=>i).filter(i=>(rows.some(r=>typeof r[i]==='number'&&Number.isFinite(r[i]))||rows.length&&rows.every(r=>r[i]==null)&&['X','Y','Size','Latitude','Longitude'].includes(roles[i]))),selected={};
 const rowFormats=options._rowFormatMap||new Map(rows.map((row,i)=>[row,options.rowFormats?.[i]]));let sourceRows=options._rowValueMap,sourceFormats=options._sourceRowFormatMap;
 function pick(name,roleNames=[],pattern=null,fallback=-1){
  const value=options.channels?.[name];let index;
  if(value==='none')index=-1;
  else if(value!==undefined&&value!==''&&value!=='auto'){index=Number(value);if(!Number.isInteger(index)||index<0||index>=labels.length)throw Error('Invalid '+name+' field mapping.')}
  else{index=roles.findIndex(r=>roleNames.includes(r));if(index<0&&pattern)index=labels.findIndex(s=>pattern.test(s));if(index<0)index=fallback}
  selected[name]=index;return index;
 }
 function number(index,label){if(index<0||!numeric.includes(index))throw Error(label+' requires a numeric query field. Choose it in Chart fields.');return index}
 function rowValue(row,index){return index>=0?row[index]:undefined}
 function identity(row,detail,color){return {_rowValues:sourceRows?.get(row)??row,_rowFormats:sourceFormats?.has(row)?sourceFormats.get(row):rowFormats.get(row),_rowIdentity:options.visual?(typeof module!=='undefined'?require('./chart-interactions'):root.ChartInteractionAPI).compoundIdentity(options.visual,row):null,_raw:Object.fromEntries(labels.map((label,i)=>[label,row[i]])),_categoryValue:rowValue(row,detail),_dimension:rowValue(row,color)}}
 function colorEncoding(index){return index>=0?{field:'_color',type:numeric.includes(index)?'quantitative':'nominal',title:labels[index]}:{value:'#337b60'}}
 function tooltip(fields){return fields.filter(([,i])=>i>=0).map(([field,i,quant])=>({field,title:labels[i],type:quant?'quantitative':'nominal'}))}
 function finish(){spec.usermeta={...(spec.usermeta||{}),channels:selected};if(spec.projection){const fit=mapFit(spec.data.values,spec.width,spec.height),viewport=mapViewport(options.mapViewport||fit);spec.params=[{name:'mapZoom',value:viewport.zoom},{name:'mapPanX',value:viewport.x},{name:'mapPanY',value:viewport.y}];spec.usermeta.mapViewport=viewport;spec.usermeta.mapAutoViewport=fit;spec.usermeta.mapDataKey=JSON.stringify(spec.data.values.map(d=>[d._categoryValue,d._longitude,d._latitude,d._value==null]))}return spec}
 if(type==='scatterChart'){
  const x=pick('x',['X'],null,numeric[0]??-1),singleAxis=!!options.visual&&!roles.includes('Y')&&(!options.channels?.y||options.channels.y==='auto'),y=singleAxis?-1:pick('y',['Y'],null,numeric.find(i=>i!==x&&!['Size','Category','Details','Formatting','Tooltips'].includes(roles[i]))??-1);if(x<0||y<0&&!singleAxis)throw Error('Scatter X and Y require mapped query fields.');
  if(x===y)throw Error('Scatter X and Y must be different fields.');
  const size=pick('size',['Size']),color=pick('color',['Series','Legend']),detail=pick('detail',['Details','Category']);
  const xProjection=Object.values(options.visual?.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false))[x],xColumn=xProjection?.field?.Column,xMetadata=options.model?.tables?.find(t=>t.name===xColumn?.Expression?.SourceRef?.Entity)?.columns?.find(c=>c.name===xColumn?.Property),categoricalX=!!xColumn&&/^(?:VARCHAR|STRING|TEXT)/i.test(xMetadata?.type||xMetadata?.dataType||'');
  const sampled=sampleScatter(rows,x,y,size,3500,categoricalX);spec.usermeta={...(spec.usermeta||{}),scatterSampling:{limit:3500,inputRows:rows.length,plottedRows:sampled.length}};
  spec.data.values=sampled.map(r=>({_x:r[x],_y:y<0?0:r[y],_size:Math.abs(rowValue(r,size)??0),_signedSize:rowValue(r,size),_color:rowValue(r,color),_detail:rowValue(r,detail),...identity(r,detail,color)}));
  const xSort=options.visual?.definition?.query?.sortDefinition?.sort?.find(s=>JSON.stringify(s.field)===JSON.stringify(xProjection?.field)),xDomain=[...new Set(sampled.map(r=>r[x]))];if(categoricalX&&!xSort&&!xMetadata.sortByColumn)xDomain.sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
  spec.mark={type:'point',filled:true,size:64,opacity:.75,tooltip:true};spec.encoding={x:{field:'_x',type:categoricalX?'ordinal':'quantitative',title:labels[x],...(categoricalX?{sort:xDomain}:{})},y:{field:'_y',type:'quantitative',title:y<0?null:labels[y],...(y<0?{axis:null,scale:{domain:[-1,1],nice:false,zero:false}}:{})},color:colorEncoding(color),tooltip:tooltip([['_x',x,!categoricalX],['_y',y,true],['_signedSize',size,true],['_detail',detail],['_color',color]])};
  if(size>=0)spec.encoding.size={field:'_size',type:'quantitative',title:labels[size],legend:options.showSizeLegend===true?{}:null,scale:{range:[20,800]}};
  spec.params=[{name:'zoom',select:categoricalX?{type:'interval',encodings:['y']}:'interval',bind:'scales'}];return finish();
 }
 if(['stripPlot','stripChart'].includes(type)){
  const value=number(pick('value',['Y','Values','Value'],null,numeric[0]??-1),'Strip value'),category=pick('category',['Category','Rows'],null,labels.findIndex((_,i)=>!numeric.includes(i))),color=pick('color',['Series','Legend']);
  if(category===value)throw Error('Strip category and value must be different fields.');
  spec.data.values=rows.filter(r=>r[value]!=null).map(r=>({_value:r[value],_category:category>=0?r[category]??'(Blank)':'All',_color:rowValue(r,color),...identity(r,category,color)}));
  spec.mark={type:'tick',thickness:2,size:18,opacity:.65,tooltip:true};spec.encoding={x:{field:'_value',type:'quantitative',title:labels[value]},y:{field:'_category',type:'nominal',title:category>=0?labels[category]:null},color:colorEncoding(color),tooltip:tooltip([['_category',category],['_value',value,true],['_color',color]])};return finish();
 }
 if(['ternaryChart','ternaryPlot'].includes(type)){
  const a=number(pick('a',['A','ComponentA','X'],null,numeric[0]??-1),'Component A'),b=number(pick('b',['B','ComponentB','Y'],null,numeric.find(i=>i!==a)??-1),'Component B'),c=number(pick('c',['C','ComponentC','Z'],null,numeric.find(i=>i!==a&&i!==b)??-1),'Component C');
  if(new Set([a,b,c]).size!==3)throw Error('Ternary charts need three distinct component fields.');
  const color=pick('color',['Series','Legend']),detail=pick('detail',['Details','Category']);
  if(rows.some(r=>[a,b,c].some(i=>r[i]!=null&&r[i]<0)))throw Error('Ternary components must be nonnegative.');
  const h=Math.sqrt(3)/2;
  spec.data.values=rows.filter(r=>[a,b,c].every(i=>r[i]!=null&&Number.isFinite(r[i]))&&r[a]+r[b]+r[c]>0&&Number.isFinite(r[a]+r[b]+r[c])).map(r=>{const total=r[a]+r[b]+r[c];return {_x:(r[b]+r[c]/2)/total,_y:h*r[c]/total,_a:r[a],_b:r[b],_c:r[c],_pa:r[a]/total,_pb:r[b]/total,_pc:r[c]/total,_color:rowValue(r,color),_detail:rowValue(r,detail),...identity(r,detail,color)}});
  if(!spec.data.values.length)throw Error('Ternary components need a positive total; zero or missing totals cannot be plotted.');
  if(spec.data.values.length<rows.length)spec.usermeta={mappingWarnings:[(rows.length-spec.data.values.length)+' rows omitted: missing, zero or non-finite component totals.']};
  const grid=[];
  for(const t of [.2,.4,.6,.8])grid.push({_x:t/2,_y:h*t,_x2:1-t/2,_y2:h*t},{_x:t,_y:0,_x2:t+(1-t)/2,_y2:h*(1-t)},{_x:1-t,_y:0,_x2:(1-t)/2,_y2:h*(1-t)});
  const coords={x:{field:'_x',type:'quantitative',scale:{domain:[-.12,1.12]},axis:null},y:{field:'_y',type:'quantitative',scale:{domain:[-.1,h+.12]},axis:null}};
  const outline=[{_x:0,_y:0,_x2:1,_y2:0},{_x:1,_y:0,_x2:.5,_y2:h},{_x:.5,_y:h,_x2:0,_y2:0}];
  spec.layer=[{data:{values:grid},mark:{type:'rule',color:'#d7e1d4',strokeWidth:1},encoding:{...coords,x2:{field:'_x2'},y2:{field:'_y2'}}},{data:{values:outline},mark:{type:'rule',color:'#627668',strokeWidth:1.5},encoding:{...coords,x2:{field:'_x2'},y2:{field:'_y2'}}},{mark:{type:'point',filled:true,size:65,tooltip:true},encoding:{...coords,color:colorEncoding(color),tooltip:[...tooltip([['_a',a,true],['_b',b,true],['_c',c,true],['_detail',detail]]),...['_pa','_pb','_pc'].map((field,i)=>({field,type:'quantitative',title:labels[[a,b,c][i]]+' share',format:'.1%'}))]}},{data:{values:[{_x:0,_y:-.055,label:labels[a]},{_x:1,_y:-.055,label:labels[b]},{_x:.5,_y:h+.055,label:labels[c]}]},mark:{type:'text',fontSize:11,color:'#344e40'},encoding:{...coords,text:{field:'label'}}}];return finish();
 }
 let features=options.visual?.mapFeatures||geography();
 const locationIndex=roles.findIndex(r=>['Category','Location','Details'].includes(r));
 const locationProjection=Object.values(options.visual?.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false))[locationIndex];
 const stateHint=/state|province/i.test([labels[locationIndex],locationProjection?.field?.Column?.Property].filter(Boolean).join(' '));
 if(!options.visual?.mapFeatures&&stateHint&&root.Death2Geo?.usStates){const valid=new Set(root.Death2Geo.usStates.flatMap(f=>f.properties.keys.map(normal)));if(rows.some(r=>valid.has(normal(r[locationIndex]))))features=root.Death2Geo.usStates;}
 const base={data:{values:features},mark:{type:'geoshape',fill:'#edf2e8',stroke:'#c6d2c1',strokeWidth:.4,clip:true}};
 const viewport=mapViewport(options.mapViewport);
 spec.params=[{name:'mapZoom',value:viewport.zoom},{name:'mapPanX',value:viewport.x},{name:'mapPanY',value:viewport.y}];
 spec.projection={type:'equalEarth',scale:{expr:'max(1, min((width - 12) / 5.5, (height - 12) / 2.7)) * mapZoom'},translate:{expr:'[width * (0.5 + mapPanX), height * (0.5 + mapPanY)]'}};
 if(['map','pointMap'].includes(type)){
  const lat=pick('latitude',['Latitude'],/^(latitude|lat)$/i),lon=pick('longitude',['Longitude'],/^(longitude|lon|lng|long)$/i),coordinates=lat>=0||lon>=0;
  if(coordinates){
   const coordinate=v=>typeof v==='number'?v:typeof v==='string'&&/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(v.trim())?Number(v):null;
   const originalRows=rows,originalSources=sourceRows,originalFormats=sourceFormats;
   rows=rows.map(row=>row.map((v,i)=>i===lat||i===lon?coordinate(v):v));
   sourceRows=new Map(rows.map((row,i)=>[row,originalSources?.get(originalRows[i])??originalRows[i]]));sourceFormats=new Map(rows.map((row,i)=>[row,originalFormats?.has(originalRows[i])?originalFormats.get(originalRows[i]):rowFormats.get(originalRows[i])]));
   for(const i of [lat,lon])if(i>=0&&!numeric.includes(i)&&rows.some(r=>typeof r[i]==='number'&&Number.isFinite(r[i])))numeric.push(i);
  }
  let country=-1;
  if(coordinates){number(lat,'Latitude');number(lon,'Longitude')}else{country=pick('country',['Location','Category','Details'],/^(country|country name|country code|iso.?[23]|alpha-[23]|location)$/i,labels.findIndex((_,i)=>!numeric.includes(i)&&rows.some(row=>resolveCountry(row[i],features).feature)));if(country<0)throw Error('Map needs latitude/longitude fields or a country name / ISO code field. Choose it in Chart fields.')}
  if(coordinates&&lat===lon)throw Error('Latitude and longitude must be different fields.');
  const invalidCoordinates=coordinates?rows.filter(r=>r[lat]!=null&&Math.abs(r[lat])>90||r[lon]!=null&&Math.abs(r[lon])>180).length:0;
  const size=pick('size',['Size']),color=pick('color',['Series','Legend']),detail=pick('detail',['Details','Category','Location']);
  if(size>=0)number(size,'Size');const signedSize=size>=0&&rows.some(r=>r[size]<0);
  const missing=[],ambiguous=[];let coordinateFallbacks=0;
  spec.data.values=rows.flatMap(r=>{
   let latitude,longitude;
   if(coordinates){if(r[lat]==null||r[lon]==null||Math.abs(r[lat])>90||Math.abs(r[lon])>180){const fallback=/country|region|continent/i.test(labels[detail]||'')?resolveCountry(r[detail],features).feature:null;if(!fallback){missing.push(String(r[detail]??'(Blank)'));return []}[longitude,latitude]=countryPoint(fallback);coordinateFallbacks++}else{latitude=r[lat];longitude=r[lon]}}
   else{const match=resolveCountry(r[country],features);if(!match.feature){(match.reason==='ambiguous'?ambiguous:missing).push(String(r[country]??'(Blank)'));return []}[longitude,latitude]=countryPoint(match.feature)}
   return [{_latitude:latitude,_longitude:longitude,_size:Math.abs(rowValue(r,size)??0),_signedSize:rowValue(r,size),_color:rowValue(r,color),_detail:rowValue(r,detail>=0?detail:country),...identity(r,coordinates?detail:country,color)}];
  });
  const warnings=[];if(coordinateFallbacks)warnings.push(coordinateFallbacks+' locations without valid embedded coordinates resolved from local geography.');if(invalidCoordinates)warnings.push(invalidCoordinates+' out-of-range coordinate locations omitted.');if(signedSize)warnings.push('Negative bubble sizes use absolute magnitudes; tooltip values retain their signs.');
  if(missing.length)warnings.push(missing.length+(coordinates?' locations without coordinates omitted: ':' unmatched country values omitted: ')+[...new Set(missing)].slice(0,5).join(', '));
  if(ambiguous.length)warnings.push(ambiguous.length+' ambiguous country values omitted: '+[...new Set(ambiguous)].slice(0,5).join(', ')+'. Use a full country name or ISO code.');
  if(!coordinates&&!spec.data.values.length)throw Error('No country locations could be resolved. '+warnings.join(' '));
  if(!coordinates)warnings.unshift('Country names resolved offline to representative country locations.');
  if(warnings.length)spec.usermeta={mappingWarnings:warnings};
  const encoding={longitude:{field:'_longitude',type:'quantitative'},latitude:{field:'_latitude',type:'quantitative'},color:colorEncoding(color),tooltip:tooltip([['_detail',detail>=0?detail:country],['_latitude',lat,true],['_longitude',lon,true],['_signedSize',size,true]])};
  if(size>=0)encoding.size={field:'_size',type:'quantitative',title:labels[size],legend:options.showSizeLegend===true?{}:null,scale:{range:[20,600]}};
  spec.layer=[base,{mark:{type:'circle',size:55,opacity:.8,tooltip:true,clip:true},encoding}];return finish();
 }
 const country=pick('country',['Category','Location','Details'],/^(country|country name|country code|iso.?[23]|alpha-[23])$/i,labels.findIndex((_,i)=>!numeric.includes(i)));
 const hasValue=!options.visual||roles.some(r=>['Y','Size','Color','Values','Value'].includes(r))||options.channels?.value&&options.channels.value!=='auto';
 const value=pick('value',['Y','Size','Color','Values','Value'],null,numeric.find(i=>i!==country)??-1);if(hasValue)number(value,'Map value');
 if(country<0)throw Error('Country maps need a country name or ISO code field.');
 const missing=[],seen=new Set();
 spec.data.values=rows.flatMap(r=>{const {feature}=resolveCountry(r[country],features),region=normal(r[country]);
  const regional=resolveRegion(r[country],features),matches=regional.length?regional:feature?[feature]:[];
  if(!matches.length){missing.push(String(r[country]??'(Blank)'));return []}
  return matches.map(f=>{const canonical=f.properties.name;if(seen.has(canonical))throw Error('Filled maps need one query row per location, without overlapping regions. Filter or group extra dimensions first.');seen.add(canonical);return {...f,...identity(r,country,-1),_country:r[country],_value:hasValue?r[value]:1,_tooltipValue:r[value],_categoryValue:r[country]}});
 });
 if(!spec.data.values.length)throw Error('No country values match the local geography. Use country names or ISO codes.');
 spec.layer=[base,{mark:{type:'geoshape',stroke:'white',strokeWidth:.5,tooltip:true,clip:true},encoding:{color:hasValue?{field:'_value',type:'quantitative',title:labels[value],scale:{scheme:'greens'}}:{value:'#337b60'},tooltip:tooltip([['_country',country],[hasValue?'_value':'_tooltipValue',value,true]])}}];
 if(missing.length)spec.usermeta={mappingWarnings:[missing.length+' unmatched country values: '+missing.slice(0,5).join(', ')+(missing.length>5?'…':'')]};
 return finish();
}
const api={sampleScatter,types,channels,build,mapLimits,mapViewport,mapFit,projectEqualEarth};if(typeof module!=='undefined')module.exports=api;root.AdvancedCharts=api;
})(globalThis);
