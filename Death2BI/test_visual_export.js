const assert=require('node:assert/strict'),X=require('./visual-export.js');
assert.equal(X.csv(['Text','Value'],[['a,b\n"q"',-3],['=1',null]]),'\ufeff"Text","Value"\r\n"a,b\n""q""","-3"\r\n"\'=1",""\r\n');
const model={name:'Report.pbix',tables:[{name:'Countries'},{name:'Population'}],measures:[{Name:'Average Population',TableName:'_Measures',Expression:"AVERAGE('Population'[Value])"}]};
const field=(kind,table,name)=>({[kind]:{Expression:{SourceRef:{Entity:table}},Property:name}});
const visual={id:'chart/one',definition:{query:{queryState:{Category:{projections:[{field:field('Column','Countries','Country')}]},Y:{projections:[{field:field('Measure','_Measures','Average Population')}]}}}}};
assert.deepEqual(X.sourceTables(model,visual),['Population','Countries']);assert.equal(X.filename(model,visual,'chart'),'Report-chart_one-chart.csv');
console.log('PASS CSV quoting, Unicode BOM, formula-safe text, file names and measure lineage for source-table selection');
