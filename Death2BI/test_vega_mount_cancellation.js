const assert=require('node:assert/strict'),R=require('./vega-renderer');

class Element{
 constructor(tag='div'){this.tagName=tag;this.style={cssText:''};this.attrs={};this.dataset={};this.children=[];this.listeners=new Map();this.connected=true;this.clientWidth=500;this.clientHeight=300;this.scrollTop=0;this.classList={add(){}}}
 get isConnected(){return this.connected&&(!this.parent||this.parent.isConnected)}
 setAttribute(key,value){this.attrs[key]=value}
 appendChild(node){node.parent=this;this.children.push(node);return node}
 append(...nodes){nodes.forEach(node=>this.appendChild(node))}
 replaceChildren(...nodes){this.children.forEach(node=>node.parent=null);this.children=[];this.append(...nodes)}
 addEventListener(key,fn){if(!this.listeners.has(key))this.listeners.set(key,new Set());this.listeners.get(key).add(fn)}
 removeEventListener(key,fn){const set=this.listeners.get(key);set?.delete(fn);if(!set?.size)this.listeners.delete(key)}
 emit(key,event={}){for(const fn of this.listeners.get(key)||[])fn(event)}
 querySelector(){return null}querySelectorAll(){return []}
}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const original=Object.fromEntries(['document','scheduler','vegaEmbed','ResizeObserver'].map(key=>[key,global[key]]));
const records=[],observers=[],yields=[];let holdYields=false,autoEmbed=false,onEmbed;
global.document={createElement:tag=>new Element(tag)};
global.scheduler={yield(){if(!holdYields)return tick();const gate=deferred();yields.push(gate);return gate.promise}};
global.ResizeObserver=class{constructor(fn){this.fn=fn;this.disconnected=0;observers.push(this)}observe(element){this.element=element}disconnect(){this.disconnected++}};
global.vegaEmbed=(element,spec)=>{
 const gate=deferred(),record={element,spec,gate,finalized:0,writes:0,handlers:new Map()};
 const view={addEventListener(key,fn){record.writes++;record.handlers.set(key,fn)},finalize(){record.finalized++;record.handlers.clear()},width(){return view},height(){return view},resize(){return view},runAsync(){record.writes++;return Promise.resolve()}};
 record.view=view;records.push(record);onEmbed?.(record);if(autoEmbed)gate.resolve({view});return gate.promise;
};
const labels=['Category','Value'],rows=[['A',1],['B',2]],roles=['Category','Y'];
const options=extra=>({onHover(){},onLeave(){},onSelect(){},...extra});
const mount=(host=new Element(),extra={})=>R.mount(host,'clusteredColumnChart',labels,rows,roles,options(extra));
async function until(test,message){for(let n=0;n<200&&!test();n++)await tick();assert(test(),message)}
async function releaseYield(){assert(yields.length,'Expected cooperative task yield');yields.shift().resolve();await tick()}
function settle(record){record.gate.resolve({view:record.view})}
async function finishYields(){holdYields=false;while(yields.length){yields.shift().resolve();await tick()}}
function reset(){R.disposeAll();assert.equal(yields.length,0,'Previous task gates must be drained');records.length=0;observers.length=0;onEmbed=undefined;autoEmbed=false;holdYields=false}

