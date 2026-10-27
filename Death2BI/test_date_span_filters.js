const assert=require('node:assert/strict'),E=require('./report-engine');
const column={Column:{Expression:{SourceRef:{Entity:'Calendar'}},Property:'Date'}},aggregate={Aggregation:{Expression:column,Function:3}},span=(unit,date)=>({DateSpan:{Expression:{Literal:{Value:"datetime'"+date+"'"}},TimeUnit:unit}});
const entry=(kind,right,left=aggregate)=>({filter:{Where:[{Condition:{Comparison:{ComparisonKind:kind,Left:left,Right:right}}}]}});
const visual=(kind,right)=>({type:'scatterChart',filters:[entry(kind,right)],definition:{query:{queryState:{Values:{projections:[{field:aggregate,nativeQueryRef:'First date'}]}}}}});
const model={tables:[{name:'Calendar',columns:[{name:'Date'}]}],measures:[],relationships:[]};
const second=span(5,'1899-12-31T23:59:35.987');
const plan=E.measureFilterPlan(visual(2,second));assert.equal(plan.predicates[0](['1899-12-31 23:59:34']),false);assert.equal(plan.predicates[0](['1899-12-31 23:59:35']),true);assert.equal(plan.predicates[0](['1900-01-01']),true);assert.equal(plan.predicates[0]([null]),false);
const sql=E.buildQuery(model,{},visual(2,second));assert.match(sql.sql,/TRY_CAST\("v1" AS TIMESTAMP\)/);assert.match(sql.sql,/>= '1899-12-31T23:59:35.000'/);assert.equal(sql.labels.length,1);
for(const [kind,inside,before,after] of [[0,true,false,false],[5,false,true,true],[1,false,false,true],[2,true,false,true],[3,false,true,false],[4,true,true,false]]){
 const test=E.measureFilterPlan(visual(kind,second)).predicates[0];assert.equal(test(['1899-12-31T23:59:35.500']),inside);assert.equal(test(['1899-12-31T23:59:34.999']),before);assert.equal(test(['1899-12-31T23:59:36.000']),after);
}
for(const [unit,start,end] of [[0,'2024-02-29T00:00:00.000','2024-03-01T00:00:00.000'],[2,'2024-02-01T00:00:00.000','2024-03-01T00:00:00.000'],[3,'2024-01-01T00:00:00.000','2025-01-01T00:00:00.000'],[4,'2020-01-01T00:00:00.000','2030-01-01T00:00:00.000'],[6,'2024-02-29T12:34:00.000','2024-02-29T12:35:00.000'],[7,'2024-02-29T12:00:00.000','2024-02-29T13:00:00.000']]){
 const right=span(unit,'2024-02-29T12:34:56.123'),p=E.measureFilterPlan(visual(0,right));assert.deepEqual(p.sqlPredicates[0].dateSpan,{start,end});assert(p.predicates[0]([start]));assert(!p.predicates[0]([end]));
 const parsed=E.parseFilters([entry(0,right,column)]);assert(parsed[0].sql.includes(start));assert(parsed[0].sql.includes(end));assert.deepEqual(parsed[0].columns,['Date']);
}
assert.throws(()=>E.measureFilterPlan(visual(0,span(1,'2024-01-01T00:00:00'))),/week-start/);
assert.throws(()=>E.parseFilters([entry(0,{DateSpan:{Expression:{Now:{}},TimeUnit:0}},column)]),/static datetime/);
const before=JSON.stringify(visual(2,second));E.measureFilterPlan(JSON.parse(before));assert.equal(JSON.stringify(visual(2,second)),before);
console.log('PASS static DateSpan date/aggregate filters, typed date comparisons, six comparison kinds, second/day/month/year/decade/minute/hour boundaries and explicit unsupported forms');
