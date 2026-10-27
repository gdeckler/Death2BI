const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const Style=require('./report-style.js'),Renderer=require('./vega-renderer.js');
const lit=x=>({expr:{Literal:{Value:typeof x==='string'?"'"+x+"'":String(x)}}}),fill=x=>({solid:{color:lit(x)}});
const theme={dataColors:['#123456','#abcdef','#ff0000'],foreground:'#333333',background:'#f9f9f9',visualStyles:{'*':{'*':{legend:[{properties:{show:lit(false)}}]}}}};
assert.equal(Style.value({expr:{ThemeDataColor:{ColorId:2,Percent:0}}},theme),'#123456');
assert.equal(Style.value({expr:{ThemeDataColor:{ColorId:3,Percent:0}}},theme),'#abcdef');
assert.equal(Style.color(lit('#FFFFFF00'),theme),'#FFFFFF00');
assert.equal(Style.url(lit('javascript:alert(1)'),{theme}),null);
assert.equal(Style.url(lit('https://example.org/picture.png'),{theme}),'https://example.org/picture.png');
assert.equal(Style.stableColor('B',theme,['A','B','C']),'#abcdef');
assert.equal(Style.stableColor('B',theme,['A','B','C']),Style.stableColor('B',theme,['A','B','C']));
assert.equal(Style.value({Conditional:{Cases:[{Condition:{Comparison:{ComparisonKind:1,Left:{Measure:{Property:'Value'}},Right:{Literal:{Value:'10'}}}},Value:{Literal:{Value:"'#ff0000'"}}}],Else:{Literal:{Value:"'#00ff00'"}}}},theme,{Value:20}),'#ff0000');
const model={theme,colorDomains:{'Sales\u0000Region':['A','B','C']}};
const visual={type:'clusteredColumnChart',definition:{objects:{categoryAxis:[{properties:{showAxisTitle:lit(false),fontSize:lit(12)}}],valueAxis:[{properties:{start:lit(0),end:lit(100)}}],dataPoint:[{properties:{fill:fill('#654321')},selector:{data:[{scopeId:{Comparison:{Right:{Literal:{Value:"'B'"}}}}}]}}]},query:{queryState:{Category:{projections:[{field:{Column:{Expression:{SourceRef:{Entity:'Sales'}},Property:'Region'}}}]},Y:{projections:[{field:{Measure:{Property:'Value'}}}]}}}}};
const labels=['Region','Value'],rows=[['A',10],['B',20]],roles=['Category','Y'];
const spec=Renderer.buildSpec(visual.type,labels,rows,roles,{model,visual,width:500,height:300});
assert.equal(spec.encoding.color.scale.range[0],'#123456');
assert.equal(spec.data.values[1]._pbiColor,'#654321'); // category override on a single-measure chart
assert.equal(spec.encoding.color.legend,null);
assert.deepEqual(spec.encoding.y.scale.domain,[0,100]);
assert.equal(spec.encoding.x.axis.labelFontSize,16);
const filtered=Renderer.buildSpec('pieChart',labels,[['B',20]],roles,{model,visual:{...visual,type:'pieChart'},width:400,height:300});
assert.equal(filtered.layer[0].encoding.color.scale.range[0],'#654321');
const shape={type:'shape',definition:{objects:{shape:[{properties:{tileShape:lit('ellipse')}}],fill:[{properties:{fillColor:fill('#ff0000'),transparency:lit(50)}}]}}};
assert.match(Style.shapeMarkup(model,shape),/<ellipse/);assert.match(Style.shapeMarkup(model,shape),/fill-opacity="0.5"/);
assert.equal(Style.shapeMarkup(model,{...shape,definition:{objects:{shape:[{properties:{tileShape:lit('not-a-shape')}}]}}}),null);
const ctx=vm.createContext({console,setTimeout,clearTimeout,URL,structuredClone});
for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/vendor',file),'utf8'),ctx);
(async()=>{for(const type of ['clusteredColumnChart','stackedBarChart','lineChart','areaChart','pieChart','donutChart','heatmap','scatterChart']){
 const scatter=type==='scatterChart';const s=Renderer.buildSpec(type,scatter?['Country','X','Y']:labels,scatter?[['France',7,11],['Germany',8,12]]:rows,scatter?['Category','X','Y']:roles,{model,visual:scatter?{type,definition:{objects:{categoryLabels:[{properties:{show:lit(true),fontSize:lit(8)}}]}}}:{...visual,type},width:500,height:300});
 const view=new ctx.vega.View(ctx.vega.parse(ctx.vegaLite.compile(s).spec),{renderer:'none'});
 try{await view.runAsync();assert.match(await view.toSVG(),/<svg/)}finally{view.finalize()}
}console.log('PASS: theme references, safe URLs, selectors, stable domains, rules, axes, legends, shapes and styled Vega SVGs')})().catch(e=>{console.error(e);process.exitCode=1});

