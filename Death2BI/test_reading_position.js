const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),Library=require('./report-library');
const html=fs.readFileSync(__dirname+'/dist/index.html','utf8').replace(/\r\n/g,'\n');
const section=(start,end)=>html.slice(html.indexOf(start),html.indexOf(end,html.indexOf(start)));
const functions=section('function rememberReadingPosition(){','let uploadPending=')+section('function visibleReports(){','function renderWorkspaces(){')+section('async function selectWorkspace(id){','function workspaceDialog(')+section('async function chooseReport(id,','async function refreshReports(){');
const body=section('},onSignIn:async session=>{','}});\n$(\'#ownerfilter\')').split('},onSignIn:async session=>{')[1];
async function run(position,{admin=true}={}){
 const memory=new Map(),storage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)},reports=[{id:'older',createdAt:'2020-01-01',workspaceId:'w1',ownerId:'u',summaryOnly:true},{id:'newest',createdAt:'2026-01-01',workspaceId:'w2',ownerId:'u',summaryOnly:true}],saved=[];
 const demo={id:'demo',pages:[{id:'overview'},{id:'regions'}]},user={id:'u',username:'user',isAdmin:admin};
 const context={console,Promise,accountUI:{session:{user}},authEpoch:0,reportSelectionGeneration:0,navigationReady:false,navigationKey:'',navigationQueue:Promise.resolve(),local:false,snapshotExporting:false,workspaceEmpty:false,workspaceId:'',workspaces:[{id:'w1'},{id:'w2'}],ownerFilter:'u',accountStorage:storage,localStorage:storage,library:new Library(storage),demo,model:demo,pageIndex:0,selectedTable:0,tab:'Reports',render(){},toast:m=>{throw Error(m)},CustomVisuals:{setAccount(){},async load(){}},$:()=>({}),loadWorkspaces:async()=>{},api:async(path,options)=>{
  if(path==='/api/reading-position'){if(options){saved.push(JSON.parse(options.body));return saved.at(-1)}return position}
  if(path==='/api/models?summary=1')return reports;
  return {...reports.find(r=>path.endsWith('/'+r.id)),summaryOnly:false,pages:[{id:'first'},{id:'second'},{id:'secret',hidden:true}]};
 }};
 vm.createContext(context);vm.runInContext(functions+'\nasync function signIn(session){'+body+'}',context);await context.signIn({user});await context.navigationQueue;return context;
}
(async()=>{
 let c=await run({reportId:'older',pageId:'second',workspaceId:'w1'});assert.equal(c.model.id,'older');assert.equal(c.pageIndex,1);assert.equal(c.workspaceId,'w1');
 c=await run({reportId:'older',pageId:'removed',workspaceId:'w1'});assert.equal(c.pageIndex,0);
 c=await run({reportId:'older',pageId:'secret',workspaceId:'w1'},{admin:false});assert.equal(c.pageIndex,0);
 c=await run({reportId:'deleted',pageId:'second',workspaceId:'w2'});assert.equal(c.model.id,'newest');assert.equal(c.pageIndex,0);
 console.log('PASS fresh-browser restoration, non-latest report selection, stable page IDs and deleted/hidden-page fallbacks');
})().catch(e=>{console.error(e);process.exitCode=1});
