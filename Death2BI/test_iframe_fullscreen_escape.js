const assert=require('node:assert/strict'),vm=require('node:vm'),F=require('./custom-frame'),C=require('./custom-visuals'),H=require('./html-reports');

function runtime(frames=[]){
 const listeners=new Map(),sent=[],parent={postMessage:(data,target)=>sent.push({data:JSON.parse(JSON.stringify(data)),target})};
 Object.defineProperty(parent,'document',{get(){throw Error('Opaque frames cannot read parent document')}});
 const context=vm.createContext({console:{error(){}},parent,document:{querySelectorAll:selector=>selector==='iframe'?frames:[]},addEventListener:(name,fn,capture)=>{if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push({fn,capture})}});
 return {context,sent,listeners,dispatch(name,event){for(const {fn} of listeners.get(name)||[])fn(event)}};
}
function checkKeys(instance){
 instance.sent.length=0;
 for(const key of ['a','Enter','Tab','Esc','escape','ArrowLeft',undefined])instance.dispatch('keydown',{key,code:'Escape',keyCode:27,reportData:'private'});
 assert.equal(instance.sent.length,0,'Only the Escape key requests exit');
 instance.dispatch('keydown',{key:'Escape',reportData:'private'});
 assert.deepEqual(instance.sent,[{data:{type:'death2bi-exit-fullscreen'},target:'*'}]);
 assert.equal(instance.listeners.get('keydown')[0].capture,true,'Capture handles Escape before visual key handlers stop propagation');
}

// Run the actual custom-host bootstrap, including its normal ready event.
const custom=runtime(),element={clientWidth:200,clientHeight:100},tooltip={style:{}};
custom.context.document.getElementById=id=>id==='visual'?element:tooltip;
custom.context.document.createElement=tagName=>({tagName});
custom.context.document.head={appendChild:node=>{if(node.tagName==='script')vm.runInContext(node.textContent,custom.context)}};
custom.context.ResizeObserver=class{observe(){}};custom.context.window=custom.context;
vm.runInContext('('+F.bootstrap.toString()+')('+JSON.stringify({token:'secret-token',guid:'Example',js:'window.powerbi.visuals.plugins.Example={create:()=>({update(){}})}'})+',()=>({}))',custom.context);
assert(custom.sent.some(message=>message.data.type==='ready'));checkKeys(custom);
const customDocument=F.documentFor({guid:'Example',js:''},'nonce-token');assert.match(customDocument,/death2bi-exit-fullscreen/);assert.match(customDocument,/frame-src 'none'/);assert(!customDocument.includes('allow-same-origin'));

