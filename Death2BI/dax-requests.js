(function(root){
'use strict';
async function request(fetcher,path,options={}){
 if(!['/api/dax','/api/query'].includes(path)||options.method!=='POST'||options.signal?.aborted)return fetcher(path,options);
 // Attach after the query-cache key is calculated, so identical requests still share work.
 const requestId=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join(''),body=JSON.stringify({...JSON.parse(options.body),requestId});
 const cancel=()=>{const headers=new Headers(options.headers||{});headers.set('Content-Type','application/json');Promise.resolve().then(()=>fetcher(path+'/cancel',{method:'POST',headers,credentials:options.credentials||'same-origin',keepalive:true,body:JSON.stringify({requestId})})).catch(()=>{})};
 options.signal?.addEventListener('abort',cancel,{once:true});
 try{return await fetcher(path,{...options,body})}
 finally{options.signal?.removeEventListener('abort',cancel)}
}
const api={request};if(typeof module!=='undefined')module.exports=api;root.DaxRequests=api;
})(typeof globalThis!=='undefined'?globalThis:this);