(async()=>{
 try{
  // A pre-aborted mount cannot overwrite a still-visible, installed chart.
  autoEmbed=true;const host=new Element(),live=await mount(host),before=host.children[0],aborted=new AbortController();aborted.abort();
  assert.equal(await mount(host,{signal:aborted.signal}),undefined);assert.equal(host.children[0],before);assert.equal(records.length,1);assert.equal(records[0].finalized,0);assert.equal(live,records[0].view);reset();

  // The first browser task boundary happens before walking the input or
  // replacing its host. Navigation/filter input can cancel planning entirely.
  holdYields=true;let scanned=0;const protectedRows=new Proxy(rows,{get(target,key,receiver){if(key==='map'||key===Symbol.iterator)scanned++;return Reflect.get(target,key,receiver)}}),early=new AbortController(),earlyHost=new Element(),sentinel=new Element();earlyHost.append(sentinel);
  const earlyMount=R.mount(earlyHost,'lineChart',labels,protectedRows,roles,{signal:early.signal});
  assert.equal(scanned,0);assert.equal(records.length,0);assert.equal(earlyHost.children[0],sentinel);
  let inputHandled=false;await tick();inputHandled=true;early.abort();await releaseYield();assert.equal(await earlyMount,undefined);assert(inputHandled);assert.equal(scanned,0);assert.equal(records.length,0);assert.equal(earlyHost.children[0],sentinel);await finishYields();reset();

  // Each embed result is owned by the host/generation that launched it.
  for(const reason of ['abort','dispose','detach']){
   const controller=new AbortController(),target=new Element(),pending=mount(target,{signal:controller.signal});await until(()=>records.length===1,'Embed did not start');
   if(reason==='abort')controller.abort();else if(reason==='dispose')R.disposeAll();else target.connected=false;
   settle(records[0]);assert.equal(await pending,undefined,reason+' must return no stale view');assert.equal(records[0].finalized,1);assert.equal(records[0].writes,0,'No handlers may install on a retired embed');assert.equal(observers.length,0);assert.equal(target.listeners.size,0);R.disposeAll();controller.abort();assert.equal(records[0].finalized,1,'Retirement is idempotent');reset();
  }

  const reused=new Element(),older=mount(reused);await until(()=>records.length===1,'Old embed did not start');const newer=mount(reused);await until(()=>records.length===2,'New embed did not start');settle(records[1]);assert.equal(await newer,records[1].view);const currentSurface=reused.children[0];settle(records[0]);assert.equal(await older,undefined);assert.equal(records[0].finalized,1);assert.equal(records[0].writes,0);assert.equal(records[1].finalized,0);assert.equal(reused.children[0],currentSurface);assert.equal(observers.length,1);assert(reused.listeners.size>0);reset();

  // Abort remains effective after a successful installation: event handlers
  // and resize observers must disappear, and queued callbacks cannot write.
  autoEmbed=true;const installedController=new AbortController(),installedHost=new Element();await mount(installedHost,{signal:installedController.signal});const installed=records[0],observer=observers[0];assert(installedHost.listeners.size>0);assert(installed.handlers.size>0);
  installedController.abort();const writes=installed.writes;assert.equal(installed.finalized,1);assert.equal(observer.disconnected,1);assert.equal(installedHost.listeners.size,0);assert.equal(installed.handlers.size,0);observer.fn([{contentRect:{width:900,height:500}}]);await tick();assert.equal(installed.writes,writes);R.disposeAll();assert.equal(installed.finalized,1);reset();

  // Detachment discovered by ResizeObserver uses the same complete cleanup.
  autoEmbed=true;const detachedHost=new Element();await mount(detachedHost);detachedHost.connected=false;observers[0].fn([{contentRect:{width:800,height:500}}]);assert.equal(records[0].finalized,1);assert.equal(observers[0].disconnected,1);assert.equal(detachedHost.listeners.size,0);R.disposeAll();assert.equal(records[0].finalized,1);reset();

  // Both planning and compilation are separated by browser tasks. An abort
  // after host planning but before embed prevents expensive compilation.
  holdYields=true;const beforeCompile=new AbortController(),compileHost=new Element(),compilePending=mount(compileHost,{signal:beforeCompile.signal});
  await releaseYield();assert.equal(compileHost.children.length,1);assert.equal(records.length,0);await releaseYield();assert.equal(records.length,0);beforeCompile.abort();await releaseYield();assert.equal(await compilePending,undefined);assert.equal(records.length,0);await finishYields();reset();

  // Small multiples yield between children; cancellation stops later child
  // launches and links already-started child embeds to the parent signal.
  const facets=Array.from({length:30},(_,i)=>['A','Panel '+i,i]),facetSnapshot=JSON.stringify(facets),faceted=new Element(),facetController=new AbortController();let countAtAbort;
  onEmbed=()=>{countAtAbort=faceted.children[0].children.length;facetController.abort()};
  const multiple=R.mount(faceted,'clusteredColumnChart',['Category','Panel','Value'],facets,['Category','SmallMultiples','Y'],options({signal:facetController.signal}));
  await until(()=>records.length>0,'First small-multiple embed did not start');assert(countAtAbort<30,'All children launched in a single blocking burst');onEmbed=undefined;records.forEach(settle);assert.equal(await multiple,undefined);assert(records.length<30);assert(records.every(record=>record.finalized===1));assert.equal(observers.length,0);assert.equal(JSON.stringify(facets),facetSnapshot);reset();

  // Active failures remain visible to the caller. Cancelled failures are
  // obsolete and cannot replace the current page with a render error.
  const activeFailure=mount(new Element());await until(()=>records.length===1,'Failure embed did not start');records[0].gate.reject(Error('active compiler failure'));await assert.rejects(activeFailure,/active compiler failure/);reset();
  const failureController=new AbortController(),staleFailure=mount(new Element(),{signal:failureController.signal});await until(()=>records.length===1,'Cancelled failure embed did not start');failureController.abort();records[0].gate.reject(Error('obsolete compiler failure'));assert.equal(await staleFailure,undefined);reset();

  // If a child fails before all later children have launched, the rejection
  // is already observed, but the active error still reaches its parent.
  autoEmbed=true;let failed=false;onEmbed=record=>{if(!failed){failed=true;record.gate.reject(Error('active facet failure'))}};
  await assert.rejects(R.mount(new Element(),'clusteredColumnChart',['Category','Panel','Value'],facets.slice(0,4),['Category','SmallMultiples','Y'],{}),/active facet failure/);assert(records.every(record=>record.finalized<=1));reset();

  console.log('PASS cooperative browser yields, abort before planning/embed, pending embed abort/dispose/detach/remount, installed cleanup and small-multiple cancellation/error ownership');
 }finally{await finishYields();R.disposeAll();Object.assign(global,original)}
})().catch(error=>{console.error(error);process.exitCode=1});
