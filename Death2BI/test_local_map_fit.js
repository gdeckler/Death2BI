const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const R=require('./vega-renderer'),A=require('./advanced-charts');
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});
for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/vendor',file),'utf8'),context);
const regional=[[-1.54,52.44,2],[-.50,52.94,3],[-.93,52.65,1]],city=[[-.142,51.503,2],[-.134,51.507,3]],tiny=[[-.142,51.503,2],[-.14199999,51.50300001,3]];
function points(rows){return rows.map(([longitude,latitude])=>({_longitude:longitude,_latitude:latitude}))}
function finiteViewport(viewport){assert(Number.isFinite(viewport.zoom)&&viewport.zoom>=A.mapLimits.minZoom&&viewport.zoom<=A.mapLimits.maxZoom);assert(Number.isFinite(viewport.x)&&Number.isFinite(viewport.y))}
async function render(rows,width=500,height=300,options={}){
 const categorical=rows.some(row=>row.length>3),spec=R.buildSpec('map',['Longitude','Latitude','Cases',...(categorical?['District']:[])],rows,['Longitude','Latitude','Size',...(categorical?['Series']:[])],{width,height,showSizeLegend:true,...options});
 const view=new context.vega.View(context.vega.parse(context.vegaLite.compile(spec).spec),{renderer:'none'});
 try{await view.runAsync();const fit=R.mapFitForView(spec.data.values,view,width,height);if(spec.projection)await view.signal('mapZoom',fit.zoom).signal('mapPanX',fit.x).signal('mapPanY',fit.y).runAsync();const innerWidth=view.width(),innerHeight=view.height(),marks=[];function visit(item){if(item.mark?.marktype==='symbol'&&Number.isFinite(item.datum?._longitude))marks.push(item);for(const child of item.items||[])visit(child)}visit(view.scenegraph().root);assert.equal(marks.length,rows.length);for(const mark of marks){assert(Number.isFinite(mark.x)&&Number.isFinite(mark.y));assert(mark.x>=23&&mark.x<=innerWidth-23,'Local point must fit horizontal viewport padding');assert(mark.y>=23&&mark.y<=innerHeight-23,'Local point must fit vertical viewport padding')}return {spec,fit,width:innerWidth,height:innerHeight,marks:marks.map(mark=>({x:mark.x,y:mark.y})),zoom:spec.projection?view.signal('mapZoom'):fit.zoom};}finally{view.finalize()}
}
(async()=>{
 const county=await render(regional);assert(county.zoom>32);const span=axis=>Math.max(...county.marks.map(p=>p[axis]))-Math.min(...county.marks.map(p=>p[axis]));assert(Math.max(span('x')/(county.width-48),span('y')/(county.height-48))>.99,'A regional cluster should fill one padded projection axis');
 const town=await render(city);assert(town.zoom>county.zoom);assert(town.zoom>1000);
 await render(regional.map((row,i)=>[...row,'District '+String.fromCharCode(65+i)]),500,300,{showSizeLegend:false});
 const detail=await render(tiny);assert.equal(detail.zoom,A.mapLimits.maxZoom);
 const singleton=await render([regional[0]]);assert.equal(singleton.zoom,A.mapLimits.pointZoom);assert(Math.abs(singleton.marks[0].x-singleton.width/2)<1e-6);assert(Math.abs(singleton.marks[0].y-singleton.height/2)<1e-6);
 const coincident=await render([regional[0],regional[0]]);assert.equal(coincident.zoom,A.mapLimits.pointZoom);
 await render([[-1.0,52.5,1],[-.9,52.5,1]]);await render([[0,51.0,1],[0,51.1,1]]);
 const empty=await render([]);assert.deepEqual(empty.fit,{zoom:A.mapLimits.minZoom,x:0,y:0});
 finiteViewport(A.mapFit(points(regional),20,20));finiteViewport(A.mapFit(points(regional),NaN,Infinity));
 const invalid=[{_longitude:NaN,_latitude:52},{_longitude:Infinity,_latitude:52},{_longitude:0,_latitude:Infinity}];assert.deepEqual(A.mapFit(invalid),{zoom:A.mapLimits.minZoom,x:0,y:0});
 const mixed=A.mapFit([...invalid,...points(regional)],500,300);assert.deepEqual(mixed,A.mapFit(points(regional),500,300));
 assert.deepEqual(R.mapFitForView(points(regional),{width:()=>undefined,height:()=>null},500,300),A.mapFit(points(regional),500,300));
 assert.deepEqual(A.mapViewport({zoom:A.mapLimits.maxZoom*2,x:Infinity,y:NaN}),{zoom:A.mapLimits.maxZoom,x:0,y:0});
 console.log('PASS regional/city/tiny map fitting, shared finite zoom bounds, single/coincident/one-axis domains, invalid/empty data and actual Vega symbol positions');
})().catch(error=>{console.error(error);process.exitCode=1});
