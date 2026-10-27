const assert=require('node:assert/strict'),S=require('./report-style');
const literal=value=>({expr:{Literal:{Value:typeof value==='string'?"'"+value+"'":String(value)}}}),source=name=>({sourceFile:{image:{url:{expr:{ResourcePackageItem:{ItemName:name}}}}}}),model={assets:{all:'https://example.com/all.png',eyes:'https://example.com/eyes.png',blood:'https://example.com/blood.png'},theme:{visualStyles:{image:{'*':{image:[{transparency:20},{selector:{id:'hover'},properties:{fit:'Fill'}}]}}}}};
const visual={type:'image',z:0,layerOrder:0,definition:{objects:{image:[{properties:{...source('all'),fit:literal('Stretch')}},{selector:{id:'default'},properties:{transparency:literal(100)}},{selector:{id:'hover'},properties:source('eyes')},{selector:{id:'press'},properties:source('blood')}]},visualContainerObjects:{general:[{properties:{altText:literal('Decorative source description')}}]}}};
class EventNode{
 constructor(document){this.ownerDocument=document;this.listeners=new Map();this.style={};this.dataset={};this.attributes=new Map();this.tabIndex=-1;this.classList={add(){}};this.hidden=false}
 addEventListener(name,fn){if(!this.listeners.has(name))this.listeners.set(name,new Set());this.listeners.get(name).add(fn)}
 removeEventListener(name,fn){this.listeners.get(name)?.delete(fn)}
 emit(name,properties={}){const event={target:this,preventDefault(){this.defaultPrevented=true},...properties};for(const fn of [...(this.listeners.get(name)||[])])fn(event);this['on'+name]?.(event);return event}
 setAttribute(name,value){this.attributes.set(name,String(value))}getAttribute(name){return this.attributes.get(name)??null}removeAttribute(name){this.attributes.delete(name)}
 contains(node){return node===this||node===this.img}
 set innerHTML(markup){this.markup=markup;this.img=new EventNode();const source=/ src="([^"]+)"/.exec(markup);if(source)this.img.setAttribute('src',source[1]);this.img.style.opacity=/opacity:([^;]+)/.exec(markup)?.[1];this.img.style.objectFit=/object-fit:([^;]+)/.exec(markup)?.[1];this.img.hidden=/ hidden/.test(markup)}
 get innerHTML(){return this.markup}
 querySelector(selector){return selector==='img'?this.img:null}
}
const doc=new EventNode(),el=new EventNode(doc),original=JSON.stringify(visual),originalModel=JSON.stringify(model);
assert.equal(S.imagePlan(model,visual).source,model.assets.all);assert.equal(S.imagePlan(model,visual).opacity,0);
assert.equal(S.imagePlan(model,visual,'hover').source,model.assets.eyes);assert.equal(S.imagePlan(model,visual,'hover').opacity,.8,'Hover inherits All, not Default transparency100');assert.equal(S.imagePlan(model,visual,'press').source,model.assets.blood);
assert.equal(S.imagePlan(model,visual,'hover').objectFit,'fill','authored All overrides theme-specific Hover fit');
const unordered=structuredClone(visual);unordered.definition.objects.image.reverse();assert.equal(S.imagePlan(model,unordered).opacity,0,'state properties override All independently of entry ordering');assert.equal(S.imagePlan(model,unordered,'hover').source,model.assets.eyes);
S.container(el,model,visual);const containerBefore={...el.style};assert.equal(S.staticVisual(el,model,visual),true);assert.equal(el.img.style.opacity,'0');assert.equal(el.img.dataset.pbiImageState,'default');assert.equal(el.tabIndex,0);assert.equal(el.style.pointerEvents,'auto','authored states must receive events through the decorative pointer-events:none CSS');
let clicks=0,keys=0;el.onclick=()=>clicks++;el.onkeydown=()=>keys++;
el.emit('pointerenter',{pointerType:'mouse'});assert.equal(el.img.getAttribute('src'),model.assets.eyes);assert.equal(el.img.dataset.pbiImageState,'hover');
el.emit('pointerdown',{button:0,pointerId:9});assert.equal(el.img.getAttribute('src'),model.assets.blood);assert.equal(el.img.dataset.pbiImageState,'press');assert.equal(doc.listeners.get('pointerup').size,1);
doc.emit('pointerup',{target:el.img,pointerId:10});assert.equal(el.img.dataset.pbiImageState,'press','other pointer cannot release primary pressed state');
doc.emit('pointerup',{target:el.img,pointerId:9});assert.equal(el.img.getAttribute('src'),model.assets.eyes);assert.equal(doc.listeners.get('pointerup').size,0);el.emit('click');assert.equal(clicks,1,'authored click handler is not replaced or duplicated');
el.emit('pointerleave');assert.equal(el.img.style.opacity,'0');assert.equal(el.img.getAttribute('src'),model.assets.all);
el.emit('pointerenter');el.emit('pointerdown',{button:2,pointerId:9});assert.equal(el.img.dataset.pbiImageState,'hover','secondary clicks do not trigger pressed style');
el.emit('pointerdown',{button:0,pointerId:9});doc.emit('pointerup',{target:{},pointerId:9});assert.equal(el.img.dataset.pbiImageState,'default','release outside resets Default');
el.emit('pointerenter');el.emit('pointerdown',{button:0,pointerId:9});doc.emit('pointercancel',{pointerId:9});assert.equal(el.img.dataset.pbiImageState,'default');assert.equal(doc.listeners.get('pointercancel').size,0);
el.emit('pointerenter');el.emit('pointerdown',{button:0,pointerId:9});el.emit('pointerleave');assert.equal(el.img.dataset.pbiImageState,'default');assert.equal(doc.listeners.get('pointerup').size,0);
el.emit('focus');assert.equal(el.img.dataset.pbiImageState,'hover');assert.equal(el.emit('keydown',{key:' '}).defaultPrevented,true);assert.equal(el.img.dataset.pbiImageState,'press');assert.equal(keys,1,'authored keyboard action handler remains active');el.emit('keyup',{key:' '});assert.equal(el.img.dataset.pbiImageState,'hover');el.emit('blur');assert.equal(el.img.dataset.pbiImageState,'default');
el.emit('pointerdown',{button:0,pointerId:4,pointerType:'touch'});assert.equal(el.img.dataset.pbiImageState,'press');el.emit('pointerup',{pointerId:4});assert.equal(el.img.dataset.pbiImageState,'default','touch release does not leave Hover active');
el.emit('pointerenter');el.emit('pointerdown',{button:0,pointerId:8});S.staticVisual(el,model,visual);assert.equal(doc.listeners.get('pointerup').size,0,'re-render cleans document release watchers');assert.equal(el.listeners.get('pointerdown').size,1,'re-render replaces listeners without accumulation');assert.equal(el.img.dataset.pbiImageState,'default');
assert.deepEqual({...el.style,pointerEvents:undefined},{...containerBefore,pointerEvents:undefined});assert.equal(JSON.stringify(visual),original);assert.equal(JSON.stringify(model),originalModel);
const invalid=structuredClone(visual);invalid.definition.objects.image[2].properties={sourceUrl:literal('javascript:alert(1)')};S.staticVisual(el,model,invalid);el.emit('pointerenter');assert.equal(el.img.hidden,true);assert.equal(el.img.getAttribute('src'),null);el.emit('pointerleave');assert.equal(el.img.hidden,false);assert.equal(el.img.getAttribute('src'),model.assets.all);
const allOnly=structuredClone(visual);allOnly.definition.objects.image=allOnly.definition.objects.image.slice(0,1);assert.equal(S.imagePlan({},allOnly).source,null);assert.equal(S.staticVisual(new EventNode(doc),{},allOnly),false);
S.staticVisual(el,model,allOnly);assert.equal(el.style.pointerEvents,undefined,'switching to decorative content restores click-through');assert.equal(el.tabIndex,-1,'state-only tab stop is cleaned on re-render');assert.equal(el.onclick instanceof Function,true,'action handler survives cleanup');
const decorative=new EventNode(doc);decorative.style.pointerEvents='none';S.staticVisual(decorative,model,allOnly);assert.equal(decorative.style.pointerEvents,'none','theme-only state defaults do not intercept ordinary images');
const hovered=new EventNode(doc);hovered.matches=selector=>selector===':hover';S.staticVisual(hovered,model,visual);assert.equal(hovered.img.dataset.pbiImageState,'hover','re-render under a stationary pointer starts in its actual Hover state');
const navigation=new EventNode(doc);navigation.style.pointerEvents='auto';S.staticVisual(navigation,model,visual);S.staticVisual(navigation,model,allOnly);assert.equal(navigation.style.pointerEvents,'auto','preexisting navigation hit-testing is retained');
console.log('PASS native image All/Default/Hover/Press state inheritance, URL/fit/transparency, pointer and keyboard lifecycle, action preservation, cleanup, source immutability and safe URLs');
