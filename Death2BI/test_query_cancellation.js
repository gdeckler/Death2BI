const assert=require('node:assert/strict');
const {QueryCache}=require('./query-cache');
const turn=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}}
function watchedController(){const controller=new AbortController(),signal=controller.signal,listeners=new Set(),add=signal.addEventListener.bind(signal),remove=signal.removeEventListener.bind(signal);signal.addEventListener=(type,listener,options)=>{if(type==='abort')listeners.add(listener);return add(type,listener,options)};signal.removeEventListener=(type,listener,options)=>{if(type==='abort')listeners.delete(listener);return remove(type,listener,options)};return {controller,signal,listeners}}
async function main(){
 const unhandled=[],onUnhandled=error=>unhandled.push(error);process.on('unhandledRejection',onUnhandled);
 try{
  // Cancelling before the loader is dispatched must not send an HTTP request.
  {
   const cache=new QueryCache(),consumer=watchedController();let calls=0;
   const pending=cache.get('r','1',{sql:'obsolete'},()=>{calls++;return {rows:[[1]]}},consumer.signal),rejected=assert.rejects(pending,{name:'AbortError'});
   consumer.controller.abort();assert.equal(cache.stats().pending,0);await rejected;await turn();assert.equal(calls,0);assert.equal(consumer.listeners.size,0);
  }
  // A page can leave without cancelling a request still used by a live page.
  {
   const cache=new QueryCache(),first=watchedController(),second=watchedController(),response=deferred();let transport,calls=0;
   const load=signal=>{calls++;transport=signal;return response.promise};
   const a=cache.get('r','1',{sql:'shared'},load,first.signal),aRejected=assert.rejects(a,{name:'AbortError'});
   const b=cache.get('r','1',{sql:'shared'},load,second.signal);await turn();
   first.controller.abort();await aRejected;assert.equal(transport.aborted,false);assert.equal(cache.stats().pending,1);
   response.resolve({rows:[[7]]});const answer=await b;answer.rows[0][0]=99;
   assert.equal((await cache.get('r','1',{sql:'shared'},()=>assert.fail('Completed shared result should be cached'))).rows[0][0],7);
   assert.equal(calls,1);assert.equal(first.listeners.size,0);assert.equal(second.listeners.size,0);
  }
  // Last-consumer cancellation aborts immediately even if a server ignores it.
  // A replacement with the same key can start before that stale server replies.
  {
   const cache=new QueryCache(),first=watchedController(),second=watchedController(),stale=deferred(),replacement=deferred();let oldTransport,newTransport,oldCalls=0,newCalls=0;
   const oldLoad=signal=>{oldTransport=signal;oldCalls++;return stale.promise};
   const a=cache.get('r','1',{sql:'same'},oldLoad,first.signal),aRejected=assert.rejects(a,{name:'AbortError'});
   const b=cache.get('r','1',{sql:'same'},oldLoad,second.signal),bRejected=assert.rejects(b,{name:'AbortError'});await turn();
   first.controller.abort();assert.equal(oldTransport.aborted,false);
   second.controller.abort();assert.equal(oldTransport.aborted,true);assert.equal(cache.stats().pending,0);await Promise.all([aRejected,bRejected]);
   const fresh=cache.get('r','1',{sql:'same'},signal=>{newTransport=signal;newCalls++;return replacement.promise});await turn();
   stale.resolve({rows:[['stale']]});await turn();assert.equal(cache.stats().pending,1);assert.equal(cache.stats().entries,0);assert.equal(newTransport.aborted,false);
   replacement.resolve({rows:[['fresh']]});assert.deepEqual(await fresh,{rows:[['fresh']]});
   assert.deepEqual(await cache.get('r','1',{sql:'same'},()=>assert.fail('Stale reply must not overwrite replacement cache')),{rows:[['fresh']]});
   assert.equal(oldCalls,1);assert.equal(newCalls,1);assert.equal(first.listeners.size,0);assert.equal(second.listeners.size,0);
  }
  // Explicit invalidation rejects all matching consumers without waiting for
  // a transport to settle, while an unrelated report keeps running.
  {
   const cache=new QueryCache(),aController=watchedController(),bController=watchedController(),abandoned=deferred(),other=deferred();let abandonedSignal,otherSignal;
   const a=cache.get('a','1',{sql:'slow'},signal=>{abandonedSignal=signal;return abandoned.promise},aController.signal),aRejected=assert.rejects(a,{name:'AbortError'});
   const a2=cache.get('a','1',{sql:'slow'},()=>assert.fail('Should share matching request')),a2Rejected=assert.rejects(a2,{name:'AbortError'});
   const b=cache.get('b','1',{sql:'slow'},signal=>{otherSignal=signal;return other.promise},bController.signal);await turn();
   cache.invalidate('a');assert.equal(abandonedSignal.aborted,true);assert.equal(otherSignal.aborted,false);assert.equal(cache.stats().pending,1);
   await Promise.all([aRejected,a2Rejected]);assert.equal(aController.listeners.size,0);
   other.resolve({rows:[['other']]});assert.deepEqual(await b,{rows:[['other']]});assert.equal(bController.listeners.size,0);
   abandoned.resolve({rows:[['abandoned']]});await turn();assert.equal(cache.stats().entries,1);
   assert.deepEqual(await cache.get('b','1',{sql:'slow'},()=>assert.fail('Other report cache should remain')),{rows:[['other']]});
  }
  // Cached copies retain the cancellation contract and never abort or remove
  // the completed cache entry merely because a new consumer leaves.
  {
   const cache=new QueryCache();await cache.get('r','1',{},()=>({rows:[[42]]}));const consumer=watchedController();
   const hit=cache.get('r','1',{},()=>assert.fail('Cache hit cannot load'),consumer.signal),rejected=assert.rejects(hit,{name:'AbortError'});
   consumer.controller.abort();await rejected;assert.equal(cache.stats().entries,1);assert.equal(consumer.listeners.size,0);
   assert.deepEqual(await cache.get('r','1',{},()=>assert.fail('Completed cache survives cancellation')),{rows:[[42]]});
  }
  // Cancellation is also safe with several subscriptions to the same signal,
  // and an abort-driven transport rejection cannot become unhandled.
  {
   const cache=new QueryCache(),consumer=watchedController();let signal,abortEvents=0;
   const load=transport=>{signal=transport;return new Promise((resolve,reject)=>transport.addEventListener('abort',()=>{abortEvents++;const error=new Error('transport stopped');error.name='AbortError';reject(error)},{once:true}))};
   const a=cache.get('r','1',{},load,consumer.signal),b=cache.get('r','1',{},load,consumer.signal),ra=assert.rejects(a,{name:'AbortError'}),rb=assert.rejects(b,{name:'AbortError'});await turn();
   consumer.controller.abort();assert.equal(signal.aborted,true);await Promise.all([ra,rb]);await turn();assert.equal(abortEvents,1);assert.equal(cache.stats().pending,0);assert.equal(cache.stats().entries,0);assert.equal(consumer.listeners.size,0);
  }
  await turn();assert.deepEqual(unhandled,[]);
  console.log('PASS query cancellation: undispatched and obsolete transports stop; shared consumers, replacement races, report invalidation, copies, listeners and late replies remain correct.');
 }finally{process.off('unhandledRejection',onUnhandled)}
}
main().catch(error=>{console.error(error);process.exitCode=1});
