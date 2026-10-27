const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),R=require('./vega-renderer');
const sandbox={console,setTimeout,clearTimeout,structuredClone};vm.createContext(sandbox);
for(const name of ['vega','vega-lite'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+name+'.min.js','utf8'),sandbox);
const model={theme:{foreground:'#F7F0DF',textClasses:{label:{fontFace:'Arial'}}}};
const visual=(properties={})=>({type:'lineChart',definition:{objects:{categoryAxis:[{properties:{fontSize:16,showAxisTitle:false,axisType:'Categorical',...properties}}]}}});
function labels(view,names){const found=[];function walk(node){const text=Array.isArray(node.text)?node.text.join(' '):node.text;if(node.mark?.role==='axis-label'&&names.includes(text))found.push(node);for(const child of node.items||[])walk(child)}walk(view.scenegraph().root);return found}
async function render(spec){const view=new sandbox.vega.View(sandbox.vega.parse(sandbox.vegaLite.compile(spec).spec),{renderer:'none'});await view.runAsync();return view}
(async()=>{
 const source=visual(),before=JSON.stringify(source),rows=[['Childhood',10],['Adult',20]],names=rows.map(r=>r[0]);
 const spec=R.buildSpec('lineChart',['Age','Count'],rows,['Category','Y'],{model,visual:source,width:1198,height:238}),view=await render(spec);
 assert.equal(labels(view,names).length,2);assert(labels(view,names).every(n=>n.angle===0));assert(view.height()>140,'short charts retain plot height');
 assert(labels(view,names).every(n=>n.align==='center'&&n.baseline==='top'));
 await view.width(150).height(238).resize().runAsync();assert(labels(view,names).every(n=>n.angle<0),'narrow resize rotates labels');
 await view.width(1198).height(238).resize().runAsync();assert(labels(view,names).every(n=>n.angle===0),'wide resize restores horizontal labels');view.finalize();
 assert.equal(JSON.stringify(source),before);assert.deepEqual(rows,[['Childhood',10],['Adult',20]]);

 const regions=['North America','South America','East Europe','West Europe'],wrapped=R.buildSpec('lineChart',['Region','Value'],regions.map((s,i)=>[s,i+1]),['Category','Y'],{model,visual:visual({fontSize:10.5}),width:300,height:260}),regionView=await render(wrapped),regionLabels=labels(regionView,regions);
 assert.equal(regionLabels.length,4);assert(regionLabels.every(n=>n.angle===0),'two-line word wrapping keeps labels horizontal');
 assert(regionLabels.some(n=>Array.isArray(n.text)&&n.text.length===2));assert(regionView.height()>150);regionView.finalize();

 const dense=Array.from({length:8},(_,i)=>['LongUnbrokenCategory'+i,i+1]),denseView=await render(R.buildSpec('lineChart',['Category','Value'],dense,['Category','Y'],{model,visual:visual(),width:250,height:180}));
 assert(labels(denseView,dense.map(r=>r[0])).every(n=>n.angle<0));assert(denseView.height()>90,'rotated labels have a bounded height');
 await denseView.width(250).height(90).resize().runAsync();assert(denseView.height()>20,'height shrink retains a visible plot');assert(labels(denseView,dense.map(r=>r[0])).every(n=>n.limit<40));
 await denseView.width(250).height(400).resize().runAsync();assert(denseView.height()>200,'height growth restores plotting space');denseView.finalize();

 const explicit=R.buildSpec('lineChart',['Age','Count'],rows,['Category','Y'],{model,visual:visual({labelAngle:-30}),width:1198,height:238});assert.equal(explicit.encoding.x.axis.labelAngle,-30);
 const hidden=R.buildSpec('lineChart',['Age','Count'],rows,['Category','Y'],{model,visual:visual({show:false}),width:1198,height:238});assert.equal(hidden.encoding.x.axis,null);
 const numeric=R.buildSpec('lineChart',['Year','Count'],[[2020,10],[2021,20]],['Category','Y'],{width:300,height:180});assert.equal(numeric.encoding.x.type,'quantitative');assert.equal(numeric.encoding.x.axis?.labelAngle,undefined);
 const bars=R.buildSpec('clusteredBarChart',['Age','Count'],rows,['Category','Y'],{width:300,height:180});assert.equal(bars.encoding.y.axis.labelAngle,0);assert.equal(bars.encoding.x.axis?.labelAngle,undefined);
 const column=await render(R.buildSpec('clusteredColumnChart',['Age','Count'],rows,['Category','Y'],{model,visual:{...visual(),type:'clusteredColumnChart'},width:600,height:238}));assert(labels(column,names).every(n=>n.angle===0));column.finalize();
 console.log('PASS adaptive horizontal, wrapped and rotated x-axis labels; plot height, responsive resizing, explicit/hidden/numeric axes, bars, columns and source immutability');
})().catch(error=>{console.error(error);process.exitCode=1});
