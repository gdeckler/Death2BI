const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),Style=require('./report-style');
function deferred(){let resolve;const promise=new Promise(yes=>resolve=yes);return {promise,resolve}}
class Events{
 constructor(){this.listeners=new Map()}
 addEventListener(name,fn){if(!this.listeners.has(name))this.listeners.set(name,new Set());this.listeners.get(name).add(fn)}
 removeEventListener(name,fn){this.listeners.get(name)?.delete(fn)}
 dispatchEvent(event){for(const fn of [...(this.listeners.get(event.type)||[])])fn(event)}
}
function fixture(){
 const doc=new Events(),win=new Events(),observers=[],changes=[];let disconnections=0,requests=0,exits=0;
 class Node{
  constructor(tag='div'){this.tagName=tag;this.id='';this.className='';this.children=[];this.parentElement=null;this.style={};this.attributes={};this.dataset={};this.textContent='';this.inert=false;this.focusCalls=[];this.clientWidth=1600;this.clientHeight=900;const node=this;this.classList={add(...names){const classes=new Set(node.className.split(/\s+/).filter(Boolean));for(const name of names)classes.add(name);node.className=[...classes].join(' ')},remove(...names){node.className=node.className.split(/\s+/).filter(name=>!names.includes(name)).join(' ')},contains(name){return node.className.split(/\s+/).includes(name)}}}
  get isConnected(){return this===doc.body||!!this.parentElement?.isConnected}
  contains(node){return node===this||this.children.some(child=>child.contains(node))}
  appendChild(node){if(node.parentElement)node.parentElement.removeChild(node);this.children.push(node);node.parentElement=this;return node}
  append(...nodes){for(const node of nodes)this.appendChild(node)}
  prepend(node){this.appendChild(node);this.children.splice(this.children.indexOf(node),1);this.children.unshift(node)}
  removeChild(node){if(doc.fullscreenElement&&node.contains(doc.fullscreenElement)&&node.isConnected)disconnections++;this.children.splice(this.children.indexOf(node),1);node.parentElement=null;return node}
  replaceChildren(...nodes){for(const node of [...this.children])this.removeChild(node);for(const node of nodes)this.appendChild(node)}
  replaceWith(node){const parent=this.parentElement,index=parent.children.indexOf(this);parent.removeChild(this);if(node.parentElement)node.parentElement.removeChild(node);parent.children.splice(index,0,node);node.parentElement=parent}
  remove(){this.parentElement?.removeChild(this)}
  setAttribute(name,value){this.attributes[name]=String(value);if(name==='id')this.id=String(value);if(name==='class')this.className=String(value)}
  getAttribute(name){return this.attributes[name]}
  hasAttribute(name){return Object.hasOwn(this.attributes,name)}
  removeAttribute(name){delete this.attributes[name]}
  matches(selector){return selector[0]==='#'?this.id===selector.slice(1):selector[0]==='.'?this.classList.contains(selector.slice(1)):this.tagName===selector}
  querySelectorAll(selector){const found=[];for(const child of this.children){if(child.matches(selector))found.push(child);found.push(...child.querySelectorAll(selector))}return found}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null}
  focus(options){this.focusCalls.push(options);for(let node=this;node;node=node.parentElement)if(node.inert)return;doc.activeElement=this}
  getBoundingClientRect(){return {left:200,top:100,bottom:130,width:250,height:30}}
  set innerHTML(markup){const parsed=parse(markup);this.replaceChildren(...[...parsed.children])}
  get offsetWidth(){return parseFloat(this.style.width)||0}
  get offsetHeight(){return parseFloat(this.style.height)||0}
 }
 function parse(markup){const fragment=new Node('fragment'),stack=[fragment];for(const token of markup.matchAll(/<(\/?)([a-z][\w-]*)([^>]*)>|([^<]+)/gi)){if(token[4]){stack.at(-1).textContent+=token[4];continue}if(token[1]){stack.pop();continue}const node=new Node(token[2]);for(const attribute of token[3].matchAll(/([\w-]+)="([^"]*)"/g)){const [_,key,value]=attribute;if(key==='style'){for(const piece of value.split(';')){const [name,val]=piece.split(':');if(name&&val)node.style[name.trim()]=val.trim()}}else node.setAttribute(key,value)}stack.at(-1).appendChild(node);if(!/\/$/.test(token[3])&&!['input','img','br'].includes(token[2]))stack.push(node)}return fragment}
 doc.body=new Node('body');doc.fullscreenElement=null;doc.fullscreenEnabled=true;doc.querySelector=selector=>doc.body.matches(selector)?doc.body:doc.body.querySelector(selector);doc.getElementById=id=>doc.querySelector('#'+id);doc.createTextNode=text=>Object.assign(new Node('text'),{textContent:text});doc.createElement=tag=>{const node=new Node(tag);if(tag==='template'){node.content=new Node('fragment');Object.defineProperty(node,'innerHTML',{set:markup=>node.content=parse(markup)})}return node};
 win.Event=class{constructor(type){this.type=type}};win.MutationObserver=class{constructor(fn){this.fn=fn;this.disconnected=false;observers.push(this)}observe(){}disconnect(){this.disconnected=true}};
 doc.body.innerHTML='<div class="app-chrome" id="navigation"></div><main id="body"><aside class="pages">Old pages</aside><div class="workspace"><div class="canvasbar">Old bar</div><div id="interactionbar">Old filters</div><div id="reportstage"><div id="report" style="width:1920px;height:1080px"></div></div></div></main>';
 const stage=doc.getElementById('reportstage'),canvas=doc.getElementById('report'),body=doc.getElementById('body');
 stage.requestFullscreen=async()=>{requests++;doc.fullscreenElement=stage;doc.dispatchEvent({type:'fullscreenchange'})};doc.exitFullscreen=async()=>{exits++;doc.fullscreenElement=null;doc.dispatchEvent({type:'fullscreenchange'})};
 const context=vm.createContext({document:doc,ReportStyle:Style,innerWidth:1600,innerHeight:900,setTimeout,clearTimeout});vm.runInContext(fs.readFileSync(__dirname+'/report-fullscreen.js','utf8'),context);const api=context.ReportFullscreen;
 const controller=new api.Controller({getTarget:()=>stage,document:doc,window:win,onChange:active=>changes.push(active)});
 return {doc,win,context,api,controller,stage,canvas,body,changes,Node,observers,fireObservers(){for(const observer of observers)if(!observer.disconnected)observer.fn()},get disconnections(){return disconnections},get requests(){return requests},get exits(){return exits}};
}
(async()=>{
 // Native fullscreen includes only the report stage, fits both dimensions,
 // keeps floating tooltips out of the scaled canvas and responds to native Esc.
 {
  const h=fixture(),tooltip=new h.Node();tooltip.id='vg-tooltip-element';tooltip.classList.add('visible');h.doc.body.appendChild(tooltip);assert.strictEqual(h.api.overlayHost(),h.doc.body);
  let normalFits=0;const normalFit=()=>{if(!h.controller.active()){h.canvas.style.zoom='.5';normalFits++}};h.win.addEventListener('resize',normalFit);
  await h.controller.enter();assert.equal(h.requests,1);assert.strictEqual(h.doc.fullscreenElement,h.stage);assert(h.controller.active());assert(h.stage.classList.contains('report-fullscreen-active'));assert(h.doc.body.classList.contains('report-is-fullscreen'));assert.equal(h.stage.contains(h.doc.getElementById('navigation')),false);assert.strictEqual(h.api.overlayHost(),h.stage);assert.strictEqual(tooltip.parentElement,h.stage);assert.equal(tooltip.inert,false,'a fullscreen tooltip must remain accessible after portal relocation');assert.equal(tooltip.classList.contains('visible'),false);assert.equal(Number(h.canvas.style.zoom),1600/1920);
  h.stage.clientWidth=1200;h.stage.clientHeight=500;h.win.dispatchEvent({type:'resize'});assert.equal(Number(h.canvas.style.zoom),500/1080);
  h.doc.fullscreenElement=null;h.doc.dispatchEvent({type:'fullscreenchange'});assert.equal(h.controller.active(),false);assert.strictEqual(tooltip.parentElement,h.doc.body);assert.deepEqual(h.changes,[true,false]);assert.equal(h.canvas.style.zoom,'.5');assert.equal(normalFits,1);assert.strictEqual(h.api.overlayHost(),h.doc.body);h.controller.dispose();assert.equal(h.doc.listeners.get('keydown').size,0);assert.equal(h.doc.listeners.get('fullscreenchange').size,0);assert(h.observers.every(observer=>observer.disconnected));h.win.removeEventListener('resize',normalFit);
 }
 // The native fullscreen node must never be detached/reparented during a
 // filter/page repaint, or the browser would automatically leave fullscreen.
 {
  const h=fixture();await h.controller.enter();const parent=h.stage.parentElement,oldCanvas=h.canvas;
  h.api.renderBody(h.body,'<aside class="pages">New pages</aside><div class="workspace"><div class="canvasbar">New bar</div><div id="interactionbar">New filters</div><div id="reportstage"><div id="report" style="width:1000px;height:500px"></div></div></div>');
  assert.strictEqual(h.doc.fullscreenElement,h.stage);assert.strictEqual(h.stage.parentElement,parent);assert.equal(h.disconnections,0);assert.equal(oldCanvas.isConnected,false);assert.equal(h.stage.querySelector('#report').style.width,'1000px');assert.equal(Number(h.stage.querySelector('#report').style.zoom),1.6);assert.equal(h.body.querySelector('.pages').textContent,'New pages');assert.equal(h.body.querySelector('.canvasbar').textContent,'New bar');assert.equal(h.body.querySelector('#interactionbar').textContent,'New filters');await h.controller.exit();assert.equal(h.exits,1);h.controller.dispose();
 }
 // Embedded browsers can use the canvas-only CSS viewport and Escape even
 // when native fullscreen is unavailable or its promise is rejected.
 for(const rejected of [false,true]){
  const h=fixture();if(rejected)h.stage.requestFullscreen=async()=>{throw Error('Native fullscreen denied')};else h.doc.fullscreenEnabled=false;
  await h.controller.enter();assert(h.controller.active());assert.equal(h.doc.fullscreenElement,null);assert.strictEqual(h.api.overlayHost(),h.stage);let prevented=false;h.doc.dispatchEvent({type:'keydown',key:'Escape',preventDefault(){prevented=true}});assert(prevented);assert.equal(h.controller.active(),false);assert.equal(h.doc.body.classList.contains('report-is-fullscreen'),false);assert.strictEqual(h.api.overlayHost(),h.doc.body);h.controller.dispose();
 }
 // A delayed native request cannot resurrect fullscreen after the user exits.
 {
  const h=fixture(),pending=deferred();h.stage.requestFullscreen=()=>pending.promise;const entering=h.controller.enter();assert(h.controller.active());await h.api.exit();assert.equal(h.controller.active(),false);h.doc.fullscreenElement=h.stage;h.doc.dispatchEvent({type:'fullscreenchange'});pending.resolve();await entering;assert.equal(h.doc.fullscreenElement,null);assert.equal(h.controller.active(),false);assert.equal(h.exits,1);h.controller.dispose();
 }
 // The shared dropdown slicer really portals into the fullscreen stage and
 // still commits selections; it returns to the body after fullscreen exits.
 {
  const h=fixture();h.doc.fullscreenEnabled=false;await h.controller.enter();vm.runInContext(fs.readFileSync(__dirname+'/report-controls.js','utf8'),h.context);
  const values=[],el=new h.Node();h.canvas.appendChild(el);const lit=value=>({expr:{Literal:{Value:typeof value==='string'?"'"+value+"'":String(value)}}}),visual={id:'slicer',type:'slicer',definition:{query:{queryState:{Values:{projections:[{field:{Column:{Expression:{SourceRef:{Entity:'Dim'}},Property:'Category'}}}]}}},objects:{data:[{properties:{mode:lit('Dropdown')}}],selection:[{properties:{singleSelect:lit(true)}}]}}};
  h.context.ReportControls.categoricalSlicer(el,{theme:{}},visual,['A','B'],{onChange:filters=>values.push(filters.selected)});el.querySelector('button').onclick();let popup=h.stage.querySelector('.pbi-slicer-popup');assert(popup);assert.strictEqual(popup.parentElement,h.stage);assert.equal(h.canvas.contains(popup),false);popup.querySelectorAll('input')[1].onchange();assert.deepEqual(values,['B']);assert.equal(h.stage.querySelector('.pbi-slicer-popup'),null);
  await h.controller.exit();el.querySelector('button').onclick();popup=h.doc.body.querySelector('.pbi-slicer-popup');assert.strictEqual(popup.parentElement,h.doc.body);h.context.ReportControls.closePopup();h.controller.dispose();
 }
 // Newly created native tooltip nodes are moved into the fallback viewport,
 // while removal of the host ends the presentation and releases observers.
 {
  const h=fixture();h.doc.fullscreenEnabled=false;await h.controller.enter();const tooltip=new h.Node();tooltip.id='vg-tooltip-element';tooltip.classList.add('visible');h.doc.body.appendChild(tooltip);h.fireObservers();assert.strictEqual(tooltip.parentElement,h.stage);assert.equal(tooltip.inert,false,'a fullscreen tooltip must remain accessible after portal relocation');assert.equal(tooltip.classList.contains('visible'),false);h.stage.remove();h.fireObservers();assert.equal(h.controller.active(),false);assert.equal(h.doc.body.classList.contains('report-is-fullscreen'),false);assert(h.observers.every(observer=>observer.disconnected));h.controller.dispose();
 }
 // Opaque sandbox frames cannot share an origin. Only the exact WindowProxy
 // of a current descendant frame may relay its Escape key to the parent.
 {
  const h=fixture();h.doc.fullscreenEnabled=false;await h.controller.enter();const known=new h.Node('iframe'),foreign=new h.Node('iframe'),empty=new h.Node('iframe');known.contentWindow={name:'known'};foreign.contentWindow={name:'foreign'};empty.contentWindow=null;h.stage.append(known,empty);h.doc.body.appendChild(foreign);
  const message=source=>h.win.dispatchEvent({type:'message',data:{type:'death2bi-exit-fullscreen'},origin:'null',source});
  message(foreign.contentWindow);assert(h.controller.active());message({name:'unknown'});assert(h.controller.active());message(null);assert(h.controller.active(),'a null source cannot authenticate an uninitialized iframe');
  h.win.dispatchEvent({type:'message',data:{type:'unrelated'},origin:'null',source:known.contentWindow});assert(h.controller.active());
  known.remove();message(known.contentWindow);assert(h.controller.active(),'a stale detached iframe cannot exit the new presentation');h.stage.appendChild(known);message(known.contentWindow);assert.equal(h.controller.active(),false);
  h.controller.dispose();assert.equal(h.win.listeners.get('message').size,0);
 }
 // CSS fallback must isolate keyboard focus just like native fullscreen. All
 // ancestor siblings become inert, including chrome replaced during repaint.
 {
  const h=fixture();h.doc.fullscreenEnabled=false;const navigation=h.doc.getElementById('navigation'),trigger=new h.Node('button'),preexistingInert=new h.Node(),control=new h.Node('button');navigation.appendChild(trigger);h.doc.body.appendChild(preexistingInert);preexistingInert.inert=true;h.canvas.appendChild(control);trigger.focus();
  await h.controller.enter();assert.strictEqual(h.doc.activeElement,h.stage);assert.equal(h.stage.getAttribute('tabindex'),'-1');assert.equal(h.stage.focusCalls.at(-1).preventScroll,true);
  for(const node of [navigation,h.body.querySelector('.pages'),h.body.querySelector('.canvasbar'),h.body.querySelector('#interactionbar')])assert.equal(node.inert,true);
  assert.equal(h.stage.inert,false);assert.equal(h.canvas.inert,false);control.focus();assert.strictEqual(h.doc.activeElement,control);trigger.focus();assert.strictEqual(h.doc.activeElement,control,'hidden app chrome cannot receive keyboard focus');
  h.api.renderBody(h.body,'<aside class="pages">Replacement pages</aside><div class="workspace"><div class="canvasbar">Replacement bar</div><div id="interactionbar">Replacement filters</div><div id="reportstage"><div id="report" style="width:1000px;height:500px"></div></div></div>');
  for(const selector of ['.pages','.canvasbar','#interactionbar'])assert.equal(h.body.querySelector(selector).inert,true,'replaced chrome must remain outside the focus scope');
  const newBackground=new h.Node();h.doc.body.appendChild(newBackground);h.fireObservers();assert.equal(newBackground.inert,true);
  await h.controller.exit();assert.strictEqual(h.doc.activeElement,trigger);assert.equal(trigger.focusCalls.at(-1).preventScroll,true);assert.equal(h.stage.hasAttribute('tabindex'),false);
  for(const node of [navigation,newBackground,h.body.querySelector('.pages'),h.body.querySelector('.canvasbar'),h.body.querySelector('#interactionbar')])assert.equal(node.inert,false);
  assert.equal(preexistingInert.inert,true,'existing disabled/background state must be preserved');assert.equal(h.controller.background.size,0);h.controller.dispose();
 }
 // Authored tabindex survives, and a removed entry button is not focused when
 // fullscreen exits or is disposed after a page/report replacement.
 {
  const h=fixture();h.doc.fullscreenEnabled=false;h.stage.setAttribute('tabindex','3');const trigger=new h.Node('button');h.doc.getElementById('navigation').appendChild(trigger);trigger.focus();await h.controller.enter();trigger.remove();h.controller.dispose();assert.equal(h.stage.getAttribute('tabindex'),'3');assert.equal(trigger.focusCalls.length,1);assert.equal(h.doc.getElementById('navigation').inert,false);assert.equal(h.controller.background.size,0);
 }
 console.log('PASS report fullscreen: canvas-only native/fallback, Esc and fit restoration, connected-stage repaints, popup/tooltip hosting, pending-request races and lifecycle cleanup.');
})().catch(error=>{console.error(error);process.exitCode=1});
