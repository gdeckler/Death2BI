const assert=require('node:assert/strict'),T=require('./table-rendering'),S=require('./report-style'),fs=require('node:fs'),path=require('node:path');
const lit=x=>({expr:{Literal:{Value:typeof x==='string'?"'"+x+"'":String(x)}}}),solid=x=>({solid:{color:lit(x)}});
const theme={maximum:'#abcdef',minimum:'#123456',foreground:'#222222'},settings={positiveColor:solid('maxColor'),negativeColor:solid('minColor'),axisColor:solid('foreground')};
let bar=T.dataBar(25,settings,[0,100],theme,S);assert.equal(bar.width,25);assert.equal(bar.color,'#abcdef');assert.equal(bar.hideText,false);assert.equal(bar.axisColor,'#222222');
bar=T.dataBar(-25,settings,[-50,100],theme,S);assert.equal(bar.color,'#123456');assert.equal(bar.showAxis,true);assert.ok(Math.abs(bar.axis-100/3)<1e-9);assert.ok(Math.abs(bar.width-100/6)<1e-9);
const reverse=T.dataBar(-25,{...settings,reverseDirection:lit(true)},[-50,100],theme,S);assert.ok(Math.abs(reverse.left-(100-bar.left-bar.width))<1e-9);assert.ok(Math.abs(reverse.axis-(100-bar.axis))<1e-9);
bar=T.dataBar(.25,{minValue:lit(0),maxValue:lit(1),hideText:lit(true),positiveColor:solid('#33aa55')},[100],{},S);assert.equal(bar.width,25);assert.equal(bar.hideText,true);assert.equal(bar.color,'#33aa55');
assert.equal(T.dataBar(10,{minValue:lit(0),maxValue:lit(1)},[],{},S).width,100);
assert.equal(T.dataBar(0,{},[0,0],{},S).width,0);
assert.equal(T.dataBar(-10,{},[-20,-10],{},S).width,50);
assert.equal(T.dataBar(null,{},[],{},S),null);assert.equal(T.dataBar('25',{},[],{},S),null);assert.equal(T.dataBar(Infinity,{},[],{},S),null);
assert.equal(T.dataBar(10,{show:lit(false)},[10],{},S),null);assert.equal(T.dataBar(10,{minValue:lit(20),maxValue:lit(10)},[10],{},S),null);
for(const [option,total,expected] of [[0,false,true],[0,true,true],[1,false,true],[1,true,false],[2,false,false],[2,true,true]])assert.equal(T.barMatches({totalMatchingOption:lit(option)},total,S,{}),expected);
assert.equal(T.dataBar(10,{positiveColor:solid('maxColor')},[10],{},S).color,'#118DFF');
// Retained PBIX settings must target the displayed measure, including renamed Matrix values.
const file=path.join(__dirname,'data/c3a15b6a597c4c2086a7de651934eecd/manifest.json');
if(fs.existsSync(file)){const m=JSON.parse(fs.readFileSync(file,'utf8'));for(const index of [0,2]){const v=m.pages[index].visuals.find(v=>v.type==='pivotTable'),rule=v.definition.objects.columnFormatting.find(x=>x.properties.dataBars);assert.ok(T.matchesColumn(rule,v,['Year','Count'],1));assert.equal(T.dataBar(182,rule.properties.dataBars,[257,243,307,250,239,194,217,182],m.theme,S).width,182/307*100);assert.equal(T.barMatches(rule.properties.dataBars,true,S,m.theme),false)}}
console.log('PASS data bars: signed domains, theme/literal colors, fixed bounds, reversal, blank/zero/invalid values, hide text, total scopes and PBIX selectors');
