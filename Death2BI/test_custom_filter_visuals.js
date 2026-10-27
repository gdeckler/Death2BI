const assert=require('node:assert/strict'),vm=require('node:vm');
const D=require('./custom-dataview'),C=require('./custom-visuals'),F=require('./custom-frame'),Controls=require('./report-controls'),Engine=require('./report-engine');
const field={Column:{Expression:{SourceRef:{Entity:'Weights'}},Property:'Weight Value'}},visual={id:'slider',type:'weightedDualLabelSliderExample',definition:{query:{queryState:{sliderValue:{projections:[{field,queryRef:'Weights.Weight Value',nativeQueryRef:'Sum of Weight Value'}]}}},objects:{general:[{properties:{filter:{filter:{Version:2,From:[{Name:'s',Entity:'Weights',Type:0}],Where:[{Condition:{In:{Expressions:[{Column:{Expression:{SourceRef:{Source:'s'}},Property:'Weight Value'}}],Values:[[{Literal:{Value:'0.35D'}}]]}}}]}}}}]}}};
const caps={dataRoles:[{name:'sliderValue',kind:'Grouping'}],dataViewMappings:[{categorical:{categories:{for:{in:'sliderValue'}},values:{select:[]}}}],objects:{general:{properties:{filter:{type:{filter:true}}}},extra:{properties:{filter:{type:{filter:true}}}}}},pkg={id:'slider-package',guid:visual.type,name:'Weighted slider',capabilities:caps,js:''},model={id:'report',customVisuals:[pkg],theme:{},tables:[{name:'Weights',columns:[{name:'Weight Value',type:'DOUBLE'}]}],relationships:[],measures:[]};
const saved=visual.definition.objects.general[0].properties.filter;
assert(C.isFilterVisual(visual.type,model));assert(!C.isFilterVisual('Other',model));assert(Controls.isFilterVisual(model,visual));
const initial=D.jsonFilters(visual,[saved]);assert.deepEqual(initial,[{target:{table:'Weights',column:'Weight Value'},operator:'In',values:[.35],filterType:1}]);
assert.deepEqual(D.jsonFilters(visual,D.reportFilters(visual,initial)),initial);
const basic={target:initial[0].target,operator:'NotIn',values:[.2,.4]};assert.deepEqual(D.jsonFilters(visual,D.reportFilters(visual,basic)),D.normalizeJsonFilters(visual,basic));
const range={target:initial[0].target,logicalOperator:'And',conditions:[{operator:'GreaterThanOrEqual',value:.2},{operator:'LessThan',value:.8}]};
assert.deepEqual(D.jsonFilters(visual,D.reportFilters(visual,range)),D.normalizeJsonFilters(visual,range));
const report=D.reportFilters(visual,{...initial[0],values:[.7]}),compiled=Engine.buildQuery(model,{visuals:[]},{type:'tableEx',definition:{query:{queryState:{Values:{projections:[{field}]}}}}},report);assert.match(compiled.sql,/0\.7/);
assert.throws(()=>D.reportFilters(visual,{...initial[0],target:{table:'Movies',column:'Secret'}}),/bound model column/);
assert.throws(()=>D.reportFilters(visual,{...initial[0],target:{...initial[0].target,sql:'SELECT 1'}}),/bound model column/);
assert.throws(()=>D.reportFilters(visual,{...initial[0],values:[Infinity]}),/not supported/);
assert.throws(()=>D.reportFilters(visual,{...initial[0],operator:'Between',values:[0,1]}),/not supported/);
assert.throws(()=>D.reportFilters(visual,{...initial[0],values:['a'.repeat(10001)]}),/not supported/);
const view=D.build(pkg,visual,{columns:['v0'],types:['DOUBLE'],rows:[[0],[.35],[.5],[1]]},{labels:['Sum of Weight Value'],formats:['0%']});
assert.equal(view.categorical.categories[0].source.displayName,'Weight Value');assert.equal(view.categorical.categories[0].source.queryName,'Weights.Weight Value');assert.deepEqual(view.categorical.categories[0].values,[0,.35,.5,1]);
const affected=Controls.filtersFor(model,{visuals:[visual,{id:'self',type:'slicer'},{id:'blocked',type:'slicer'}]},'self',v=>v.id==='slider'?report:[],source=>source!=='blocked');assert.deepEqual(affected,report);
assert.deepEqual(Controls.filtersFor(model,{visuals:[visual]},visual.id,()=>report,()=>true),[]);
console.log('PASS capability-driven custom filters, saved numeric state, full slider domain, bound-column validation and shared filter compilation');

