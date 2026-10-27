const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),S=require('./report-style');
const literal=value=>({expr:{Literal:{Value:typeof value==='string'?"'"+value.replaceAll("'","''")+"'":String(value)}}});
// Synthetic bytes test preservation of an embedded font URL, not font decoding.
const font=Buffer.from([119,79,70,50,0,1,0,0]).toString('base64');
const svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 240"><defs><style>@font-face{font-family:Embedded;src:url(data:font/woff2;base64,'+font+')}text{font-family:\'Embedded\';fill:#f4dfaa}</style></defs><rect width="720" height="240" fill="#101923"/><text x="20" y="60">O&apos;Brien — Niñez • 100%</text><circle cx="600" cy="120" r="18"><animate attributeName="opacity" values="1;0;1" dur="2s" repeatCount="indefinite"/></circle></svg>';
const prefix='data:image/svg+xml;utf8,',partial=prefix+svg.replace(/[#%]/g,c=>c==='#'?'%23':'%25'),normalized=prefix+encodeURIComponent(svg);
for(const input of [prefix+svg,partial,normalized,literal(partial)]){
 const source=S.url(input,{});assert.equal(source,normalized);assert.equal(decodeURIComponent(source.slice(source.indexOf(',')+1)),svg);
 assert(source.includes('%23f4dfaa')&&source.includes('base64%2C'+font.replaceAll('=','%3D')),'color hashes and font bytes remain inside the image payload');
 assert(!source.includes('<svg')&&!source.includes('#'),'raw SVG markup and color fragments cannot become HTML children or URL fragments');
}
const base64='data:image/svg+xml;base64,'+Buffer.from(svg).toString('base64');assert.equal(S.url(base64,{}),base64);assert.equal(Buffer.from(base64.split(',')[1],'base64').toString(),svg);
const field={Measure:{Expression:{SourceRef:{Entity:'Measures'}},Property:'Dynamic SVG'}},model={theme:{background:'#ffffff'},tables:[],measures:[]};
function visual(){return {id:'dynamic-svg',type:'image',z:4200,layerOrder:7,width:720,height:240,definition:{objects:{image:[{selector:{id:'default'},properties:{sourceField:{expr:field},sourceType:literal('FieldValue'),fit:literal('Stretch'),transparency:literal(35),altText:literal("O'Brien — Niñez illustration")}}]},visualContainerObjects:{background:[{properties:{show:true,color:{solid:{color:'#203040'}},transparency:25}}],border:[{properties:{show:true,color:{solid:{color:'#aabbcc'}},width:2}}]}}}}
function element(){return {isConnected:true,removed:false,style:{},classList:{add(){}},innerHTML:'',querySelector:selector=>selector==='img'?{}:null,remove(){this.removed=true}}}
function checkImage(v,url=normalized){const plan=S.imagePlan(model,v);assert.equal(plan.source,url);assert.equal(plan.objectFit,'fill');assert.equal(plan.opacity,.65);assert.equal(plan.alt,"O'Brien — Niñez illustration");const el=element();S.container(el,model,v);const style={...el.style};assert.equal(S.staticVisual(el,model,v),true);assert.deepEqual(el.style,style,'image URL resolution must not replace container background, border, layer or title styling');assert.equal(el.style.zIndex,'7');assert.equal(el.style.background,'#203040bf');assert.equal(el.style.border,'2px solid #aabbcc');assert.equal(/ src="([^"]+)"/.exec(el.innerHTML)?.[1].replaceAll('&#39;',"'"),url,'HTML attribute escaping preserves apostrophes in the original SVG URL');assert.match(el.innerHTML,/object-fit:fill;object-position:center/);assert.match(el.innerHTML,/opacity:0\.65;/);assert.doesNotMatch(el.innerHTML,/<(?:svg|style|animate|script)\b/);return el}
const staticSource=visual();staticSource.definition.objects.image.push({properties:{imageUrl:partial}});const staticBefore=JSON.stringify({model,staticSource});checkImage(staticSource);assert.equal(JSON.stringify({model,staticSource}),staticBefore);
const defaultFit=structuredClone(staticSource);delete defaultFit.definition.objects.image[0].properties.fit;assert.equal(S.imagePlan(model,defaultFit).objectFit,'contain');const hidden=visual();assert.equal(S.staticVisual(element(),model,hidden),false,'an unresolved source is omitted instead of rendering a broken image');

// Exercise the production UI's dynamic-image augmentation branch. Query APIs
// are mocked; URL/style resolution and the code being extracted are real.
const ui=fs.readFileSync(__dirname+'/dist/index.html','utf8'),evaluate=ui.indexOf('async function evaluate('),start=ui.indexOf(" if(v.type==='image'){",evaluate),end=ui.indexOf(" if(v.type==='textbox'){",start);
assert(evaluate>=0&&start>evaluate&&end>start,'the shared UI dynamic-image branch must remain discoverable');const branch=ui.slice(start,end);
async function resolve(mode,rows=[[partial]]){
 const source=visual(),before=JSON.stringify({model,source}),calls=[],el=element(),context={ReportStyle:S,model,p:{id:'page'},source,el,visualApi:{},slicerFilters:()=>[{slicer:true}],chartInteractions:{filtersFor:()=>[{selected:true}]},omitVisual:(_el,_v,message)=>{el.omitted=message},ReportEngine:{buildQuery:(m,p,v,extra)=>{calls.push({kind:'plan',v,extra});if(mode==='fallback')throw Error('DAX translation requires Python');if(mode==='unexpected')throw Error('Source metadata unavailable');return {sql:'SELECT dynamic_svg'}},pythonQuery:async(m,p,v,extra)=>{calls.push({kind:'python',v,extra});return {result:{rows}}}},runQuery:async sql=>{calls.push({kind:'sql',sql});return {rows}}};
 const result=await vm.runInNewContext('(async()=>{let v=source;'+branch+';return v})()',context);
 assert.equal(JSON.stringify({model,source}),before,'dynamic rendering must not modify source image bindings or style definitions');return {source,result,calls,el};
}
(async()=>{
 for(const mode of ['sql','fallback']){
  const {source,result,calls}=await resolve(mode);assert(result);checkImage(result);assert.equal(result.definition.objects.image.length,source.definition.objects.image.length+1);assert.equal(result.definition.objects.image[0].properties.sourceField.expr,field);assert.equal(result.definition.visualContainerObjects,source.definition.visualContainerObjects);
  const plan=calls.find(c=>c.kind==='plan');assert.deepEqual(Array.from(plan.extra),[{slicer:true},{selected:true}]);assert.equal(plan.v.type,'card');assert.equal(plan.v.definition.query.queryState.Values.projections[0].field,field);assert.deepEqual(calls.map(c=>c.kind),mode==='sql'?['plan','sql']:['plan','python']);
  if(mode==='fallback')assert.deepEqual(calls.find(c=>c.kind==='python').extra,plan.extra);
 }
 const blank=await resolve('sql',[[null]]);assert.equal(blank.el.removed,true);assert.equal(blank.result,undefined);
 const multiple=await resolve('sql',[[partial],[partial]]);assert.match(multiple.el.omitted,/single URL/);assert.equal(multiple.result,undefined);
 const unexpected=await resolve('unexpected');assert.match(unexpected.el.omitted,/Source metadata unavailable/);assert.deepEqual(unexpected.calls.map(c=>c.kind),['plan'],'unrelated errors must not trigger an inaccurate fallback');
 console.log('PASS measure-generated SVG images: raw/partial/base64 URLs, embedded font bytes, Unicode, apostrophes, SMIL/viewBox preservation, image fit/load source, SQL/Python UI augmentation, filters, blank/error handling and immutable source styles');
})().catch(error=>{console.error(error);process.exitCode=1});
