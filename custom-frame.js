(function(root){
function suppressNativeTooltips(target,observe=true){
 const svg='http://www.w3.org/2000/svg',generated=new WeakMap();
 function preserve(node,text){if(!node||!text?.trim())return;const prior=generated.get(node),unchanged=prior&&node.getAttribute(prior.name)===prior.text,named=['aria-label','aria-labelledby','alt'].some(name=>node.hasAttribute(name)&&!(unchanged&&prior.name===name)),name=named?'aria-description':'aria-label';if(unchanged&&prior.name===name){node.setAttribute(name,text);prior.text=text;return}if(unchanged)node.removeAttribute(prior.name);if(!node.hasAttribute(name)){node.setAttribute(name,text);generated.set(node,{name,text})}}
 function clear(node){
  if(node.nodeType===1&&node.namespaceURI===svg&&node.localName==='title'){
   const parents=new Set([node.parentElement]),id=node.getAttribute('id');
   if(id)for(const parent of (node.ownerDocument||target).querySelectorAll?.('[aria-labelledby]')||[]){const references=(parent.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean);if(!references.includes(id))continue;const remaining=references.filter(reference=>reference!==id);if(remaining.length)parent.setAttribute('aria-labelledby',remaining.join(' '));else parent.removeAttribute('aria-labelledby');parents.add(parent)}
   for(const parent of parents)preserve(parent,node.textContent);node.remove();return;
  }
  if(node.hasAttribute?.('title')){preserve(node,node.getAttribute('title'));node.removeAttribute('title')}
  for(const child of node.querySelectorAll?.('[title],svg title')||[])clear(child);
 }
 clear(target);
 if(!observe||typeof MutationObserver==='undefined')return ()=>{};
 const observer=new MutationObserver(records=>{for(const record of records){if(record.type==='attributes')clear(record.target);else for(const node of record.addedNodes)clear(node)}});
 observer.observe(target,{subtree:true,childList:true,attributes:true,attributeFilter:['title']});return ()=>observer.disconnect();
}
function bootstrap(config,createSnapshotDOM,removeNativeTooltips){
 'use strict';
 const snapshotDOM=createSnapshotDOM();
 const token=config.token,send=(type,payload={})=>parent.postMessage({death2custom:true,token,type,...payload},'*');
 // Keyboard events in an opaque sandbox do not bubble to the report host.
 addEventListener('keydown',event=>{if(event.key==='Escape')parent.postMessage({type:'death2bi-exit-fullscreen'},'*')},true);
 const element=document.getElementById('visual'),tooltip=document.getElementById('tooltip'),tooltipEnabled=config.tooltipEnabled!==false,externalTooltip=tooltipEnabled&&config.reportTooltip,cleanupTitles=config.reportTooltip||!tooltipEnabled?removeNativeTooltips?.(document):null;let visual,view,selected=[],callbacks=[],objects={},jsonFilters=[];
 const error=e=>{console.error('Custom visual error',e?.stack||e);send('error',{message:String(e?.message||e).slice(0,2000)})};
 addEventListener('error',event=>error(event.error||event.message));addEventListener('unhandledrejection',event=>error(event.reason));
 let blocked=false;addEventListener('securitypolicyviolation',event=>{if(!blocked&&/connect-src|img-src/.test(event.violatedDirective)){blocked=true;send('warning',{message:'External resources are blocked. Geometry can render locally; enable declared network services in Custom visuals if needed.'})}});
 const palette=config.theme?.dataColors?.length?config.theme.dataColors:['#337b60','#4e8fa6','#c89849','#8b6aa8','#ca7b70','#9dbd67','#568475','#889ab5'];
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
 let hoverRows=[];function tooltipBridge(options){if(!tooltipEnabled)return;const ids=options?.identities||[];if(ids.length)hoverRows=[...new Set(ids.flatMap(id=>id?.rows||[]))];if(externalTooltip)send('tooltip',{rows:hoverRows,coordinates:options?.coordinates||[0,0]})}
 function tooltipShow(options){tooltipBridge(options);if(!tooltipEnabled||externalTooltip){tooltip.style.display='none';return}const rows=options?.dataItems||[];tooltip.replaceChildren();for(const item of rows){const line=document.createElement('div');line.textContent=(item.displayName?item.displayName+': ':'')+(item.value??'');tooltip.appendChild(line)}tooltip.style.display=rows.length?'block':'none';tooltip.style.left=Math.max(0,Math.min(innerWidth-180,options.coordinates?.[0]||0))+'px';tooltip.style.top=Math.max(0,Math.min(innerHeight-60,options.coordinates?.[1]||0))+'px'}
 const host={
  instanceId:token,locale:'en-US',hostEnv:0,hostCapabilities:{allowInteractions:true,allowModalDialog:false},
  colorPalette:{colors:palette.map(value=>({value})),getColorByIndex:index=>({value:palette[((index%palette.length)+palette.length)%palette.length]}),getColor:color,isHighContrast:false,foreground:{value:config.theme?.foreground||'#193a37'},background:{value:config.theme?.background||'#ffffff'},foregroundSelected:{value:'#337b60'},hyperlink:{value:'#2470a0'}},
  createSelectionIdBuilder:idBuilder,createSelectionManager:()=>manager,
  createLocalizationManager:()=>({getDisplayName:key=>config.strings?.[key]||key}),
  eventService:{renderingStarted:()=>send('rendering'),renderingFinished:()=>send('finished'),renderingFailed:(options,message)=>error(message||'The custom visual reported a render failure'),trace:()=>{}},
  tooltipService:{enabled:()=>tooltipEnabled,show:tooltipShow,move:options=>{tooltipBridge(options);if(!tooltipEnabled||externalTooltip){tooltip.style.display='none';return}if(options.dataItems)tooltipShow(options);else{tooltip.style.left=Math.max(0,Math.min(innerWidth-180,options.coordinates?.[0]||0))+'px';tooltip.style.top=Math.max(0,Math.min(innerHeight-60,options.coordinates?.[1]||0))+'px'}},hide:()=>{tooltip.style.display='none';hoverRows=[];if(tooltipEnabled)send('tooltipLeave')}},
  persistProperties:changes=>{
   for(const item of changes?.merge||[]){if(item.selector){send('warning',{message:'Per-data-point persisted formatting is not implemented.'});continue}objects[item.objectName]={...(objects[item.objectName]||{}),...item.properties}}
   for(const item of changes?.remove||[]){if(!item.selector)delete objects[item.objectName]}
   send('persist',{changes});if(view){view.metadata.objects={...view.metadata.objects,...objects};queueMicrotask(update)}
  },
  fetchMoreData:()=>{send('warning',{message:'This workbench supplies up to 10,000 query rows; fetchMoreData is not implemented.'});return false},
  refreshHostData:()=>send('refresh'),displayWarningIcon:(title,detail)=>send('warning',{message:String(title)+': '+String(detail||'')}),
  applyJsonFilter:(filters,objectName,propertyName,action)=>{
   if(!(config.filterProperties||[]).some(p=>p.objectName===objectName&&p.propertyName===propertyName))throw Error('Custom visual filter property is not declared in its capabilities.');
   if(action!==0&&action!==1)throw Error('Custom visual filter action is not supported.');
   send('filter',{filters:filters==null?[]:Array.isArray(filters)?filters:[filters],objectName,propertyName,action});
  },applyCustomSort:unsupported('applyCustomSort'),launchUrl:unsupported('launchUrl'),openModalDialog:unsupported('openModalDialog'),
  downloadService:{exportStatus:async()=>2,status:async()=>2,exportVisualsContent:async()=>false,exportVisualsContentExtended:async()=>({downloadCompleted:false})},storageService:{get:unsupported('storageService'),set:unsupported('storageService')},
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
 function update(){if(!visual||!view)return;try{const result=visual.update({dataViews:[view],jsonFilters,viewport:{width:Math.max(1,element.clientWidth),height:Math.max(1,element.clientHeight)},type:62,viewMode:0,editMode:0,operationKind:0,isInFocus:false});Promise.resolve(result).then(()=>send('finished')).catch(error)}catch(e){error(e)}}
 addEventListener('message',event=>{if(event.source!==parent||event.data?.token!==token)return;const message=event.data;if(message.type==='data'){view=hydrate(message.view);objects={...view.metadata.objects};jsonFilters=message.filters||[];const indices=new Set(message.selectedRows||[]);const identities=view.categorical?.categories?.[0]?.identity||view.table?.identity||[];selected=identities.filter(id=>id.rows?.length&&id.rows.every(index=>indices.has(index))).map(id=>selectionId([id.key],id.rows));update();callbacks.forEach(fn=>fn())}else if(message.type==='snapshot'){(async()=>{try{await Promise.race([document.fonts.ready,new Promise(resolve=>setTimeout(resolve,1000))]);await Promise.race([new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))),new Promise(resolve=>setTimeout(resolve,250))]);const result=await snapshotDOM.freeze(element,{inlineStyles:true});send('snapshot',{requestId:message.requestId,...result})}catch(e){send('snapshot',{requestId:message.requestId,error:String(e.message||e)})}})()}else if(message.type==='destroy'){try{visual?.destroy?.()}catch{}visual=null;cleanupTitles?.()}});
 try{
  window.powerbi={visuals:{plugins:{}},extensibility:{visual:{}}};for(const [name,entries] of Object.entries({VisualUpdateType:{Data:2,Resize:4,ViewMode:8,Style:16,ResizeEnd:32,All:62},VisualDataChangeOperationKind:{Create:0,Append:1,Segment:2},ViewMode:{View:0,Edit:1,InFocusEdit:2}})){const enumeration={...entries};for(const [key,value] of Object.entries(entries))enumeration[value]=key;window.powerbi[name]=enumeration}window.dialogRegistry={};
  const style=document.createElement('style');style.textContent=config.css;document.head.appendChild(style);
  const script=document.createElement('script');script.nonce=config.nonce;script.textContent=config.js;document.head.appendChild(script);
  const plugin=window.powerbi.visuals.plugins[config.guid]||window.powerbi.visuals.plugins[config.guid+'_DEBUG'];if(!plugin?.create)throw Error('The visual bundle did not register its GUID with powerbi.visuals.plugins.');
  visual=plugin.create({element,host});new ResizeObserver(()=>update()).observe(element);send('ready');
 }catch(e){error(e)}
}
function safeNumericFormatter(expression){
 // The legacy Walkers setting is a tiny number formatter, not a script host.
 // Recognize common numeric forms without evaluating uploaded JavaScript.
 const identity=d=>d;if(typeof expression!=='string'||expression.length>256||/[\u0000-\u001f]/.test(expression))return identity;
 let text=expression.trim(),prefix='',suffix='';
 const literal=source=>source[0]==='"'?JSON.parse(source):source.slice(1,-1);
 const after=/^(.+?)\s*\+\s*((?:"[^"\\\r\n]*"|'[^'\\\r\n]*'))$/.exec(text);
 if(after){text=after[1].trim();suffix=literal(after[2])}
 const before=/^((?:"[^"\\\r\n]*"|'[^'\\\r\n]*'))\s*\+\s*(.+)$/.exec(text);
 if(before){prefix=literal(before[1]);text=before[2].trim()}
 text=text.replace(/\s+/g,'');let format;
 if(text==='d')format=identity;
 const math=/^Math\.(round|floor|ceil|abs|trunc)\(d\)$/.exec(text);
 if(math)format=d=>Math[math[1]](d);
 const fixed=/^d\.toFixed\((\d{1,2})\)$/.exec(text);
 if(fixed&&Number(fixed[1])<=20)format=d=>d.toFixed(Number(fixed[1]));
 if(!format)return identity;
 return prefix||suffix?d=>prefix+format(d)+suffix:format;
}
function compatibleScript(pkg){
 // Webpack's legacy global-object probe needlessly invokes dynamic code.
 let source=pkg.js.replace(/\b(?:new\s+)?Function\(\s*(["'])return this\1\s*\)\(\)/g,'globalThis');
 // The publisher's legacy formatter constructs a Function even for its default
 // Math.round(d) + '%' setting. Replace only this known factory and retain CSP.
 if(pkg.guid==='wishyoulizationwalkers'&&pkg.version==='1.0.2'){
  const factory='function(t){var e;try{(e=new Function("d","return "+t+";"))(1)}catch(t){console.log(t),e=new Function("d","return d;")}return e}';
  source=source.replace(factory,'('+safeNumericFormatter.toString()+')');
 }
 // Violin 1.3.0.4 dereferences a missing x-axis generator when axes are hidden
 // and no category role is bound (the compact distribution-only layout).
 if(pkg.guid==='violinPlot4D46EB9EB3A141D9BA2289793175D971'&&pkg.version==='1.3.0.4')return source.replace('else this.viewModel.xAxis.generator.tickFormat("")','else this.viewModel.xAxis.generator&&this.viewModel.xAxis.generator.tickFormat("")');
 // Some embedded Deneb 2.0 bundles contain a damaged ellipsis regex.
 // Repair only the exact invalid helper; keep all unrelated package code intact.
 if(/^(?:STANDALONE)?deneb[0-9a-f]{32}$/i.test(pkg.guid||'')&&pkg.version==='2.0.0.0')return source.replace('return e.replace(/(?)|(\\.\\.\\.)/g, "");','return e.replace(/(\\u2026)|(\\.\\.\\.)/g, "");');
 return source;
}
function documentFor(pkg,token,network=false,theme={},imageSources=[],reportTooltip=false,externalImages=false,tooltipEnabled=true){
 const imageUrls=imageSources.filter(s=>{try{const u=new URL(s);return u.protocol==='https:'&&!u.username&&!u.password&&!/[\s;\"']/.test(s)}catch{return false}});
 const nonce=token.replace(/[^a-zA-Z0-9]/g,''),domains=network?(pkg.networkDomains||[]).join(' '):'',policy="default-src 'none'; script-src 'nonce-"+nonce+"'"+(/^(?:STANDALONE)?deneb[0-9a-f]{32}$/i.test(pkg.guid||'')?" 'unsafe-eval'":"")+"; style-src 'unsafe-inline'; img-src data: blob: "+domains+(externalImages?" https: http: ":" ")+imageUrls.join(' ')+"; connect-src "+(domains||"'none'")+"; font-src data:; media-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; worker-src 'none'";
 const snapshotFactory=(typeof module!=='undefined'?require('./snapshot-dom.js'):root.SnapshotDOM).create.toString();
 const filterProperties=Object.entries(pkg.capabilities?.objects||{}).flatMap(([objectName,object])=>Object.entries(object.properties||{}).filter(([,property])=>property?.type?.filter===true).map(([propertyName])=>({objectName,propertyName})));
 const config={token,nonce,theme,reportTooltip,tooltipEnabled,guid:pkg.guid,js:compatibleScript(pkg),css:pkg.css||'',strings:{},network,domains:pkg.networkDomains||[],filterProperties};
 const encoded=JSON.stringify(config).replaceAll('<','\\u003c').replaceAll('\u2028','\\u2028').replaceAll('\u2029','\\u2029');
 return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+policy.replaceAll('"','&quot;')+'"><style>html,body,#visual{margin:0;width:100%;height:100%;overflow:hidden}body{font-family:Segoe UI,sans-serif}#tooltip{display:none;position:fixed;z-index:999999;background:#193a37;color:white;border-radius:4px;font:12px sans-serif;padding:8px;max-width:260px;pointer-events:none}</style></head><body><div id="visual"></div><div id="tooltip" role="tooltip"></div><script nonce="'+nonce+'">('+bootstrap.toString()+')('+encoded+','+snapshotFactory+','+suppressNativeTooltips.toString()+');<\/script></body></html>';
}
const api={suppressNativeTooltips,documentFor,bootstrap,compatibleScript};if(typeof module!=='undefined')module.exports=api;root.CustomFrame=api;
})(globalThis);
