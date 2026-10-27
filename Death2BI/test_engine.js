const assert=require('node:assert/strict');
const E=require('./report-engine.js');
const field=(table,column)=>({Column:{Expression:{SourceRef:{Entity:table}},Property:column}});
const inFilter=(table,column,value)=>({filter:{Where:[{Condition:{In:{Expressions:[field(table,column)],Values:[[{Literal:{Value:value}}]]}}}]}});
assert.equal(E.parseFilters([{field:field('People','Name'),howCreated:'Drillthrough'}]).length,0);
assert.deepEqual(E.parseFilters([{expression:field('People','Name'),type:'Categorical',isHiddenInViewMode:true},{expression:{Measure:{Expression:{SourceRef:{Entity:'People'}},Property:'Count'}},type:'Categorical',howCreated:5}]),[]);
assert.throws(()=>E.parseFilters([{expression:{Comparison:{}}}]),/Unsupported legacy filter expression/);
assert.throws(()=>E.parseFilters([{expression:field('People','Name'),Condition:{In:{}}}]),/Unsupported legacy filter expression/);
const nulls=E.parseFilters([inFilter('People','Name','null')]);assert.match(nulls[0].sql,/IS NULL/);
const apostrophe=E.parseFilters([inFilter('People','Name',"'O''Brien'")]);assert.match(apostrophe[0].sql,/O''Brien/);
assert.throws(()=>E.parseFilters([{filter:{Where:[{Condition:{TopN:{}}}]}}]),/Unsupported/);
const m={measures:[],relationships:[{FromTableName:'Hours',FromColumnName:'EmployeeID',ToTableName:'People',ToColumnName:'ID',IsActive:1,Cardinality:'M:1',CrossFilteringBehavior:'Both'}]};
const f=E.parseFilters([inFilter('People','EmployeeType',"'Billable'")]);
assert.match(E.whereFor('Hours',f,m),/EXISTS/);assert.match(E.whereFor('Hours',f,m),/"People"\."ID" = "Hours"\."EmployeeID"/);
const combined=E.whereFor('Hours',[...f,...E.parseFilters([inFilter('People','Location',"'West'")])],m);
assert.equal((combined.match(/EXISTS/g)||[]).length,1);
const visual={type:'card',definition:{query:{queryState:{Values:{projections:[{field:{Aggregation:{Expression:field('Hours','Hours'),Function:0}}}]}}}}};
assert.match(E.buildQuery(m,{reportFilters:[inFilter('People','EmployeeType',"'Billable'")]},visual).sql,/WHERE EXISTS/);
console.log('PASS: empty drillthrough, categorical/NULL/escaped filters, relationship propagation, combined predicates, aggregate SQL, unsupported filter rejection');
if(process.argv[2]){
 const fs=require('node:fs');const model=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const results=[];
 for(const page of model.pages)for(const v of page.visuals){
  if(!['card','clusteredColumnChart','clusteredBarChart','lineChart','tableEx','slicer'].includes(v.type))continue;
  try{const query=E.buildQuery(model,page,v);results.push({page:page.name,id:v.id,type:v.type,...query})}
  catch(e){results.push({page:page.name,id:v.id,type:v.type,error:e.message})}
 }
 fs.writeFileSync(process.argv[3],JSON.stringify(results,null,2));
 console.log('Real report:',results.filter(r=>!r.error).length,'compiled visual queries;',results.filter(r=>r.error).length,'explicit unsupported DAX/expression mappings.');
}

// Automatic date hierarchies keep calendar grain and active date-table filters.
const dateModel={measures:[],tables:[{name:'LocalDateTable_dates',columns:['Date','Year','QuarterNo','MonthNo','Day'].map(name=>({name}))}],relationships:[{FromTableName:'Releases',FromColumnName:'Date',ToTableName:'LocalDateTable_dates',ToColumnName:'Date',IsActive:1,Cardinality:'M:1',CrossFilteringBehavior:'Single'}]};
const hierarchy=level=>({HierarchyLevel:{Expression:{Hierarchy:{Expression:{PropertyVariationSource:{Expression:{SourceRef:{Entity:'Releases'}},Property:'Date',Name:'Variation'}},Hierarchy:'Date Hierarchy'}},Level:level}});
const line={type:'lineChart',definition:{query:{queryState:{Category:{projections:['Year','Month','Day'].map(level=>({field:hierarchy(level),nativeQueryRef:level}))},Y:{projections:[{field:{Aggregation:{Expression:field('Releases','Index'),Function:5}},nativeQueryRef:'Count'}]}}}}};
const datePlan=E.buildQuery(dateModel,{filters:[inFilter('LocalDateTable_dates','Year','2025L')]},line);
assert.match(datePlan.sql,/date_trunc\('day', "Releases"\."Date"\)/);assert.match(datePlan.sql,/COUNT\("Releases"\."Index"\)/);assert.match(datePlan.sql,/WHERE EXISTS/);assert.match(datePlan.sql,/ORDER BY "v0" ASC/);assert.deepEqual(datePlan.roles,['Category','Y']);assert.deepEqual(datePlan.labels,['Date','Count']);
assert.equal(line.definition.query.queryState.Category.projections.length,3);
const monthLine=structuredClone(line);monthLine.definition.query.queryState.Category.projections.pop();assert.match(E.buildQuery(dateModel,{},monthLine).sql,/date_trunc\('month'/);
const yearLine=structuredClone(line);yearLine.definition.query.queryState.Category.projections.length=1;assert.match(E.buildQuery(dateModel,{},yearLine).sql, /"LocalDateTable_dates"\."Year"/);
assert.throws(()=>E.buildQuery({...dateModel,relationships:[]},{},line),/resolve.*hierarchy/);
console.log('PASS: automatic date hierarchy day/month/year grain, chronological ordering and date filters');

const implicitAggregate={measures:[{Name:'New Hires',TableName:'Employee',Expression:'SUM([isNewHire])'}],relationships:[]};
const implicitVisual={type:'card',definition:{query:{queryState:{Values:{projections:[{field:{Measure:{Property:'New Hires',Expression:{SourceRef:{Entity:'Employee'}}}}}]}}}}};
assert.match(E.buildQuery(implicitAggregate,{},implicitVisual).sql,/SUM\("Employee"\."isNewHire"\)/);
console.log('PASS: unqualified aggregate columns resolve against the measure home table');
const hierarchySelection=[{filter:{Where:[{Condition:{In:{Expressions:[hierarchy('Year')],Values:[[{Literal:{Value:'2025L'}}]]}}}]}}];
assert.match(E.buildQuery(dateModel,{},line,hierarchySelection).sql,/"LocalDateTable_dates"\."Year" = 2025/);
const distinctLine=structuredClone(line);distinctLine.definition.query.queryState.Y.projections[0].field.Aggregation.Function=2;assert.match(E.buildQuery(dateModel,{},distinctLine).sql,/COUNT\(DISTINCT/);
console.log('PASS hierarchy slicer predicates and distinct/non-null count identities');
