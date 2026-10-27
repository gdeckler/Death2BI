const assert=require('node:assert/strict'),C=require('./report-controls'),S=require('./report-style');
class Node{
 constructor(tag){this.tagName=tag.toUpperCase();this.style={cssText:''};this.children=[];this.dataset={};this.attributes={};this.textContent=''}
 appendChild(node){this.children.push(node);return node}prepend(node){this.children.unshift(node)}setAttribute(name,value){this.attributes[name]=String(value)}getAttribute(name){return this.attributes[name]??null}
 querySelectorAll(selector){const out=[];function walk(node){for(const child of node.children){if(selector==='button'&&child.tagName==='BUTTON')out.push(child);walk(child)}}walk(this);return out}
}
const previous={document:global.document,ReportStyle:global.ReportStyle};global.document={createElement:tag=>new Node(tag)};global.ReportStyle=S;
const field={Column:{Expression:{SourceRef:{Entity:'Picker'}},Property:'Choice'}},model={theme:{dataColors:['#123456']}},values=['A','B','C'];
function setup(selection={},selected=['A']){
 const visual={id:'button-picker',type:'slicer',originalType:'advancedSlicerVisual',definition:{visualType:'advancedSlicerVisual',query:{queryState:{Values:{projections:[{field,nativeQueryRef:'Choice'}]}}},objects:{selection:[{properties:selection}],fillCustom:[{properties:{show:false}}],value:[{properties:{show:false}}]}}},el=new Node('section'),changes=[],filters=C.categoricalFilter(field,selected),before=JSON.stringify({visual,filters,values});
 C.categoricalSlicer(el,model,visual,values,{filters,onChange:next=>changes.push(next)});
 const buttons=el.children[0].children.filter(node=>node.tagName==='BUTTON'),offset=selection.selectAllCheckboxEnabled?1:0;
 const click=(value,event={})=>buttons[values.indexOf(value)+offset].onclick({ctrlKey:false,metaKey:false,...event}),latest=()=>C.selectedValues(changes.at(-1));
 return {visual,filters,changes,buttons,click,latest,checkSource:()=>assert.equal(JSON.stringify({visual,filters,values}),before,'live click state must not mutate original saved filters or visual definitions')};
}
try{
 // A rerender can wait for an asynchronous security/data request. All these
 // events deliberately use the SAME mounted controls before any replacement.
 const rapid=setup({multiSelectWithCtrl:true});
 rapid.click('B',{ctrlKey:true});assert.deepEqual(rapid.latest(),['A','B']);
 rapid.click('C',{metaKey:true});assert.deepEqual(rapid.latest(),['A','B','C'],'a second rapid Cmd click must include the preceding Ctrl selection');
 rapid.click('A',{ctrlKey:true});assert.deepEqual(rapid.latest(),['B','C'],'toggle removes from the latest live selection');
 rapid.click('C');assert.deepEqual(rapid.latest(),['C'],'plain click replaces multiple selection');
 rapid.click('C');assert.equal(rapid.changes.at(-1),null,'second click can clear a non-strict selection');
 rapid.click('B',{metaKey:true});assert.deepEqual(rapid.latest(),['B'],'Cmd selection after clearing starts from empty');rapid.checkSource();

 const direct=setup({multiSelectWithCtrl:false});direct.click('B');assert.deepEqual(direct.latest(),['A','B']);direct.click('C');assert.deepEqual(direct.latest(),['A','B','C']);direct.click('A');assert.deepEqual(direct.latest(),['B','C']);direct.click('B');direct.click('C');assert.equal(direct.changes.at(-1),null,'removing the final selected value clears the filter');direct.checkSource();
 const clear=setup({multiSelectWithCtrl:true,selectAllCheckboxEnabled:true});clear.click('B',{ctrlKey:true});clear.buttons[0].onclick({});assert.equal(clear.changes.at(-1),null);clear.click('C',{ctrlKey:true});assert.deepEqual(clear.latest(),['C'],'Select all/clear resets local selection before the next click');clear.checkSource();

 const single=setup({singleSelect:true});single.click('B',{ctrlKey:true});assert.deepEqual(single.latest(),['B']);single.click('C',{metaKey:true});assert.deepEqual(single.latest(),['C'],'single selection never accumulates with modifiers');single.click('C',{ctrlKey:true});assert.equal(single.changes.at(-1),null);single.checkSource();
 const strict=setup({strictSingleSelect:true});strict.click('B');strict.click('B',{ctrlKey:true});assert.deepEqual(strict.latest(),['B'],'strict single selection cannot deselect its selected value');strict.click('C',{metaKey:true});assert.deepEqual(strict.latest(),['C']);strict.click('C');assert.deepEqual(strict.latest(),['C']);strict.checkSource();
 console.log('PASS same-DOM rapid Ctrl/Cmd button selection, plain replacement, toggle/clear, modifier-free multi-select, single/strict settings and immutable saved source');
}finally{Object.assign(global,previous)}
