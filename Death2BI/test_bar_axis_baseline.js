const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),R=require('./vega-renderer');
const lit=value=>({expr:{Literal:{Value:String(value)}}}),model={theme:{},measures:[]};
function spec(type='clusteredBarChart',axis={end:lit(7.5)},rows=[['Snakes',6],['Trapped',5],['War',5],['Heights',4]],labels=true){
 const visual={type,definition:{objects:{valueAxis:[{properties:{show:lit(false),...axis}}]}}};
 return R.buildSpec(type,['Fear','Count'],rows,['Category','Y'],{model,visual,width:600,height:260,dataLabels:{show:labels}});
}
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});for(const name of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/vendor',name),'utf8'),context);
async function render(spec,type='clusteredBarChart'){
 const horizontal=/BarChart$/i.test(type),axis=horizontal?'x':'y',compiled=context.vegaLite.compile(spec).spec,view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});
 try{await view.runAsync();const scale=compiled.scales.find(s=>s.name===axis),domain=JSON.parse(JSON.stringify(view.scale(scale.name).domain())),marks=[];function walk(n){if(n.mark?.marktype==='rect'&&n.datum?._categoryValue!==undefined)marks.push({category:n.datum._categoryValue,value:n.datum._value,start:horizontal?n.x:n.y+n.height,length:horizontal?n.width:n.height});for(const child of n.items||[])walk(child)}walk(view.scenegraph().root);assert(!(await view.toSVG()).includes('NaN'));return {domain,marks}}finally{view.finalize()}
}
(async()=>{
 for(const type of ['clusteredBarChart','barChart','stackedBarChart','clusteredColumnChart','columnChart','stackedColumnChart']){
  for(const show of [false,true]){const result=await render(spec(type,undefined,undefined,show),type);assert.deepEqual(result.domain,[0,7.5]);const low=result.marks.find(m=>m.category==='Heights'),high=result.marks.find(m=>m.category==='Snakes');assert(low.length>0);assert(Math.abs(low.length/high.length-4/6)<1e-10);assert(result.marks.every(m=>Math.abs(m.start-high.start)<1e-10));}
 }
 const explicit=await render(spec('clusteredBarChart',{start:lit(2),end:lit(7.5)}));assert.deepEqual(explicit.domain,[2,7.5]);
 const negative=await render(spec('clusteredBarChart',{end:lit(7.5)},[['A',-4],['B',-6]]));assert.deepEqual(negative.domain,[-6,7.5]);assert(negative.marks.every(m=>m.length>0));
 const negativeMaximum=await render(spec('clusteredBarChart',{end:lit(-1)},[['A',-4],['B',-6]]));assert.equal(negativeMaximum.domain[1],-1);
 for(const type of ['hundredPercentStackedBarChart','hundredPercentStackedColumnChart']){const normalized=await render(spec(type,{end:lit(1)}),type);assert.deepEqual(normalized.domain,[0,1]);assert(normalized.marks.every(m=>m.length>0));}
 const combo=R.buildSpec('lineClusteredColumnComboChart',['Fear','Count','Rate'],[['A',4,.1],['B',6,.2]],['Category','Y','Y2'],{model,visual:{type:'lineClusteredColumnComboChart',definition:{objects:{valueAxis:[{properties:{end:lit(7.5)}}],y2Axis:[{properties:{secEnd:lit(.3)}}]}}}});assert.equal(combo.layer[0].encoding.y.scale.zero,true);assert.equal(combo.layer[1].encoding.y.scale.zero,false);
 const log=spec('clusteredBarChart',{end:lit(100),logAxisScale:lit(true)});assert.equal(log.layer[0].encoding.x.scale.type,'log');assert.equal(log.layer[0].encoding.x.scale.zero,undefined);await render(log);
 const line=spec('lineChart');assert.equal(line.encoding.y.scale.zero,false);const scatter=R.buildSpec('scatterChart',['X','Y'],[[4,5],[6,7]],['X','Y'],{model,visual:{type:'scatterChart',definition:{objects:{valueAxis:[{properties:{end:lit(7.5)}}]}}}});assert.equal(scatter.encoding.y.scale.zero,false);
 console.log('PASS bar/column zero baseline with maximum-only bounds, actual nonzero lengths and proportions, hidden axes, labels, explicit minima, negative bounds, logarithmic and non-bar scales');
})().catch(error=>{console.error(error);process.exitCode=1});
