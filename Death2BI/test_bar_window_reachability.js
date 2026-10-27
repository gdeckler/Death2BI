const assert=require('node:assert/strict'),R=require('./vega-renderer');
const rows=[['First',14],['Second',13],['Bottom',11]],labels=['Fear','Value'],roles=['Category','Y'];
for(const type of ['barChart','clusteredBarChart','stackedBarChart','hundredPercentStackedBarChart'])for(const height of [60,80,100,120,180])for(const show of [false,true]){
 const plan=R.barWindow(type,labels,rows,roles,height,{dataLabels:{show}});if(!plan)continue;
 assert(Number.isInteger(plan.totalHeight));assert(Math.floor((plan.totalHeight-height)/plan.step)>=plan.categories.length-plan.count,'Bottom window must be reachable within the browser scroll range');
}
class Node{
 constructor(tag){this.tagName=tag;this.style={};this.children=[];this.listeners=new Map();this.attrs={};this.dataset={};this.classList={add(){}};this._connected=true;this._scrollTop=0}
 get isConnected(){return this._connected&&(this.parentNode?.isConnected??true)}
 get clientHeight(){const explicit=this.style.height??this.style.cssText?.match(/(?:^|;)height:([^;]+)/)?.[1];return /px$/.test(explicit||'')?parseFloat(explicit):this._height??this.parentNode?.clientHeight??100}
 get clientWidth(){return this._width??this.parentNode?.clientWidth??500}
 get scrollHeight(){return Math.max(this.clientHeight,Math.round(this.children.reduce((sum,child)=>sum+child.clientHeight,0)))}
 get scrollTop(){return this._scrollTop}set scrollTop(value){this._scrollTop=Math.max(0,Math.min(this.scrollHeight-this.clientHeight,value))}
 setAttribute(key,value){this.attrs[key]=value}appendChild(child){child.parentNode=this;this.children.push(child);return child}replaceChildren(...children){for(const child of this.children)child.parentNode=null;this.children=[];for(const child of children)this.appendChild(child)}
 addEventListener(key,fn){if(!this.listeners.has(key))this.listeners.set(key,new Set());this.listeners.get(key).add(fn)}removeEventListener(key,fn){const set=this.listeners.get(key);set?.delete(fn);if(!set?.size)this.listeners.delete(key)}
 emit(key,event={}){for(const fn of this.listeners.get(key)||[])fn({target:this,preventDefault(){},...event})}querySelectorAll(){return []}
}
// Debounced renders now deliberately yield browser tasks. Await completion
// instead of assuming the timer, spec planning and embed finish within 45 ms.
async function wait(ready=()=>true){for(let i=0;i<100;i++){await new Promise(resolve=>setTimeout(resolve,10));if(ready())return}assert(ready(),'Timed out waiting for the requested bar window')}
(async()=>{
 const original=Object.fromEntries(['document','vegaEmbed','ResizeObserver'].map(key=>[key,global[key]])),records=[],observers=[];let embedGate=null;
 global.document={createElement:tag=>new Node(tag)};global.ResizeObserver=class{constructor(fn){this.fn=fn;observers.push(this)}observe(target){this.target=target}disconnect(){this.disconnected=true}};
 global.vegaEmbed=async(el,spec)=>{const gate=embedGate;embedGate=null;const record={el,spec,finalized:false},view={finalize(){record.finalized=true},addEventListener(){},width(){return this},height(){return this},resize(){return this},runAsync(){return Promise.resolve()}};records.push(record);if(gate){gate.started();await gate.wait}return {view}};
 const make=height=>{const el=new Node('div');el._height=height;return el};
 try{
  const source=JSON.stringify(rows),el=make(100);await R.mount(el,'clusteredBarChart',labels,rows,roles,{dataLabels:{show:true}});assert.equal(el.dataset.firstCategory,'First');const first=records.at(-1);assert(first.spec.data.values.some(d=>d._category==='First'));
  el.emit('keydown',{key:'End'});await wait(()=>el.dataset.lastCategory==='Bottom');assert.equal(el.dataset.lastCategory,'Bottom');assert(records.at(-1).spec.data.values.some(d=>d._category==='Bottom'));assert.equal(records.at(-1).spec.data.values.at(-1)._value,11);
  el._scrollTop=-30;el.emit('scroll');await wait(()=>el.dataset.firstCategory==='First');assert.equal(el.dataset.firstCategory,'First','Negative elastic overscroll must clamp to the first window');
  const observer=observers.find(o=>o.target===el);el._height=1000;observer.fn();await wait(()=>el.dataset.lastCategory==='Bottom');assert.equal(el.dataset.firstCategory,'First');assert.equal(el.dataset.lastCategory,'Bottom');assert.equal(records.at(-1).spec.data.values.length,3,'Growing viewport must show every category once they all fit');
  el._height=80;observer.fn();await wait(()=>el.dataset.lastCategory==='First');el.emit('keydown',{key:'End'});await wait(()=>el.dataset.lastCategory==='Bottom');assert.equal(el.dataset.lastCategory,'Bottom');assert(records.at(-1).spec.data.values.some(d=>d._category==='Bottom'));assert.equal(JSON.stringify(rows),source);
  R.disposeAll();assert.equal(el.listeners.size,0);assert(records.every(record=>record.finalized));
  const many=Array.from({length:10000},(_,i)=>['Category '+String(i).padStart(5,'0'),i+1]),large=make(240);await R.mount(large,'barChart',labels,many,roles);large.emit('keydown',{key:'End'});await wait(()=>large.dataset.lastCategory==='Category 09999');assert.equal(large.dataset.lastCategory,'Category 09999');assert.equal(records.at(-1).spec.data.values.at(-1)._value,10000);assert(records.at(-1).spec.data.values.length<20,'Only the current category window should be rendered');R.disposeAll();
  const seriesRows=rows.flatMap(([category,value])=>[[category,'Positive',value],[category,'Negative',-value]]),series=make(100);await R.mount(series,'stackedBarChart',['Fear','Series','Value'],seriesRows,['Category','Series','Y']);series.emit('keydown',{key:'End'});await wait(()=>series.dataset.lastCategory==='Bottom');const bottom=records.at(-1).spec.data.values.filter(value=>value._category==='Bottom');assert.equal(bottom.length,2);assert.deepEqual(bottom.map(value=>value._value),[11,-11]);assert.deepEqual(bottom.map(value=>value._dimension),['Positive','Negative']);R.disposeAll();
  let release,notify;const started=new Promise(resolve=>notify=resolve);embedGate={wait:new Promise(resolve=>release=resolve),started:notify};const retiring=make(80),pending=R.mount(retiring,'clusteredBarChart',labels,rows,roles);await started;R.disposeAll();release();await pending;await wait();assert.equal(retiring.listeners.size,0);assert(records.every(record=>record.finalized),'A pending embedded window must be retired after disposal');
  console.log('PASS short bar bottom-window reachability, integer scroll extents, negative scroll clamp, resized full domains,10k final categories, stable rows/order and pending-window cleanup');
 }finally{R.disposeAll();Object.assign(global,original)}
})().catch(error=>{console.error(error);process.exitCode=1});
