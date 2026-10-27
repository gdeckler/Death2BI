const assert=require('node:assert/strict'),E=require('./report-engine'),R=require('./vega-renderer'),M=require('./matrix-rendering');
const v={type:'map',definition:{query:{queryState:{Category:{projections:[{field:{Column:{Expression:{SourceRef:{Entity:'T'}},Property:'city'}}}]}}}}},m={tables:[{name:'T',columns:[{name:'city'},{name:'latitude'},{name:'longitude'}]}]};
const p=E.geographicVisual(v,m);assert.ok(p.definition.query.queryState.Latitude);assert.equal(v.definition.query.queryState.Latitude,undefined);assert.equal(E.geographicVisual(p,m),p);
// Location roles establish geographic intent without English place-name
// conventions. Inference must stay within the bound table and preserve source.
for(const property of ['LGA','Administrative area code','Gemeindeschlüssel','지역']){
 const source=structuredClone(v);source.definition.query.queryState.Category.projections[0].field.Column.Property=property;
 const model={tables:[{name:'T',columns:[{name:property,type:'VARCHAR'},{name:'latitude',type:'DOUBLE'},{name:'longitude',type:'DOUBLE'}]}]};
 const before=JSON.stringify({source,model}),inferred=E.formattingVisual(source,model),state=inferred.definition.query.queryState;
 assert.equal(state.Latitude.projections[0].field.GeoMean.table,'T');assert.equal(state.Latitude.projections[0].field.GeoMean.column,'latitude');assert.equal(state.Longitude.projections[0].field.GeoMean.column,'longitude');
 assert.equal(JSON.stringify({source,model}),before);
 assert.equal(E.geographicVisual(inferred,model),inferred,'repeated conversion must not duplicate geographic fields');
 const explicit=structuredClone(source);explicit.definition.query.queryState.Latitude={projections:[{field:{Column:{Expression:{SourceRef:{Entity:'T'}},Property:'latitude'}}}]};
 assert.equal(E.geographicVisual(explicit,model),explicit,'authored coordinate roles take precedence, including partial bindings');
 for(const columns of [[{name:'latitude',type:'VARCHAR'},{name:'longitude',type:'DOUBLE'}],[{name:'latitude',type:'DOUBLE'},{name:'lat',type:'DOUBLE'},{name:'longitude',type:'DOUBLE'}],[{name:'latitude',type:'DOUBLE'}]])assert.equal(E.geographicVisual(source,{tables:[{name:'T',columns}]}),source,'ambiguous, nonnumeric or incomplete coordinate pairs cannot be inferred');
 assert.equal(E.geographicVisual(source,{tables:[{name:'Other',columns:model.tables[0].columns}]}),source,'another table cannot supply inferred coordinates');
 const filled={...source,type:'filledMap'};assert.equal(E.geographicVisual(filled,model),filled,'area maps retain their authored polygon mapping');
}
const s=R.buildSpec('map',['Region','N'],[['South Asia',-9],['Australasia & Oceania',4]],['Category','Size'],{});assert.equal(s.data.values.length,2);assert.equal(s.data.values[0]._size,9);assert.equal(s.data.values[0]._signedSize,-9);
const spark=M.sparklineMarkup({sparkline:[[2020,2],[2021,4]]});assert.match(spark,/<svg/);assert.match(spark,/M2.00,28.00 L118.00,2.00/);assert.equal(M.sparklineMarkup('<script>'),null);console.log('PASS embedded coordinate inference, region maps and accessible sparkline SVG');
