const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const Style=require('./report-style');
const ref=(ColorId,Percent=0)=>({solid:{color:{expr:{ThemeDataColor:{ColorId,Percent}}}}});
assert.equal(Style.color(ref(0),{}),'#FFFFFF');
assert.equal(Style.color(ref(1),{}),'#000000');
assert.equal(Style.color(ref(2),{}),'#118DFF');
assert.equal(Style.color(ref(0,-.1),{}),'#e6e6e6');
assert.equal(Style.color(ref(0),{background:'#123456'}),'#FFFFFF');
assert.equal(Style.color(ref(2),{dataColors:[]}),'#118DFF');
const element=()=>({style:{},querySelector:()=>null});
function backgrounds(model,page){const canvas=element(),workspace=element();Style.pageStyle(canvas,workspace,model,page);return [canvas.style.background,workspace.style.background]}
const partial={theme:{name:'Custom',visualStyles:{page:{'*':{}}}},reportObjects:{}};
assert.deepEqual(backgrounds(partial,{objects:{outspace:[{properties:{color:ref(0)}}]}}),['#ffffffff','#FFFFFFff']);
assert.equal(backgrounds(partial,{objects:{background:[{properties:{color:ref(0)}}]}})[0],'#FFFFFFff');
assert.equal(backgrounds({theme:{background:'#ff0000'}},{objects:{}})[0],'#ff0000ff');
assert.equal(backgrounds(partial,{objects:{background:[{properties:{color:ref(0),transparency:50}}]}})[0],'#FFFFFF80');
const dark={theme:{foreground:'#FFFFFF',background:'#3a3a3a',dataColors:['#70B0E0']}};
assert.equal(backgrounds(dark,{objects:{background:[{properties:{color:ref(1)}}]}})[0],'#000000ff');
assert.equal(Style.color(ref(0),dark.theme),'#FFFFFF');
assert.equal(Style.color(ref(1,.6),dark.theme),'#999999');
assert.equal(Style.color(ref(2),dark.theme),'#70B0E0');
assert.equal(Style.color('foreground',dark.theme),'#FFFFFF');
assert.equal(Style.color('background',dark.theme),'#3a3a3a');
// Image defaults disable the latent theme fill; an explicit enable still paints.
const imageTheme={theme:{...dark.theme,visualStyles:{'*':{'*':{background:[{color:{solid:{color:'#3a3a3a'}}}]}},image:{'*':{background:[{show:false}],border:[{show:false}],padding:[{top:0,right:0,bottom:0,left:0}]}}}}};
const image={type:'image',definition:{}},imageEl={style:{},classList:{add(){}}};
Style.container(imageEl,imageTheme,image);assert.equal(imageEl.style.background,'transparent');
image.definition.visualContainerObjects={background:[{properties:{show:true,color:{solid:{color:'#123456'}},transparency:50}}]};
Style.container(imageEl,imageTheme,image);assert.equal(imageEl.style.background,'#12345680');
image.definition.visualContainerObjects.background[0].properties.show=false;
Style.container(imageEl,imageTheme,image);assert.equal(imageEl.style.background,'transparent');
// Exercise the saved report fixtures when present, without modifying them.
for(const id of ['c3a15b6a597c4c2086a7de651934eecd','1b605a78c4be4eb4b4bf4f3d27154e14']){
 const file=path.join(__dirname,'data',id,'manifest.json');if(!fs.existsSync(file))continue;
 const model=JSON.parse(fs.readFileSync(file,'utf8'));const colors=backgrounds(model,model.pages[0]);
 if(model.name==='Power BI Releases.pbix')assert.deepEqual(colors,['#ffffffff','#FFFFFFff']);
 if(model.name==='LearnPowerBI.pbix')assert.equal(colors[0],'#D3DCE0ff');
}
console.log('PASS partial-theme background/foreground defaults, accents, shading, explicit backgrounds, transparency and report fixtures');
