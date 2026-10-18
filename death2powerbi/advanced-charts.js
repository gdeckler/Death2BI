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
function mapViewport(value={}){
 const finite=(n,fallback)=>Number.isFinite(n)?n:fallback,zoom=Math.max(1,Math.min(32,finite(value.zoom,1)));
 return {zoom,x:Math.max(-zoom,Math.min(zoom,finite(value.x,0))),y:Math.max(-zoom,Math.min(zoom,finite(value.y,0)))};
}
let countryIndex, indexedFeatures;
const countryPoints=new WeakMap();
function resolveCountry(value,features){
 if(indexedFeatures!==features){countryIndex=new Map();indexedFeatures=features;for(const feature of features)for(const key of feature.properties.keys){const normalized=normal(key),matches=countryIndex.get(normalized)||new Set();matches.add(feature);countryIndex.set(normalized,matches)}}
 const key=normal(value),aliases={uk:'unitedkingdom',turkiye:'turkey',ivorycoast:'cotedivoire',congokinshasa:'cod',congobrazzaville:'cog',southkorea:'kor',northkorea:'prk',russianfederation:'rus',unitedstatesofamerica:'usa',vaticancity:'vat',easttimor:'tls'};
 const matches=countryIndex.get(aliases[key]||key);
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
function build(spec,type,labels,rows,roles=[],options={}){
 const numeric=labels.map((_,i)=>i).filter(i=>rows.some(r=>typeof r[i]==='number'&&Number.isFinite(r[i]))),selected={};
 function pick(name,roleNames=[],pattern=null,fallback=-1){
  const value=options.channels?.[name];let index;
  if(value==='none')index=-1;
  else if(value!==undefined&&value!==''&&value!=='auto'){index=Number(value);if(!Number.isInteger(index)||index<0||index>=labels.length)throw Error('Invalid '+name+' field mapping.')}
  else{index=roles.findIndex(r=>roleNames.includes(r));if(index<0&&pattern)index=labels.findIndex(s=>pattern.test(s));if(index<0)index=fallback}
  selected[name]=index;return index;
 }
 function number(index,label){if(index<0||!numeric.includes(index))throw Error(label+' requires a numeric query field. Choose it in Chart fields.');return index}
 function rowValue(row,index){return index>=0?row[index]:undefined}
 function identity(row,detail,color){return {_categoryValue:rowValue(row,detail),_dimension:rowValue(row,color)}}
 function colorEncoding(index){return index>=0?{field:'_color',type:numeric.includes(index)?'quantitative':'nominal',title:labels[index]}:{value:'#337b60'}}
 function tooltip(fields){return fields.filter(([,i])=>i>=0).map(([field,i,quant])=>({field,title:labels[i],type:quant?'quantitative':'nominal'}))}
 function finish(){spec.usermeta={...(spec.usermeta||{}),channels:selected};return spec}
 if(type==='scatterChart'){
  const x=number(pick('x',['X'],null,numeric[0]??-1),'X'),y=number(pick('y',['Y'],null,numeric.find(i=>i!==x)??-1),'Y');
  if(x===y)throw Error('Scatter X and Y must be different fields.');
  const size=pick('size',['Size']),color=pick('color',['Series','Legend']),detail=pick('detail',['Details','Category']);
  if(size>=0)number(size,'Size');
  if(size>=0&&rows.some(r=>r[size]<0))throw Error('Bubble size cannot be negative.');
  spec.data.values=rows.filter(r=>r[x]!=null&&r[y]!=null).map(r=>({_x:r[x],_y:r[y],_size:rowValue(r,size),_color:rowValue(r,color),_detail:rowValue(r,detail),...identity(r,detail,color)}));
  spec.mark={type:'point',filled:true,opacity:.75,tooltip:true};spec.encoding={x:{field:'_x',type:'quantitative',title:labels[x]},y:{field:'_y',type:'quantitative',title:labels[y]},color:colorEncoding(color),tooltip:tooltip([['_x',x,true],['_y',y,true],['_size',size,true],['_detail',detail],['_color',color]])};
  if(size>=0)spec.encoding.size={field:'_size',type:'quantitative',title:labels[size],scale:{range:[20,800]}};
  spec.params=[{name:'zoom',select:'interval',bind:'scales'}];return finish();
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
 const features=geography();
 const base={data:{values:features},mark:{type:'geoshape',fill:'#edf2e8',stroke:'#c6d2c1',strokeWidth:.4,clip:true}};
 const viewport=mapViewport(options.mapViewport);
 spec.params=[{name:'mapZoom',value:viewport.zoom},{name:'mapPanX',value:viewport.x},{name:'mapPanY',value:viewport.y}];
 spec.projection={type:'equalEarth',scale:{expr:'max(1, min((width - 12) / 5.5, (height - 12) / 2.7)) * mapZoom'},translate:{expr:'[width * (0.5 + mapPanX), height * (0.5 + mapPanY)]'}};
 if(['map','pointMap'].includes(type)){
  const lat=pick('latitude',['Latitude'],/^(latitude|lat)$/i),lon=pick('longitude',['Longitude'],/^(longitude|lon|lng|long)$/i),coordinates=lat>=0||lon>=0;
  let country=-1;
  if(coordinates){number(lat,'Latitude');number(lon,'Longitude')}else{country=pick('country',['Location','Category','Details'],/^(country|country name|country code|iso.?[23]|alpha-[23]|location)$/i,labels.findIndex((_,i)=>!numeric.includes(i)&&rows.some(row=>resolveCountry(row[i],features).feature)));if(country<0)throw Error('Map needs latitude/longitude fields or a country name / ISO code field. Choose it in Chart fields.')}
  if(coordinates&&lat===lon)throw Error('Latitude and longitude must be different fields.');
  if(rows.some(r=>r[lat]!=null&&Math.abs(r[lat])>90||r[lon]!=null&&Math.abs(r[lon])>180))throw Error('Map coordinates must be latitude −90…90 and longitude −180…180.');
  const size=pick('size',['Size']),color=pick('color',['Series','Legend']),detail=pick('detail',['Details','Category','Location']);
  if(size>=0)number(size,'Size');if(size>=0&&rows.some(r=>r[size]<0))throw Error('Map bubble size cannot be negative.');
  const missing=[],ambiguous=[];
  spec.data.values=rows.flatMap(r=>{
   let latitude,longitude;
   if(coordinates){if(r[lat]==null||r[lon]==null)return [];latitude=r[lat];longitude=r[lon]}
   else{const match=resolveCountry(r[country],features);if(!match.feature){(match.reason==='ambiguous'?ambiguous:missing).push(String(r[country]??'(Blank)'));return []}[longitude,latitude]=countryPoint(match.feature)}
   return [{_latitude:latitude,_longitude:longitude,_size:rowValue(r,size),_color:rowValue(r,color),_detail:rowValue(r,detail>=0?detail:country),...identity(r,coordinates?detail:country,color)}];
  });
  const warnings=[];
  if(missing.length)warnings.push(missing.length+' unmatched country values omitted: '+[...new Set(missing)].slice(0,5).join(', '));
  if(ambiguous.length)warnings.push(ambiguous.length+' ambiguous country values omitted: '+[...new Set(ambiguous)].slice(0,5).join(', ')+'. Use a full country name or ISO code.');
  if(!coordinates&&!spec.data.values.length)throw Error('No country locations could be resolved. '+warnings.join(' '));
  if(!coordinates)warnings.unshift('Country names resolved offline to representative country locations.');
  if(warnings.length)spec.usermeta={mappingWarnings:warnings};
  const encoding={longitude:{field:'_longitude',type:'quantitative'},latitude:{field:'_latitude',type:'quantitative'},color:colorEncoding(color),tooltip:tooltip([['_detail',detail>=0?detail:country],['_latitude',lat,true],['_longitude',lon,true],['_size',size,true]])};
  if(size>=0)encoding.size={field:'_size',type:'quantitative',title:labels[size],scale:{range:[20,600]}};
  spec.layer=[base,{mark:{type:'circle',size:55,opacity:.8,tooltip:true,clip:true},encoding}];return finish();
 }
 const country=pick('country',['Category','Location','Details'],/^(country|country name|country code|iso.?[23]|alpha-[23])$/i,labels.findIndex((_,i)=>!numeric.includes(i))),value=number(pick('value',['Y','Size','Color','Values'],null,numeric.find(i=>i!==country)??-1),'Map value');
 if(country<0)throw Error('Country maps need a country name or ISO code field.');
 const missing=[],seen=new Set();
 spec.data.values=rows.flatMap(r=>{const {feature}=resolveCountry(r[country],features);if(!feature){missing.push(String(r[country]??'(Blank)'));return []}const canonical=feature.properties.name;if(seen.has(canonical))throw Error('Country maps need one query row per country. Filter or group extra dimensions first.');seen.add(canonical);return [{...feature,_country:r[country],_value:r[value],_categoryValue:r[country]}]});
 if(!spec.data.values.length)throw Error('No country values match the local geography. Use country names or ISO codes.');
 spec.layer=[base,{mark:{type:'geoshape',stroke:'white',strokeWidth:.5,tooltip:true,clip:true},encoding:{color:{field:'_value',type:'quantitative',title:labels[value],scale:{scheme:'greens'}},tooltip:tooltip([['_country',country],['_value',value,true]])}}];
 if(missing.length)spec.usermeta={mappingWarnings:[missing.length+' unmatched country values: '+missing.slice(0,5).join(', ')+(missing.length>5?'…':'')]};
 return finish();
}
const api={types,channels,build,mapViewport};if(typeof module!=='undefined')module.exports=api;root.AdvancedCharts=api;
})(globalThis);
