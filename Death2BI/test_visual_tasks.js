const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}}
async function flush(){for(let i=0;i<10;i++)await Promise.resolve()}
function harness(){const timers=new Map(),module={exports:{}};let serial=0;vm.runInNewContext(fs.readFileSync(require.resolve('./visual-tasks'),'utf8'),{module,setTimeout:fn=>{const id=++serial;timers.set(id,fn);return id},clearTimeout:id=>timers.delete(id)});return {api:module.exports,timers,async tick(){const batch=[...timers.values()];timers.clear();for(const fn of batch)fn();await flush()}}}
(async()=>{
 const unhandled=[],onUnhandled=error=>unhandled.push(error);process.on('unhandledRejection',onUnhandled);
 try{
  {
   const h=harness(),queue=new h.api.TaskQueue({concurrency:2}),first=deferred(),second=deferred(),started=[];
   const work=[first.promise,second.promise,'third','fourth'],tasks=work.map((value,index)=>queue.run(()=>{started.push(index);return value}));
   assert.equal(queue.stats().active,2);assert.equal(queue.stats().queued,2);assert.deepEqual(started,[]);
   await flush();assert.deepEqual(started,[],'A promise-only yield cannot let browser input run');
   await h.tick();assert.deepEqual(started,[0,1]);second.resolve('second');await flush();
   assert.equal(queue.stats().active,2);assert.equal(queue.stats().queued,1);assert.deepEqual(started,[0,1]);
   await h.tick();assert.deepEqual(started,[0,1,2]);await h.tick();assert.deepEqual(started,[0,1,2,3]);
   first.resolve('first');assert.deepEqual(await Promise.all(tasks),['first','second','third','fourth']);assert.equal(queue.stats().active,0);assert.equal(queue.stats().queued,0);
  }
  {
   const h=harness(),queue=new h.api.TaskQueue({concurrency:1}),old=new AbortController(),slow=deferred(),started=[];
   const active=queue.run(()=>{started.push('old active');return slow.promise},old.signal),activeRejected=assert.rejects(active,{name:'AbortError'});
   const queued=queue.run(()=>assert.fail('An obsolete queued visual must never start'),old.signal),queuedRejected=assert.rejects(queued,{name:'AbortError'});
   await h.tick();assert.deepEqual(started,['old active']);old.abort();await Promise.all([activeRejected,queuedRejected]);await flush();
   const replacement=queue.run(()=>{started.push('replacement');return 'fresh'});await h.tick();assert.equal(await replacement,'fresh');
   slow.resolve('late old result');await flush();assert.deepEqual(started,['old active','replacement']);assert.equal(queue.stats().active,0);assert.equal(queue.stats().queued,0);
  }
  {
   const h=harness(),queue=new h.api.TaskQueue({concurrency:1}),controller=new AbortController();
   const pending=queue.run(()=>assert.fail('Cancelled pre-paint work ran'),controller.signal),rejected=assert.rejects(pending,{name:'AbortError'});
   controller.abort();await rejected;await flush();assert.equal(h.timers.size,0);assert.equal(queue.stats().active,0);
   await assert.rejects(queue.run(()=>assert.fail('Pre-aborted signal dispatched'),controller.signal),{name:'AbortError'});
   assert.throws(()=>h.api.check(controller.signal),{name:'AbortError'});
   assert.throws(()=>h.api.yieldToUI(controller.signal),{name:'AbortError'});
  }
  {
   const h=harness(),queue=new h.api.TaskQueue({concurrency:2}),reasons=[0,false,null,undefined,'plain failure',Error('failure')],caught=[];
   const tasks=reasons.map((reason,index)=>queue.run(()=>{throw reason}).then(()=>assert.fail('A thrown value was resolved as success'),error=>{assert.strictEqual(error,reason);caught.push(index)}));
   while(h.timers.size){await h.tick()}await Promise.all(tasks);assert.equal(caught.length,reasons.length);assert.equal(queue.stats().active,0);
  }
  {
   const h=harness(),controller=new AbortController(),pending=h.api.yieldToUI(controller.signal),rejected=assert.rejects(pending,{name:'AbortError'});
   assert.equal(h.timers.size,1);controller.abort();await rejected;assert.equal(h.timers.size,0);
  }
  await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(unhandled,[]);
  console.log('PASS visual tasks: real task-boundary yields, bounded dispatch, ordered results, obsolete queue cancellation, replacement priority, falsy failures and no late/unhandled completions.');
 }finally{process.off('unhandledRejection',onUnhandled)}
})().catch(error=>{console.error(error);process.exitCode=1});
