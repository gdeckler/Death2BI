const assert=require('node:assert/strict'),E=require('./report-engine');
const column={Column:{Expression:{SourceRef:{Entity:'T'}},Property:'Category'}},measure=Property=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property}});
const top={filter:{From:[{Name:'sub',Expression:{Subquery:{Query:{From:[{Name:'t',Entity:'T'}],Select:[column],OrderBy:[{Direction:2,Expression:measure('Rank')}],Top:2}}}},{Name:'t',Entity:'T'}],Where:[{Condition:{In:{Expressions:[column],Table:{SourceRef:{Source:'sub'}}}}}]}};
const model={id:'fixture',tables:[{name:'T',columns:[{name:'Category'}]}],relationships:[],measures:[{Name:'Rank',TableName:'M',Expression:'RANKX(ALL(T[Category]),1)',FormatStringExpression:'"0.00"'},{Name:'Color',TableName:'M',Expression:'"red"'}]};
const visual={type:'barChart',filters:[top],definition:{query:{queryState:{Category:{projections:[{field:column}]},Y:{projections:[{field:measure('Rank')}]},Formatting:{projections:[{field:measure('Color'),nativeQueryRef:'Color'}]}}}}};
(async()=>{
 const base=structuredClone(visual);delete base.definition.query.queryState.Formatting;let topCalls=0,filters;
 const api=async(path,options)=>{const p=JSON.parse(options.body);if(p.operation==='topN'){topCalls++;return {values:['A','B']}}filters=p.baseFilters;return {rows:[['A',1],['B',2]],columns:['v0','v1'],types:['VARCHAR','DOUBLE']}};
 const data=await E.pythonQuery(model,{},base,[],async()=>({rows:[['A'],['B']]}),api);
 assert.equal(topCalls,1);assert.deepEqual(data.compiled._resolvedFilters,filters);assert(filters[0].sql.includes("'A'"));
 const formatted=await E.optionalFormatting(model,{},visual,[],data,async(path,options)=>{const p=JSON.parse(options.body);assert.deepEqual(p.baseFilters,filters);return {rows:[['A','red'],['B','blue']],types:['VARCHAR','VARCHAR']}});
 assert.deepEqual(formatted.result.rows,[['A',1,'red'],['B',2,'blue']]);assert.equal(topCalls,1);
 const dynamic=await E.dynamicFormats(model,{},base,[],data,async(path,options)=>{const p=JSON.parse(options.body);assert.equal(p.operation,'formats');assert.deepEqual(p.baseFilters,filters);return {rowFormats:[['','0.0'],['','0.00']]}});
 assert.deepEqual(dynamic.result.rowFormats,[['','0.0'],['','0.00']]);assert.equal(topCalls,1);assert(top.filter.From[0].Expression.Subquery);
 const sqlModel={...model,measures:[{Name:'Rank',TableName:'M',Expression:'SUM(T[N])'}]};
 const sql=E.buildQuery(sqlModel,{},base);assert(sql._resolvedFilters[0].sql.includes('RANK() OVER'));
 console.log('PASS formatting and dynamic formats retain the executed SQL/DAX Top N context without re-resolving source filters or mutating them');
})().catch(error=>{console.error(error);process.exitCode=1});
