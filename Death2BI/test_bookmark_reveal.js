const assert=require('node:assert/strict'),S=require('./report-style');
const p={visuals:[{id:'poster',ownHidden:true},{id:'envelope',ownHidden:false},{id:'untouched',ownHidden:true},{id:'group',type:'group',ownHidden:true},{id:'child',ownHidden:false,groupChain:['group']}]};
S.applyBookmarkDisplay(p,{visualContainers:{poster:{singleVisual:{}},envelope:{singleVisual:{display:{mode:'hidden'}}}}});
assert(!p.visuals[0].hidden);assert(p.visuals[1].hidden);assert(p.visuals[2].hidden);assert(p.visuals[4].hidden);
S.applyBookmarkDisplay(p,{visualContainerGroups:{group:{}}},['group']);assert(!p.visuals[4].hidden);
S.applyBookmarkDisplay(p,{visualContainers:{poster:{singleVisual:{display:{mode:'hidden'}}},untouched:{singleVisual:{}}}},['poster']);assert(p.visuals[0].hidden);assert(p.visuals[2].hidden);
console.log('PASS bookmark default-visible reveal, explicit hiding, absent-state preservation, group reveal and scope');
