const assert=require('node:assert/strict'),F=require('./model-formats.js'),V=require('./vega-renderer.js');
assert.equal(F.text(.242,'0.0%'),'24.2%');assert.equal(F.text(1.2,'0.00'),'1.20');assert.equal(F.text(-.125,'0.0%;-0.0%;0.0%'),'-12.5%');assert.equal(F.text(1234.5,'#,0.00'),'1,234.50');
const spec=V.buildSpec('clusteredColumnChart',['Country','Rate'],[['A',.242]],['Category','Y'],{formats:['','0.0%']});assert.equal(spec.encoding.y.axis.format,'.1%');assert.equal(spec.data.values[0]._formattedValue,'24.2%');assert.equal(spec.data.values[0]._value,.242);
console.log('PASS numeric formatting: percentages, decimals, grouping, negatives, numeric chart values');
