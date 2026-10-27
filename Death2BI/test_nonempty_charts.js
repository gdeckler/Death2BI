const R=require('./vega-renderer'),assert=require('assert');
const field={Column:{Expression:{SourceRef:{Entity:'D'}},Property:'Category'}},measure={Measure:{Expression:{SourceRef:{Entity:'M'}},Property:'Top'}};
const visual={definition:{query:{queryState:{Category:{projections:[{field}]},Y:{projections:[{field:measure}]}}}}};
let s=R.buildSpec('clusteredBarChart',['Category','Top'],[['A',null],['B',0],['C',3]],['Category','Y'],{visual});assert.deepEqual(s.data.values.map(d=>d._category),['B','C']);
visual.definition.query.queryState.Category.projections[0].showAll=true;s=R.buildSpec('clusteredBarChart',['Category','Top'],[['A',null],['B',0]],['Category','Y'],{visual});assert.equal(s.data.values.length,2);console.log('Nonempty chart categories and explicit showAll passed');
