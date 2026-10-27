const assert=require('node:assert/strict'),D=require('./custom-dataview'),F=require('./custom-frame');
const pkg={guid:'violinPlot4D46EB9EB3A141D9BA2289793175D971',js:'',capabilities:{dataRoles:[{name:'sampling',kind:'Grouping'},{name:'measure',kind:'Measure'},{name:'category',kind:'Grouping'}],dataViewMappings:[{categorical:{categories:{select:[{for:{in:'category'}},{for:{in:'sampling'}}]},values:{bind:{to:'measure'}}}}]}};
const visual={definition:{query:{queryState:{measure:{projections:[{field:{Measure:{Property:'Average'}}}]},sampling:{projections:[{field:{Column:{Expression:{SourceRef:{Entity:'Facts'}},Property:'Country'}}}]}}}}};
const view=D.build(pkg,visual,{columns:['v0','v1'],types:['DOUBLE','VARCHAR'],rows:[[7,'France'],[8,'Finland']]},{labels:['Average','Country'],formats:['0.00',null]});
assert.deepEqual(view.categorical.categories[0].values,['France','Finland']);assert.deepEqual(view.categorical.values[0].values,[7,8]);
const html=F.documentFor(pkg,'safe-token');assert.match(html,/colors:palette.map/);assert.match(html,/VisualUpdateType/);assert.match(html,/VisualDataChangeOperationKind/);
console.log('PASS legacy Violin sampling/measure roles, palette and API enums');

const legacy={...pkg,version:"1.3.0.4",js:'else this.viewModel.xAxis.generator.tickFormat("")'};assert.match(F.compatibleScript(legacy),/generator&&/);assert.equal(F.compatibleScript({...legacy,version:"2.0"}),legacy.js);