class Node{
 constructor(name,attrs={}){this.localName=name;this.nodeType=1;this.attrs=new Map(Object.entries(attrs));this.children=[];this.textContent='';this.contentWindow=name==='iframe'?{}:undefined}
 get attributes(){return [...this.attrs].map(([name,value])=>({name,value}))}hasAttribute(name){return this.attrs.has(name)}getAttribute(name){return this.attrs.get(name)??null}setAttribute(name,value){this.attrs.set(name,String(value))}removeAttribute(name){this.attrs.delete(name)}
 appendChild(node){node.parentElement=this;this.children.push(node);return node}prepend(node){node.parentElement=this;this.children.unshift(node)}insertBefore(node,next){if(!next)return this.appendChild(node);node.parentElement=this;this.children.splice(this.children.indexOf(next),0,node)}
 get nextSibling(){return this.parentElement?.children[this.parentElement.children.indexOf(this)+1]??null}
 remove(){if(this.parentElement)this.parentElement.children.splice(this.parentElement.children.indexOf(this),1)}
 querySelectorAll(selector){const matches=node=>selector.split(',').some(part=>part==='*'||part==='meta[http-equiv]'&&node.localName==='meta'&&node.hasAttribute('http-equiv')||part===node.localName);return this.children.flatMap(node=>[...(matches(node)?[node]:[]),...node.querySelectorAll(selector)])}
 set httpEquiv(value){this.setAttribute('http-equiv',value)}set content(value){this.setAttribute('content',value)}
 get outerHTML(){return '<'+this.localName+[...this.attrs].map(([key,value])=>' '+key+'="'+value.replaceAll('&','&amp;').replaceAll('"','&quot;')+'"').join('')+'>'+this.textContent+this.children.map(node=>node.outerHTML).join('')+'</'+this.localName+'>'}
}
const oldParser=global.DOMParser,parsed=[];
global.DOMParser=class{parseFromString(source){
 const root=new Node('html'),head=root.appendChild(new Node('head')),body=root.appendChild(new Node('body'));
 if(source==='parent')body.appendChild(new Node('iframe',{srcdoc:'child'}));
 const doc={nodeType:9,documentElement:root,head,body,createElement:name=>new Node(name),querySelectorAll:selector=>root.querySelectorAll(selector)};parsed.push(doc);return doc;
}};
try{
 const source=C.htmlDocument('parent','safe-nonce'),parentDocument=parsed[0],childDocument=parsed[1];assert.equal(parsed.length,2);
 for(const doc of [parentDocument,childDocument]){
  const escape=doc.head.children.find(node=>node.localName==='script'&&node.textContent.includes('htmlEscapeBridge'));
  assert(escape,'Native HTML installs Escape handling even with no external tooltip');assert.equal(escape.getAttribute('nonce'),'safe-nonce');
  const csp=doc.head.children.find(node=>node.localName==='meta');assert(doc.head.children.indexOf(csp)<doc.head.children.indexOf(escape));assert.match(csp.getAttribute('content'),/connect-src 'none'; frame-src about:/);assert(!csp.getAttribute('content').includes('unsafe-eval'));
  const nested=doc.querySelectorAll('iframe'),native=runtime(nested);vm.runInContext(escape.textContent,native.context);checkKeys(native);native.sent.length=0;
  for(const origin of [{},null,native.context.parent])native.dispatch('message',{source:origin,data:{type:'death2bi-exit-fullscreen',secret:'private'}});
  assert.equal(native.sent.length,0,'Unrelated frame windows cannot relay Escape');
  if(nested.length){
   const frame=nested[0];assert.equal(frame.getAttribute('sandbox'),'allow-scripts');assert.equal(frame.getAttribute('referrerpolicy'),'no-referrer');
   native.dispatch('message',{source:frame.contentWindow,data:{type:'unrelated',secret:'private'}});assert.equal(native.sent.length,0);
   native.dispatch('message',{source:frame.contentWindow,data:{type:'death2bi-exit-fullscreen',secret:'private'}});assert.deepEqual(native.sent,[{data:{type:'death2bi-exit-fullscreen'},target:'*'}],'Nested opaque frames forward only a newly constructed data-free exit action');
  }
 }
 assert(source.includes('htmlEscapeBridge'));assert(!source.includes('allow-same-origin'));assert.equal(parsed[0].head.children.filter(node=>node.localName==='script').length,1);
}finally{global.DOMParser=oldParser}

// Imported standalone reports keep their original restrictive CSP and sandbox.
const standalone=H.isolatedDocument('<script>globalThis.authored=true</script>'),script=/<script>([\s\S]*?)<\/script>/.exec(standalone)[1],isolated=runtime();
vm.runInContext(script,isolated.context);checkKeys(isolated);assert(standalone.indexOf('Content-Security-Policy')<standalone.indexOf('<script>'));assert.match(H.policy,/connect-src 'none'; frame-src 'none'/);assert(standalone.endsWith('<script>globalThis.authored=true</script>'));
const oldDocument=global.document,created=[];global.document={createElement:tag=>{const node=new Node(tag);node.style={};created.push(node);return node}};
try{const target=new Node('main');target.replaceChildren=(...children)=>target.children=children;const frame=H.mount(target,'<p>Private report values</p>');assert.equal(frame.getAttribute('sandbox'),'allow-scripts');assert.equal(frame.referrerPolicy,'no-referrer');assert(!frame.srcdoc.includes('allow-same-origin'))}finally{global.document=oldDocument}
console.log('PASS Escape-only opaque custom/native/imported HTML relays, capture handling, nested frame source validation, data-free messages and unchanged CSP/sandbox isolation');
