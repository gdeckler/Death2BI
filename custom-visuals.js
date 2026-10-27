(function(root){
const sessions=new Set(),packages=new Map();let externalImages=false;let library=[];
let storageKey='death2powerbi.customVisualSettings.signedout';
function setAccount(id,inheritLegacy=false){disposeAll();packages.clear();library=[];storageKey='death2powerbi.customVisualSettings.'+(id||'signedout');if(inheritLegacy){try{if(localStorage.getItem(storageKey)===null){const old=localStorage.getItem('death2powerbi.customVisualSettings');if(old!==null)localStorage.setItem(storageKey,old)}}catch{}}}
function settings(){try{return JSON.parse(localStorage.getItem(storageKey)||'{}')}catch{return {}}}
function saveSettings(value){try{localStorage.setItem(storageKey,JSON.stringify(value))}catch{}}
async function load(api){externalImages=(await api('/api/branding')).allowExternalImages===true;const [custom,builtins]=await Promise.all([api('/api/custom-visuals'),api('/api/builtin-visuals')]);library=[...builtins,...custom.filter(p=>!builtins.some(b=>b.id===p.id))];return library}
function resolve(type,model){if(isHtmlContent(type))return {id:'native-html-content',guid:type,name:'HTML Content',nativeHtml:true};if(type==='kpi')return library.find(p=>p.builtin&&p.guid===root.NativeKPI?.guid);const embedded=model?.customVisuals?.find(p=>p.guid===type);return library.find(p=>p.id===embedded?.id)||embedded||library.find(p=>p.guid===type)}
function isFilterVisual(type,model){const pkg=model?.customVisuals?.find(p=>p.guid===type)||library.find(p=>p.guid===type);return !!pkg&&Object.values(pkg.capabilities?.objects||{}).some(object=>Object.values(object.properties||{}).some(property=>property?.type?.filter===true))}
async function get(id,api){if(!packages.has(id))packages.set(id,await api('/api/custom-visuals/'+id));return packages.get(id)}
function options(id){return settings()['package:'+id]||{network:false}}
function configure(id,value){const all=settings();all['package:'+id]={...options(id),...value};saveSettings(all)}
function disposeAll(){for(const session of [...sessions])session.dispose()}
async function mount(container,pkgMeta,visual,result,compiled,{api,model,page,onSelection,onRefresh,onHover,onLeave,onFilters,filters,selectedRows=[],tooltip}={}){
 if(tooltip===false){onHover=undefined;onLeave=undefined}
 if(pkgMeta.nativeHtml)return mountHtml(container,visual,result,compiled,{model,onHover,onLeave,tooltip});
 const pkg=await get(pkgMeta.id,api);if(!container.isConnected)return;
 const key='visual:'+model.id+':'+visual.id+':'+pkg.id,all=settings(),overrides=all[key]||{};
 const styled=root.ReportStyle?{...visual,definition:{...visual.definition,objects:root.ReportStyle.resolveTheme(root.ReportStyle.objects(model,visual),model.theme||{})}}:visual;
 const view=CustomDataView.build(pkg,styled,result,compiled,overrides);
 const filterProperties=CustomDataView.filterProperties(pkg),slots=new Map(),firstFilter=filterProperties[0];let currentFilters=filterProperties.length?CustomDataView.jsonFilters(visual,filters??(visual.definition?.objects?.general||[]).map(o=>o.properties?.filter).filter(Boolean)):[];
 if(firstFilter)slots.set(firstFilter.objectName+':'+firstFilter.propertyName,currentFilters);
 const frame=document.createElement('iframe');frame.title=pkg.name+' custom visual';frame.setAttribute('sandbox','allow-scripts');frame.referrerPolicy='no-referrer';frame.style.cssText='width:100%;height:100%;border:0;min-height:0;display:block;background:transparent';
 const token=crypto.randomUUID(),note=document.createElement('div');note.style.cssText='font-size:11px;padding:3px;color:#806b36;flex:none';
 container.replaceChildren(frame,note);container.style.cssText+=';display:flex;flex-direction:column;min-height:0';frame.style.flex='1';
 let disposed=false,finished=false,resolveReady,rejectReady;const snapshots=new Map();
 const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject});
 const timer=setTimeout(()=>{if(!finished){note.textContent='The custom visual did not complete startup within 10 seconds.';rejectReady(Error(note.textContent))}},10000);
 function message(event){
  const data=event.data;if(disposed||event.source!==frame.contentWindow||!data?.death2custom||data.token!==token)return;
  if(data.type==='snapshot'){const pending=snapshots.get(data.requestId);if(pending){clearTimeout(pending.timer);snapshots.delete(data.requestId);data.error?pending.reject(Error(data.error)):pending.resolve({html:data.html,warnings:data.warnings})}return}
  if(data.type==='ready')frame.contentWindow.postMessage({token,type:'data',view,selectedRows,filters:currentFilters},'*');
  if(data.type==='finished'){finished=true;clearTimeout(timer);resolveReady({frame})}
  if(data.type==='error'){note.textContent='Custom visual error: '+String(data.message||'Unknown error').slice(0,2000);note.style.color='#a03c30';finished=true;clearTimeout(timer);rejectReady(Error(note.textContent))}
  if(data.type==='warning')note.textContent=String(data.message||'').slice(0,2000);
  if(data.type==='refresh')onRefresh?.();
  if(data.type==='tooltipLeave')onLeave?.();
  if(data.type==='tooltip'&&onHover){const rowIndex=data.rows?.find(i=>Number.isInteger(i)&&i>=0&&i<result.rows.length);if(rowIndex!==undefined){const rect=frame.getBoundingClientRect();onHover(result.rows[rowIndex],{clientX:rect.left+(Number(data.coordinates?.[0])||0)*rect.width/Math.max(1,frame.clientWidth),clientY:rect.top+(Number(data.coordinates?.[1])||0)*rect.height/Math.max(1,frame.clientHeight)},[...new Set(data.rows.filter(i=>Number.isInteger(i)&&i>=0&&i<result.rows.length))].map(i=>result.rows[i]))}}
  if(data.type==='selection'){
   if(!Array.isArray(data.rows)||data.rows.length>result.rows.length||data.rows.some(i=>!Number.isInteger(i)||i<0||i>=result.rows.length))return;
   onSelection?.([...new Set(data.rows)]);
  }
  if(data.type==='filter'){
   try{
    if(!filterProperties.some(p=>p.objectName===data.objectName&&p.propertyName===data.propertyName)||![0,1].includes(data.action))throw Error('The custom visual filter property or action is not supported.');
    const key=data.objectName+':'+data.propertyName,next=data.action===1?[]:CustomDataView.normalizeJsonFilters(visual,data.filters),updated=new Map(slots);
    if(next.length)updated.set(key,next);else updated.delete(key);
    const merged=[...updated.values()].flat(),report=CustomDataView.reportFilters(visual,merged);
    if(JSON.stringify(merged)===JSON.stringify(currentFilters))return;
    if(!onFilters)throw Error('Custom visual filters are not available in this preview.');
    slots.clear();for(const [name,value] of updated)slots.set(name,value);currentFilters=merged;onFilters(report);
   }catch(error){note.textContent='Custom visual filter: '+String(error.message);note.style.color='#a03c30'}
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
 const session={frame,capture(){return new Promise((resolve,reject)=>{const requestId=crypto.randomUUID(),timer=setTimeout(()=>{snapshots.delete(requestId);reject(Error('Custom visual snapshot timed out.'))},15000);snapshots.set(requestId,{resolve,reject,timer});frame.contentWindow.postMessage({token,type:'snapshot',requestId},'*')})},dispose(){if(disposed)return;disposed=true;clearTimeout(timer);for(const pending of snapshots.values()){clearTimeout(pending.timer);pending.reject(Error('Custom visual was disposed.'))}snapshots.clear();frame.contentWindow?.postMessage({token,type:'destroy'},'*');removeEventListener('message',message);frame.remove();sessions.delete(session);resolveReady({disposed:true})}};
 sessions.add(session);addEventListener('message',message);
 const imageSources=/^(?:STANDALONE)?deneb[0-9a-f]{32}$/i.test(pkg.guid||'')?[...new Set(result.rows.flatMap(row=>row.filter(value=>typeof value==='string'&&/^https:\/\//i.test(value)&&/\.(?:png|jpe?g|gif|webp|svg)(?:[?#]|$)/i.test(value))))]:[];
 frame.srcdoc=CustomFrame.documentFor(pkg,token,!!options(pkg.id).network,model.theme||{},imageSources,!!onHover,externalImages,tooltip!==false);
 if(result.truncated)note.textContent='Preview limited to 10,000 query rows.';
 try{return await ready}catch(error){session.dispose();throw error}
}

function isHtmlContent(type){return /^(?:htmlContent(?:[0-9a-f]{32}|Lite[0-9a-f]{32})?|paraHTMLViewer[0-9a-f]{32})$/i.test(type||'')}
function htmlValues(result,compiled){const index=compiled.roles?.findIndex(role=>['content','cvalue'].includes(String(role).toLowerCase()));if(!Number.isInteger(index)||index<0)throw Error('HTML Content requires a content field.');const values=result.rows.map(row=>row[index]).filter(value=>value!=null).map(String);if(values.reduce((n,v)=>n+v.length,0)>8000000)throw Error('HTML Content exceeds the 8,000,000-character rendering limit.');return values}
function htmlDocument(content,nonce,depth=0,budget={frames:0},suppressTitles=false){
 if(depth>12)throw Error('HTML Content nested-frame limit exceeded.');
 const doc=new DOMParser().parseFromString(content,'text/html');
 for(const node of doc.querySelectorAll('meta[http-equiv],base,object,embed'))node.remove();
 for(const node of doc.querySelectorAll('*'))for(const attribute of [...node.attributes])if(/^on/i.test(attribute.name)||attribute.name==='nonce')node.removeAttribute(attribute.name);
 for(const node of doc.querySelectorAll('script')){if(node.hasAttribute('src'))node.remove();else node.setAttribute('nonce',nonce)}
 for(const node of doc.querySelectorAll('iframe')){if(++budget.frames>256)throw Error('HTML Content exceeds 256 nested frames.');const nested=node.getAttribute('srcdoc');node.removeAttribute('src');node.setAttribute('sandbox','allow-scripts');node.setAttribute('referrerpolicy','no-referrer');if(nested!=null)node.setAttribute('srcdoc',htmlDocument(nested,nonce,depth+1,budget,suppressTitles))}
 for(const node of doc.querySelectorAll('img'))node.setAttribute('referrerpolicy','no-referrer');
 for(const node of doc.querySelectorAll('a')){const href=node.getAttribute('href')||'';if(!/^#/.test(href))node.removeAttribute('href');node.removeAttribute('target')}
 const csp=doc.createElement('meta');csp.httpEquiv='Content-Security-Policy';csp.content="default-src 'none'; script-src 'nonce-"+nonce+"'; style-src 'unsafe-inline'; img-src data: blob: https:; font-src data:; connect-src 'none'; frame-src about:; media-src data: blob:; worker-src 'none'; form-action 'none'; base-uri 'none'";doc.head.prepend(csp);
 const style=doc.createElement('style');style.textContent='html,body{margin:0;min-height:100%;background:transparent}body{font-family:Segoe UI,sans-serif}';doc.head.prepend(style);
 const escapeScript=doc.createElement('script');escapeScript.setAttribute('nonce',nonce);escapeScript.textContent='('+htmlEscapeBridge.toString()+')();';doc.head.insertBefore(escapeScript,csp.nextSibling);
 if(suppressTitles){const Frame=typeof module!=='undefined'?require('./custom-frame'):root.CustomFrame;Frame.suppressNativeTooltips(doc,false);const script=doc.createElement('script');script.setAttribute('nonce',nonce);script.textContent='('+Frame.suppressNativeTooltips.toString()+')(document);';doc.head.insertBefore(script,csp.nextSibling)}
 return '<!doctype html>'+doc.documentElement.outerHTML;
}
function htmlEscapeBridge(){
 const send=()=>parent.postMessage({type:'death2bi-exit-fullscreen'},'*');
 addEventListener('keydown',event=>{if(event.key==='Escape')send()},true);
 // Sanitized HTML can use nested opaque srcdoc frames. Only forward this
 // data-free action from one of this document's own child frame windows.
 addEventListener('message',event=>{if(event.data?.type==='death2bi-exit-fullscreen'&&[...document.querySelectorAll('iframe')].some(frame=>frame.contentWindow===event.source))send()});
}
function htmlHoverBridge(token){
 let frame=0,latest;
 const send=()=>{frame=0;if(latest)parent.postMessage({death2custom:true,token,type:'htmlHover',...latest},'*')};
 addEventListener('mousemove',event=>{const row=event.target.closest?.('[data-pbi-html-row]');if(!row)return;latest={row:Number(row.getAttribute('data-pbi-html-row')),x:event.clientX/Math.max(1,innerWidth),y:event.clientY/Math.max(1,innerHeight)};if(!frame)frame=requestAnimationFrame(send)});
 addEventListener('mouseleave',()=>{if(frame)cancelAnimationFrame(frame);frame=0;latest=null;parent.postMessage({death2custom:true,token,type:'htmlLeave'},'*')});
}
async function mountHtml(container,visual,result,compiled,{model,onHover,onLeave,tooltip}){
 if(tooltip===false){onHover=undefined;onLeave=undefined}
 const values=htmlValues(result,compiled),p=root.ReportStyle.props(root.ReportStyle.objects(model,visual),'contentFormatting'),theme=model.theme||{},raw=root.ReportStyle.value(p.showRawHtml,theme);
 if(root.ReportStyle.value(p.format,theme)==='markdown')throw Error('HTML Content Markdown mode is not implemented.');
 const document=new DOMParser().parseFromString('<html><head></head><body></body></html>','text/html');
 const contentIndex=compiled.roles.findIndex(role=>['content','cvalue'].includes(String(role).toLowerCase())),rowIndices=result.rows.flatMap((row,i)=>row[contentIndex]!=null?[i]:[]);
 for(const [valueIndex,value] of values.entries()){const wrapper=document.createElement(raw?'pre':'div');wrapper.setAttribute('data-pbi-html-row',String(rowIndices[valueIndex]));if(raw)wrapper.textContent=value;else{const parsed=new DOMParser().parseFromString(value,'text/html');for(const node of [...parsed.head.childNodes])document.head.appendChild(document.importNode(node,true));for(const node of [...parsed.body.childNodes])wrapper.appendChild(document.importNode(node,true))}document.body.appendChild(wrapper)}
 const stylesheet=root.ReportStyle.value(root.ReportStyle.props(root.ReportStyle.objects(model,visual),'stylesheet').stylesheet,theme);if(stylesheet){const style=document.createElement('style');style.textContent=String(stylesheet);document.head.appendChild(style)}
 const style=document.createElement('style');style.textContent='body{font-size:'+Math.max(1,Math.min(200,Number(root.ReportStyle.value(p.fontSize,theme))||12))*4/3+'px;text-align:'+(root.ReportStyle.value(p.align,theme)||'left')+'}';document.head.appendChild(style);
 const frame=container.ownerDocument.createElement('iframe');frame.title='HTML Content custom visual';frame.setAttribute('sandbox','allow-scripts');frame.referrerPolicy='no-referrer';frame.style.cssText='width:100%;height:100%;border:0;display:block;background:transparent';
 const token=crypto.randomUUID(),nonce=token.replace(/[^a-zA-Z0-9]/g,''),html=htmlDocument(document.documentElement.outerHTML,nonce,0,{frames:0},tooltip===false||!!onHover);
 const snapshotFactory=root.SnapshotDOM.create.toString();
 const bridge='<script nonce="'+nonce+'">'+(onHover?'('+htmlHoverBridge.toString()+')('+JSON.stringify(token)+');':'')+'const snapshot=('+snapshotFactory+')();addEventListener("message",async e=>{if(e.source!==parent||e.data?.token!=='+JSON.stringify(token)+'||e.data.type!=="snapshot")return;try{const captured=await snapshot.freeze(document.documentElement,{inlineStyles:true});parent.postMessage({death2custom:true,token:'+JSON.stringify(token)+',type:"snapshot",requestId:e.data.requestId,...captured},"*")}catch(error){parent.postMessage({death2custom:true,token:'+JSON.stringify(token)+',type:"snapshot",requestId:e.data.requestId,error:String(error.message)},"*")}});<\/script>';
 frame.srcdoc=html.replace('</body>',bridge+'</body>');container.replaceChildren(frame);
 let disposed=false;const pending=new Map();
 const listener=event=>{const data=event.data;if(event.source!==frame.contentWindow||data?.token!==token)return;if(data.type==='htmlHover'&&onHover&&Number.isInteger(data.row)&&data.row>=0&&data.row<result.rows.length){const rect=frame.getBoundingClientRect();onHover(result.rows[data.row],{clientX:rect.left+Math.max(0,Math.min(1,Number(data.x)||0))*rect.width,clientY:rect.top+Math.max(0,Math.min(1,Number(data.y)||0))*rect.height});return}if(data.type==='htmlLeave'){onLeave?.();return}if(data.type!=='snapshot')return;const request=pending.get(data.requestId);if(request){clearTimeout(request.timer);pending.delete(data.requestId);data.error?request.reject(Error(data.error)):request.resolve({html:data.html,warnings:data.warnings||[]})}};
 const session={frame,capture(){return new Promise((resolve,reject)=>{const requestId=crypto.randomUUID(),timer=setTimeout(()=>{pending.delete(requestId);reject(Error('HTML Content snapshot timed out'))},15000);pending.set(requestId,{resolve,reject,timer});frame.contentWindow.postMessage({token,type:'snapshot',requestId},'*')})},dispose(){if(disposed)return;disposed=true;for(const r of pending.values()){clearTimeout(r.timer);r.reject(Error('HTML Content disposed'))}pending.clear();removeEventListener('message',listener);frame.remove();sessions.delete(session)}};
 sessions.add(session);addEventListener('message',listener);return {frame};
}
function capture(frame){const session=[...sessions].find(s=>s.frame===frame);return session?session.capture():Promise.reject(Error('Custom visual is not active.'))}
const api={htmlHoverBridge,isHtmlContent,isFilterVisual,htmlValues,htmlDocument,capture,load,resolve,get,options,configure,disposeAll,mount,setAccount,list:()=>library};if(typeof module!=='undefined')module.exports=api;root.CustomVisuals=api;
})(globalThis);
