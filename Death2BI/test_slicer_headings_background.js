const assert=require('node:assert/strict'),S=require('./report-style');
class Node{constructor(tag){this.tagName=tag;this.style={};this.children=[];this.textContent='';this.className='';this.classList={contains:n=>this.className.split(' ').includes(n)}}querySelector(s){return this.children.find(n=>s.includes('h3')?n.tagName==='h3':s.includes('pbi-slicer-header')?n.className==='pbi-slicer-header':n.className==='pbi-subtitle')}prepend(n){n.parent=this;this.children.unshift(n)}after(n){n.parent=this.parent;this.parent.children.splice(this.parent.children.indexOf(this)+1,0,n)}remove(){this.parent.children=this.parent.children.filter(n=>n!==this)}}
global.document={createElement:tag=>new Node(tag)};
const lit=x=>({expr:{Literal:{Value:String(x)}}});
for(const titleOn of [false,true])for(const headerOn of [false,true]){
 const el=new Node('section'),placeholder=new Node('h3');el.prepend(placeholder);
 const v={type:'slicer',definition:{objects:{header:[{properties:{show:lit(headerOn),text:'Slicer header',fontColor:'#ffffff',textSize:13}}]},visualContainerObjects:{title:[{properties:{show:lit(titleOn),text:'Visual title',fontColor:'#ff0000'}}]}}};
 S.styleSlicerHeadings(el,{},v,'Field');assert.deepEqual(el.children.map(n=>n.textContent),[...(titleOn?['Visual title']:[]),...(headerOn?['Slicer header']:[])]);S.styleSlicerHeadings(el,{},v,'Field');assert.equal(el.children.length,Number(titleOn)+Number(headerOn));if(headerOn){const head=el.querySelector('.pbi-slicer-header');assert.equal(head.style.color,'#ffffff');assert.equal(head.style.fontSize,13*4/3+'px')}
}
const source={type:'slicer',definition:{objects:{header:[{properties:{fontColor:'#ffffff'}}]},visualContainerObjects:{title:[{properties:{show:lit(false),text:'Disabled saved title'}}]}}};assert.equal(S.slicerHeadingPlan({},source,'Release Date').text,'Release Date');assert.equal(S.slicerHeadingPlan({},source,'Release Date').show,true);
assert.equal(S.backgroundSize('Stretch'),'100% 100%');assert.equal(S.backgroundSize('Fit'),'100% 100%');assert.equal(S.backgroundSize('Contain'),'contain');assert.equal(S.backgroundSize('Normal'),'auto');assert.equal(S.backgroundSize('Fill'),'cover');
console.log('PASS independent slicer Title/Header visibility and formatting, default field headers, repeated rendering and canvas Stretch/Fit/Contain/Normal/Fill modes');
