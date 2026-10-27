const assert=require('node:assert/strict'),E=require('./report-engine');
const column=(table,name='Value')=>({Column:{Expression:{SourceRef:{Entity:table}},Property:name}}),measure=(table,name)=>({Measure:{Expression:{SourceRef:{Entity:table}},Property:name}}),visual=field=>({type:'tableEx',definition:{query:{queryState:{Values:{projections:[{field,nativeQueryRef:'Value'}]}}}}}),page={filters:[],reportFilters:[]};
const model={id:'fixture',tables:[{name:'Good',columns:[{name:'Value'}]}],relationships:[],measures:[{TableName:'Period',Name:'Constant',Expression:'42'},{TableName:'Good',Name:'Missing total',Expression:"SUM('Period'[Value])"}],unavailableTables:[{name:'Period',error:'Embedded IDFX metadata missing.'}]};
const extraction=error=>error.code==='SOURCE_DATA_UNAVAILABLE'&&/source table “Period”/.test(error.message)&&/Embedded IDFX metadata missing/.test(error.message);
async function run(){
 assert.throws(()=>E.parameterQuery(model,page,visual(column('Period')),'Period'),extraction);
 assert.throws(()=>E.buildQuery(model,page,visual(column('Period'))),extraction);
 assert.throws(()=>E.buildQuery(model,page,visual({Aggregation:{Expression:column('Period'),Function:0}})),extraction);
 assert.throws(()=>E.buildQuery(model,page,visual(measure('Good','Missing total'))),extraction,'simple measure dependency must retain the extraction cause');
 assert.throws(()=>E.underlyingPlan(model,page,visual(column('Period')),[],'Period'),extraction);
 let calls=0;await assert.rejects(E.pythonQuery(model,page,visual(column('Period')),[],async()=>{calls++},async()=>{calls++}),extraction);assert.equal(calls,0,'known missing physical data fails before SQL or DAX requests');
 assert.match(E.parameterQuery(model,page,visual(column('Good')),'Good'),/SELECT \* FROM "Good"/);
 assert.match(E.buildQuery(model,page,visual(column('Good'))).sql,/FROM "Good"/);
 assert.match(E.buildQuery(model,page,visual(measure('Period','Constant'))).sql,/SELECT (?:DISTINCT )?42 AS/,'unavailable measure home table alone does not imply unavailable source rows');
 const result=await E.pythonQuery(model,page,visual(measure('Period','Constant')),[],async()=>{throw Error('constant should not query a category domain')},async(path,options)=>{assert.equal(path,'/api/dax');assert.equal(JSON.parse(options.body).fields[0].Measure.Property,'Constant');return {rows:[[42]]}});assert.deepEqual(result.result.rows,[[42]]);
 assert.doesNotThrow(()=>E.assertTableAvailable(model,'Unknown'),'do not invent an extraction cause for an unrelated table');assert.doesNotThrow(()=>E.assertTableAvailable({},'Period'));
 assert.doesNotThrow(()=>E.assertTableAvailable({...model,tables:[{name:'PERIOD',columns:[]}]},'period'),'successful extraction wins over stale unavailable metadata');
 assert.match(E.buildQuery({...model,tables:[{name:'Period',columns:[{name:'Value'}]}]},page,visual(column('Period'))).sql,/FROM "Period"/);
 const disconnected=[{table:'Period',columns:['Value'],sql:'"Period"."Value" = 1'}];assert.equal(E.whereFor('Good',disconnected,model),'','unrelated filters are not an unavailable source dependency');
 const relationship={IsActive:true,Cardinality:'M:1',FromTableName:'Good',FromColumnName:'Value',ToTableName:'Period',ToColumnName:'Value'};
 assert.throws(()=>E.whereFor('Good',disconnected,{...model,relationships:[relationship]}),extraction,'a propagated predicate requires its unavailable dimension');
 assert.throws(()=>E.buildQuery(model,page,visual({DateBucket:{table:'Period',column:'Date',unit:'month'}})),extraction);
 const snapshot=JSON.stringify(model);E.buildQuery(model,page,visual(column('Good')));assert.equal(JSON.stringify(model),snapshot);
 console.log('PASS unavailable-source diagnostics for parameters, visuals, physical DAX fields, aggregates and propagated filters; recovered/partial models and constant measures remain usable');
}
run().catch(error=>{console.error(error);process.exitCode=1});
