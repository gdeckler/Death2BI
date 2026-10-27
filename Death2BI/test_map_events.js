const assert=require('node:assert/strict'),R=require('./vega-renderer'),A=require('./advanced-charts');
class Node{
 constructor(tag){this.tagName=tag;this.style={};this.children=[];this.listeners=new Map();this.attrs={};this.classList={add(){}};this.isConnected=true;this.clientWidth=500;this.clientHeight=300}
 setAttribute(key,value){this.attrs[key]=value}appendChild(node){this.children.push(node);return node}replaceChildren(...nodes){this.children=nodes}
 addEventListener(key,fn){if(!this.listeners.has(key))this.listeners.set(key,new Set());this.listeners.get(key).add(fn)}
 removeEventListener(key,fn){const listeners=this.listeners.get(key);listeners?.delete(fn);if(!listeners?.size)this.listeners.delete(key)}
 emit(key,event){for(const fn of this.listeners.get(key)||[])fn(event)}remove(){}querySelector(selector){return selector==='svg'?this.svg:null}
 getBoundingClientRect(){return {left:0,top:0,width:this.clientWidth,height:this.clientHeight}}setPointerCapture(){}hasPointerCapture(){return false}releasePointerCapture(){}
}
function button(el,label){for(const child of el.children){if(child.attrs['aria-label']===label)return child;const found=button(child,label);if(found)return found}}
const event=values=>({preventDefault(){this.prevented=true},stopPropagation(){},...values});
(async()=>{
 const original=Object.fromEntries(['document','vegaEmbed','requestAnimationFrame','cancelAnimationFrame','ResizeObserver'].map(key=>[key,global[key]])),frames=new Map(),observers=[],records=[];let next=0,layoutGate=null;
 global.ResizeObserver=class{constructor(fn){this.fn=fn;observers.push(this)}observe(){}disconnect(){}};
 global.document={createElement:tag=>new Node(tag)};global.requestAnimationFrame=fn=>{frames.set(++next,fn);return next};global.cancelAnimationFrame=id=>frames.delete(id);
 async function flush(){for(const [id,fn] of frames){frames.delete(id);fn()}await Promise.resolve();for(const [id,fn] of frames){frames.delete(id);fn()}await Promise.resolve()}
 global.vegaEmbed=async(el,spec)=>{
  const signals=new Map((spec.params||[]).map(p=>[p.name,p.value])),handlers=new Map(),gate=layoutGate,runGates=gate?[gate]:[],diagnostics={writes:0,lateWrites:0,runs:0,lateRuns:0,finalized:false};layoutGate=null;let width=spec.width-10,height=spec.height-55;
  const write=()=>{diagnostics.writes++;if(diagnostics.finalized)diagnostics.lateWrites++};
  const view={signal(key,value){if(arguments.length===1)return signals.get(key);write();signals.set(key,value);return this},runAsync(){diagnostics.runs++;if(diagnostics.finalized)diagnostics.lateRuns++;const held=runGates.shift();if(held){held.started();return held.wait}return Promise.resolve()},addEventListener(key,fn){write();handlers.set(key,fn)},finalize(){diagnostics.finalized=true;handlers.clear()},width(value){if(!arguments.length)return width;write();width=value;return this},height(value){if(!arguments.length)return height;write();height=value;return this},resize(){write();return this}};
  records.push({signals,handlers,view,spec,runGates,diagnostics});return {view};
 };
 const rows=[['West',-1.54,52.44,2],['East',-.50,52.94,3],['Centre',-.93,52.65,1]],labels=['Place','Longitude','Latitude','Cases'],roles=['Details','Longitude','Latitude','Size'];
 async function mount(data=rows,key='local-event-test',onElement){const el=new Node('div');el.svg=new Node('svg');onElement?.(el);let selections=0,clears=0;await R.mount(el,'map',labels,data,roles,{mapKey:key,onSelect:()=>selections++,onClear:()=>clears++});await flush();return {el,record:records.at(-1),observer:observers.at(-1),selected:()=>selections,cleared:()=>clears}}
 try{
  const first=await mount(),{el,record}=first,initial=record.signals.get('mapZoom');assert(initial>32);const fit=A.mapFit(record.spec.data.values,record.view.width(),record.view.height());
  assert.equal(initial,fit.zoom,'Initial fit must use actual projection dimensions after legend/padding layout');assert.equal(record.signals.get('mapPanX'),fit.x);assert.equal(record.signals.get('mapPanY'),fit.y);
  button(el,'Zoom in map').onclick(event({}));await flush();assert(record.signals.get('mapZoom')>initial);const plusZoom=record.signals.get('mapZoom');
  const wheel=event({deltaY:100,deltaMode:0,clientX:100,clientY:100});el.svg.emit('wheel',wheel);await flush();assert(wheel.prevented);assert(record.signals.get('mapZoom')<plusZoom);assert(record.signals.get('mapZoom')>32);const manualZoom=record.signals.get('mapZoom');
  first.observer.fn([{contentRect:{width:500,height:240}}]);await flush();assert.equal(record.signals.get('mapZoom'),manualZoom,'Resize must preserve manual zoom');const pan=record.signals.get('mapPanX');
  el.svg.emit('pointerdown',event({button:0,isPrimary:true,pointerId:1,clientX:100,clientY:100}));el.svg.emit('pointermove',event({pointerId:1,clientX:150,clientY:120}));await flush();el.svg.emit('pointerup',event({pointerId:1}));assert(record.signals.get('mapPanX')>pan);
  record.handlers.get('click')({}, {datum:{_categoryValue:'West'},mark:{role:'mark'}});assert.equal(first.selected(),0,'Dragging must not select');
  el.svg.emit('pointerdown',event({button:0,isPrimary:true,pointerId:2,clientX:150,clientY:120}));el.svg.emit('pointerup',event({pointerId:2}));record.handlers.get('click')({}, {datum:{_categoryValue:'West'},mark:{role:'mark'}});assert.equal(first.selected(),1);assert.equal(first.cleared(),0);
  const beforeMiddle=record.signals.get('mapZoom');el.svg.emit('pointerdown',event({button:1,isPrimary:true,pointerId:3,clientX:150,clientY:120}));el.svg.emit('pointermove',event({pointerId:3,clientX:150,clientY:70}));await flush();el.svg.emit('pointerup',event({pointerId:3}));assert(record.signals.get('mapZoom')>beforeMiddle);assert(record.signals.get('mapZoom')>32);
  const cachedZoom=record.signals.get('mapZoom');R.disposeAll();assert.equal(el.svg.listeners.size,0);const restored=await mount();assert.equal(restored.record.signals.get('mapZoom'),cachedZoom,'Identical report data restores the manual viewport');
  const zoomIn=button(restored.el,'Zoom in map');for(let i=0;i<20;i++)zoomIn.onclick(event({}));await flush();assert.equal(restored.record.signals.get('mapZoom'),A.mapLimits.maxZoom);assert.equal(zoomIn.disabled,true);
  restored.el.svg.emit('wheel',event({deltaY:-500,deltaMode:0,clientX:100,clientY:100}));await flush();assert.equal(restored.record.signals.get('mapZoom'),A.mapLimits.maxZoom);
  const zoomOut=button(restored.el,'Zoom out map');for(let i=0;i<20;i++)zoomOut.onclick(event({}));await flush();assert.equal(restored.record.signals.get('mapZoom'),A.mapLimits.minZoom);assert.equal(zoomOut.disabled,true);
  button(restored.el,'Fit map to data').onclick(event({}));await flush();assert(restored.record.signals.get('mapZoom')>32);assert.equal(restored.record.signals.get('mapZoom'),A.mapFit(restored.record.spec.data.values,restored.record.view.width(),restored.record.view.height()).zoom);
  const oldFit=restored.record.signals.get('mapZoom');restored.observer.fn([{contentRect:{width:700,height:400}}]);await flush();assert.notEqual(restored.record.signals.get('mapZoom'),oldFit,'Automatic fit follows resized data viewport');
  button(restored.el,'Zoom in map').onclick(event({}));await flush();const previous=restored.record.signals.get('mapZoom');R.disposeAll();const changed=await mount([['A',-10,45,1],['B',20,60,2]]);assert.notEqual(changed.record.signals.get('mapZoom'),previous,'Changed coordinate domain invalidates manual viewport cache');
  R.disposeAll();for(const mode of ['dispose','detach']){let release,notify,target;const started=new Promise(resolve=>notify=resolve);layoutGate={wait:new Promise(resolve=>release=resolve),started:notify};const pending=mount(rows,mode+'-during-layout',el=>target=el);await started;if(mode==='dispose')R.disposeAll();else target.isConnected=false;release();const disposed=await pending;assert.equal(disposed.el.svg.listeners.size,0);assert.equal(disposed.el.listeners.size,0,'Retired map must not gain listeners after pending layout');assert.equal(disposed.record.handlers.size,0)}
  for(const mode of ['dispose','detach']){
   const current=await mount(rows,mode+'-during-resize');let release,notify;const started=new Promise(resolve=>notify=resolve);current.record.runGates.push({wait:new Promise(resolve=>release=resolve),started:notify});
   current.observer.fn([{contentRect:{width:700,height:400}}]);await started;
   if(mode==='dispose')R.disposeAll();else{current.el.isConnected=false;current.observer.fn([{contentRect:{width:700,height:400}}])}
   assert.equal(current.record.diagnostics.finalized,true);const stopped={...current.record.diagnostics};current.observer.fn([{contentRect:{width:900,height:500}}]);release();await flush();
   assert.deepEqual(current.record.diagnostics,stopped,'Pending resize must not mutate or run a finalized view');assert.equal(current.record.diagnostics.lateWrites,0);assert.equal(current.record.diagnostics.lateRuns,0);assert.equal(frames.size,0);assert.equal(current.el.svg.listeners.size,0);assert.equal(current.el.listeners.size,0);assert.equal(current.record.handlers.size,0);
  }
  console.log('PASS local map inner-viewport fitting, zoom beyond32 through controls/wheel/middle drag, finite shared limits, manual cache/resize, automatic reset/refit, drag selection and async disposal cleanup');
 }finally{R.disposeAll();Object.assign(global,original)}
})().catch(error=>{console.error(error);process.exitCode=1});
