const assert=require('node:assert/strict'),S=require('./report-style');
const m={theme:{}},v={type:'cardVisual',definition:{objects:{}}},c={labels:['A','B','C','D'],roles:['Data','Data','Data','Data'],formats:['0','0','0','0']},r={rows:[[1,2,3,4]]};
const lit=x=>({expr:{Literal:{Value:String(x)+'D'}}});
assert.match(S.cardResultMarkup(m,v,c,r),/grid-template-columns:repeat\(4,/);
for(const [orientation,columns] of [[1,1],[2,4],[0,2]]){
 const copy=structuredClone(v);copy.definition.objects.layout=[{properties:{orientation:lit(orientation),columnCount:lit(2)}}];
 assert.match(S.cardResultMarkup(m,copy,c,r),new RegExp('grid-template-columns:repeat\\('+columns+','));
}
const themed={theme:{visualStyles:{cardVisual:{'*':{layout:[{orientation:1}]}}}}};
assert.match(S.cardResultMarkup(themed,v,c,r),/grid-template-columns:repeat\(1,/);
console.log('PASS multi-card default horizontal, authored vertical/horizontal/grid and theme arrangement');
