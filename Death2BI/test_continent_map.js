const assert=require('node:assert/strict'),R=require('./vega-renderer');
const s=R.buildSpec('filledMap',['Continent','People'],[['Europe',75],['Africa',2]],['Category','Tooltips'],{});
assert.ok(s.data.values.length>2);assert.ok(s.data.values.some(d=>d.properties.name==='France'&&d._value===75&&d._categoryValue==='Europe'));assert.ok(s.data.values.every(d=>['Europe','Africa'].includes(d._country)));
assert.throws(()=>R.buildSpec('filledMap',['Location','People'],[['Europe',75],['France',2]],['Category','Y'],{}),/overlapping regions/);
console.log('PASS continent filled maps retain region values and selection identities');
