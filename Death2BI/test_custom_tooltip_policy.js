const assert=require('node:assert/strict'),vm=require('node:vm'),F=require('./custom-frame'),C=require('./custom-visuals');
class Node{
 constructor(name,attributes={},text='',svg=false){this.localName=name;this.tagName=name;this.nodeType=1;this.namespaceURI=svg?'http://www.w3.org/2000/svg':'http://www.w3.org/1999/xhtml';this.attrs=new Map(Object.entries(attributes));this.children=[];this.textContent=text;this.style={}}
 get attributes(){return [...this.attrs].map(([name,value])=>({name,value}))}hasAttribute(name){return this.attrs.has(name)}getAttribute(name){return this.attrs.get(name)??null}setAttribute(name,value){this.attrs.set(name,String(value))}removeAttribute(name){this.attrs.delete(name)}
 appendChild(node){node.remove();node.parentElement=this;this.children.push(node);return node}prepend(node){node.remove();node.parentElement=this;this.children.unshift(node)}insertBefore(node,next){if(!next)return this.appendChild(node);node.remove();node.parentElement=this;this.children.splice(this.children.indexOf(next),0,node)}remove(){if(this.parentElement){const list=this.parentElement.children;list.splice(list.indexOf(this),1);this.parentElement=null}}
 get nextSibling(){return this.parentElement?.children[this.parentElement.children.indexOf(this)+1]??null}
 querySelectorAll(selector){const matches=node=>selector.split(',').some(part=>part==='*'||part==='[title]'&&node.hasAttribute('title')||part==='[aria-labelledby]'&&node.hasAttribute('aria-labelledby')||part==='svg title'&&node.localName==='title'&&node.namespaceURI.includes('svg')||part==='meta[http-equiv]'&&node.localName==='meta'&&node.hasAttribute('http-equiv')||node.localName===part);return this.children.flatMap(node=>[...(matches(node)?[node]:[]),...node.querySelectorAll(selector)])}
 set httpEquiv(value){this.setAttribute('http-equiv',value)}set content(value){this.setAttribute('content',value)}
 get outerHTML(){return '<'+this.localName+[...this.attrs].map(([key,value])=>' '+key+'="'+value.replaceAll('&','&amp;').replaceAll('"','&quot;')+'"').join('')+'>'+this.textContent+this.children.map(node=>node.outerHTML).join('')+'</'+this.localName+'>'}
}
function documentFixture(nested=false){
 const root=new Node('html'),head=root.appendChild(new Node('head')),body=root.appendChild(new Node('body'));
 const doc={nodeType:9,documentElement:root,head,body,querySelectorAll:selector=>root.querySelectorAll(selector),createElement:name=>new Node(name)};
 head.appendChild(new Node('title',{},'Document title'));head.appendChild(new Node('script',{},'/* authored script */'));
 const label=body.appendChild(new Node('span',{title:'Default data 70'},'Visible text'));
 const accessible=body.appendChild(new Node('span',{title:'Supplemental data','aria-label':'Original accessible name'},'Other visible text'));
 const svg=body.appendChild(new Node('svg',{},'',true));svg.appendChild(new Node('title',{},'SVG default tooltip',true));svg.appendChild(new Node('text',{},'Visible chart title',true));
 if(nested)body.appendChild(new Node('iframe',{srcdoc:'child'}));
 return {doc,label,accessible,svg};
}
const sample=documentFixture();let observer;
const oldObserver=global.MutationObserver;global.MutationObserver=class{constructor(fn){this.callback=fn;observer=this}observe(target,options){this.target=target;this.options=options}disconnect(){this.disconnected=true}};
try{
 const cleanup=F.suppressNativeTooltips(sample.doc);assert.equal(sample.label.hasAttribute('title'),false);assert.equal(sample.label.getAttribute('aria-label'),'Default data 70');assert.equal(sample.accessible.getAttribute('aria-label'),'Original accessible name');assert.equal(sample.accessible.getAttribute('aria-description'),'Supplemental data');assert.equal(sample.svg.getAttribute('aria-label'),'SVG default tooltip');assert.equal(sample.svg.querySelectorAll('svg title').length,0);assert.equal(sample.svg.children[0].textContent,'Visible chart title');assert.equal(sample.doc.head.children[0].textContent,'Document title');
 sample.label.setAttribute('title','Repainted after sort');observer.callback([{type:'attributes',target:sample.label}]);assert.equal(sample.label.hasAttribute('title'),false);assert.equal(sample.label.getAttribute('aria-label'),'Repainted after sort','generated accessible value follows repaint');
 const fresh=new Node('span',{title:'Late node'},'Late content');sample.doc.body.appendChild(fresh);observer.callback([{type:'childList',addedNodes:[fresh]}]);assert.equal(fresh.hasAttribute('title'),false);assert.equal(fresh.getAttribute('aria-label'),'Late node');
 const freshTitle=sample.svg.appendChild(new Node('title',{},'Updated SVG tooltip',true));observer.callback([{type:'childList',addedNodes:[freshTitle]}]);assert.equal(sample.svg.querySelectorAll('svg title').length,0);cleanup();assert.equal(observer.disconnected,true);
}finally{global.MutationObserver=oldObserver}
const named=documentFixture();named.svg.children[0].setAttribute('id','nativeTitle');named.svg.setAttribute('aria-labelledby','nativeTitle');F.suppressNativeTooltips(named.doc,false);assert.equal(named.svg.hasAttribute('aria-labelledby'),false);assert.equal(named.svg.getAttribute('aria-label'),'SVG default tooltip','a removed title must not leave a dangling accessible-name reference');
const combined=documentFixture();combined.svg.children[0].setAttribute('id','nativeTitle');combined.svg.children[1].setAttribute('id','caption');combined.svg.setAttribute('aria-labelledby','caption nativeTitle');F.suppressNativeTooltips(combined.doc,false);assert.equal(combined.svg.getAttribute('aria-labelledby'),'caption');assert.equal(combined.svg.getAttribute('aria-description'),'SVG default tooltip','unaffected accessible references remain and removed title text stays available');
const twoNativeTitles=documentFixture();twoNativeTitles.svg.setAttribute('title','Native attribute tooltip');twoNativeTitles.svg.children[0].setAttribute('id','nativeTitle');twoNativeTitles.svg.setAttribute('aria-labelledby','nativeTitle');F.suppressNativeTooltips(twoNativeTitles.doc,false);assert.equal(twoNativeTitles.svg.getAttribute('aria-label'),'SVG default tooltip','accessible name survives simultaneous title attribute and referenced SVG-title removal');

