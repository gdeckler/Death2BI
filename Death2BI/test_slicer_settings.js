const assert=require('node:assert/strict'),C=require('./report-controls');
const lit=v=>({expr:{Literal:{Value:typeof v==='string'?"'"+v+"'":String(v)}}});
const slicer=objects=>({definition:{objects}});
assert.equal(C.slicerSettings({},slicer({data:[{properties:{mode:lit('Dropdown')}}],selection:[{properties:{selectAllCheckboxEnabled:lit(true)}}]})).single,false);
assert.equal(C.slicerSettings({},slicer({data:[{properties:{mode:lit('Dropdown')}}],selection:[{properties:{selectAllCheckboxEnabled:lit(true)}}]})).selectAll,true);
assert.equal(C.slicerSettings({},slicer({data:[{properties:{mode:lit('Basic')}}],general:[{properties:{orientation:{expr:{Literal:{Value:'1D'}}}}}]})).layout,'tiles');
assert.equal(C.slicerSettings({},slicer({data:[{properties:{mode:lit('Basic')}}]})).layout,'list');
assert.equal(C.slicerSettings({},slicer({selection:[{properties:{singleSelect:lit(true),multiSelectWithCtrl:lit(false)}}]})).single,true);
const expr={Column:{Expression:{SourceRef:{Entity:'Countries'}},Property:'Country'}};
const f=C.categoricalFilter(expr,['France',"O'Brien",null]);assert.deepEqual(C.selectedValues(f),['France',"O'Brien",null]);assert.deepEqual(C.selectedValues(JSON.parse(JSON.stringify(f))),['France',"O'Brien",null]);
assert.equal(f[0].filter.Where[0].Condition.In.Values.length,3);assert.equal(C.categoricalFilter(expr,[])[0].filter.Where[0].Condition.In.Values.length,0);
console.log('PASS source tile orientation, list/dropdown, selection defaults/overrides, typed multi-value filters, blanks and escaped values');

