const assert=require('node:assert/strict'),V=require('./vega-renderer');
const visual={type:'scatterChart',definition:{objects:{categoryAxis:[{properties:{labelDisplayUnits:1e9,labelPrecision:1}}],valueAxis:[{properties:{labelDisplayUnits:1e6,labelPrecision:2}}]}}};
let s=V.buildSpec('scatterChart',['Budget','Revenue'],[[940000000,4000000000]],['X','Y'],{model:{theme:{}},visual,formats:['0','0']});assert.match(s.encoding.x.axis.labelExpr,/1000000000/);assert.match(s.encoding.x.axis.labelExpr,/\.1f/);assert.match(s.encoding.y.axis.labelExpr,/1000000/);assert.match(s.encoding.y.axis.labelExpr,/\.2f/);
visual.definition.objects.categoryAxis=[{properties:{}}];s=V.buildSpec('scatterChart',['Budget','Revenue'],[[940000000,4e9]],['X','Y'],{model:{theme:{}},visual});assert.match(s.encoding.x.axis.labelExpr,/1000000000/);assert.match(s.encoding.x.axis.labelExpr,/"B"/);
console.log('PASS independent scatter X/Y display units and decimal precision, including automatic billion-axis extent');
