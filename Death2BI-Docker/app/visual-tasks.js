/* Bounded, cooperative work for the current report view. */
(function(root){
'use strict';
function aborted(){const error=Error('Visual loading cancelled.');error.name='AbortError';return error}
function check(signal){if(signal?.aborted)throw aborted()}
function yieldToUI(signal){
 check(signal);
 return new Promise((resolve,reject)=>{
  const cancel=()=>{clearTimeout(timer);reject(aborted())},timer=setTimeout(()=>{signal?.removeEventListener('abort',cancel);signal?.aborted?reject(aborted()):resolve()},0);
  signal?.addEventListener('abort',cancel,{once:true});
 });
}
class TaskQueue{
 constructor({concurrency=3}={}){this.concurrency=Math.max(1,Math.floor(concurrency)||3);this.active=0;this.waiting=[]}
 run(work,signal){
  if(signal?.aborted)return Promise.reject(aborted());
  return new Promise((resolve,reject)=>{
   const entry={work,signal,resolve,reject,started:false,done:false};
   entry.cancel=()=>this.finish(entry,aborted(),undefined,true);signal?.addEventListener('abort',entry.cancel,{once:true});this.waiting.push(entry);this.drain();
  });
 }
 finish(entry,error,value,failed=false){
  if(entry.done)return;entry.done=true;entry.signal?.removeEventListener('abort',entry.cancel);
  if(entry.started)this.active--;else{const index=this.waiting.indexOf(entry);if(index>=0)this.waiting.splice(index,1)}
  failed?entry.reject(error):entry.resolve(value);this.drain();
 }
 drain(){
  while(this.active<this.concurrency&&this.waiting.length){
   const entry=this.waiting.shift();if(entry.done)continue;entry.started=true;this.active++;
   // A browser task boundary lets navigation/input/paint run before another visual.
   (async()=>{await yieldToUI(entry.signal);check(entry.signal);return entry.work()})().then(value=>this.finish(entry,null,value),error=>this.finish(entry,error,undefined,true));
  }
 }
 stats(){return {active:this.active,queued:this.waiting.length,concurrency:this.concurrency}}
}
const api={TaskQueue,yieldToUI,check,aborted};if(typeof module!=='undefined')module.exports=api;root.VisualTasks=api;
})(typeof globalThis!=='undefined'?globalThis:this);
