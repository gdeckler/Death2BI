const assert=require('node:assert/strict'),R=require('./vega-renderer'),C=require('./report-controls');
const v={type:'scatterChart',definition:{query:{queryState:{}}}};
const spec=R.buildSpec('scatterChart',['ID','Size by measure','Votes'],[[1,20,400],[2,30,500]],['Category','Size','X'],{model:{theme:{}},visual:v});
assert.equal(spec.encoding.size.legend,null);assert.ok(spec.data.values.every(d=>d._y===0));assert.deepEqual(spec.data.values.map(d=>d._size),[20,30]);
const explicit=R.buildSpec('scatterChart',['X','Y','Size'],[[1,2,3]],['X','Y','Size'],{showSizeLegend:true});assert.deepEqual(explicit.encoding.size.legend,{});
const col=(t,p)=>({Column:{Expression:{SourceRef:{Entity:t}},Property:p}}),old={Measure:{Expression:{SourceRef:{Entity:'M'}},Property:'Profit'}};
const model={measures:[{Name:'ROI'}],fieldParameters:{Choices:{columns:['Label','Fields'],fieldColumn:'Fields',rows:[['ROI',"'M'[ROI]"]]}}};
const slicer={id:'s',type:'slicer',definition:{query:{queryState:{Values:{projections:[{field:col('Choices','Label')}]}}}}};
const table={id:'t',definition:{query:{queryState:{},sortDefinition:{sort:[{field:old,direction:'Descending'}]}}}};
table.definition.query.queryState.Values={projections:[{field:old}],fieldParameters:[{parameterExpr:col('Choices','Label'),index:0,length:1,sortDirection:'Descending'}]};

model.fieldParameters.Choices.fieldColumn='Label';
const selection=C.categoricalFilter(col('Choices','Label'),['ROI']),resolved=C.resolve(model,{visuals:[slicer]},table,()=>selection);
assert.equal(resolved.definition.query.queryState.Values.projections[0].field.Measure.Property,'ROI');assert.equal(resolved.definition.query.sortDefinition.sort[0].field.Measure.Property,'ROI');assert.equal(C.filtersFor(model,{visuals:[slicer]},'t',()=>selection,()=>true).length,1);assert.equal(table.definition.query.queryState.Values.projections[0].field.Measure.Property,'Profit');
console.log('PASS native scatter size-legend suppression and single-axis layout; metric parameter field, sorting and DAX context preservation');
