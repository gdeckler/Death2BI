const assert=require('node:assert/strict'),D=require('./dax-requests'),{QueryCache}=require('./query-cache');
(async()=>{
 const calls=[],controller=new AbortController();
 const fetcher=(path,options)=>{calls.push({path,options});if(path==='/api/dax/cancel')return Promise.resolve({ok:true});return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(Error('Cancelled'),{name:'AbortError'})),{once:true}))};
 const task=D.request(fetcher,'/api/dax',{method:'POST',headers:{'X-CSRF-Token':'csrf'},body:JSON.stringify({id:'report'}),signal:controller.signal});
 const rejected=assert.rejects(task,{name:'AbortError'});controller.abort();await rejected;
 assert.equal(calls.length,2);assert.equal(calls[1].path,'/api/dax/cancel');assert.equal(calls[1].options.headers.get('X-CSRF-Token'),'csrf');
 assert.match(JSON.parse(calls[0].options.body).requestId,/^[a-f0-9]{32}$/);assert.equal(JSON.parse(calls[0].options.body).requestId,JSON.parse(calls[1].options.body).requestId);
 const done=new AbortController();let count=0;await D.request(async()=>{count++;return {}},'/api/dax',{method:'POST',body:'{}',signal:done.signal});done.abort();assert.equal(count,1);
 const cache=new QueryCache(),first=new AbortController();let finish,network=0;
 const load=signal=>D.request((path,opt)=>{network++;return new Promise(resolve=>finish=()=>resolve({rows:[[3]]}))},'/api/dax',{method:'POST',body:'{}',signal});
 const a=cache.get('r','1',{query:'same'},load,first.signal),b=cache.get('r','1',{query:'same'},load);const aborted=assert.rejects(a,{name:'AbortError'});
 await Promise.resolve();first.abort();await aborted;assert.equal(network,1);finish();assert.deepEqual((await b).rows,[[3]]);assert.equal(network,1);
 const unhandled=[],onUnhandled=error=>unhandled.push(error);process.on('unhandledRejection',onUnhandled);
 try{
  // SQL receives the same cancellable transport contract, including public
  // report authorization and CSRF headers without mutating the caller's Headers.
  const sqlCalls=[],sqlController=new AbortController(),headers=new Headers({'X-CSRF-Token':'sql-csrf','X-Public-Token':'public-secret','Content-Type':'application/json'});
  const sqlFetcher=(path,opt)=>{sqlCalls.push({path,options:opt});if(path==='/api/query/cancel')return Promise.reject(Error('Cancel endpoint unavailable'));return new Promise((resolve,reject)=>opt.signal.addEventListener('abort',()=>reject(Object.assign(Error('SQL cancelled'),{name:'AbortError'})),{once:true}))};
  const sql=D.request(sqlFetcher,'/api/query',{method:'POST',headers,credentials:'include',body:JSON.stringify({id:'public-report',sql:'SELECT 1'}),signal:sqlController.signal}),sqlRejected=assert.rejects(sql,{name:'AbortError'});
  sqlController.abort();sqlController.abort();await sqlRejected;await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sqlCalls.length,2);assert.equal(sqlCalls[1].path,'/api/query/cancel');
  const startedBody=JSON.parse(sqlCalls[0].options.body),cancelledBody=JSON.parse(sqlCalls[1].options.body);
  assert.equal(startedBody.sql,'SELECT 1');assert.equal(startedBody.id,'public-report');assert.match(startedBody.requestId,/^[a-f0-9]{32}$/);assert.deepEqual(cancelledBody,{requestId:startedBody.requestId});
  for(const name of ['X-CSRF-Token','X-Public-Token'])assert.equal(sqlCalls[1].options.headers.get(name),headers.get(name));
  assert.equal(sqlCalls[1].options.credentials,'include');assert.equal(sqlCalls[1].options.keepalive,true);assert.equal(sqlCalls[1].options.signal,undefined);assert.notEqual(sqlCalls[1].options.headers,headers);
  assert.equal(headers.get('Content-Type'),'application/json');
  // A completed SQL request removes its abort hook and keeps its normal result.
  const completeSqlCalls=[],completed=new AbortController(),result={rows:[[42]],types:['BIGINT']};
  assert.strictEqual(await D.request(async(path,opt)=>{completeSqlCalls.push({path,opt});return result},'/api/query',{method:'POST',body:'{"sql":"SELECT 42"}',signal:completed.signal}),result);
  completed.abort();await Promise.resolve();assert.equal(completeSqlCalls.length,1);
  // An already-aborted native-fetch signal must not dispatch a query or a
  // cancellation RPC. The transport observes the abort before sending anything.
  const early=new AbortController();early.abort();const earlyCalls=[];
  await assert.rejects(D.request(async(path,opt)=>{earlyCalls.push(path);assert.equal(opt.signal.aborted,true);assert.equal(JSON.parse(opt.body).requestId,undefined);throw Object.assign(Error('Aborted before dispatch'),{name:'AbortError'})},'/api/query',{method:'POST',body:'{}',signal:early.signal}),{name:'AbortError'});
  assert.deepEqual(earlyCalls,['/api/query']);
  // A synchronous exception from a cancellation transport is consumed just as
  // a rejected cancellation RPC is; it must not escape the AbortSignal event.
  const throws=new AbortController(),throwCalls=[];
  const throwing=D.request((path,opt)=>{throwCalls.push(path);if(path.endsWith('/cancel'))throw Error('synchronous cancellation failure');return new Promise((resolve,reject)=>opt.signal.addEventListener('abort',()=>reject(Object.assign(Error('Aborted'),{name:'AbortError'})),{once:true}))},'/api/query',{method:'POST',headers:{'X-Public-Token':'public'},body:'{}',signal:throws.signal});
  const throwingRejected=assert.rejects(throwing,{name:'AbortError'});throws.abort();await throwingRejected;await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(throwCalls,['/api/query','/api/query/cancel']);
  // Abandoning the last SQL cache consumer cancels the physical request, while
  // its request ID stays out of the stable cache key and stale data is not saved.
  const sqlCache=new QueryCache(),leaving=new AbortController(),lastCalls=[];
  const cachedSql=sqlCache.get('sql-report','1',{path:'/api/query',sql:'slow'},signal=>D.request((path,opt)=>{lastCalls.push({path,opt});if(path.endsWith('/cancel'))return Promise.resolve({ok:true});return new Promise((resolve,reject)=>opt.signal.addEventListener('abort',()=>reject(Object.assign(Error('Aborted'),{name:'AbortError'})),{once:true}))},'/api/query',{method:'POST',body:'{"sql":"slow"}',signal}),leaving.signal),cachedRejected=assert.rejects(cachedSql,{name:'AbortError'});
  await Promise.resolve();leaving.abort();await cachedRejected;await new Promise(resolve=>setImmediate(resolve));assert.equal(sqlCache.stats().pending,0);assert.equal(sqlCache.stats().entries,0);assert.deepEqual(lastCalls.map(call=>call.path),['/api/query','/api/query/cancel']);
  // Unrelated API calls retain their original transport/body contract.
  const plain={method:'GET',headers:{'X-Public-Token':'public'}},passThrough=[];
  await D.request(async(path,opt)=>{passThrough.push({path,opt});return {}},'/api/models',plain);assert.strictEqual(passThrough[0].opt,plain);
  await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(unhandled,[]);
 }finally{process.off('unhandledRejection',onUnhandled)}
 console.log('PASS DAX/SQL cancellation IDs, CSRF/public headers, early/completed abort, normal SQL, shared/last cache consumers, failed cancel transports and no unhandled races');
})().catch(e=>{console.error(e);process.exitCode=1});
