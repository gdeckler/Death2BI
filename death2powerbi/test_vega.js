const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const R=require('./vega-renderer.js');
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});
for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/vendor',file),'utf8'),context);
async function render(spec){
 const compiled=context.vegaLite.compile(spec).spec;
 const view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});
 try{await view.runAsync();const svg=await view.toSVG();assert.match(svg,/<svg/);assert.ok(!svg.includes('NaN'));return svg}finally{view.finalize()}
}
(async()=>{
 for(const type of R.types){
  let labels=['Country','Value'],rows=[['A',10],['B',20],['C',15]],roles=['Category','Y'];
  if(type==='scatterChart'){labels=['X','Y'];rows=[[1,2],[2,3],[4,5]];roles=['X','Y']}
  if(['ternaryChart','ternaryPlot'].includes(type)){labels=['A','B','C'];rows=[[1,2,3],[3,2,1]];roles=['A','B','C']}
  if(['map','pointMap'].includes(type)){labels=['Country','Latitude','Longitude','Size'];rows=[['France',48.86,2.35,10],['Germany',52.52,13.4,20]];roles=['Category','Latitude','Longitude','Size']}
  if(['filledMap','choroplethMap'].includes(type)){labels=['Country','Value'];rows=[['France',10],['Germany',20]];roles=['Category','Y']}
  if(type.includes('Combo')){labels=['Country','Revenue','Count'];rows=[['A',10,1],['B',20,4]];roles=['Category','Y','Y2']}
  if(['histogram','histogramChart','boxplot','boxPlot'].includes(type)){labels=['Value'];rows=[[1],[1],[2],[3],[5],[8]];roles=['Values']}
  const spec=R.buildSpec(type,labels,rows,roles);assert.ok(spec.data.values.length>0);await render(spec);
 }
 await render(R.buildSpec('clusteredColumnChart',['Country','Revenue','Profit'],[['A',10,-2],['B',20,4]],['Category','Y','Y']));
 await render(R.buildSpec('stackedAreaChart',['Date','Series','Amount'],[['A','One',2],['A','Two',3],['B','One',4],['B','Two',5]],['Category','Series','Y']));
 await render(R.buildSpec('map',['Country','Value'],[['France',10],['Germany',20],['USA',30]],['Category','Size']));
 const nulls=R.buildSpec('lineChart',['Date','Value'],[['2020-01-01',1],['2020-02-01',null]],['Category','Y']);assert.equal(nulls.data.values[1]._value,null);await render(nulls);
 await render(R.buildSpec('clusteredColumnChart',['Category','Value'],[],['Category','Y']));
 assert.throws(()=>R.buildSpec('pieChart',['A','B'],[['A',-1]],['Category','Y']),/negative/);
 const literal=value=>({expr:{Literal:{Value:value}}});
 const on={objects:{labels:[{properties:{show:literal('true'),labelPrecision:literal('1L'),color:{solid:{color:literal("'#123456'")}}}}]}};
 const settings=R.dataLabelOptions(on);assert.equal(settings.show,true);assert.equal(settings.precision,1);assert.equal(settings.color,'#123456');
 assert.equal(R.dataLabelOptions({objects:{labels:[{properties:{show:{expr:{Literal:{Value:'false'}}}}}]}}).show,false);
 for(const type of ['clusteredBarChart','clusteredColumnChart','stackedBarChart','stackedColumnChart','hundredPercentStackedBarChart','hundredPercentStackedColumnChart']){
  const labeled=R.buildSpec(type,['Region','Rate','Second'],[['A',.123,-.05],['B',.25,null]],['Category','Y','Y'],{formats:['','0.00%','0.00%'],dataLabels:settings});
  assert.equal(labeled.layer[1].encoding.text.field,'_label');assert.equal(labeled.data.values[0]._label,'12.3%');assert.equal(labeled.data.values[3]._label,'');
  const svg=await render(labeled);assert.match(svg,/fill="#123456"/);if(!type.startsWith('hundredPercent'))assert.ok(svg.includes('12.3%'));
 }
 const grouped=R.buildSpec('clusteredColumnChart',['A','B','C'],[['X',1,2]],['Category','Y','Y'],{dataLabels:{show:true}});assert.deepEqual(grouped.layer[0].encoding.xOffset,grouped.layer[1].encoding.xOffset);
 const hidden=R.buildSpec('clusteredBarChart',['A','B'],[['X',1]],['Category','Y'],{dataLabels:{show:false}});assert.equal(hidden.layer,undefined);
 const units=R.buildSpec('clusteredBarChart',['A','B'],[['X',12500]],['Category','Y'],{dataLabels:{show:true,units:1000,precision:1}});assert.equal(units.data.values[0]._label,'12.5K');
 console.log('PASS: data-label import, six bar/column types, percentages, precision, units, hidden labels, nulls, negative values and grouped placement');
 console.log('PASS:',R.types.length,'Vega-Lite type mappings compile and render SVG; multiple series, negative values, nulls and empty results');
 if(process.argv[2]){
  const model=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),query=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  const visual=model.pages.flatMap(p=>p.visuals).find(v=>v.type==='clusteredColumnChart');
  const svg=await render(R.buildSpec(visual.type,query.labels,query.rows,query.roles));
  if(process.argv[4])fs.writeFileSync(process.argv[4],svg);
  console.log('PASS: imported chart rendered with actual DuckDB results');
 }
})().catch(e=>{console.error(e);process.exitCode=1});
