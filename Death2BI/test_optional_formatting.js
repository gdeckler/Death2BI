const A=require('node:assert/strict'),E=require('./report-engine');
const column={Column:{Expression:{SourceRef:{Entity:'T'}},Property:'Category'}},measure=name=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property:name}});
const model={id:'test',tables:[{name:'T',columns:[{name:'Category'}]}],relationships:[],measures:['Value','Color','Reference'].map(Name=>({Name,TableName:'M'}))};
const visual={definition:{query:{queryState:{Category:{projections:[{field:column}]},Y:{projections:[{field:measure('Value')}]},Formatting:{projections:[{field:measure('Color'),nativeQueryRef:'Color'},{field:measure('Reference'),nativeQueryRef:'Reference'}]}}}}};
const data={compiled:{labels:['Category','Value'],roles:['Category','Y'],formats:['','0'],warnings:[]},result:{columns:['v0','v1'],types:['VARCHAR','DOUBLE'],rows:[['A',12],['B',24]]}};
(async()=>{
 let calls=0;
 const result=await E.optionalFormatting(model,{},visual,[],data,async(url,options)=>{
  calls++;const p=JSON.parse(options.body);A.deepEqual(p.groups.map(g=>g.values),[{'0':'A'},{'0':'B'}]);A.deepEqual(p.fields[0],column);
  if(p.fields.length===3||p.fields[1].Measure.Property==='Reference')throw Error('Unsupported reference expression');
  return {rows:[['A','#123456'],['B','#abcdef']],types:['VARCHAR','VARCHAR']};
 });
 A.equal(calls,3);A.deepEqual(result.result.rows,[['A',12,'#123456',null],['B',24,'#abcdef',null]]);A.match(result.compiled.warnings[0],/Reference/);A.equal(data.result.rows[0].length,2);
 calls=0;
 const budget=await E.optionalFormatting(model,{},visual,[],data,async()=>{calls++;throw Error('Python DAX step limit exceeded')});
 A.equal(calls,1);A.equal(budget.result.rows[1][1],24);A.match(budget.compiled.warnings[0],/limit exceeded/);
 console.log('PASS optional formatting isolation, successful-field recovery, group identity, immutable data and bounded retries');
})().catch(e=>{console.error(e);process.exitCode=1});
