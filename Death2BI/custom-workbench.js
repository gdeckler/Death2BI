(function(root){
const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
async function render({target,model,api,evaluate,page}){
 target.innerHTML='<section class="panel"><h2>Custom Power BI visuals</h2><p>Import a .pbiviz package, or use visuals embedded in your saved reports. Uploaded JavaScript runs in an isolated frame with network access off by default. <a href="/api/custom-visuals/support" target="_blank" rel="noopener">Supported host APIs and limits</a></p><label>Visual package <input id="customfile" type="file" accept=".pbiviz"></label><p id="customimportstatus" role="status"></p><label>Installed visual <select id="custompackage" aria-label="Installed custom visual"></select></label><div id="customdetails"></div><div id="customroles" style="display:flex;flex-wrap:wrap;gap:12px;margin:18px 0"></div><button id="custompreviewbutton">Render preview with selected fields</button><div id="custompreview" style="height:550px;margin-top:16px;border:1px solid #dfe7e3;border-radius:8px;overflow:hidden"></div></section>';
 const panel=target.firstElementChild,packages=await CustomVisuals.load(api);if(!target.isConnected||target.firstElementChild!==panel)return;
 const selector=target.querySelector('#custompackage');
 selector.innerHTML=packages.map(p=>'<option value="'+p.id+'">'+escape(p.name)+' · '+escape(p.version)+' · '+p.id.slice(-6)+'</option>').join('');
 const fields=model.tables.flatMap(table=>table.columns.map(column=>({label:table.name+' · '+column.name,table:table.name,column:column.name,type:column.type,field:{Column:{Expression:{SourceRef:{Entity:table.name}},Property:column.name}}})));
 fields.push(...model.measures.map(m=>({label:'Measure · '+(m.Name||m.name),type:'DOUBLE',field:{Measure:{Expression:{SourceRef:{Entity:m.TableName}},Property:m.Name||m.name}}})));
 let current;
 function choose(){
  CustomVisuals.disposeAll();target.querySelector('#custompreview').replaceChildren();
  current=packages.find(p=>p.id===selector.value);const details=target.querySelector('#customdetails'),roles=target.querySelector('#customroles');
  if(!current){details.innerHTML='<p>No packages installed yet. Import a .pbiviz file above.</p>';roles.innerHTML='';target.querySelector('#custompreviewbutton').disabled=true;return}
  target.querySelector('#custompreviewbutton').disabled=model.id==='demo';
  details.innerHTML='<p>API '+escape(current.apiVersion)+' · GUID '+escape(current.guid)+'</p>'+(current.networkDomains.length?'<label><input type="checkbox" id="customnetwork" '+(CustomVisuals.options(current.id).network?'checked':'')+'> Allow declared external resources for this package</label><p style="font-size:11px">Enabling this sends requests to: '+current.networkDomains.map(escape).join(', ')+'</p>':'<p>No external network services declared.</p>');
  const network=details.querySelector('#customnetwork');if(network)network.onchange=()=>CustomVisuals.configure(current.id,{network:network.checked});
  roles.innerHTML=(current.capabilities.dataRoles||[]).map((role,index)=>'<label style="display:flex;flex-direction:column;max-width:300px">'+escape(role.displayName||role.name)+'<select data-custom-role="'+index+'" aria-label="Custom role '+escape(role.displayName||role.name)+'"><option value="">Not assigned</option>'+fields.map((f,i)=>'<option value="'+i+'">'+escape(f.label)+'</option>').join('')+'</select></label>').join('');
 }
 selector.onchange=choose;choose();
 target.querySelector('#customfile').onchange=async event=>{const file=event.target.files[0];if(!file)return;const status=target.querySelector('#customimportstatus');status.textContent='Importing visual package…';try{const body=new FormData();body.append('file',file);const result=await api('/api/custom-visuals/import',{method:'POST',body});status.textContent='Imported '+result.name+'.';await render({target,model,api,evaluate,page});target.querySelector('#custompackage').value=result.id;target.querySelector('#custompackage').onchange()}catch(error){status.textContent=error.message}};
 target.querySelector('#custompreviewbutton').onclick=async()=>{
  const queryState={};for(const select of roles()){if(select.value==='')continue;const role=current.capabilities.dataRoles[+select.dataset.customRole],f=fields[+select.value];let field=f.field;
   if((role.kind==='Measure'||role.kind===1)&&field.Column){if(!/INT|DOUBLE|DECIMAL|FLOAT|REAL/.test(f.type))return target.querySelector('#custompreview').textContent=role.displayName+' requires a numeric field.';field={Aggregation:{Expression:field,Function:0}}}
   queryState[role.name]={projections:[{field,displayName:f.label,nativeQueryRef:f.label,queryRef:f.label}]};
  }
  const preview=target.querySelector('#custompreview');preview.className='visual';preview.style.position='relative';
  CustomVisuals.disposeAll();
  await evaluate({id:'custom-preview-'+current.id,type:current.guid,definition:{query:{queryState}}},page||{},preview);
 };
 function roles(){return target.querySelectorAll('[data-custom-role]')}
}
const api={render};if(typeof module!=='undefined')module.exports=api;root.CustomWorkbench=api;
})(globalThis);
