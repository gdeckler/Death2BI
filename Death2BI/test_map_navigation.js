const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const R=require('./vega-renderer.js'),A=require('./advanced-charts.js');
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});
for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/vendor',file),'utf8'),context);
const normalize=s=>s.replace(/clip\d+/g,'clip').replace(/-?\d+\.\d+/g,n=>String(Math.round(Number(n)*1e6)/1e6));
(async()=>{
 assert(Object.isFrozen(A.mapLimits));assert(A.mapLimits.maxZoom>32);
 assert.deepEqual(A.mapViewport({zoom:100,x:Infinity,y:NaN}),{zoom:100,x:0,y:0});
 assert.deepEqual(A.mapViewport({zoom:A.mapLimits.maxZoom*2,x:Infinity,y:NaN}),{zoom:A.mapLimits.maxZoom,x:0,y:0});
 assert.deepEqual(A.mapViewport({zoom:-1,x:99,y:-99}),{zoom:1,x:1,y:-1});
 for(const type of ['map','pointMap','filledMap','choroplethMap']){
  const spec=R.buildSpec(type,['Country','Value'],[['France',10],['Germany',20]],['Category','Size']);
  assert.ok(spec.layer.every(layer=>layer.mark.clip));
  const compiled=context.vegaLite.compile(spec).spec,view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});
  try{
   await view.runAsync();const initial=await view.toSVG();assert.equal(view.signal('mapZoom'),spec.usermeta.mapAutoViewport.zoom);assert.ok(view.signal('mapZoom')>1);
   await view.signal('mapZoom',4).signal('mapPanX',-.2).signal('mapPanY',.3).runAsync();const changed=await view.toSVG();assert.notEqual(changed,initial);assert.ok(!changed.includes('NaN'));
   const fit=spec.usermeta.mapAutoViewport;await view.signal('mapZoom',fit.zoom).signal('mapPanX',fit.x).signal('mapPanY',fit.y).runAsync();assert.ok(normalize(await view.toSVG())===normalize(initial),'Reset must restore the initial map projection');
  }finally{view.finalize()}
  const projected=A.projectEqualEarth(10,50),vegaProjection=context.vega.projection('equalEarth')().scale(1).translate([0,0]);assert.ok(projected.every((x,i)=>Math.abs(x-vegaProjection([10,50])[i])<1e-9));
  const restored=R.buildSpec(type,['Country','Value'],[['France',10]],['Category','Size'],{mapViewport:{zoom:4,x:-.2,y:.3}});
  assert.deepEqual(restored.params.map(p=>p.value),[4,-.2,.3]);
 }
 console.log('PASS: all four map types zoom/pan/reset via live projection signals, clip their viewport, restore state and clamp limits');
})().catch(error=>{console.error(error);process.exitCode=1});
