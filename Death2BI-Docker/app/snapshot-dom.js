/* Freeze rendered DOM into inert, self-contained snapshot markup. Shared with sandbox frames. */
(function(root){
function create(){
 const properties=('display position top right bottom left width height min-width min-height max-width max-height box-sizing margin padding overflow overflow-x overflow-y opacity visibility color background-color background-image background-size background-position background-repeat border border-radius box-shadow font-family font-size font-style font-weight line-height letter-spacing text-align text-decoration white-space word-break overflow-wrap vertical-align flex flex-direction flex-wrap flex-grow flex-shrink flex-basis align-items align-self justify-content gap grid-template-columns grid-template-rows transform transform-origin fill fill-opacity stroke stroke-width stroke-opacity stroke-dasharray stroke-linecap stroke-linejoin text-anchor dominant-baseline clip-path paint-order vector-effect').split(' ');
 const safeImage=value=>/^data:image\/(?:png|jpeg|gif|webp|avif|bmp|svg\+xml|x-icon|vnd.microsoft.icon);/i.test(value||'');
 function sanitize(node){
  node.querySelectorAll('script,iframe,object,embed,link,meta,base,style,form,button,select,input,textarea,.vega-actions,.map-controls,details,#tooltip').forEach(n=>n.remove());
  for(const n of [node,...node.querySelectorAll('*')])for(const a of [...n.attributes]){
   const name=a.name.toLowerCase(),v=a.value.trim();
   if(name.startsWith('on')||['srcdoc','srcset','action','formaction','nonce'].includes(name)||['href','xlink:href','src'].includes(name)&&!safeImage(v)&&!v.startsWith('#'))n.removeAttribute(a.name);
   if(name==='style'){n.style.removeProperty('animation');n.style.removeProperty('transition');n.style.removeProperty('behavior');n.style.removeProperty('-moz-binding')}
  }
  return node;
 }
 function cache(){return {images:new Map(),bytes:0,warnings:[]}}
 async function imageData(url,assets){
  if(safeImage(url)||url.startsWith('#'))return url;
  if(assets.images.has(url))return assets.images.get(url);
  const pending=(async()=>{
   const parsed=new URL(url,location.href);if(!['https:','http:','blob:'].includes(parsed.protocol)||parsed.username||parsed.password)throw Error('Unsupported image URL');
   const response=await fetch(parsed.href,{credentials:'omit',signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error('Image request failed');
   if(Number(response.headers.get('content-length'))>10000000)throw Error('Image exceeds 10 MB');
   const blob=await response.blob();if(blob.size>10000000||assets.bytes+blob.size>64000000)throw Error('Snapshot image budget exceeded');
   if(!/^image\//i.test(blob.type))throw Error('Response is not an image');assets.bytes+=blob.size;
   return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)});
  })();assets.images.set(url,pending);return pending;
 }
 async function freeze(source,{inlineStyles=false,frameCapture,assets=cache()}={}){
  const warningStart=assets.warnings.length;
  const clone=source.cloneNode(true),originals=[source,...source.querySelectorAll('*')],copies=[clone,...clone.querySelectorAll('*')];
  for(let i=0;i<originals.length;i++){
   const original=originals[i],copy=copies[i],computed=getComputedStyle(original);
   if(inlineStyles)for(const property of properties){const value=computed.getPropertyValue(property);if(value)copy.style.setProperty(property,value)}
   else if(computed.backgroundImage!=='none')copy.style.backgroundImage=computed.backgroundImage;
   if(original.tagName==='CANVAS'){
    try{const img=document.createElement('img');img.src=original.toDataURL();img.style.cssText=copy.style.cssText;img.width=original.width;img.height=original.height;copy.replaceWith(img)}catch{copy.replaceWith(document.createTextNode('Canvas could not be captured.'));assets.warnings.push('A canvas could not be captured.')}
   }
   if(original.tagName==='SELECT'){const label=document.createElement('span');label.textContent=[...original.selectedOptions].map(o=>o.textContent).join(', ');copy.replaceWith(label)}
  }
  for(const button of clone.querySelectorAll('button[data-snapshot-slicer]')){const label=document.createElement('span');label.textContent=button.textContent;label.style.cssText=button.style.cssText;button.replaceWith(label)}
  const frames=[...source.querySelectorAll('iframe')],frameCopies=[...clone.querySelectorAll('iframe')];
  for(let i=0;i<frames.length;i++){
   const replacement=document.createElement('div');replacement.style.cssText=frameCopies[i].style.cssText;replacement.style.minHeight='0';replacement.style.overflow='hidden';
   try{
    if(!frameCapture)throw Error('No snapshot bridge');const result=await frameCapture(frames[i]);
    if(!result?.html||result.html.length>25000000)throw Error('Invalid custom visual snapshot');
    const doc=new DOMParser().parseFromString(result.html,'text/html');sanitize(doc.body);replacement.append(...doc.body.childNodes);
    // Sandboxed visuals often reuse SVG clip-path IDs. Keep every captured instance independent.
    const prefix='snapshot-'+crypto.randomUUID()+'-',ids=new Map();for(const n of replacement.querySelectorAll('[id]')){ids.set(n.id,prefix+n.id);n.id=prefix+n.id}
    for(const n of replacement.querySelectorAll('*'))for(const attr of [...n.attributes]){let value=attr.value;for(const [old,id] of ids){value=value.split('url(#'+old+')').join('url(#'+id+')').split('url("#'+old+'")').join('url("#'+id+'")');if(value==='#'+old)value='#'+id}if(value!==attr.value)n.setAttribute(attr.name,value)}
    assets.warnings.push(...(result.warnings||[]));
   }catch(error){replacement.textContent='Custom visual could not be captured.';assets.warnings.push('Custom visual capture failed: '+String(error.message||error).slice(0,250))}
   frameCopies[i].replaceWith(replacement);
  }
  const jobs=[];
  for(const n of [clone,...clone.querySelectorAll('*')]){
   for(const attr of n.tagName?.toLowerCase()==='image'?['href','xlink:href']:n.tagName==='IMG'?['src']:[]){const url=n.getAttribute(attr);if(!url)continue;jobs.push(imageData(url,assets).then(data=>n.setAttribute(attr,data)).catch(()=>{n.removeAttribute(attr);n.setAttribute('alt',n.getAttribute('alt')||'Image unavailable in snapshot');assets.warnings.push('An image could not be embedded: '+url.split('?')[0].slice(0,180))}))}
   const background=n.style?.backgroundImage;if(background&&background!=='none')jobs.push((async()=>{let updated=background;for(const match of background.matchAll(/url\(["']?([^"')]+)["']?\)/g)){try{updated=updated.replace(match[0],'url("'+await imageData(match[1],assets)+'")')}catch{updated=updated.replace(match[0],'none');assets.warnings.push('A background image could not be embedded.')}}n.style.backgroundImage=updated})());
  }
  await Promise.all(jobs);sanitize(clone);clone.removeAttribute('id');return {html:clone.outerHTML,warnings:[...new Set(assets.warnings.slice(warningStart))]};
 }
 return {freeze,sanitize,cache,safeImage};
}
const api={create,...create()};root.SnapshotDOM=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
