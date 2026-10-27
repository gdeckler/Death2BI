const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),R=require('./vega-renderer');
const column=Property=>({Column:{Expression:{SourceRef:{Entity:'Data'}},Property}}),measure=Property=>({Measure:{Expression:{SourceRef:{Entity:'Measures'}},Property}}),literal=Value=>({Literal:{Value:typeof Value==='string'?"'"+Value+"'":String(Value)}}),property=value=>({expr:literal(value)});
const colorRule={FillRule:{
 Input:measure('Color'),
 FillRule:{linearGradient2:{min:{color:literal('#808080')},max:{color:literal('#73B761')}}}
}};
const visual={type:'barChart',definition:{
 query:{queryState:{Category:{projections:[{field:column('Category'),nativeQueryRef:'Category'}]},Series:{projections:[{field:column('Self'),nativeQueryRef:'Self'}]},Y:{projections:[{field:measure('Amount'),nativeQueryRef:'Amount'}]},Formatting:{projections:[{field:measure('Color'),nativeQueryRef:'Color'}]}}},
 objects:{dataPoint:[{selector:{data:[{roles:['Series']}]},properties:{fill:{solid:{color:{expr:colorRule}}}}}],labels:[{properties:{show:property(true)}}]}
}};
const model={theme:{dataColors:['#73B761','#4A588A']},measures:[{TableName:'Measures',Name:'Amount',FormatString:'0'},{TableName:'Measures',Name:'Color',FormatString:'0'}]},rows=[['A',false,1,0],['A',true,2,0],['B',false,3,0],['B',true,4,1]],labels=['Category','Self','Amount','Color'],roles=['Category','Series','Y','Formatting'],before=JSON.stringify({model,visual,rows});
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+file,'utf8'),context);
async function render(source,{data=rows,show=true}={}){
 const spec=R.buildSpec(source.type,labels,data,roles,{model,visual:source,formats:['','','0','0'],dataLabels:{show},width:600,height:350}),compiled=context.vegaLite.compile(spec).spec,view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});
 try{await view.runAsync();const rectangles=[],symbols=[],texts=[],hidden=[];const walk=node=>{if(node.mark?.role==='mark'&&node.mark.marktype==='rect'&&node.datum?._series!==undefined)rectangles.push(node);if(node.mark?.role==='legend-symbol')symbols.push(node);if(node.mark?.role==='legend-label')texts.push(node.text);if(node.mark?.role==='mark'&&node.mark.marktype==='symbol')hidden.push(node);for(const item of node.items||[])walk(item)};walk(view.scenegraph().root);const svg=await view.toSVG();assert(!svg.includes('NaN'));return {spec,rectangles,symbols,texts,hidden}}finally{view.finalize()}
}
(async()=>{
 for(const type of ['barChart','stackedBarChart','stackedColumnChart','hundredPercentStackedBarChart','hundredPercentStackedColumnChart','clusteredBarChart','clusteredColumnChart'])for(const show of [true,false]){
  const source={...visual,type},result=await render(source,{show});assert.equal(result.rectangles.length,4,type+' keeps both boolean segments for both categories');assert.deepEqual([...new Set(result.rectangles.map(n=>n.datum._series))],['False','True']);assert.deepEqual(result.rectangles.map(n=>n.fill.toLowerCase()),['#808080','#808080','#808080','#73b761']);assert.deepEqual(result.texts,['False','True']);assert.equal(result.symbols.length,2);assert(result.symbols.every(n=>n.opacity===1&&n.size>0&&n.fill.toLowerCase()==='#808080'),'legend symbols remain visible even though their carrier marks are invisible');assert(result.hidden.every(n=>n.opacity===0&&n.size===0),'legend carriers have no visible/hittable plot marks');
  if(!type.startsWith('clustered'))for(const category of ['A','B']){const nodes=result.rectangles.filter(n=>n.datum._category===category),horizontal=type.includes('Bar')||type==='barChart',start=n=>horizontal?n.x:n.y,end=n=>start(n)+(horizontal?n.width:n.height),ordered=nodes.slice().sort((a,b)=>start(a)-start(b));assert(Math.abs(end(ordered[0])-start(ordered[1]))<1e-6,type+' stack segments must remain contiguous');assert(nodes.every(n=>(horizontal?n.width:n.height)>0));}
 }
 const disabled=structuredClone(visual);disabled.definition.objects.legend=[{properties:{show:property(false)}}];const off=await render(disabled);assert.equal(off.symbols.length,0);assert.equal(off.rectangles.length,4);assert(!off.spec.layer.some(l=>String(l.name).startsWith('pbi_conditional_legend')));
 // A color constant within each series can use the nominal scale itself.
 const constant=await render(visual,{data:rows.map(row=>[...row.slice(0,3),row[1]?1:0])});assert.equal(constant.spec.layer[0].encoding.fill,undefined);assert.deepEqual(constant.symbols.map(n=>n.fill.toLowerCase()),['#808080','#73b761']);assert(!constant.spec.layer.some(l=>String(l.name).startsWith('pbi_conditional_legend')));
 const ordinary=structuredClone(visual);delete ordinary.definition.objects.dataPoint;const original=await render(ordinary);assert.equal(original.symbols.length,2);assert(!original.spec.layer.some(l=>String(l.name).startsWith('pbi_conditional_legend')));assert.equal(JSON.stringify({model,visual,rows}),before);
 console.log('PASS conditional per-point fill preserves visible nominal legends, boolean stack segments/geometry, source colors, labels, hidden legend policy, constant-color reconciliation and ordinary chart behavior');
})().catch(error=>{console.error(error);process.exitCode=1});
