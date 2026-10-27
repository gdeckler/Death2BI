(function(root){
'use strict';
function stable(value){
 if(Array.isArray(value))return '['+value.map(stable).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}';
 return JSON.stringify(value);
}
function aborted(){const e=new Error('Visual request cancelled.');e.name='AbortError';return e}
class QueryCache{
 constructor({maxEntries=256,maxBytes=64*1024*1024}={}){this.maxEntries=maxEntries;this.maxBytes=maxBytes;this.entries=new Map();this.pending=new Map();this.bytes=0;this.hits=0;this.misses=0;this.shared=0}
 remove(key){const e=this.entries.get(key);if(e){this.bytes-=e.bytes;this.entries.delete(key)}}
 invalidate(reportId){for(const [key,e] of this.entries)if(reportId===undefined||e.reportId===reportId)this.remove(key);for(const [key,e] of this.pending)if(reportId===undefined||e.reportId===reportId){this.pending.delete(key);e.controller.abort();for(const cancel of [...e.consumers])cancel()}}
 stats(){return {entries:this.entries.size,bytes:this.bytes,pending:this.pending.size,hits:this.hits,misses:this.misses,shared:this.shared}}
 async get(reportId,revision,request,load,signal){
  if(signal?.aborted)throw aborted();
  const key=stable([reportId,revision,request]);let entry=this.entries.get(key),promise,pendingEntry;
  if(entry){this.hits++;this.entries.delete(key);this.entries.set(key,entry);promise=Promise.resolve(entry.value)}
  else if(this.pending.has(key)){this.shared++;pendingEntry=this.pending.get(key);promise=pendingEntry.promise}
  else{
   this.misses++;entry=pendingEntry={reportId,controller:new AbortController(),consumers:new Set()};this.pending.set(key,entry);
   promise=entry.promise=Promise.resolve().then(()=>{if(entry.controller.signal.aborted)throw aborted();return load(entry.controller.signal)}).then(value=>{
    if(this.pending.get(key)!==entry||entry.controller.signal.aborted)throw aborted();
    // Result rows arrive as JSON. Sorting every result object's keys is only
    // needed for request identity, not for estimating the bounded cache size.
    const copy=structuredClone(value),bytes=(JSON.stringify(copy).length+key.length)*2;
    if(bytes<=this.maxBytes){this.entries.set(key,{reportId,value:copy,bytes});this.bytes+=bytes;while(this.bytes>this.maxBytes||this.entries.size>this.maxEntries)this.remove(this.entries.keys().next().value)}
    return copy;
   }).finally(()=>{if(this.pending.get(key)===entry)this.pending.delete(key)});
  }
  // Stop an obsolete transport as soon as nobody needs its result. A shared
  // request remains alive while any other consumer still needs the same data.
  return new Promise((resolve,reject)=>{
   let settled=false;
   const finish=(complete,value)=>{if(settled)return;settled=true;signal?.removeEventListener('abort',cancel);pendingEntry?.consumers.delete(cancel);complete(value)};
   const cancel=()=>{finish(reject,aborted());if(pendingEntry&&!pendingEntry.consumers.size&&this.pending.get(key)===pendingEntry){this.pending.delete(key);pendingEntry.controller.abort()}};
   pendingEntry?.consumers.add(cancel);signal?.addEventListener('abort',cancel,{once:true});
   if(signal?.aborted)cancel();
   promise.then(value=>{if(settled)return;if(signal?.aborted)return cancel();try{finish(resolve,structuredClone(value))}catch(error){finish(reject,error)}},error=>finish(reject,error));
  });
 }
}
const api={QueryCache,stable};if(typeof module!=='undefined')module.exports=api;root.VisualQueryCache=api;
})(typeof globalThis!=='undefined'?globalThis:this);
