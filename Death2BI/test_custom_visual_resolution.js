const assert=require('node:assert/strict');
const Custom=require('./custom-visuals');

(async()=>{
 const guid='wishyoulizationwalkers';
 const stale={id:'a'.repeat(32),guid,name:'Earlier library version',capabilities:{dataRoles:[]}};
 const authored={id:'b'.repeat(32),guid,name:'Authorized report version',capabilities:{dataRoles:[{name:'category'}]}};
 const model={customVisuals:[authored]},before=structuredClone(model);
 Custom.setAccount('resolution-fixture');
 assert.equal(Custom.resolve(guid,model),authored,'a package attached after login must render without reloading the visual library');
 assert.equal(Custom.resolve(guid,{}),undefined,'missing metadata must not invent a package');
 const api=async path=>path==='/api/branding'?{}:path==='/api/custom-visuals'?[stale]:[];
 await Custom.load(api);
 assert.equal(Custom.resolve(guid,model),authored,'the report package wins over another build sharing its GUID');
 assert.equal(Custom.resolve(guid,{}),stale,'library-only discovery remains supported');
 const exact={...authored,name:'Loaded exact report package'};
 await Custom.load(async path=>path==='/api/branding'?{}:path==='/api/custom-visuals'?[stale,exact]:[]);
 assert.equal(Custom.resolve(guid,model),exact,'use already loaded metadata for the exact content identity');
 assert.deepEqual(model,before,'resolution must preserve report metadata');
 assert.equal(Custom.resolve('htmlContent',model).nativeHtml,true,'native HTML rendering retains priority');
 Custom.setAccount('another-resolution-fixture');
 assert.equal(Custom.resolve(guid,{}),undefined,'account changes clear library references');
 assert.equal(Custom.resolve(guid,model),authored,'authorized report metadata is independently usable after a library reset');
 // Mount still fetches through the authenticated API rather than treating
 // metadata as executable content or bypassing a revoked package permission.
 const paths=[];
 await assert.rejects(Custom.mount({isConnected:true},authored,{id:'v'}, {rows:[]}, {},{
  model:{id:'report'},api:async path=>{paths.push(path);throw Error('Visual package not found.');}
 }),/Visual package not found/);
 assert.deepEqual(paths,['/api/custom-visuals/'+authored.id]);
 console.log('PASS: authorized report metadata survives missing/stale libraries, exact package identity wins, account reset and fetch authorization remain enforced');
})().catch(error=>{console.error(error);process.exitCode=1;});
