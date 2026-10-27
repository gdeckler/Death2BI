const assert=require('node:assert/strict'),Style=require('./report-style.js');
const lit=x=>({expr:{Literal:{Value:String(x)}}});
for(const type of ['card','cardVisual','multiRowCard']){
 const v={type,definition:{objects:{}}};
 const html=Style.cardMarkup({},v,['Trailing 12'],['182']);
 assert.match(html,/<div class="big">182<\/div><small class="card-category">Trailing 12<\/small>/);
 assert.doesNotMatch(html,/<h3>/);
 v.definition.objects.categoryLabels=[{properties:{show:lit(false)}}];
 assert.doesNotMatch(Style.cardMarkup({},v,['Trailing 12'],['182']),/card-category/);
}
const multi=Style.cardMarkup({}, {type:'multiRowCard',definition:{}}, ['A','B'], ['10','20']);
assert.equal((multi.match(/card-category/g)||[]).length,2);
assert.match(Style.cardMarkup({}, {type:'card',definition:{}}, ['<unsafe>'], ['1']),/&lt;unsafe&gt;/);
console.log('PASS category labels default on, explicit off, multi-value cards, title independence and escaping');
