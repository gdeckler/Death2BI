const assert=require('node:assert/strict'),S=require('./report-style'),C=require('./report-controls'),E=require('./report-engine'),X=require('./visual-export');
const lit=x=>({expr:{Literal:{Value:typeof x==='string'?"'"+x+"'":String(x)}}});
const theme={background:'#EC670F',dataColors:['#EC670F','#3C3C3B','#E5EAEE','#5C85E6','#29BCC0','#7EAE40','#20B2E7','#D3DCE0']};
assert.equal(S.value({ThemeDataColor:{ColorId:3}},theme),'#3C3C3B');
assert.equal(S.value({ThemeDataColor:{ColorId:9}},theme),'#D3DCE0');
const shape=S.shapeMarkup({theme},{type:'shape',width:200,height:700,definition:{objects:{shape:[{properties:{tileShape:lit('rectangleRounded'),rectangleRoundedCurve:lit(3)}}]}}});
const rx=+shape.match(/rx="([\d.]+)"/)[1],ry=+shape.match(/ry="([\d.]+)"/)[1];assert.ok(Math.abs(rx*200-ry*700)<.001);
assert.equal(S.props({items:[{fontFamily:'Segoe UI',fontSize:14}]},'items').fontFamily,'Segoe UI');
const el={style:{},dataset:{},children:[],setAttribute(){},querySelector:()=>null,querySelectorAll:()=>[]};S.styleCard(el,{theme},{type:'card',definition:{}});assert.equal(el.style.textAlign,'center');
X.attach(null,{},null,{type:'slicer'},null); // control visuals never access/create export DOM
const expression={Column:{Expression:{SourceRef:{Entity:'Calendar'}},Property:'Date'}};
const filters=C.rangeFilter(expression,'2019-01-02','2019-02-03');assert.ok(JSON.stringify(filters).includes("datetime'2019-01-02T00:00:00'"));
assert.equal(E.fieldFormat({}, {field:{Arithmetic:{Operator:3,Right:{ScopedEval:{}}}}}),'0.00%');
console.log('PASS theme palette positions, circular corners, card alignment, raw theme fonts, date ranges, percent-of-total format and no slicer exports');
