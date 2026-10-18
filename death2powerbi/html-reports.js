/* Standalone snapshot documents and opaque-origin imported report frames. */
(function(root){
const policy="default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' data: blob:; style-src 'unsafe-inline' data: blob:; img-src data: blob:; font-src data: blob:; media-src data: blob:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; worker-src 'none'";
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function isolatedDocument(source){return '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+escape(policy)+'">'+source}
function mount(target,source){
 const frame=document.createElement('iframe');frame.title='Imported HTML report';frame.setAttribute('sandbox','allow-scripts');frame.referrerPolicy='no-referrer';frame.style.cssText='width:100%;height:80vh;min-height:600px;border:1px solid #dce4de;background:white;border-radius:8px';frame.srcdoc=isolatedDocument(source);target.replaceChildren(frame);return frame;
}
function download(source,name){const url=URL.createObjectURL(new Blob([source],{type:'text/html;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)}
function capture(report){
 const clone=report.cloneNode(true);
 // Canvases have no serialized pixels. Preserve their current image instead.
 const canvasCopies=[...clone.querySelectorAll('canvas')];report.querySelectorAll('canvas').forEach((canvas,i)=>{const copy=canvasCopies[i];if(!copy)return;try{const image=document.createElement('img');image.src=canvas.toDataURL();image.style.cssText=canvas.style.cssText;image.width=canvas.width;image.height=canvas.height;copy.replaceWith(image)}catch{copy.replaceWith(document.createTextNode('Canvas could not be captured.'))}});
 clone.querySelectorAll('iframe').forEach(frame=>{const note=document.createElement('p');note.textContent='Custom visual: live embedded content is unavailable in this snapshot.';frame.replaceWith(note)});
 const originalSelects=[...report.querySelectorAll('select')];clone.querySelectorAll('select').forEach((select,i)=>{const label=document.createElement('span');label.textContent=[...originalSelects[i].selectedOptions].map(option=>option.textContent).join(', ');select.replaceWith(label)});
 clone.querySelectorAll('script,button,select,input,textarea,.vega-actions,.map-controls,details').forEach(node=>node.remove());
 clone.querySelectorAll('*').forEach(node=>{for(const attr of [...node.attributes]){if(/^on/i.test(attr.name)||['href','xlink:href','src','srcset'].includes(attr.name)&&!attr.value.startsWith('data:')&&!attr.value.startsWith('#'))node.removeAttribute(attr.name)}});
 clone.removeAttribute('id');return clone.outerHTML;
}
function documentFor(name,pages,css){
 if(!pages.length)throw Error('There are no report pages to export.');
 const packageData={format:'death2powerbi-snapshot',version:1,name,createdAt:new Date().toISOString(),pages};
 const bytes=new TextEncoder().encode(JSON.stringify(packageData));let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
 const encoded=btoa(binary),safeCss=css.replace(/@import[^;]*;/gi,'').replace(/url\((?![\"']?(?:data:|#))[^)]*\)/gi,'none').replace(/<\/style/gi,'<\\/style');
 return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="'+escape(policy)+'"><title>'+escape(name)+' — Snapshot</title><style>'+safeCss+'\nbody{margin:0;background:#f4f6f2}header.snapshot{padding:18px 24px;background:white;border-bottom:1px solid #dce4de}nav.snapshot{display:flex;gap:8px;flex-wrap:wrap;padding:12px 24px}main.snapshot{overflow:auto;padding:16px 24px}.snapshot-page[hidden]{display:none!important}.snapshot-page .report{position:relative;background:white;flex:none}.snapshot-page .visual{position:absolute}.snapshot-note{font-size:12px;color:#53675c}svg{max-width:100%}</style></head><body><header class="snapshot"><h1>'+escape(name)+'</h1><p class="snapshot-note">Static snapshot · '+escape(packageData.createdAt)+' · Values reflect saved page filters and selections at export. Slicers and cross-filtering are frozen. Unsupported/custom visuals may show explanatory messages. No semantic-model data is included.</p></header><nav class="snapshot">'+pages.map((p,i)=>'<button data-page="'+i+'">'+escape(p.name)+(p.hidden?' (hidden)':'')+'</button>').join('')+'</nav><main class="snapshot">'+pages.map((p,i)=>'<section class="snapshot-page"'+(i?' hidden':'')+'><h2>'+escape(p.name)+'</h2>'+p.html+'</section>').join('')+'</main><script id="death2powerbi-snapshot" type="application/octet-stream">'+encoded+'<'+ '/script><'+'script>document.querySelectorAll("nav.snapshot button").forEach((b,i)=>b.onclick=()=>document.querySelectorAll(".snapshot-page").forEach((p,j)=>p.hidden=i!==j));<'+ '/script></body></html>';
}
const api={mount,download,capture,documentFor,isolatedDocument,policy};root.HTMLReports=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
