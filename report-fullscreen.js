/* Canvas-only presentation, with native fullscreen when the browser permits it. */
(function(root){
'use strict';
let controller;
function overlayHost(){const doc=root.document;return doc?.querySelector('.report-fullscreen-active')||(['reportstage','htmlreportviewer'].includes(doc?.fullscreenElement?.id)?doc.fullscreenElement:doc?.body)}
function fitCanvas(canvas){
 if(!canvas)return;const host=canvas.parentElement;
 if(!host?.classList?.contains('report-fullscreen-active')&&root.document?.fullscreenElement!==host)return;
 const width=parseFloat(canvas.style.width)||canvas.offsetWidth,height=parseFloat(canvas.style.height)||canvas.offsetHeight;
 if(width>0&&height>0)canvas.style.zoom=String(Math.min(host.clientWidth/width,host.clientHeight/height));
}
function renderBody(body,markup){
 const host=overlayHost();
 if(host?.id==='reportstage'&&body.contains(host)){
  // Keep the fullscreen element connected while filters/bookmarks replace its
  // canvas. Detaching the fullscreen element would make the browser exit.
  const template=root.document.createElement('template');template.innerHTML=markup;
  const canvas=template.content.querySelector('#report');
  if(canvas){
   for(const selector of ['.pages','.canvasbar','#interactionbar']){
    const previous=body.querySelector(selector),next=template.content.querySelector(selector);
    if(previous&&next)previous.replaceWith(next);
   }
   host.replaceChildren(canvas);fitCanvas(canvas);controller?.update();return;
  }
 }
 body.innerHTML=markup;
}
class Controller{
 constructor({getTarget,onChange=()=>{},document=root.document,window=root}={}){
  this.getTarget=getTarget;this.onChange=onChange;this.doc=document;this.win=window;this.host=null;this.native=false;this.generation=0;this.background=new Map();
  this.changed=()=>{if(this.host&&this.doc.fullscreenElement===this.host){this.native=true;this.update()}else if(this.native)this.reset()};
  this.key=event=>{if(event.key==='Escape'&&this.host){event.preventDefault();this.exit()}};
  this.message=event=>{if(event.source&&event.data?.type==='death2bi-exit-fullscreen'&&this.host&&[...this.host.querySelectorAll('iframe')].some(frame=>frame.contentWindow===event.source))this.exit()};
  this.resize=()=>this.update();this.doc.addEventListener('fullscreenchange',this.changed);this.doc.addEventListener('keydown',this.key);this.win.addEventListener('resize',this.resize);this.win.addEventListener('message',this.message);
  controller=this;
 }
 active(){return !!this.host}
 blockBackground(){
  // Fallback presentation must also keep keyboard focus out of hidden chrome.
  for(let node=this.host;node&&node!==this.doc.body;node=node.parentElement){
   for(const sibling of node.parentElement?.children||[])if(sibling!==node&&!this.background.has(sibling)){this.background.set(sibling,!!sibling.inert);sibling.inert=true}
  }
 }
 moveTooltip(){
  const tooltip=this.doc.getElementById('vg-tooltip-element'),target=this.host||this.doc.body;
  if(tooltip&&tooltip.parentElement!==target){tooltip.classList.remove('visible');target.appendChild(tooltip)}
 }
 update(){
  if(!this.host)return;if(!this.host.isConnected){this.exit();return}
  this.moveTooltip();this.blockBackground();fitCanvas(this.host.querySelector('#report'));
 }
 async enter(){
  const host=this.getTarget?.();if(!host||!host.isConnected)return;
  if(this.host===host)return;if(this.host)await this.exit();
  const generation=++this.generation;this.previousFocus=this.doc.activeElement;this.host=host;this.native=false;this.addedTabIndex=!host.hasAttribute?.('tabindex');if(this.addedTabIndex)host.setAttribute?.('tabindex','-1');host.classList.add('report-fullscreen-active');this.doc.body.classList.add('report-is-fullscreen');this.onChange(true);this.update();host.focus?.({preventScroll:true});
  const Observer=this.win.MutationObserver;
  if(Observer){this.observer=new Observer(()=>this.update());this.observer.observe(this.doc.body,{childList:true,subtree:true})}
  if(host.requestFullscreen&&this.doc.fullscreenEnabled!==false){
   try{await host.requestFullscreen()}catch{/* The canvas-only viewport remains usable in embedded browsers. */}
   if(generation!==this.generation||this.host!==host){if(this.doc.fullscreenElement===host)try{await this.doc.exitFullscreen()}catch{};return}
   this.native=this.doc.fullscreenElement===host;
  }
  this.update();
 }
 reset(){
  if(!this.host)return;const previous=this.host;this.generation++;this.host=null;this.native=false;this.observer?.disconnect();this.observer=null;
  previous.classList.remove('report-fullscreen-active');if(this.addedTabIndex)previous.removeAttribute?.('tabindex');this.doc.body.classList.remove('report-is-fullscreen');for(const [node,inert] of this.background)node.inert=inert;this.background.clear();this.moveTooltip();this.onChange(false);if(this.previousFocus?.isConnected)this.previousFocus.focus?.({preventScroll:true});this.previousFocus=null;
  // The normal report fit observer runs after the fullscreen host returns to
  // document flow. Resize also covers the viewport-only fallback.
  if(this.win.Event)this.win.dispatchEvent(new this.win.Event('resize'));
 }
 async exit(){const previous=this.host;this.reset();if(previous&&this.doc.fullscreenElement===previous)try{await this.doc.exitFullscreen()}catch{}}
 toggle(){return this.host?this.exit():this.enter()}
 dispose(){this.exit();this.doc.removeEventListener('fullscreenchange',this.changed);this.doc.removeEventListener('keydown',this.key);this.win.removeEventListener('resize',this.resize);this.win.removeEventListener('message',this.message);if(controller===this)controller=null}
}
const api={Controller,overlayHost,fitCanvas,renderBody,exit:()=>controller?.exit()};if(typeof module!=='undefined')module.exports=api;root.ReportFullscreen=api;
})(typeof globalThis!=='undefined'?globalThis:this);
