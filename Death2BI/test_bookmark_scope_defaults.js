const assert=require('node:assert/strict'),S=require('./report-style');

// Portable source-shaped fixture: a 27-visual PBIR page with a stale selected
// visual list, but no applyOnlyToTargetVisuals flag. No report assets are needed.
const pageId='poster',overlay='cbb15214283960b17325',end='195d00880430b3be12c8';
const ids=['5272d82a42ec99964221','c6a29b0922f9944e5fe8','b626358b1798d715a1a5','e31a7c083a495fdb88d0','5aa55052bfeb966d32d8','5979eb87ae150cc3a441','5d9c8a1345707560c888','d1f20e82b87d9dfe2a35','1dc58dc63c6a0ce4b98a','21a2ceaa83bbba9d7a7e','99a7e16090d26bab5888','4b172adbf9793adb1659','2c9b457046339ba88cbe','4b445c0955dcdb1dd501','d71f6cbd95fbd43249ea','130957e77579e72d3360','7f37db4fc201ec32beae','ebf23451c3548b2d44e0','39ea76ee660984bcf20a','5044ffc6fd6e715af28f','8dc92d15952849a99358','ca3cc64d318394b006fd',overlay,'50358933c40dcbc96245','c79dc94b40e4e68e76e6','b7ff560c8da6ad9410d1',end];
const initialVisible=new Set(['5272d82a42ec99964221','99a7e16090d26bab5888','d71f6cbd95fbd43249ea','39ea76ee660984bcf20a','5044ffc6fd6e715af28f','8dc92d15952849a99358','ca3cc64d318394b006fd',overlay]);
const model={pages:[{id:pageId,visuals:ids.map(id=>({id,type:'image',ownHidden:!initialVisible.has(id),hidden:!initialVisible.has(id),definition:{}}))}]};
const visibilitySets=[['39ea76ee660984bcf20a','ebf23451c3548b2d44e0'],['130957e77579e72d3360','7f37db4fc201ec32beae','d71f6cbd95fbd43249ea','4b445c0955dcdb1dd501']];
function state(index){const visible=new Set(visibilitySets[index]);return {name:'game-'+index,options:{targetVisualNames:[end],preserveNewVisualVisibility:true},explorationState:{activeSection:pageId,sections:{[pageId]:{visualContainers:Object.fromEntries(ids.map(id=>[id,{singleVisual:{visualType:'image',objects:{},...(!visible.has(id)?{display:{mode:'hidden'}}:{})}}]))}}}}}
const original=JSON.stringify(model),bookmarks=[state(0),state(1)],originalBookmarks=JSON.stringify(bookmarks);
let current=model;
for(let index=0;index<bookmarks.length;index++){
 const bookmark=bookmarks[index];assert.equal(Object.hasOwn(bookmark.options,'applyOnlyToTargetVisuals'),false);assert.equal(Object.keys(bookmark.explorationState.sections[pageId].visualContainers).length,27);
 assert.deepEqual(S.bookmarkScope(bookmark),[],'a stale target list does not enable selected-visual mode');
 const plan=S.bookmarkPlan(current,bookmark,{activePageId:pageId});
 assert.equal(plan.targetPageId,pageId);assert.deepEqual(plan.pages[0].visuals.filter(v=>!v.hidden).map(v=>v.id).sort(),visibilitySets[index].slice().sort());
 assert.equal(plan.pages[0].visuals.find(v=>v.id===overlay).hidden,true,'the clicked start overlay must be removed by the page snapshot');
 assert.equal(plan.pages[0].visuals.find(v=>v.id===end).hidden,true,'the stale target itself remains hidden');
 assert.deepEqual(plan.clearPages,[pageId]);assert.equal(plan.resetSlicers.length,27);
 current={...current,pages:plan.pages};
}
assert.equal(JSON.stringify(model),original);assert.equal(JSON.stringify(bookmarks),originalBookmarks);

