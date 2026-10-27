/* Local group administration; membership changes are enforced on the server. */
(function(root){
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
class GroupUI{
 constructor({api}){this.api=api}
 async render(target){
  target.innerHTML='<section class="panel" id="grouppanel"><div style="display:flex;justify-content:space-between;align-items:center;gap:12px"><h2>Groups</h2><button class="primary" id="creategroup" disabled>Create group</button></div><p>Local groups contain accounts. Share a report with a group to grant its current members read access. Membership changes apply to subsequent requests.</p><div id="grouplist" role="status">Loading groups…</div></section>';
  const panel=target.firstElementChild;
  const [groups,users]=await Promise.all([this.api('/api/admin/groups'),this.api('/api/admin/accounts')]);
  if(panel!==target.firstElementChild)return;
  panel.querySelector('#creategroup').disabled=false;
  panel.querySelector('#creategroup').onclick=()=>this.edit(null,users,target);
  panel.querySelector('#grouplist').innerHTML=groups.length?'<div class="tablewrap"><table class="table"><thead><tr><th>Group</th><th>Members</th><th>Shared reports</th><th>Actions</th></tr></thead><tbody>'+groups.map(g=>'<tr><td>'+esc(g.name)+'</td><td>'+g.memberIds.length+'<br><small>'+esc(g.memberIds.map(id=>users.find(u=>u.id===id)?.username||'Unknown account').join(', '))+'</small></td><td>'+g.reportCount+'</td><td><button data-edit-group="'+g.id+'">Manage members / rename</button> <button data-delete-group="'+g.id+'">Delete group</button></td></tr>').join('')+'</tbody></table></div>':'<p>No groups yet. Create a group, then add accounts and select it in Share report.</p>';
  panel.querySelectorAll('[data-edit-group]').forEach(b=>b.onclick=()=>this.edit(groups.find(g=>g.id===b.dataset.editGroup),users,target));
  panel.querySelectorAll('[data-delete-group]').forEach(b=>b.onclick=()=>this.remove(groups.find(g=>g.id===b.dataset.deleteGroup),target));
 }
 edit(group,users,view){
  const target=document.querySelector('#modal');
  target.innerHTML='<div class="modalback"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="grouptitle"><h2 id="grouptitle">'+(group?'Manage group':'Create group')+'</h2><form id="groupform"><label style="display:block;margin-top:16px">Group name<input name="name" required maxlength="80" autocomplete="off" style="display:block;width:100%;padding:10px;margin:6px 0 16px" value="'+esc(group?.name||'')+'"></label><fieldset style="border:1px solid var(--line);border-radius:7px"><legend>Member accounts</legend><div style="max-height:230px;overflow:auto">'+users.map(u=>'<label style="display:block;padding:8px"><input type="checkbox" name="member" value="'+esc(u.id)+'" '+(group?.memberIds.includes(u.id)?'checked':'')+'> '+esc(u.username)+(u.identity?' · '+esc(u.identity.provider):'')+'</label>').join('')+'</div></fieldset><p>Removing a member revokes access granted through this group. Direct shares and other group memberships still apply.</p><p id="grouperror" role="alert"></p><div style="display:flex;justify-content:flex-end;gap:10px"><button type="button" id="cancelgroup">Cancel</button><button type="submit" class="primary">Save group</button></div></form></section></div>';
  target.querySelector('input[name="name"]').focus();target.querySelector('#cancelgroup').onclick=()=>target.replaceChildren();
  const form=target.querySelector('form');form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button[type="submit"]');button.disabled=true;
   try{await this.api(group?'/api/admin/groups/update':'/api/admin/groups',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...(group?{id:group.id}:{}),name:form.elements.name.value,memberIds:[...form.querySelectorAll('input[name="member"]:checked')].map(x=>x.value)})});target.replaceChildren();await this.render(view)}catch(error){const output=target.querySelector('#grouperror');if(output)output.textContent=error.message;button.disabled=false}
  };
 }
 remove(group,view){
  const target=document.querySelector('#modal');target.innerHTML='<div class="modalback"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="deletegrouptitle"><h2 id="deletegrouptitle">Delete group?</h2><p>Delete '+esc(group.name)+' and its report sharing grants. Accounts, reports, direct shares and other groups are kept.</p><form id="deletegroupform"><label>Type the group name to confirm<input name="confirmation" required autocomplete="off" style="display:block;width:100%;padding:10px;margin:10px 0"></label><p id="deletegrouperror" role="alert"></p><div style="display:flex;justify-content:flex-end;gap:10px"><button type="button" id="canceldeletegroup">Cancel</button><button type="submit" style="color:#a14438">Delete group</button></div></form></section></div>';
  target.querySelector('#canceldeletegroup').onclick=()=>target.replaceChildren();target.querySelector('form').onsubmit=async e=>{e.preventDefault();const form=e.target,button=form.querySelector('button[type="submit"]');button.disabled=true;try{await this.api('/api/admin/groups/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:group.id,confirmName:form.elements.confirmation.value})});target.replaceChildren();await this.render(view)}catch(error){const output=target.querySelector('#deletegrouperror');if(output)output.textContent=error.message;button.disabled=false}};
 }
}
root.GroupUI=GroupUI;
})(globalThis);
