const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),R=require('./vega-renderer');
const sandbox=vm.createContext({console,setTimeout,clearTimeout,structuredClone});
for(const name of ['vega','vega-lite'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+name+'.min.js','utf8'),sandbox);
const col=Property=>({Column:{Expression:{SourceRef:{Entity:'Calendar'}},Property}});
const visual={type:'lineChart',definition:{query:{queryState:{Category:{projections:['Year','M'].map(name=>({field:col(name),nativeQueryRef:name,active:true}))},Y:{projections:[{field:{Measure:{Expression:{SourceRef:{Entity:'Metrics'}},Property:'Count'}},nativeQueryRef:'Count'}]}},sortDefinition:{isDefaultSort:true,sort:[]}}}};
const rows=Array.from({length:24},(_,i)=>[2023+Math.floor(i/12),i%12+1,i+10]),labels=['Year','M','Count'],roles=['Category','Category','Y'];
(async()=>{
 const before=JSON.stringify({visual,rows});
 for(const type of ['lineChart','areaChart','stackedAreaChart','hundredPercentStackedAreaChart','clusteredColumnChart','clusteredBarChart']){
  const spec=R.buildSpec(type,labels,rows,roles,{visual:{...visual,type},model:{theme:{}},width:1200,height:300,fieldTypes:['INTEGER','INTEGER','BIGINT']});
  const horizontal=type==='clusteredBarChart',axis=spec.encoding[horizontal?'y':'x'];
  assert.equal(axis.type,'ordinal');assert.equal(axis.title,'Year / M');assert.deepEqual(axis.sort,rows.map(r=>r[0]+' / '+r[1]));
  assert.equal(spec.data.values.length,24,'numeric hierarchy levels must not become measures');
  assert.equal(spec.data.values[0]._rowIdentity.fields.length,2,'selection retains both hierarchy fields');
  const native=sandbox.vegaLite.compile(spec).spec,view=new sandbox.vega.View(sandbox.vega.parse(native),{renderer:'none'});
  try{await view.runAsync();const svg=await view.toSVG();assert(!svg.includes('NaN')&&!svg.includes('Infinity'));assert(svg.includes('2023 / 1'));assert(svg.includes('2024 / 12'));assert.equal(view.scale(horizontal?'y':'x').domain().length,24)}finally{view.finalize()}
 }
 const width=R.contentWidth('lineChart',labels,rows,roles,200,{visual,model:{}});assert(width>1000,'scroll width counts complete Year / M keys');
 const single=R.buildSpec('lineChart',['Year','Count'],[[2023,10],[2024,20]],['Category','Y']);assert.equal(single.encoding.x.type,'quantitative','one numeric category retains continuous axis');
 const dates=R.buildSpec('lineChart',['Date','Count'],[['2023-01-01',10],['2024-01-01',20]],['Category','Y']);assert.equal(dates.encoding.x.type,'temporal');
 assert.equal(JSON.stringify({visual,rows}),before);
 console.log('PASS compound numeric hierarchy axes, all levels and measures, real Vega marks, compound selection, scrolling and single-level numeric/date axes');
})().catch(error=>{console.error(error);process.exitCode=1});