// The browser embeds export controls before ReportControls is defined. Resolve
// that dependency at use time, after startup, rather than capturing undefined.
const exportContext=vm.createContext({ReportEngine:{}});
vm.runInContext(require('node:fs').readFileSync(require('node:path').join(__dirname,'visual-export.js'),'utf8'),exportContext);
exportContext.ReportControls={isFilterVisual:()=>true};
assert.doesNotThrow(()=>exportContext.VisualExport.attach({},model,{},visual,{}));
console.log('PASS browser module order and custom-filter export exclusion');

// Exercise the real sandbox bootstrap with an instrumented visual, without a browser.
const events={},messages=[],parent={postMessage:message=>messages.push(message)},element={clientWidth:400,clientHeight:50},tooltip={style:{}};
const context=vm.createContext({console,JSON,Map,Set,Math,Promise,queueMicrotask,innerWidth:400,innerHeight:50,parent,updates:[],addEventListener:(name,listener)=>events[name]=listener,ResizeObserver:class{observe(){}},document:{getElementById:id=>id==='visual'?element:tooltip,createElement:type=>({tagName:type,style:{}}),head:{appendChild:node=>{if(node.tagName==='script')vm.runInContext(node.textContent,context)}}}});context.window=context;
const config={token:'sandbox-test',filterProperties:D.filterProperties(pkg),js:'window.powerbi.visuals.plugins.testSlider={create:({host})=>{globalThis.sliderHost=host;return {update:options=>updates.push(options)}}}',guid:'testSlider'};
vm.runInContext('('+F.bootstrap.toString()+')('+JSON.stringify(config)+',()=>({}));',context);
events.message({source:parent,data:{token:config.token,type:'data',filters:initial,view:{metadata:{columns:[],objects:{}}}}});
assert.deepEqual(JSON.parse(JSON.stringify(context.updates[0].jsonFilters)),initial);
context.sliderHost.applyJsonFilter(initial[0],'general','filter',0);assert.equal(messages.at(-1).type,'filter');assert.equal(messages.at(-1).action,0);
context.sliderHost.applyJsonFilter(null,'general','filter',1);assert.deepEqual(JSON.parse(JSON.stringify(messages.at(-1).filters)),[]);
assert.throws(()=>context.sliderHost.applyJsonFilter(initial[0],'undeclared','filter',0),/not declared/);
assert.throws(()=>context.sliderHost.applyJsonFilter(initial[0],'general','filter',7),/action is not supported/);
console.log('PASS sandbox host capability checks, jsonFilters feedback, merge and removal messages');

// Exercise the parent boundary: a sandbox cannot mutate unrelated fields or inject SQL.
(async()=>{
 const listeners=new Set(),nodes=[],committed=[];global.CustomDataView=D;global.CustomFrame=F;
 global.addEventListener=(type,listener)=>{if(type==='message')listeners.add(listener)};global.removeEventListener=(type,listener)=>listeners.delete(listener);
 const frameWindow={postMessage:message=>{frameWindow.message=message}},container={isConnected:true,style:{cssText:''},replaceChildren(...children){this.children=children}};
 global.document={createElement:type=>{const node={type,style:{cssText:''},setAttribute(){},remove(){},contentWindow:type==='iframe'?frameWindow:undefined};nodes.push(node);return node}};
 const mounting=C.mount(container,pkg,visual,{columns:['v0'],types:['DOUBLE'],rows:[[0],[.35],[1]]},{labels:['Weight Value'],formats:['0%']},{api:async()=>pkg,model,filters:[saved],onFilters:filters=>committed.push(filters)});
 await new Promise(resolve=>setImmediate(resolve));const frame=nodes[0],actualToken=frame.srcdoc.match(/"token":"([^"]+)"/)[1];
 const send=(data,source=frameWindow)=>{for(const listener of [...listeners])listener({source,data:{death2custom:true,token:actualToken,...data}})};
 send({type:'ready'});assert.deepEqual(frameWindow.message.filters,initial);send({type:'finished'});await mounting;
 const change={type:'filter',objectName:'general',propertyName:'filter',action:0,filters:{...initial[0],values:[.7]}};
 send(change,{});assert.equal(committed.length,0);send(change);assert.equal(committed.length,1);assert.deepEqual(D.jsonFilters(visual,committed.at(-1))[0].values,[.7]);send(change);assert.equal(committed.length,1);
 send({...change,filters:{...initial[0],target:{table:'Private',column:'ID'}}});assert.equal(committed.length,1);assert.match(nodes[1].textContent,/bound model column/);
 send({...change,objectName:'extra',filters:{...initial[0],values:[.9]}});assert.equal(committed.length,2);
 send({...change,action:1,filters:[]});assert.equal(committed.length,3);assert.deepEqual(D.jsonFilters(visual,committed.at(-1))[0].values,[.9]);
 C.disposeAll();delete global.document;delete global.addEventListener;delete global.removeEventListener;
 console.log('PASS sandbox origin/token checks, effective-change deduplication, target rejection and property-local removal');
})().catch(error=>{console.error(error);process.exitCode=1});
