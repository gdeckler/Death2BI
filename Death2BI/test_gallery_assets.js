const assert=require('assert'),S=require('./report-style'),A=require('./advanced-charts');
const raw="<svg xmlns='http://www.w3.org/2000/svg' fill='#fff'><text>50%</text></svg>";
const u=S.url('data:image/svg+xml;utf8,'+raw,{});assert(!u.includes('#'));assert.equal(decodeURIComponent(u.slice(u.indexOf(',')+1)),raw);
const encoded='data:image/svg+xml,'+encodeURIComponent(raw);assert.equal(S.url(encoded,{}),encoded);
assert.equal(S.url('data:image/svg+xml;base64,PHN2Zz4=',{}),'data:image/svg+xml;base64,PHN2Zz4=');
const f={type:'Feature',properties:{name:'Custom Area',keys:['Custom Area']},geometry:{type:'Polygon',coordinates:[[[0,0],[10,0],[10,10],[0,0]]]}};
const spec=A.build({width:400,height:300,data:{}},'filledMap',['Area','Value'],[['Custom Area',3]],['Category','Value'],{visual:{mapFeatures:[f]}});assert.equal(spec.data.values.length,1);assert.equal(spec.data.values[0]._value,3);assert.deepEqual(spec.layer[0].data.values,[f]);
console.log('SVG URL and embedded Shape Map regressions passed');

assert.equal(decodeURIComponent(S.url("data:image/svg+xml;utf8,<svg fill='%23fff'>50%</svg>",{}).split(",")[1]),"<svg fill='#fff'>50%</svg>");
