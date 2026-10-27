const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const PublicLinks=require('./public-links-ui.js');
const ServerAdmin=require('./server-admin.js');
async function main(){
 const markup=PublicLinks.table([{id:'id',reportName:'<script>',created_name:'<admin>',created_at:1,visits:2,last_seen_at:null,expires_at:null,removed_at:null}]);
 assert(markup.includes('&lt;script&gt;'));assert(markup.includes('&lt;admin&gt;'));assert(markup.includes('Remove public link'));assert(markup.includes('Active'));
 const removed=PublicLinks.table([{id:'id',reportName:'Report',created_name:'admin',created_at:1,visits:0,removed_at:2}]);assert(removed.includes('Removed'));assert(!removed.includes('data-remove-public'));
 const nodes={};for(const id of ['addressstatus','serverdomain','serverport','serverbind','serverscheme','publicport','addressmessage'])nodes['#'+id]={value:'',textContent:''};
 const button={disabled:false};nodes.form={querySelector:()=>button};
 const target={innerHTML:'',querySelector:key=>nodes[key]};
 const info={domain:'localhost',port:8765,scheme:'http',publicPort:8766,bindAddress:'0.0.0.0',activePort:8765,activeBindAddress:'0.0.0.0',pendingOrigin:'http://localhost:8766'};
 let submitted;
 await ServerAdmin.render(target,async(url,options)=>{assert.equal(url,'/api/admin/server-address');if(!options)return info;submitted=JSON.parse(options.body);return{...submitted,pendingOrigin:'https://reports.example.com'}});
 assert.equal(nodes['#publicport'].value,8766);assert(target.innerHTML.includes('Sharing domain name'));assert(target.innerHTML.includes('immediately'));
 nodes['#serverdomain'].value='reports.example.com';nodes['#serverscheme'].value='https';nodes['#publicport'].value='443';
 await nodes.form.onsubmit({preventDefault(){},target:nodes.form});
 assert.deepEqual(submitted,{domain:'reports.example.com',scheme:'https',publicPort:443,port:8765,bindAddress:'0.0.0.0'});
 assert(nodes['#addressmessage'].textContent.includes('No restart is needed'));assert(nodes['#addressstatus'].textContent.includes('https://reports.example.com'));assert(!button.disabled);
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8').replace(/\r\n/g,'\n');
 for(const [marker,file] of [['PUBLIC LINKS UI','public-links-ui.js'],['SERVER ADMIN','server-admin.js']])assert.equal(html.split('/* '+marker+' START */\n')[1].split('\n/* '+marker+' END */')[0],fs.readFileSync(path.join(__dirname,file),'utf8').replace(/\r\n/g,'\n').trimEnd());
 assert(html.includes("headers.set('X-Report-Link',publicToken)"));assert(html.includes("credentials:publicToken?'omit':'same-origin'"));assert(html.includes('accountUI.session.user.publicLink||!model'));
 console.log('PASS public-link escaping, revocation controls, immediate sharing-domain updates and embedded UI consistency');
}
main().catch(error=>{console.error(error);process.exitCode=1});
