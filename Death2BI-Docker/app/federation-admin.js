(function(root){
async function render(target,api){
 target.innerHTML='<section class="panel" style="margin-top:20px"><h2>Federated sign-in</h2><p>Configure Google and Microsoft Entra ID application registrations. Changes apply immediately to new sign-ins. Local accounts and existing report permissions remain available. Federated sign-in uses identity scopes and creates a local account stub associated with the provider identity.</p><p>Register the callback URL below in the provider portal. Client secrets are write-only: leave the secret blank to retain it. Changing a client ID requires a matching new secret. This page configures Death2BI; it does not create registrations or change consent settings in Google or Entra.</p><div id="federationforms" role="status">Loading provider settings…</div></section>';
 const host=target.querySelector('#federationforms'),info=await api('/api/admin/federation');host.replaceChildren();
 for(const name of ['google','entra']){
  const form=document.createElement('form');form.style.cssText='border-top:1px solid #dfe7e3;padding:20px 0';
  form.innerHTML='<h3>'+(name==='google'?'Google':'Microsoft Entra ID')+'</h3><p><label><input type="checkbox" name="enabled"> Enable sign-in</label></p><p><label>Application client ID <input name="clientId" type="text" autocomplete="off" style="width:min(100%,500px)"></label></p>'+(name==='entra'?'<p><label>Directory tenant ID <input name="tenantId" type="text" autocomplete="off" style="width:min(100%,500px)"></label></p>':'')+'<p><label>Client secret <input name="clientSecret" type="password" autocomplete="new-password" style="width:min(100%,500px)"></label> <span class="secretstate"></span></p><p><label>Redirect / callback URL <input name="callback" type="text" readonly style="width:min(100%,600px)"></label></p><button class="primary" type="submit">Save '+(name==='google'?'Google':'Entra ID')+' settings</button><p class="federationmessage" role="status"></p>';
  const docs=document.createElement('p');docs.className='federation-docs';docs.append('Official setup documentation (opens in a new tab): ');
  const links=name==='google'?[
   ['Create OAuth credentials and configure sign-in','https://developers.google.com/identity/openid-connect/openid-connect#settingup'],
   ['Web application redirect URLs','https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred']
  ]:[
   ['Register an application','https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app'],
   ['Create a client secret','https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials#add-a-client-secret'],
   ['Configure redirect URLs','https://learn.microsoft.com/en-us/entra/identity-platform/reply-url']
  ];
  for(const [i,[label,url]] of links.entries()){if(i)docs.append(' · ');const link=document.createElement('a');link.href=url;link.textContent=label;link.target='_blank';link.rel='noopener noreferrer';docs.appendChild(link)}
  form.querySelector('h3').after(docs);
  host.appendChild(form);const control=n=>form.elements.namedItem(n),status=form.querySelector('.federationmessage');
  function display(item){control('enabled').checked=!!item.enabled;control('clientId').value=item.clientId;if(name==='entra')control('tenantId').value=item.tenantId;control('clientSecret').value='';control('clientSecret').placeholder=item.hasSecret?'Saved secret retained when blank':'Enter client secret';control('callback').value=item.callbackUrl;form.querySelector('.secretstate').textContent=item.hasSecret?'Secret saved':'No secret saved'}display(info.providers[name]);
  form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector('button');button.disabled=true;status.textContent='Saving…';try{const saved=await api('/api/admin/federation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:name,enabled:control('enabled').checked,clientId:control('clientId').value,clientSecret:control('clientSecret').value,tenantId:name==='entra'?control('tenantId').value:''})});display(saved.providers[name]);status.textContent='Saved. New sign-ins use these settings immediately. Register the exact callback URL with the provider. Credentials are not verified against the provider until sign-in.'}catch(e){status.textContent=e.message}finally{control('clientSecret').value='';button.disabled=false}};
 }
}
root.FederationAdmin={render};
})(globalThis);