function sandbox(policy){
 const fixture=documentFixture(),tooltip={style:{display:'none'},children:[],replaceChildren(){this.children=[]},appendChild(node){this.children.push(node)}},events={},messages=[],parent={postMessage:message=>messages.push(message)};let suppressed=0,cleaned=0;
 const document={...fixture.doc,getElementById:id=>id==='visual'?{clientWidth:200,clientHeight:100}:tooltip,createElement:name=>({tagName:name,style:{}}),head:{appendChild:node=>{if(node.tagName==='script')vm.runInContext(node.textContent,context)}}};
 const context=vm.createContext({console,JSON,Map,Set,Math,Promise,queueMicrotask,innerWidth:200,innerHeight:100,parent,document,addEventListener:(name,fn)=>events[name]=fn,ResizeObserver:class{observe(){}}});context.window=context;
 const config={token:'test',guid:'Test',...policy,js:'window.powerbi.visuals.plugins.Test={create:({host})=>{globalThis.host=host;return {update(){}}}}'};
 context.removeTitles=target=>{suppressed++;F.suppressNativeTooltips(target,false);return ()=>cleaned++};
 vm.runInContext('('+F.bootstrap.toString()+')('+JSON.stringify(config)+',()=>({}),removeTitles)',context);
 const service=context.host.tooltipService,options={identities:[{rows:[0]}],dataItems:[{displayName:'Value',value:'70'}],coordinates:[10,20]};service.show(options);service.move(options);
 return {tooltip,events,parent,messages,service,fixture,suppressed,cleanup(){events.message({source:parent,data:{token:'test',type:'destroy'}});return cleaned}};
}
const ordinary=sandbox({});assert.equal(ordinary.service.enabled(),true);assert.equal(ordinary.tooltip.style.display,'block');assert.equal(ordinary.fixture.label.hasAttribute('title'),true);assert.equal(ordinary.suppressed,0);assert.equal(ordinary.messages.some(message=>message.type==='tooltip'),false);
const external=sandbox({reportTooltip:true});assert.equal(external.service.enabled(),true);assert.equal(external.tooltip.style.display,'none');assert.ok(external.messages.some(message=>message.type==='tooltip'&&message.rows[0]===0));assert.equal(external.fixture.label.hasAttribute('title'),false);assert.equal(external.cleanup(),1);
const disabled=sandbox({reportTooltip:true,tooltipEnabled:false});assert.equal(disabled.service.enabled(),false);assert.equal(disabled.tooltip.style.display,'none');assert.equal(disabled.messages.some(message=>message.type==='tooltip'),false);assert.equal(disabled.fixture.label.hasAttribute('title'),false);disabled.service.hide();assert.equal(disabled.messages.some(message=>message.type==='tooltipLeave'),false);
assert.match(F.documentFor({guid:'Example',js:''},'token',false,{},[],false,false,false),/"tooltipEnabled":false/);assert.match(F.documentFor({guid:'Example',js:''},'token'),/"tooltipEnabled":true/);

