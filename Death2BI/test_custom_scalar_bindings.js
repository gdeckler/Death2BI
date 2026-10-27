const assert=require('node:assert/strict'),E=require('./report-engine'),D=require('./custom-dataview');
const col=Property=>({Column:{Expression:{SourceRef:{Entity:'Data'}},Property}}),measure=Property=>({Measure:{Expression:{SourceRef:{Entity:'Measures'}},Property}}),projection=(field,name,active)=>({field,queryRef:name,nativeQueryRef:name,active});
const model={id:'custom-bindings',tables:[{name:'Data',columns:[{name:'Category'},{name:'Detail'},{name:'Value'}]}],measures:[{Name:'Amount',TableName:'Measures',Expression:'SUM(Data[Value])',FormatString:'0.0'}],relationships:[]};
const visual={type:'AnyCustomVisual'+'A'.repeat(32),definition:{
 visualType:'AnyCustomVisual'+'A'.repeat(32),
 query:{queryState:{dataset:{projections:[projection(col('Category'),'Category',true),projection(col('Detail'),'Inactive drill level',false),projection(measure('Amount'),'Amount',false)]}}}
}},before=JSON.stringify({model,visual});
const pkg=kind=>({capabilities:{dataRoles:[{name:'dataset',kind}],dataViewMappings:[{categorical:{categories:{select:[{bind:{to:'dataset'}}]},values:{select:[{bind:{to:'dataset'}}]}}}]}});
const compiled=E.buildQuery(model,{},visual,[]);assert.deepEqual(compiled.labels,['Category','Amount']);assert.deepEqual(compiled.roles,['dataset','dataset']);assert.deepEqual(compiled.formats,['','0.0']);assert.match(compiled.sql,/SUM\("Data"\."Value"\)/);assert(!compiled.sql.includes('"Detail"'));assert.deepEqual(D.projections(visual).map(p=>p.nativeQueryRef),compiled.labels);
const result={columns:['v0','v1'],types:['VARCHAR','DOUBLE'],rows:[['A',0],['B',null],['C',5]]};
for(const kind of ['GroupingOrMeasure',2]){
 const view=D.build(pkg(kind),visual,result,compiled);assert.equal(view.categorical.categories.length,1);assert.equal(view.categorical.values.length,1);assert.deepEqual(view.categorical.categories[0].values,['A','B','C']);assert.deepEqual(view.categorical.values[0].values,[0,null,5]);assert.equal(view.categorical.values[0].source.isMeasure,true);assert.equal(view.categorical.values[0].source.displayName,'Amount');assert.equal(view.categorical.values[0].source.format,'0.0');assert.deepEqual(view.categorical.categories[0].identity[0].rows,[0]);assert.deepEqual(view.table.rows,result.rows);
 assert.deepEqual(D.selectionFields(visual,result.rows,[2]),{fields:[{table:'Data',column:'Category',index:0,dataField:'v0',label:'Category'}],tuples:[['C']]});
}
const scalar=structuredClone(visual);scalar.definition.query.queryState.dataset.projections=[projection(measure('Amount'),'Renamed amount',false)];const scalarPlan=E.buildQuery(model,{},scalar,[]),scalarView=D.build(pkg('GroupingOrMeasure'),scalar,{columns:['v0'],types:['DOUBLE'],rows:[[5]]},scalarPlan);assert.equal(scalarView.categorical.categories.length,0);assert.equal(scalarView.categorical.values.length,1);assert.deepEqual(scalarView.categorical.values[0].values,[5]);assert.equal(scalarView.categorical.values[0].source.displayName,'Renamed amount');
const aggregated=structuredClone(visual);aggregated.definition.query.queryState.dataset.projections[2]=projection({Aggregation:{Expression:col('Value'),Function:0}},'Summed values',false);assert.deepEqual(E.buildQuery(model,{},aggregated).labels,['Category','Summed values']);assert.deepEqual(D.projections(aggregated).map(p=>p.nativeQueryRef),['Category','Summed values']);
// Native hierarchy/field-parameter drill handling is unchanged.
const native=structuredClone(visual);native.type=native.definition.visualType='lineChart';assert.deepEqual(E.buildQuery(model,{},native).labels,['Category']);assert.deepEqual(D.projections(native).map(p=>p.nativeQueryRef),['Category']);
assert.equal(JSON.stringify({model,visual}),before);
(async()=>{
 let requests=0;
 const data=await E.pythonQuery(model,{},visual,[],async sql=>{assert.match(sql,/"Category"/);assert(!sql.includes('"Detail"'));return {rows:[['A'],['B']],columns:['v0'],types:['VARCHAR']}},async(path,options)=>{requests++;assert.equal(path,'/api/dax');const payload=JSON.parse(options.body);assert.equal(payload.fields.length,2);assert.equal(payload.fields[1].Measure.Property,'Amount');assert.deepEqual(payload.groups.map(g=>g.values),[{'0':'A'},{'0':'B'}]);return {columns:['v0','v1'],types:['VARCHAR','DOUBLE'],rows:[['A',0],['B',5]]}});
 assert.equal(requests,1);assert.deepEqual(data.compiled.roles,['dataset','dataset']);assert.deepEqual(data.compiled.labels,['Category','Amount']);assert.equal(D.build(pkg('GroupingOrMeasure'),visual,data.result,data.compiled).categorical.values.length,1);assert.equal(JSON.stringify({model,visual}),before);
 console.log('PASS inactive custom scalar bindings through SQL/Python and mixed-role data views, grouping drill exclusion, scalar-only/zero/BLANK/format aliases and immutable native behavior');
})().catch(error=>{console.error(error);process.exitCode=1});
