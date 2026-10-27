(function(root){
let defaults;
function apply(settings){
 const brand=document.querySelector('.brand'),logo=brand.querySelector('.logo');
 if(!defaults)defaults={logo:logo.innerHTML,favicon:document.querySelector('link[rel="icon"]').href};
 let name=brand.querySelector('.brand-name');if(!name){name=document.createElement('span');name.className='brand-name';for(const child of [...brand.childNodes])if(child!==logo)child.remove();brand.appendChild(name)}
 name.textContent=settings.name;name.style.cssText='overflow-wrap:anywhere;min-width:0';
 document.querySelector('.subbrand').textContent=settings.slogan;
 document.querySelector('.sidebar').style.backgroundColor=settings.sidebarColor;
 const rgb=settings.sidebarColor.match(/\w\w/g).map(x=>parseInt(x,16)),light=(rgb[0]*299+rgb[1]*587+rgb[2]*114)/1000>155;
 brand.style.color=light?'#152921':'#f9fff7';document.querySelector('.subbrand').style.color=light?'#30493e':'#c1d3cb';
 logo.replaceChildren();if(settings.icon){const img=document.createElement('img');img.src=settings.icon;img.alt=settings.name+' icon';img.style.cssText='width:100%;height:100%;object-fit:contain';logo.appendChild(img)}else logo.innerHTML=defaults.logo;
 const favicon=document.querySelector('link[rel="icon"]');favicon.href=settings.icon||defaults.favicon;favicon.type=settings.icon?'image/png':'image/svg+xml';
 document.title=settings.name+' · Open analytics workbench';
}
async function render(target,api){
 target.innerHTML='<section class="panel"><h2>Application branding</h2><p>These settings apply to all users. Changes appear immediately here and when other users reload the application.</p><form><p><label>Application name <input name="appName" maxlength="80" required></label></p><p><label>Slogan <input name="slogan" maxlength="160"></label></p><p><label>Left navigation background <input name="color" type="color"></label></p><p><label>Icon and browser favicon <input name="icon" type="file" accept=".png,.jpg,.jpeg,.webp,.ico"></label></p><p>PNG, JPEG, WebP or ICO, up to 500 KB. A square image with a transparent background works best. Images are resized to 256 pixels.</p><p><img alt="Current icon" style="width:48px;height:48px;object-fit:contain"><button type="button" data-remove>Use default icon</button></p><p><label><input name="externalImages" type="checkbox"> Allow sandboxed custom visuals to load any HTTP/HTTPS image URL</label><br>Image requests go directly to the image host. Scripts and other network requests remain restricted.</p><button type="submit" class="primary">Save branding</button> <button type="button" data-reset>Restore default branding</button><p role="status"></p></form></section>';
 const form=target.querySelector('form'),status=form.querySelector('[role="status"]');let current=await api('/api/branding'),icon=current.icon;if(!defaults)apply(current);
 const show=()=>{form.elements.externalImages.checked=current.allowExternalImages===true;form.elements.appName.value=current.name;form.elements.slogan.value=current.slogan;form.elements.color.value=current.sidebarColor;form.querySelector('img').src=icon||defaults.favicon};show();
 form.querySelector('[data-remove]').onclick=()=>{icon='';form.elements.icon.value='';form.querySelector('img').src=defaults.favicon;status.textContent='Default icon selected. Save branding to apply.'};
 form.elements.icon.onchange=async()=>{const file=form.elements.icon.files[0];if(!file)return;if(file.size>500000){status.textContent='Icon must be at most 500 KB.';form.elements.icon.value='';return}icon=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});status.textContent='Icon selected. Save branding to apply.'};
 async function save(payload){status.textContent='Saving…';try{current=await api('/api/admin/branding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});icon=current.icon;apply(current);show();form.elements.icon.value='';status.textContent='Branding saved.'}catch(error){status.textContent=error.message}}
 form.onsubmit=e=>{e.preventDefault();save({name:form.elements.appName.value,slogan:form.elements.slogan.value,sidebarColor:form.elements.color.value,icon,allowExternalImages:form.elements.externalImages.checked})};
 form.querySelector('[data-reset]').onclick=()=>save({reset:true});
}
root.BrandingAdmin={apply,render};
if(typeof document!=='undefined')fetch('/api/branding').then(r=>{if(!r.ok)throw Error();return r.json()}).then(apply).catch(()=>{});
})(globalThis);