// Exercise native HTML and nested-srcdoc document transformation without a browser.
const parsed=[],oldParser=global.DOMParser;global.DOMParser=class{parseFromString(content){const fixture=documentFixture(content==='parent');parsed.push(fixture);return fixture.doc}};
try{
 const html=C.htmlDocument('parent','nonce',0,{frames:0},true);assert.equal(parsed.length,2);for(const fixture of parsed){assert.equal(fixture.label.hasAttribute('title'),false);assert.equal(fixture.svg.querySelectorAll('svg title').length,0);const policy=fixture.doc.head.children.findIndex(node=>node.localName==='meta'),suppression=fixture.doc.head.children.findIndex(node=>node.localName==='script'&&node.textContent.includes('suppressNativeTooltips'));assert.ok(suppression>policy,'CSP precedes trusted suppression script');assert.equal(fixture.doc.head.children[suppression].getAttribute('nonce'),'nonce')}
 assert.ok(html.includes('Visible chart title'));assert.ok(html.includes('Document title'));assert.ok(html.includes('suppressNativeTooltips'));parsed.length=0;C.htmlDocument('ordinary','nonce');assert.equal(parsed[0].label.hasAttribute('title'),true,'ordinary native HTML retains its authored default titles');
}finally{global.DOMParser=oldParser}
console.log('PASS exclusive external/disabled sandbox tooltips, ordinary host fallback, durable HTML/SVG title suppression, accessibility, cleanup and nested native-HTML CSP injection');

(async()=>{
 const keys=['document','CustomFrame','CustomDataView','addEventListener','removeEventListener'],before=Object.fromEntries(keys.map(key=>[key,global[key]])),listeners=new Set(),created=[];
 global.CustomFrame=F;global.CustomDataView={build:()=>({metadata:{columns:[],objects:{}}}),filterProperties:()=>[]};global.addEventListener=(type,fn)=>{if(type==='message')listeners.add(fn)};global.removeEventListener=(type,fn)=>listeners.delete(fn);
 global.document={createElement:type=>{const node={style:{},setAttribute(){},remove(){},clientWidth:200,getBoundingClientRect:()=>({left:0,top:0,width:200,height:100}),contentWindow:type==='iframe'?{postMessage(){}}:undefined};created.push(node);return node}};
 try{
  for(const enabled of [false,true]){
   let hovers=0,leaves=0;const container={isConnected:true,style:{cssText:''},replaceChildren(){}},pkg={id:'policy-'+enabled,guid:'Test',name:'Example',capabilities:{},js:''},start=created.length;
   const mounting=C.mount(container,pkg,{id:'visual',type:'Test',definition:{}},{rows:[[70]]},{labels:['Value'],roles:['Y']},{api:async()=>pkg,model:{id:'report',theme:{}},tooltip:enabled?undefined:false,onHover:()=>hovers++,onLeave:()=>leaves++});
   await new Promise(resolve=>setImmediate(resolve));const frame=created[start],token=/"token":"([^"]+)"/.exec(frame.srcdoc)[1],send=data=>{for(const listener of listeners)listener({source:frame.contentWindow,data:{death2custom:true,token,...data}})};
   send({type:'ready'});send({type:'finished'});await mounting;send({type:'tooltip',rows:[0],coordinates:[10,20]});send({type:'tooltipLeave'});
   assert.equal(hovers,enabled?1:0);assert.equal(leaves,enabled?1:0);assert.ok(frame.srcdoc.includes('"tooltipEnabled":'+enabled));assert.ok(frame.srcdoc.includes('"reportTooltip":'+enabled));C.disposeAll();assert.equal(listeners.size,0);
  }
 }finally{C.disposeAll();for(const key of keys){if(before[key]===undefined)delete global[key];else global[key]=before[key]}}
 console.log('PASS parent custom-frame mounting forwards disabled/external policy and suppresses callbacks when disabled');
})().catch(error=>{console.error(error);process.exitCode=1});
