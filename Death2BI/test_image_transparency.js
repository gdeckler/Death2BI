const assert=require('node:assert/strict'),S=require('./report-style');
const image='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==',literal=Value=>({expr:{Literal:{Value}}}),properties=transparency=>({sourceFile:{image:{url:literal("'"+image+"'"),scaling:literal("'Normal'")}},fit:literal("'Fill'"),altText:literal("'Original artwork'"),...(transparency===undefined?{}:{transparency})});
function element(){const img={};return {style:{},classList:{add(){}},innerHTML:'',querySelector:selector=>selector==='img'?img:null}}
function visual(transparency){return {type:'image',z:16000,layerOrder:15,definition:{objects:{image:[{properties:properties(transparency)}]}}}}
function render(model={},v=visual()){const el=element();S.container(el,model,v);const before={...el.style};assert.equal(S.staticVisual(el,model,v),true);assert.deepEqual(el.style,before,'image transparency must not alter container/title/border opacity or layer order');assert.equal(el.style.zIndex,'15');assert.equal(v.z,16000);assert.ok(el.innerHTML.includes('src="'+image+'"'),'retain the original image URL/encoded bytes');assert.doesNotMatch(el.innerHTML,/Made with AI|badge|watermark/i,'do not invent labels or overlays');return el}
assert.ok(Math.abs(Number(/opacity:([^;]+)/.exec(render({},visual(literal('85D'))).innerHTML)[1])-.15)<1e-12);
assert.match(render({},visual()).innerHTML,/opacity:1;/);assert.match(render({},visual(literal('0D'))).innerHTML,/opacity:1;/);assert.match(render({},visual(literal('100D'))).innerHTML,/opacity:0;/);
assert.match(render({},visual(-10)).innerHTML,/opacity:1;/);assert.match(render({},visual(150)).innerHTML,/opacity:0;/);assert.match(render({},visual('invalid')).innerHTML,/opacity:1;/);
const theme={theme:{visualStyles:{'*':{'*':{image:[{transparency:20}]}},image:{'*':{image:[{transparency:50}]}}}}};
assert.match(render(theme,visual()).innerHTML,/opacity:0\.5;/);assert.match(render(theme,visual(0)).innerHTML,/opacity:1;/);
const v=visual();v.definition.objects.general=[{properties:{transparency:60}}];assert.match(render({},v).innerHTML,/opacity:0\.4;/);
v.definition.objects.image[0].properties.transparency=75;assert.match(render({},v).innerHTML,/opacity:0\.25;/);
const framed=visual(85);framed.definition.visualContainerObjects={background:[{properties:{show:true,color:{solid:{color:'#123456'}},transparency:50}}],border:[{properties:{show:true,color:{solid:{color:'#abcdef'}},width:2}}]};
const e=render({},framed);assert.equal(e.style.background,'#12345680');assert.equal(e.style.border,'2px solid #abcdef');assert.equal(e.style.opacity,undefined);
const invalid=element(),unsafe=visual(85);unsafe.definition.objects.image[0].properties.sourceFile.image.url=literal("'javascript:alert(1)'");assert.equal(S.staticVisual(invalid,{},unsafe),false);assert.equal(invalid.innerHTML,'');
for(const [source,expected] of [['Fill','cover'],['Stretch','fill'],['Fit','contain'],['Center','none'],['Normal','none'],['unknown','contain']])for(const input of [source,source.toUpperCase(),literal("'"+source.toLowerCase()+"'")]){
 const v=visual(85);v.definition.objects.image[0].properties.fit=input;assert.match(render({},v).innerHTML,new RegExp('object-fit:'+expected+';object-position:center'));
}
const noFit=visual();delete noFit.definition.objects.image[0].properties.fit;assert.match(render({},noFit).innerHTML,/object-fit:contain;/,'sourceFile Normal scaling does not override the default image fit');
const navigation=visual();navigation.navigationIcon=true;assert.match(render({},navigation).innerHTML,/object-fit:contain;/);
const legacyFit=visual();legacyFit.definition.objects.image[0].properties.imageFit=literal("'Stretch'");assert.match(render({},legacyFit).innerHTML,/object-fit:fill;/);
// Actual target: 1024-square PNG in a 606.667 x 413.333 authored image box.
// Centered cover retains the aspect ratio and crops all content outside that viewport.
const original={width:1024,height:1024},box={width:606.6666666666667,height:413.33333333333337},scale=Math.max(box.width/original.width,box.height/original.height),top=(original.height*scale-box.height)/2,sourceTop=top/scale;
assert.ok(Math.abs(top-96.66666666666669)<1e-10);assert.ok(Math.abs(sourceTop-163.16483516483518)<1e-10);assert.ok(sourceTop>51,'top source content is naturally outside the original Fill viewport; image bytes remain unchanged');
console.log('PASS image-only transparency and fit modes, literal/default/clamped settings, theme/general/image precedence, centered cover geometry, original asset bytes, container formatting/layers and safe URL behavior');
