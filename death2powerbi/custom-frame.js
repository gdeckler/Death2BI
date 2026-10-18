(function(root){
function bootstrap(config){
 'use strict';
 const token=config.token,send=(type,payload={})=>parent.postMessage({death2custom:true,token,type,...payload},'*');
 const element=document.getElementById('visual'),tooltip=document.getElementById('tooltip');let visual,view,selected=[],callbacks=[],objects={};
 const error=e=>send('error',{message:String(e?.message||e).slice(0,2000)});
 addEventListener('error',event=>error(event.error||event.message));addEventListener('unhandledrejection',event=>error(event.reason));
 let blocked=false;addEventListener('securitypolicyviolation',event=>{if(!blocked&&/connect-src|img-src/.test(event.violatedDirective)){blocked=true;send('warning',{message:'External resources are blocked. Geometry can render locally; enable declared network services in Custom visuals if needed.'})}});
 const palette=['#337b60','#4e8fa6','#c89849','#8b6aa8','#ca7b70','#9dbd67','#568475','#889ab5'];
 const color=key=>{let h=0;for(const c of String(key))h=(h*31+c.charCodeAt(0))>>>0;return {value:palette[h%palette.length]}};
 function selectionId(keys=[],rows=[]){
  const key=JSON.stringify([...new Set(keys)].sort()),ids=[...new Set(rows)].filter(Number.isInteger);
  return {key,rows:ids,getKey:()=>key,getSelector:()=>({data:keys.map(key=>({key}))}),getSelectorsByColumn:()=>({dataMap:{},metadata:key}),getSelectionId:()=>selectionId(keys,ids),equals:other=>other?.getKey?.()===key,includes:other=>other?.rows?.every(row=>ids.includes(row))||false,hasIdentity:()=>!!keys.length};
 }
 function idBuilder(){let keys=[],rows=null;const add=identity=>{if(identity){keys.push(identity.key);rows=rows===null?identity.rows||[]:rows.filter(row=>(identity.rows||[]).includes(row))}return api};
  const api={withTable:(table,index)=>add(table.identity?.[index]),withCategory:(category,index)=>add(category.identity?.[index]),withSeries:(values,group)=>add(group.identity),withMeasure:name=>{keys.push('measure:'+name);return api},withMatrixNode:()=>{throw Error('Matrix selection identities are not supported')},createSelectionId:()=>selectionId(keys,rows||[])};return api;
 }
 const manager={select:async(ids,multi=false)=>{ids=Array.isArray(ids)?ids:[ids];selected=multi||selected.length===1&&ids.length===1&&selected[0].getKey()===ids[0].getKey()?[...selected]:[];for(const id of ids){const i=selected.findIndex(x=>x.getKey()===id.getKey());if(i>=0)selected.splice(i,1);else selected.push(id)}send('selection',{rows:[...new Set(selected.flatMap(id=>id.rows))]});callbacks.forEach(fn=>fn(selected));return selected},clear:async()=>{selected=[];send('selection',{rows:[]});callbacks.forEach(fn=>fn(selected));return []},getSelectionIds:()=>selected,hasSelection:()=>selected.length>0,registerOnSelectCallback:fn=>callbacks.push(fn),showContextMenu:async()=>{send('warning',{message:'Power BI context menus are not implemented.'})}};
 const unsupported=name=>()=>{throw Error('Custom visual host service is not supported: '+name)};
 function tooltipShow(options){const rows=options?.dataItems||[];tooltip.replaceChildren();for(const item of rows){const line=document.createElement('div');line.textContent=(item.displayName?item.displayName+': ':'')+(item.value??'');tooltip.appendChild(line)}tooltip.style.display=rows.length?'block':'none';tooltip.style.left=Math.max(0,Math.min(innerWidth-180,options.coordinates?.[0]||0))+'px';tooltip.style.top=Math.max(0,Math.min(innerHeight-60,options.coordinates?.[1]||0))+'px'}
 const host={
  instanceId:token,locale:'en-US',hostEnv:0,hostCapabilities:{allowInteractions:true,allowModalDialog:false},
  colorPalette:{getColor:color,isHighContrast:false,foreground:{value:'#193a37'},background:{value:'#ffffff'},foregroundSelected:{value:'#337b60'},hyperlink:{value:'#2470a0'}},
  createSelectionIdBuilder:idBuilder,createSelectionManager:()=>manager,
  createLocalizationManager:()=>({getDisplayName:key=>config.strings?.[key]||key}),
  eventService:{renderingStarted:()=>send('rendering'),renderingFinished:()=>send('finished'),renderingFailed:(options,message)=>error(message||'The custom visual reported a render failure'),trace:()=>{}},
  tooltipService:{enabled:()=>true,show:tooltipShow,move:options=>{if(options.dataItems)tooltipShow(options);else{tooltip.style.left=Math.max(0,Math.min(innerWidth-180,options.coordinates?.[0]||0))+'px';tooltip.style.top=Math.max(0,Math.min(innerHeight-60,options.coordinates?.[1]||0))+'px'}},hide:()=>{tooltip.style.display='none'}},
  persistProperties:changes=>{
   for(const item of changes?.merge||[]){if(item.selector){send('warning',{message:'Per-data-point persisted formatting is not implemented.'});continue}objects[item.objectName]={...(objects[item.objectName]||{}),...item.properties}}
   for(const item of changes?.remove||[]){if(!item.selector)delete objects[item.objectName]}
   send('persist',{changes});if(view){view.metadata.objects={...view.metadata.objects,...objects};queueMicrotask(update)}
  },
  fetchMoreData:()=>{send('warning',{message:'This workbench supplies up to 1,000 query rows; fetchMoreData is not implemented.'});return false},
  refreshHostData:()=>send('refresh'),displayWarningIcon:(title,detail)=>send('warning',{message:String(title)+': '+String(detail||'')}),
  applyJsonFilter:unsupported('applyJsonFilter'),applyCustomSort:unsupported('applyCustomSort'),launchUrl:unsupported('launchUrl'),openModalDialog:unsupported('openModalDialog'),
  downloadService:{exportVisualsContent:unsupported('downloadService')},storageService:{get:unsupported('storageService'),set:unsupported('storageService')},
  storageV2Service:{status:async()=>2,get:unsupported('storageV2Service'),set:unsupported('storageV2Service')},
  webAccessService:{webAccessStatus:async url=>{let origin;try{origin=new URL(url).origin}catch{return 1}const declared=(config.domains||[]).some(domain=>domain.includes('*.')?origin.startsWith('https://')&&(origin.slice(8).endsWith('.'+domain.split('*.')[1])):origin===domain);return declared?(config.network?0:3):1}},
  authenticationService:{getAADToken:unsupported('authenticationService')},acquireAADTokenService:{acquireAADToken:unsupported('acquireAADTokenService')},
  licenseManager:{getAvailableServicePlans:unsupported('licenseManager'),notifyLicenseRequired:unsupported('licenseManager'),notifyLicenseRequiredTooltip:unsupported('licenseManager')},
  telemetry:{trace:()=>{}},switchFocusModeState:unsupported('switchFocusModeState')
 };
 function hydrate(data){
  for(const column of data.metadata.columns){if(!column.type.dateTime)continue;const i=column.index;for(const row of data.table?.rows||[])if(row[i]!=null)row[i]=new Date(row[i])}
  for(const category of data.categorical?.categories||[])if(category.source.type.dateTime)category.values=category.values.map(v=>v==null?v:new Date(v));
  const values=data.categorical?.values;
  if(values){values.grouped=()=>{const groups=new Map();for(const col of values){const key=JSON.stringify(col.source.groupName??null);if(!groups.has(key))groups.set(key,{name:col.source.groupName,identity:col.identity,values:[]});groups.get(key).values.push(col)}return [...groups.values()]};for(const col of values){if(values.source?.type.dateTime&&col.source.groupName!=null)col.source.groupName=new Date(col.source.groupName);if(col.source.type.dateTime)col.values=col.values.map(v=>v==null?v:new Date(v))}}
  return data;
 }
 function update(){if(!visual||!view)return;try{const result=visual.update({dataViews:[view],viewport:{width:Math.max(1,element.clientWidth),height:Math.max(1,element.clientHeight)},type:62,viewMode:0,editMode:0,operationKind:0,isInFocus:false});Promise.resolve(result).then(()=>send('finished')).catch(error)}catch(e){error(e)}}
 addEventListener('message',event=>{if(event.source!==parent||event.data?.token!==token)return;const message=event.data;if(message.type==='data'){view=hydrate(message.view);objects={...view.metadata.objects};const indices=new Set(message.selectedRows||[]);const identities=view.categorical?.categories?.[0]?.identity||view.table?.identity||[];selected=identities.filter(id=>id.rows?.length&&id.rows.every(index=>indices.has(index))).map(id=>selectionId([id.key],id.rows));update();callbacks.forEach(fn=>fn())}else if(message.type==='destroy'){try{visual?.destroy?.()}catch{}visual=null}});
 try{
  window.powerbi={visuals:{plugins:{}},extensibility:{visual:{}}};window.dialogRegistry={};
  const style=document.createElement('style');style.textContent=config.css;document.head.appendChild(style);
  const script=document.createElement('script');script.nonce=config.nonce;script.textContent=config.js;document.head.appendChild(script);
  const plugin=window.powerbi.visuals.plugins[config.guid];if(!plugin?.create)throw Error('The visual bundle did not register its GUID with powerbi.visuals.plugins.');
  visual=plugin.create({element,host});new ResizeObserver(()=>update()).observe(element);send('ready');
 }catch(e){error(e)}
}
function documentFor(pkg,token,network=false){
 const nonce=token.replace(/[^a-zA-Z0-9]/g,''),domains=network?(pkg.networkDomains||[]).join(' '):'',policy="default-src 'none'; script-src 'nonce-"+nonce+"'; style-src 'unsafe-inline'; img-src data: blob: "+domains+"; connect-src "+(domains||"'none'")+"; font-src data:; media-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; worker-src 'none'";
 const config={token,nonce,guid:pkg.guid,js:pkg.js,css:pkg.css||'',strings:{},network,domains:pkg.networkDomains||[]};
 const encoded=JSON.stringify(config).replaceAll('<','\\u003c').replaceAll('\u2028','\\u2028').replaceAll('\u2029','\\u2029');
 return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+policy.replaceAll('"','&quot;')+'"><style>html,body,#visual{margin:0;width:100%;height:100%;overflow:hidden}body{font-family:Segoe UI,sans-serif}#tooltip{display:none;position:fixed;z-index:999999;background:#193a37;color:white;border-radius:4px;font:12px sans-serif;padding:8px;max-width:260px;pointer-events:none}</style></head><body><div id="visual"></div><div id="tooltip" role="tooltip"></div><script nonce="'+nonce+'">('+bootstrap.toString()+')('+encoded+');<\/script></body></html>';
}
const api={documentFor,bootstrap};if(typeof module!=='undefined')module.exports=api;root.CustomFrame=api;
})(globalThis);
