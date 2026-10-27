const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(__dirname+'/dist/index.html','utf8');
function between(start,end){const a=html.indexOf(start),b=html.indexOf(end,a);assert(a>=0&&b>a,start);return html.slice(a,b)}
function line(start){const a=html.indexOf(start);assert(a>=0,start);return html.slice(a,html.indexOf('\n',a))}
const source=[line('function cancelVisualLoading()'),between('async function chooseReport(','\nasync function refreshReports(){'),between('async function renderReports(){','\nfunction renderReportsData('),between('function renderReportsData(','\nfunction renderFilterInspector('),line('function scheduleInteractionRender()'),line("function render(){if(tab!=='Reports')")].join('\n');
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}}
async function flush(){for(let i=0;i<12;i++)await Promise.resolve()}
function report(id='r',count=6){return {id,name:id,securityStamp:'stamp',tables:[],warnings:[],pages:[{id:'page-'+id,name:'Page '+id,width:1000,height:500,visuals:Array.from({length:count},(_,i)=>({id:id+'-'+i,type:'card',x:i*100,y:0,width:100,height:100,definition:{}}))}]}}
function harness({behavior=()=>Promise.resolve()}={}){
 const timers=new Map(),elements=new Map(),calls=[],layouts=[],events=[],invalidations=[];let serial=0;
 class Node{
  constructor(id){this.id=id;this.style={};this.classList={toggle(){}};this.isConnected=true;this.clientWidth=1000;this.parentElement={clientWidth:1000};this.textContent='';this._html=''}
  set innerHTML(value){this._html=value;if(this.id==='body'&&value.includes('id="report"')){for(const [key,node] of elements)if(key==='#report'||/^#visual\d+$/.test(key))node.isConnected=false;elements.set('#report',new Node('report'))}}
  get innerHTML(){return this._html}
  closest(){return this.parentElement}
  insertAdjacentHTML(position,value){const id=/id="(visual\d+)"/.exec(value)?.[1];if(id)elements.set('#'+id,new Node(id))}
 }
 const $=selector=>{if(!elements.has(selector))elements.set(selector,new Node(selector.slice(1)));return elements.get(selector)};
 const context=vm.createContext({AbortController,model:report(),pageIndex:0,selectedTable:0,reportRequests:new AbortController(),securityRenderGeneration:0,reportSelectionGeneration:0,authEpoch:0,workspaceEmpty:false,local:true,snapshotExporting:false,tab:'Reports',interactionTimer:undefined,accountUI:{session:{user:{isAdmin:true}}},workspaces:[],workspaceId:'',library:{add(){}},VisualQueryCache:{},visualQueryCache:{invalidate:id=>invalidations.push(id)},$,document:{querySelectorAll:()=>[]},esc:String,setTimeout:(fn,delay=0)=>{const id=++serial;timers.set(id,{fn,delay});return id},clearTimeout:id=>timers.delete(id),ReportControls:{closePopup(){}},FilterInspector:{hide(){}},ReportFullscreen:{renderBody:(body,markup)=>body.innerHTML=markup,fitCanvas(){},exit(){}},ReportStyle:{pageStyle(){},layoutTextIcons:(canvas,page)=>layouts.push({canvas,page})},CustomVisuals:{disposeAll(){}},VegaRenderer:{disposeAll(){},types:[]},ResizeObserver:class{observe(){}disconnect(){}},getComputedStyle:()=>({paddingLeft:'0',paddingRight:'0'}),rememberReadingPosition(){},hideReportTooltip:()=>events.push('hide-tooltip'),renderInteractionBar(){},renderFilterInspector(){},renderLibrary(){},renderModel:()=>events.push('model-tab'),renderSQL:()=>events.push('sql-tab'),renderCompatibility(){},evaluate:(visual,page,target,model,signal)=>{calls.push({visual,page,target,model,signal});return behavior(visual,page,target,model,signal)},api:()=>Promise.resolve({stamp:'stamp'})});
 vm.runInContext(fs.readFileSync(__dirname+'/visual-tasks.js','utf8'),context);context.visualTasks=new context.VisualTasks.TaskQueue({concurrency:3});vm.runInContext(source,context);
 return {context,timers,elements,calls,layouts,events,invalidations,$,async tick(delay=0){const batch=[...timers].filter(([,timer])=>timer.delay===delay);for(const [id,timer] of batch){timers.delete(id);timer.fn()}await flush()},async drain(){for(let i=0;timers.size&&i<30;i++)await this.tick();assert.equal(timers.size,0)}};
}
(async()=>{
 // Navigation cancels the previous view before awaiting its security stamp.
 {
  const h=harness(),previous=h.context.reportRequests,security=deferred();let securitySignal;
  previous.signal.addEventListener('abort',()=>h.events.push('previous-aborted'));
  h.context.api=(path,options)=>{assert.equal(previous.signal.aborted,true);assert.equal(path,'/api/security-context?id=r');h.events.push('security-request');securitySignal=options.signal;return security.promise};
  const rendering=h.context.renderReports();assert.equal(previous.signal.aborted,true);assert.equal(securitySignal,h.context.reportRequests.signal);assert.equal(h.context.securityRenderGeneration,1);assert(h.events.indexOf('previous-aborted')<h.events.indexOf('security-request'));
  // Leaving report pages aborts this in-flight security request immediately;
  // its late completion cannot schedule stale visuals or overwrite the new tab.
  h.context.tab='Model';h.context.render();assert.equal(securitySignal.aborted,true);assert(h.events.includes('model-tab'));
  security.resolve({stamp:'stamp'});await rendering;assert.equal(h.calls.length,0);assert.equal(h.context.visualTasks.stats().queued,0);assert.equal(h.context.tab,'Model');
 }
 // Filter changes stop obsolete work now and debounce only the replacement.
 {
  const h=harness(),previous=h.context.reportRequests;let renders=0;h.context.renderReports=()=>renders++;
  h.context.scheduleInteractionRender();assert.equal(previous.signal.aborted,true);assert.equal(renders,0);assert.deepEqual([...h.timers.values()].map(timer=>timer.delay),[75]);
  const firstScope=h.context.reportRequests;h.context.scheduleInteractionRender();assert.equal(firstScope.signal.aborted,true);assert.equal(h.timers.size,1);await h.tick(75);assert.equal(renders,1);
  h.context.scheduleInteractionRender();h.context.tab='SQL';await h.tick(75);assert.equal(renders,1,'a delayed report filter render cannot reopen another tab');
 }
 // Independent navigation cancels an old filter debounce, so it cannot restart
 // the freshly selected page a second time after that page has begun loading.
 {
  const h=harness();h.context.scheduleInteractionRender();assert.equal(h.timers.size,1);h.context.cancelVisualLoading();assert.equal(h.timers.size,0);assert.equal(h.context.interactionTimer,undefined);
 }
 // A summary-model transport can finish after ignoring AbortSignal. Its old
 // selection may neither replace the current report nor reopen Report pages.
 {
  const h=harness(),response=deferred(),original=h.context.model,previous=h.context.reportRequests;let selectionSignal,added=0;
  h.context.library.models=new Map([['slow-report',{summaryOnly:true}]]);h.context.library.add=()=>added++;
  h.context.api=(path,options)=>{assert.equal(path,'/api/models/slow-report');assert.equal(previous.signal.aborted,true);selectionSignal=options.signal;return response.promise};
  const selection=h.context.chooseReport('slow-report');assert.equal(selectionSignal.aborted,false);h.context.tab='Model';h.context.render();assert.equal(selectionSignal.aborted,true);
  response.resolve(report('slow-report'));await selection;assert.equal(added,0);assert.strictEqual(h.context.model,original);assert.equal(h.context.tab,'Model');
 }
 // Main report rendering really uses the shared three-slot task scheduler.
 // Every queued evaluate retains the old model, page, signal and element even
 // when another report reuses the same DOM IDs before that task gets a slot.
 {
  const h=harness(),original=h.context.model,page=original.pages[0],signal=h.context.reportRequests.signal;
  const rendering=h.context.renderReportsData(signal),oldTarget=h.$('#visual0');assert.equal(h.calls.length,0);assert.equal(h.context.visualTasks.stats().active,3);assert.equal(h.context.visualTasks.stats().queued,3);
  h.context.model=report('replacement');h.elements.set('#visual0',{id:'visual0',isConnected:true,style:{}});await h.tick();assert.equal(h.calls.length,3);
  assert.strictEqual(h.calls[0].target,oldTarget);assert.notStrictEqual(h.calls[0].target,h.$('#visual0'));
  for(const call of h.calls){assert.strictEqual(call.model,original);assert.strictEqual(call.page,page);assert.strictEqual(call.signal,signal)}
  await h.drain();await rendering;assert.equal(h.calls.length,6);assert.equal(h.layouts.length,1);assert.strictEqual(h.layouts[0].page,page);
 }
 // A cancelled page cannot start its queued visuals, or perform late layout,
 // while a replacement report gets the released slots without waiting on old IO.
 {
  const slow=deferred(),h=harness({behavior:(visual,page,target,model)=>model.id==='r'?slow.promise:Promise.resolve()}),old=h.context.reportRequests.signal;
  const stale=h.context.renderReportsData(old);await h.tick();assert.equal(h.calls.length,3);
  const freshSignal=h.context.cancelVisualLoading();h.context.model=report('fresh',2);const fresh=h.context.renderReportsData(freshSignal);await h.tick();await fresh;assert.equal(h.calls.filter(call=>call.model.id==='fresh').length,2);
  slow.resolve();await stale;await flush();assert.equal(h.calls.filter(call=>call.model.id==='r').length,3);assert.equal(h.layouts.length,1);assert.equal(h.layouts[0].page.id,'page-fresh');assert.equal(h.context.visualTasks.stats().active,0);assert.equal(h.context.visualTasks.stats().queued,0);
 }
 // Leaving the document cancels work and disposes its renderers. Returning
 // from BFCache must restart the view; a normal first pageshow must not do so.
 {
  const h=harness(),handlers=new Map();let vega=0,custom=0,renders=0;
  h.context.window={addEventListener:(name,handler)=>handlers.set(name,handler)};
  h.context.VegaRenderer.disposeAll=()=>vega++;h.context.CustomVisuals.disposeAll=()=>custom++;
  vm.runInContext(line("window.addEventListener('pagehide'")+line("window.addEventListener('pageshow'"),h.context);
  h.context.scheduleInteractionRender();const leaving=h.context.reportRequests.signal;assert.equal(h.timers.size,1);
  handlers.get('pagehide')();assert.equal(leaving.aborted,true);assert.equal(h.timers.size,0);assert.equal(vega,1);assert.equal(custom,1);assert(h.events.includes('hide-tooltip'));
  h.context.render=()=>renders++;handlers.get('pageshow')({persisted:false});assert.equal(renders,0);handlers.get('pageshow')({persisted:true});assert.equal(renders,1);
 }
 console.log('PASS real visual-loading UI: cancel before security fetch, tab/document departure, BFCache recovery, immediate filter cancellation/debounce, three-slot scheduler, captured view/element/signal and no stale layout.');
})().catch(error=>{console.error(error);process.exitCode=1});
