(function(root){
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=value=>value?new Date(value*1000).toLocaleString():'—';
class InvitationUI{
 constructor({api,account,onAccepted}){
  this.api=api;this.account=account;this.onAccepted=onAccepted;
  const params=new URLSearchParams(location.hash.slice(1));
  try{if(params.has('invite'))sessionStorage.setItem('d2pbi.invitation',params.get('invite'));this.token=sessionStorage.getItem('d2pbi.invitation')||''}catch{this.token=params.get('invite')||''}
  this.accepted=params.get('accepted');this.error=params.get('auth-error');
  if(this.accepted){this.clearToken()}
  if(params.has('invite')||params.has('accepted')||params.has('auth-error')||params.has('signed-in'))history.replaceState(null,'',location.pathname);
 }
 clearToken(){this.token='';try{sessionStorage.removeItem('d2pbi.invitation')}catch{}}
 async loginOptions(target){
  const section=document.createElement('section');target.querySelector('main > section').appendChild(section);
  if(this.error){const p=document.createElement('p');p.textContent=this.error;section.appendChild(p)}
  if(this.token){const p=document.createElement('p');p.textContent='You have a single-use report invitation. Sign in with an existing account or a configured identity provider to continue.';section.appendChild(p)}
  try{
   const config=await this.api('/api/auth/providers');if(!section.isConnected)return;
   for(const [provider,label] of [['entra','Microsoft Entra ID'],['google','Google']]){
    const button=document.createElement('button');button.type='button';button.textContent='Sign in with '+label;button.style.cssText='display:block;width:100%;margin-top:10px';button.disabled=!config.providers.includes(provider);button.title=button.disabled?'An administrator must configure this provider.':'';
    button.onclick=()=>this.start(provider,button);section.appendChild(button);
   }
  }catch(error){const p=document.createElement('p');p.textContent='Federated sign-in is unavailable: '+error.message;section.appendChild(p)}
 }
 async start(provider,button){
  button.disabled=true;
  try{const result=await this.api('/api/auth/oidc/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,invitation:this.token||undefined})});location.assign(result.url)}catch(error){button.disabled=false;alert(error.message)}
 }
 async afterSignIn(){
  if(this.accepted){const id=this.accepted;this.accepted=null;await this.onAccepted(id);return}
  if(!this.token)return;
  const target=document.querySelector('#modal'),token=this.token;
  try{
   const info=await this.api('/api/auth/invite-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
   target.innerHTML='<div class="modalback"><section class="modal" role="dialog" aria-modal="true" aria-label="Accept report invitation"><h2>Report invitation</h2><p>'+esc(info.reportName)+'</p><p>Accept as <strong>'+esc(this.account().session.user.username)+'</strong>? This link grants this account access to the complete report model and can only be used once.</p><p id="inviteerror" role="alert"></p><button id="acceptinvite" class="primary">Accept invitation</button> <button id="dismissinvite">Later</button></section></div>';
   target.querySelector('#dismissinvite').onclick=()=>target.replaceChildren();
   target.querySelector('#acceptinvite').onclick=async()=>{const button=target.querySelector('#acceptinvite');button.disabled=true;try{const result=await this.api('/api/invitations/redeem',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});this.clearToken();target.replaceChildren();await this.onAccepted(result.reportId)}catch(error){if(target.querySelector('#inviteerror'))target.querySelector('#inviteerror').textContent=error.message;button.disabled=false}};
  }catch(error){this.clearToken();target.innerHTML='<div class="modalback"><section class="modal"><h2>Invitation unavailable</h2><p>'+esc(error.message)+'</p><button id="closeinvite">Close</button></section></div>';target.querySelector('#closeinvite').onclick=()=>target.replaceChildren()}
 }
 table(rows){return '<div class="tablewrap"><table class="table"><thead><tr><th>Report / Link ID</th><th>Created by / at</th><th>Status / used by</th><th>Expires</th><th>Actions</th></tr></thead><tbody>'+rows.map(r=>'<tr><td>'+esc(r.reportName)+'<br><small>'+esc(r.id)+'</small></td><td>'+esc(r.created_name)+'<br>'+esc(date(r.created_at))+'</td><td>'+esc(r.used_at?'Used by '+r.used_name+' · '+date(r.used_at):r.expires_at<Date.now()/1000?'Expired':'Unused')+(r.removed_at?'<br>Removed '+esc(date(r.removed_at)):'')+'</td><td>'+esc(date(r.expires_at))+'</td><td>'+(r.removed_at?'—':'<button data-remove-invitation="'+esc(r.id)+'">Remove link</button>')+'</td></tr>').join('')+'</tbody></table></div>'}
 wireRemoval(target,reload){target.querySelectorAll('[data-remove-invitation]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await this.api('/api/invitations/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:button.dataset.removeInvitation})});await reload()}catch(error){button.disabled=false;alert(error.message)}})}
 async reportDialog(report){
  const target=document.querySelector('#modal');
  target.innerHTML='<div class="modalback"><section class="modal" role="dialog" aria-modal="true" aria-label="Report invitation links"><button class="close" id="closelinks">×</button><h2>Invitation links</h2><p>'+esc(report.name)+'</p><p>Each link can be claimed by one signed-in account. Opening it alone does not use it. Removing a used link retains its audit record; revoke the recipient in Share report to remove their report access.</p><label>Expires in <select id="invitehours"><option value="24">1 day</option><option value="168" selected>7 days</option><option value="720">30 days</option></select></label> <button class="primary" id="createlink">Generate single-use link</button><div id="newlink" role="status"></div><p id="linkerror" role="alert"></p><div id="reportlinks">Loading links…</div></section></div>';
  const panel=target.firstElementChild;
  target.querySelector('#closelinks').onclick=()=>target.replaceChildren();
  const reload=async()=>{const rows=await this.api('/api/reports/'+report.id+'/invitations');if(target.firstElementChild!==panel)return;target.querySelector('#reportlinks').innerHTML=this.table(rows);this.wireRemoval(target.querySelector('#reportlinks'),reload)};
  target.querySelector('#createlink').onclick=async()=>{const button=target.querySelector('#createlink');button.disabled=true;try{const result=await this.api('/api/reports/'+report.id+'/invitations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hours:Number(target.querySelector('#invitehours').value)})});if(target.firstElementChild!==panel)return;target.querySelector('#newlink').innerHTML='<p>Copy this link now. Its secret is only shown once.</p><textarea aria-label="Generated sharing link" readonly style="min-height:85px"></textarea>';target.querySelector('#newlink textarea').value=result.url;await reload()}catch(error){if(target.querySelector('#linkerror'))target.querySelector('#linkerror').textContent=error.message}finally{button.disabled=false}};
  try{await reload()}catch(error){if(target.querySelector('#linkerror'))target.querySelector('#linkerror').textContent=error.message}
 }
 async adminSection(panel){
  const section=document.createElement('section');section.innerHTML='<h3>All sharing links</h3><p>Includes unused, used, expired and removed invitations across all report owners.</p><div>Loading links…</div>';panel.appendChild(section);
  const reload=async()=>{const rows=await this.api('/api/admin/invitations');if(!section.isConnected)return;section.querySelector('div').innerHTML=this.table(rows);this.wireRemoval(section,reload)};
  try{await reload()}catch(error){section.querySelector('div').textContent=error.message}
 }
}
root.InvitationUI=InvitationUI;if(typeof module!=='undefined')module.exports=InvitationUI;
})(globalThis);
