const A=require('node:assert/strict'),E=require('./report-engine');
const field=name=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property:name}}),column={Column:{Expression:{SourceRef:{Entity:'T'}},Property:'C'}};
const m={id:'fixture',tables:[{name:'T',columns:[{name:'C'}]}],relationships:[],measures:['Amount','Limit','Color'].map(Name=>({Name,TableName:'M'}))};
const v=E.formattingVisual({definition:{objects:{valueAxis:[{properties:{end:{expr:field('Limit')}}}],dataPoint:[{properties:{fill:{solid:{color:{expr:field('Color')}}}}}]},query:{queryState:{Category:{projections:[{field:column}]},Y:{projections:[{field:field('Amount')}]}}}}},m);
A.equal(v.definition.query.queryState.Formatting.projections.find(p=>p.nativeQueryRef==='Limit').formattingScope,'visual');
const d={compiled:{labels:['C','Amount'],roles:['Category','Y'],formats:['',''],warnings:[]},result:{rows:[['a',1],['b',2]],columns:['v0','v1'],types:['VARCHAR','DOUBLE']}};
(async()=>{let calls=0;const result=await E.optionalFormatting(m,{},v,[],d,async(url,options)=>{calls++;const p=JSON.parse(options.body);if(p.fields.length===1){A.equal(p.groups.length,1);A.deepEqual(p.groups[0].filters,[]);return{rows:[[9]],types:['DOUBLE']}}A.equal(p.groups.length,2);return{rows:[['a','#111111'],['b','#222222']],types:['VARCHAR','VARCHAR']}});A.equal(calls,2);A.deepEqual(result.result.rows,[['a',1,9,'#111111'],['b',2,9,'#222222']]);console.log('PASS visual-level bounds and per-point formatting contexts')})().catch(e=>{console.error(e);process.exitCode=1});

