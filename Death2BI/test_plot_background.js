const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path'),R=require('./vega-renderer');
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});for(const f of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/vendor',f),'utf8'),context);
const literal=Value=>({expr:{Literal:{Value}}}),uri='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9xoAAAAASUVORK5CYII=';
const model={assets:{'Report/StaticResources/RegisteredResources/art.png':uri},theme:{}};
const visual={type:'lineChart',definition:{objects:{plotArea:[{properties:{image:{image:{url:{expr:{ResourcePackageItem:{ItemName:'art.png',PackageName:'RegisteredResources'}}},scaling:literal("'Fit'")}},transparency:literal('25D')}}]}}};
(async()=>{const spec=R.buildSpec('lineChart',['X','Y'],[[1,2],[2,3]],['Category','Y'],{model,visual,width:400,height:300});
assert.equal(spec.layer[0].mark.type,'image');assert.equal(spec.layer[0].data.values[0].url,uri);assert.equal(spec.layer[0].mark.opacity,.75);assert.equal(spec.layer[0].mark.aspect,true);assert.deepEqual(spec.layer[0].encoding.x.value,{expr:'width/2'});assert.deepEqual(spec.layer[0].mark.height,{expr:'height'});assert(spec.layer.slice(1).some(l=>l.mark.type==='line'));
const compiled=context.vegaLite.compile(spec).spec;const view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});try{await view.runAsync();const svg=await view.toSVG();assert.match(svg,/<image/);assert(svg.includes('data:image/png;base64,'));}finally{view.finalize()}
const fill=structuredClone(visual);fill.definition.objects.plotArea[0].properties.image.image.scaling=literal("'Fill'");assert.equal(R.buildSpec('lineChart',['X','Y'],[[1,2]],['Category','Y'],{model,visual:fill}).layer[0].mark.aspect,false);
const missing=R.buildSpec('lineChart',['X','Y'],[[1,2]],['Category','Y'],{model:{assets:{}},visual});assert(!missing.layer?.some(l=>l.mark.type==='image'));
console.log('PASS embedded plot-area image resolution, sizing, transparency, fit/fill, SVG embedding and missing-resource fallback');
})().catch(e=>{console.error(e.message);process.exitCode=1});
