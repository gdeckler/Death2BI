const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(__dirname+'/dist/index.html','utf8'),start=html.indexOf('async function downloadCurrentReport(){'),end=html.indexOf('\nfunction pick()',start);
assert(start>0&&end>start);assert.match(html,/<button id="downloadreport"[^>]*>Download report<\/button>/);
function harness(){
 const button={disabled:false},links=[],messages=[],requests=[],model={id:'original',name:'El séptimo arte.pbix'};
 const context=vm.createContext({local:true,workspaceEmpty:false,model,encodeURIComponent,$:id=>{assert.equal(id,'#downloadreport');return button},toast:text=>messages.push(text),api:async url=>{requests.push(url);return {url:'/api/reports/original/download',filename:model.name}},document:{createElement:tag=>{assert.equal(tag,'a');const link={click(){this.clicked=true},remove(){this.removed=true}};links.push(link);return link},body:{appendChild:link=>{link.appended=true}}}});
 vm.runInContext(html.slice(start,end),context);return {context,button,links,messages,requests};
}
(async()=>{
 const h=harness();await h.context.downloadCurrentReport();assert.deepEqual(h.requests,['/api/reports/original/download-info']);assert.equal(h.links[0].download,'El séptimo arte.pbix');assert.equal(h.links[0].href,'/api/reports/original/download');assert(h.links[0].clicked&&h.links[0].appended&&h.links[0].removed);assert.equal(h.button.disabled,false);
 for(const flag of ['local','workspaceEmpty','demo']){const x=harness();if(flag==='local')x.context.local=false;else if(flag==='workspaceEmpty')x.context.workspaceEmpty=true;else x.context.model={id:'demo'};await x.context.downloadCurrentReport();assert.equal(x.requests.length,0);assert.equal(x.links.length,0)}
 const failure=harness();failure.context.api=async()=>{throw Error('The original uploaded file is unavailable.')};await failure.context.downloadCurrentReport();assert.equal(failure.links.length,0);assert.match(failure.messages[0],/unavailable/);assert.equal(failure.button.disabled,false);
 const pending=harness();let finish;pending.context.api=url=>{pending.requests.push(url);return new Promise(resolve=>finish=resolve)};const task=pending.context.downloadCurrentReport();assert.equal(pending.button.disabled,true);pending.context.model={id:'demo'};finish({url:'/api/reports/original/download',filename:'El séptimo arte.pbix'});await task;assert.equal(pending.links[0].download,'El séptimo arte.pbix');assert.equal(pending.button.disabled,true,'completion must respect the newly selected report state');
 console.log('PASS original report download: native attachment/Unicode name, selected report identity, no Blob/full-file fetch, disabled example/empty/offline states and actionable errors.');
})().catch(error=>{console.error(error);process.exitCode=1});
