(function(root){
const sessions=new Set(),packages=new Map();let library=[];
let storageKey='death2powerbi.customVisualSettings.signedout';
function setAccount(id,inheritLegacy=false){disposeAll();packages.clear();library=[];storageKey='death2powerbi.customVisualSettings.'+(id||'signedout');if(inheritLegacy){try{if(localStorage.getItem(storageKey)===null){const old=localStorage.getItem('death2powerbi.customVisualSettings');if(old!==null)localStorage.setItem(storageKey,old)}}catch{}}}
function settings(){try{return JSON.parse(localStorage.getItem(storageKey)||'{}')}catch{return {}}}
function saveSettings(value){try{localStorage.setItem(storageKey,JSON.stringify(value))}catch{}}
async function load(api){const [custom,builtins]=await Promise.all([api('/api/custom-visuals'),api('/api/builtin-visuals')]);library=[...builtins,...custom.filter(p=>!builtins.some(b=>b.id===p.id))];return library}
function resolve(type,model){if(type==='kpi')return library.find(p=>p.builtin&&p.guid===root.NativeKPI?.guid);const embedded=model?.customVisuals?.find(p=>p.guid===type);return library.find(p=>p.id===embedded?.id)||library.find(p=>p.guid===type)}
async function get(id,api){if(!packages.has(id))packages.set(id,await api('/api/custom-visuals/'+id));return packages.get(id)}
function options(id){return settings()['package:'+id]||{network:false}}
function configure(id,value){const all=settings();all['package:'+id]={...options(id),...value};saveSettings(all)}
function disposeAll(){for(const session of [...sessions])session.dispose()}
async function mount(container,pkgMeta,visual,result,compiled,{api,model,page,onSelection,onRefresh,selectedRows=[]}={}){
 const pkg=await get(pkgMeta.id,api);if(!container.isConnected)return;
 const key='visual:'+model.id+':'+visual.id+':'+pkg.id,all=settings(),overrides=all[key]||{};
 const view=CustomDataView.build(pkg,visual,result,compiled,overrides);
 const frame=document.createElement('iframe');frame.title=pkg.name+' custom visual';frame.setAttribute('sandbox','allow-scripts');frame.referrerPolicy='no-referrer';frame.style.cssText='width:100%;height:100%;border:0;min-height:100px;display:block;background:white';
 const token=crypto.randomUUID(),note=document.createElement('div');note.style.cssText='font-size:11px;padding:3px;color:#806b36;flex:none';
 container.replaceChildren(frame,note);container.style.cssText+=';display:flex;flex-direction:column;min-height:0';frame.style.flex='1';
 let disposed=false,finished=false,resolveReady,rejectReady;
 const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject});
 const timer=setTimeout(()=>{if(!finished){note.textContent='The custom visual did not complete startup within 10 seconds.';rejectReady(Error(note.textContent))}},10000);
 function message(event){
  const data=event.data;if(disposed||event.source!==frame.contentWindow||!data?.death2custom||data.token!==token)return;
  if(data.type==='ready')frame.contentWindow.postMessage({token,type:'data',view,selectedRows},'*');
  if(data.type==='finished'){finished=true;clearTimeout(timer);resolveReady({frame})}
  if(data.type==='error'){note.textContent='Custom visual error: '+String(data.message||'Unknown error').slice(0,2000);note.style.color='#a03c30';finished=true;clearTimeout(timer);rejectReady(Error(note.textContent))}
  if(data.type==='warning')note.textContent=String(data.message||'').slice(0,2000);
  if(data.type==='refresh')onRefresh?.();
  if(data.type==='selection'){
   if(!Array.isArray(data.rows)||data.rows.length>result.rows.length||data.rows.some(i=>!Number.isInteger(i)||i<0||i>=result.rows.length))return;
   onSelection?.([...new Set(data.rows)]);
  }
  if(data.type==='persist'){
   if(!data.changes||JSON.stringify(data.changes).length>64000)return;
   if(data.changes.merge&&!Array.isArray(data.changes.merge)||data.changes.remove&&!Array.isArray(data.changes.remove))return;
   const stored=settings(),current=stored[key]||{};
   for(const item of data.changes.merge||[]){
    if(item.selector||!Object.hasOwn(pkg.capabilities.objects||{},item.objectName))continue;
    const allowed=pkg.capabilities.objects[item.objectName].properties||{};
    const properties=Object.fromEntries(Object.entries(item.properties||{}).filter(([name])=>Object.hasOwn(allowed,name)));
    current[item.objectName]={...(current[item.objectName]||{}),...properties};
   }
   for(const item of data.changes.remove||[])if(!item.selector&&Object.hasOwn(pkg.capabilities.objects||{},item.objectName))delete current[item.objectName];
   stored[key]=current;saveSettings(stored);
  }
 }
 const session={dispose(){if(disposed)return;disposed=true;clearTimeout(timer);frame.contentWindow?.postMessage({token,type:'destroy'},'*');removeEventListener('message',message);frame.remove();sessions.delete(session);resolveReady({disposed:true})}};
 sessions.add(session);addEventListener('message',message);
 frame.srcdoc=CustomFrame.documentFor(pkg,token,!!options(pkg.id).network);
 if(result.truncated)note.textContent='Preview limited to 1,000 query rows.';
 try{return await ready}catch(error){session.dispose();throw error}
}
const api={load,resolve,get,options,configure,disposeAll,mount,setAccount,list:()=>library};if(typeof module!=='undefined')module.exports=api;root.CustomVisuals=api;
})(globalThis);