// Explicit selected-visual mode retains its narrower scope, including groups.
const initialFilter=[{filter:{marker:'initial'}}],savedFilter=[{filter:{marker:'saved'}}];
const scopedModel={pages:[{id:'one',filters:initialFilter,reportFilters:initialFilter,visuals:[{id:'group',type:'group',ownHidden:false,hidden:false},{id:'child',type:'slicer',groupChain:['group'],ownHidden:false,hidden:false,filters:initialFilter,definition:{}},{id:'other',type:'image',ownHidden:false,hidden:false,filters:initialFilter,definition:{}}]},{id:'two',visuals:[{id:'another',type:'image',ownHidden:false,hidden:false,definition:{}}]}]};
const scopedBefore=JSON.stringify(scopedModel),snapshot={name:'scoped',options:{applyOnlyToTargetVisuals:true,targetVisualNames:['group'],suppressActiveSection:true},explorationState:{activeSection:'two',filters:{byExpr:savedFilter},sections:{one:{filters:{byExpr:savedFilter},visualContainerGroups:{group:{isHidden:true}},visualContainers:{child:{filters:{byExpr:savedFilter},singleVisual:{}},other:{filters:{byExpr:savedFilter},singleVisual:{display:{mode:'hidden'}}}}},two:{visualContainers:{another:{singleVisual:{display:{mode:'hidden'}}}}}}}};
let plan=S.bookmarkPlan(scopedModel,snapshot,{activePageId:'one'});assert.equal(plan.targetPageId,'one');assert.deepEqual(S.bookmarkScope(snapshot),['group']);assert.deepEqual(plan.clearPages,[]);assert.deepEqual(plan.resetSlicers,[{pageId:'one',visualId:'child'}]);
assert.equal(plan.pages[0].visuals[1].hidden,true);assert.deepEqual(plan.pages[0].visuals[1].filters,savedFilter);assert.equal(plan.pages[0].visuals[2].hidden,false);assert.deepEqual(plan.pages[0].visuals[2].filters,initialFilter);assert.deepEqual(plan.pages[0].filters,initialFilter);assert.deepEqual(plan.pages[0].reportFilters,initialFilter);assert.equal(plan.pages[1].visuals[0].hidden,false);

const empty=structuredClone(snapshot);empty.options.targetVisualNames=[];plan=S.bookmarkPlan(scopedModel,empty,{activePageId:'one'});assert.deepEqual(plan.pages,scopedModel.pages,'an explicitly selected-only bookmark with no selected visuals is a no-op');assert.deepEqual(plan.clearPages,[]);assert.deepEqual(plan.resetSlicers,[]);
const full=structuredClone(snapshot);full.options.applyOnlyToTargetVisuals=false;plan=S.bookmarkPlan(scopedModel,full,{activePageId:'one'});assert.deepEqual(S.bookmarkScope(full),[]);assert.deepEqual(plan.clearPages,['one','two']);assert.deepEqual(plan.pages[0].filters,savedFilter);assert.deepEqual(plan.pages[0].reportFilters,savedFilter);assert.equal(plan.pages[0].visuals[2].hidden,true);assert.equal(plan.pages[1].visuals[0].hidden,true);

// Display-only/data-only flags remain independent of the inferred scope.
const displayOnly=structuredClone(full);delete displayOnly.options.applyOnlyToTargetVisuals;displayOnly.options.suppressData=true;plan=S.bookmarkPlan(scopedModel,displayOnly,{activePageId:'one'});assert.deepEqual(plan.clearPages,[]);assert.deepEqual(plan.resetSlicers,[]);assert.equal(plan.pages[0].visuals[2].hidden,true);assert.deepEqual(plan.pages[0].visuals[2].filters,initialFilter);assert.deepEqual(plan.pages[0].filters,initialFilter);
const dataOnly=structuredClone(full);dataOnly.options.suppressDisplay=true;plan=S.bookmarkPlan(scopedModel,dataOnly,{activePageId:'one'});assert.equal(plan.pages[0].visuals[2].hidden,false);assert.deepEqual(plan.pages[0].visuals[2].filters,savedFilter);assert.deepEqual(plan.clearPages,['one','two']);
assert.equal(JSON.stringify(scopedModel),scopedBefore);assert.deepEqual(S.bookmarkScope({}),[]);assert.deepEqual(S.bookmarkScope({options:{}}),[]);assert.deepEqual(S.bookmarkScope({options:{applyOnlyToTargetVisuals:true}}),[]);
console.log('PASS omitted/false full-page bookmark scope, 27-visual image-action snapshots, explicit selected/group/empty scopes, independent data/display flags and immutable source');