assert.deepEqual(Style.action(model,{definition:{objects:{visualLink:[{properties:{show:lit(true),type:lit('PageNavigation'),navigationSection:lit('page2')}}]}}}),{type:'page',target:'page2'});
assert.deepEqual(Style.action(model,{definition:{objects:{visualLink:[{properties:{type:lit('Back')}}]}}}),{type:'back'});
assert.equal(Style.tooltipPage(model,{definition:{objects:{tooltip:[{properties:{section:lit('tooltip1')}}]}}}),'tooltip1');

const bounded={type:'lineChart',definition:{objects:{valueAxis:[{properties:{start:lit(7),end:lit(9)}}]}}};
const line=Renderer.buildSpec('lineChart',['Year','Score'],[[2020,7.5],[2021,8]],['Category','Y'],{model,visual:bounded});assert.equal(line.encoding.y.scale.domainMin,7);assert.equal(line.encoding.y.scale.domainMax,9);assert.equal(line.encoding.y.scale.nice,false);
const automatic=Renderer.buildSpec('lineChart',['Year','Score'],[[2020,7.5],[2021,8]],['Category','Y'],{model,visual:{type:'lineChart',definition:{}}});assert.equal(automatic.encoding.y.scale.zero,false);
const oneBound=Renderer.buildSpec('lineChart',['Year','Score'],[[2020,7.5],[2021,8]],['Category','Y'],{model,visual:{type:'lineChart',definition:{objects:{valueAxis:[{properties:{end:lit(10)}}]}}}});assert.equal(oneBound.encoding.y.scale.domainMin,undefined);assert.equal(oneBound.encoding.y.scale.domainMax,10);
const page={visuals:[{id:'g1',type:'group',ownHidden:false},{id:'g2',type:'group',ownHidden:true},{id:'a',ownHidden:false,groupChain:['g1']},{id:'b',ownHidden:false,groupChain:['g2']},{id:'card',ownHidden:false}]};
Style.applyBookmarkDisplay(page,{visualContainerGroups:{g1:{isHidden:true},g2:{isHidden:false}},visualContainers:{a:{singleVisual:{}},b:{singleVisual:{}},card:{singleVisual:{display:{mode:'hidden'}}}}});assert.equal(page.visuals[2].hidden,true);assert.equal(page.visuals[3].hidden,false);assert.equal(page.visuals[4].hidden,true);
Style.applyBookmarkDisplay(page,{visualContainerGroups:{g1:{isHidden:false},g2:{isHidden:true}},visualContainers:{a:{singleVisual:{}},b:{singleVisual:{}},card:{singleVisual:{}}}});assert.equal(page.visuals[2].hidden,false);assert.equal(page.visuals[3].hidden,true);assert.equal(page.visuals[4].hidden,false);
const home={type:'actionButton',definition:{objects:{icon:[{properties:{shapeType:lit('custom'),image:{image:{url:lit('https://example.org/home.png')}}}}]},visualContainerObjects:{visualLink:[{properties:{type:lit('PageNavigation'),navigationSection:lit('welcome')}}]}}};const fake={style:{}};assert.equal(Style.staticVisual(fake,model,home),true);assert.match(fake.innerHTML,/<img/);assert.ok(!fake.innerHTML.includes('Go to page'));
console.log('PASS: exact and automatic axis ranges, scatter label layers, custom Home icon, bookmark display states and repeated group switching');

const chron=Renderer.buildSpec('lineChart',['Year','Population'],[[2020,100],[2010,90],[2000,80]],['Category','Y'],{model,visual:{type:'lineChart',definition:{}}});assert.equal(chron.encoding.x.type,'quantitative');assert.equal(chron.encoding.x.scale.zero,false);assert.equal(chron.encoding.x.scale.nice,false);
const categorical=Renderer.buildSpec('lineChart',['Year','Population'],[[2020,100],[2010,90],[2000,80]],['Category','Y'],{model,visual:{type:'lineChart',definition:{objects:{categoryAxis:[{properties:{axisType:lit('Categorical')}}]}}}});assert.deepEqual(categorical.encoding.x.sort,[2020,2010,2000]);
const azure=Renderer.buildSpec('filledMap',['Country','Population'],[['France',10],['Germany',20]],['Category','Tooltips'],{model,visual:{type:'filledMap',originalType:'azureMap',definition:{}}});assert.equal(azure.layer[1].encoding.color.legend,null);
const legend=Renderer.buildSpec('filledMap',['Country','Population'],[['France',10],['Germany',20]],['Category','Tooltips'],{model,visual:{type:'filledMap',originalType:'azureMap',definition:{objects:{legend:[{properties:{show:lit(true)}}]}}}});assert.notEqual(legend.layer[1].encoding.color.legend,null);
console.log('PASS: continuous chronological axes, explicit categorical sort and Azure legend defaults/overrides');

const yearField={Column:{Expression:{SourceRef:{Entity:'Calendar'}},Property:'Year'}};
const descending=Renderer.buildSpec('lineChart',['Year','Population'],[[2020,100],[2010,90],[2000,80]],['Category','Y'],{model,visual:{type:'lineChart',definition:{query:{queryState:{Category:{projections:[{field:yearField}]}},sortDefinition:{sort:[{field:yearField,direction:'Descending'}]}}}}});assert.equal(descending.encoding.x.scale.reverse,true);
