const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),R=require('./vega-renderer');
const column=(table,name)=>({Column:{Expression:{SourceRef:{Entity:table}},Property:name}}),lit=value=>({expr:{Literal:{Value:JSON.stringify(value).replace(/^"|"$/g,"'")}}});
const makes=['Freightliner','International','Kenworth','Mack','Peterbilt','Volvo'];
const colors=['#6B797C','#40484A','#B08D72','#40484A','#86989C','#5B3D35'];
const rows=Array.from({length:3},(_,month)=>makes.map((make,i)=>[2024,['Jan','Feb','Mar'][month],100+i*20+month*7,make,colors[i]])).flat();
const visual={type:'stackedAreaChart',definition:{
 query:{queryState:{
  Category:{projections:['Year','Month'].map(name=>({field:column('Metrics',name),nativeQueryRef:name}))},
  Y:{projections:[{field:{Aggregation:{Expression:column('Metrics','Revenue'),Function:0}},nativeQueryRef:'Revenue'}]},
  Series:{projections:[{field:column('Trucks','Make'),nativeQueryRef:'Make'}]}
 }},
 objects:{dataPoint:makes.map((make,i)=>({
  properties:{fill:{solid:{color:lit(colors[i])}}},
  selector:{data:[{scopeId:{Comparison:{ComparisonKind:0,Left:column('Trucks','Make'),Right:{Literal:{Value:"'"+make+"'"}}}}}]}
 }))}
}};
const model={theme:{dataColors:colors}},labels=['Year','Month','Revenue','Make','Color'],roles=['Category','Category','Y','Series','Formatting'];
const context=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});
for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+file,'utf8'),context);
async function verify(source){
 const before=JSON.stringify({source,rows}),spec=R.buildSpec('stackedAreaChart',labels,rows,roles,{model,visual:source,width:800,height:280});
 assert.equal(spec.encoding.fill,undefined,'static group colors cannot replace series identity');
 assert.deepEqual(spec.encoding.color.scale.domain,makes);assert.deepEqual(spec.encoding.color.scale.range,colors);
 assert.equal(spec.data.values.length,18);assert.equal(new Set(spec.data.values.map(d=>d._series)).size,6);
 const compiled=context.vegaLite.compile(spec).spec,imputes=compiled.data.flatMap(d=>d.transform||[]).filter(t=>t.type==='impute');
 assert(imputes.length);assert(imputes.every(t=>t.groupby.includes('_series')),'area boundaries must group by series, including equal-color series');
 const view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});
 try{await view.runAsync();const svg=await view.toSVG();assert.equal((svg.match(/aria-roledescription="area mark"/g)||[]).length,6);assert(!svg.includes('NaN'))}finally{view.finalize()}
 assert.equal(JSON.stringify({source,rows}),before,'rendering must not mutate source overrides or data');
}
(async()=>{
 await verify(visual);
 const conditional=structuredClone(visual);conditional.definition.query.queryState.Formatting={projections:[{field:{Measure:{Property:'Color'}},nativeQueryRef:'Color'}]};
 conditional.definition.objects.dataPoint=[{properties:{fill:{solid:{color:{expr:{Measure:{Property:'Color'}}}}}}}];
 await verify(conditional);
 console.log('PASS distinct stacked-area series with duplicate static or measure-driven colors, stable legend mapping, matching line/fill stack groups and immutable source data');
})().catch(error=>{console.error(error);process.exitCode=1});
