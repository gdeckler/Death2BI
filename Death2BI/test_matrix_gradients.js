const assert=require('node:assert/strict'),S=require('./report-style'),T=require('./table-rendering'),M=require('./matrix-rendering');
const column=(table,property)=>({Column:{Expression:{SourceRef:{Entity:table}},Property:property}}),count={Aggregation:{Expression:column('Fire fact','random id'),Function:5}},sum={Aggregation:{Expression:column('Fire fact','random id'),Function:0}},literal=value=>({Literal:{Value:typeof value==='string'?"'"+value+"'":String(value)}});
const gradient={Input:count,FillRule:{linearGradient3:{min:{color:literal('#FFD900')},mid:{color:literal('#AD1914')},max:{color:literal('#4B0000')},nullColoringStrategy:{strategy:literal('asZero')}}}};
const background={solid:{color:{expr:{FillRule:gradient}}}},projection=(field,queryRef)=>({field,queryRef,nativeQueryRef:queryRef});
function node(){return {style:{},dataset:{},textContent:'',setAttribute(){},querySelector(){return null},appendChild(){},remove(){},getBoundingClientRect(){return {height:20}}}}
function mockTable(labels,rows,flags=[]){
 const headers=labels.map(()=>node()),bodyRows=rows.map((row,index)=>({...node(),cells:row.map(value=>({...node(),textContent:String(value??'')})),dataset:flags[index]||{}})),head=node(),body={appendChild(){}},table={...node(),tHead:head,querySelector(selector){return selector==='tbody'?body:selector==='thead'?head:null},querySelectorAll(selector){return selector==='th'?headers:selector==='tbody tr'?bodyRows:selector==='tfoot tr,tr[data-pbi-total="true"]'?bodyRows.filter(row=>row.dataset.pbiTotal==='true'):[]}};
 return {querySelector:selector=>selector==='table'?table:null,bodyRows,headers};
}
function render(visual,labels,rows,{cellData,flags,model={theme:{background:'#ffffff'}}}={}){
 const dom=mockTable(labels,rows,flags);visual={...visual,_cellData:cellData};
 const previous=global.document;global.document={createElement:node};try{S.styleTable(dom,model,visual,labels,rows)}finally{global.document=previous}
 return dom;
}
function pivot(visual,compiled,result){
 const data=M.groups(result,compiled,0,visual),keys=[...data.columns.keys()],values=visual.definition.query.queryState.Values.projections,rows=data.nodes.map(node=>[node.label,...keys.flatMap(key=>node.cells.get(key)||values.map(()=>null))]),labels=['Rows',...keys.flatMap(key=>values.map(p=>key+' '+p.nativeQueryRef))];
 const styleVisual=structuredClone(visual);styleVisual.definition.query.queryState={Values:{projections:[visual.definition.query.queryState.Rows.projections[0],...keys.flatMap(()=>values)]}};
 const cellData=data.nodes.map(node=>[{},...keys.flatMap(key=>values.map(()=>node.raw.get(key)||{}))]);
 return {data,rows,labels,styleVisual,cellData,dom:render(styleVisual,labels,rows,{cellData})};
}
function run(){
 const v={type:'pivotTable',definition:{objects:{values:[{properties:{backColor:background},selector:{metadata:'Min(Fire fact.random id)',data:[{dataViewWildcard:{matchingOption:1}}]}}]},query:{queryState:{Columns:{projections:[projection(column('Calendar','DayName'),'DayName')]},Rows:{projections:[projection(column('Hour labels','HrTxt'),'Hour')]},Values:{projections:[projection(count,'Min(Fire fact.random id)')]}}}}};
 const compiled={roles:['Columns','Rows','Values'],labels:['DayName','Hour','Count of random id']},result={rows:[['Mo','00',0],['Tu','00',50],['We','00',100],['Mo','01',25],['Tu','01',75],['We','01',null]]},p=pivot(v,compiled,result),colors=p.dom.bodyRows.map(row=>row.cells.slice(1).map(cell=>cell.style.background.toLowerCase()));
 assert.deepEqual(colors,[['#ffd900','#ad1914','#4b0000'],['#d6790a','#7c0d0a','#ffd900']]);
 assert.equal(S.value(count,{},p.data.nodes[0].raw.get('["Tu"]')),50,'native aggregated field must be bound despite stale Min queryRef');
 assert.equal(p.dom.bodyRows[0].cells[0].style.background,'#ffffff','row labels are outside the value gradient');
 const previous=global.document;global.document={createElement:node};try{p.dom.headers[1].onclick()}finally{global.document=previous}assert.equal(p.dom.bodyRows[0].cells[2].style.background.toLowerCase(),'#ad1914','cached sorts preserve the full domain');

 // Repeated pivot value fields carry distinct exact bindings, including missing cells.
 const wide={definition:{objects:{values:[{properties:{backColor:background,applyToTotals:false,applyToSubtotals:false},selector:{data:[{dataViewWildcard:{matchingOption:1}}]}}]},query:{queryState:{Values:{projections:[projection(count,'Count'),projection(sum,'Sum'),projection(count,'Count'),projection(count,'Count')]}}}}},rows=[[0,10000,100,100000],[25,90000,75,200000],[999999,1,999999,999999],[888888,1,888888,888888]],flags=[{}, {},{pbiTotal:'true'},{pbiSubtotal:'true'}],cellData=rows.map(row=>row.map(()=>({})));
 for(const row of cellData)Object.defineProperty(row[3],'__formatScope',{value:{isSubtotal:true}});
 const d=render(wide,['Count A','Sum','Count B','Subtotal'],rows,{cellData,flags});
 assert.equal(d.bodyRows[0].cells[0].style.background.toLowerCase(),'#ffd900');assert.equal(d.bodyRows[0].cells[2].style.background.toLowerCase(),'#4b0000','same measure across pivot columns shares range');
 assert.equal(d.bodyRows[1].cells[0].style.background.toLowerCase(),'#d6790a');assert.equal(d.bodyRows[1].cells[2].style.background.toLowerCase(),'#7c0d0a','grand/row/column subtotals and sibling measures must not affect automatic bounds');
 assert.equal(d.bodyRows[0].cells[3].style.background,'#ffffff','excluded column subtotal is not conditionally painted');
 const onlyTotal=structuredClone(wide);onlyTotal.definition.objects.values[0].properties={backColor:background,totalMatchingOption:2};const t=render(onlyTotal,['A','Sum','B','C'],rows,{flags});assert.equal(t.bodyRows[0].cells[0].style.background,'#ffffff');assert.equal(t.bodyRows[2].cells[0].style.background.toLowerCase(),'#4b0000');

 // A global rule remains independent per projection, and exact Count/Sum bindings never alias.
 const globalRule={definition:{objects:{columnFormatting:[{properties:{backColor:background}}]},query:{queryState:{Values:{projections:[projection(count,'Count'),projection(sum,'Sum')]}}}}};
 const g=render(globalRule,['Count','Sum'],[[0,10000],[100,90000]]);assert.equal(g.bodyRows[1].cells[0].style.background.toLowerCase(),'#4b0000');
 const exact=T.datumFor(globalRule,['Count','Sum'],[7,999]);assert.equal(S.value(count,{},exact),7);assert.equal(S.value(sum,{},exact),999);
 const missing=T.cellDatumFor(wide,['A','S','B','C'],[0,10000,null,100],2,undefined,T.datumFor(v,['DayName','Hour','Count'],['Mo','00',100]));assert.equal(S.value(count,{},missing),null);

 // Sparse pivot cells must blank all sibling inputs at that same tuple.
 const sibling=structuredClone(v);sibling.definition.query.queryState.Values.projections=[projection(count,'Count'),projection(sum,'Sum')];sibling.definition.objects.values[0].selector.metadata='Sum';
 const sparse=pivot(sibling,{roles:['Columns','Rows','Values','Values'],labels:['Day','Hour','Count','Sum']},{rows:[['Tu','00',0,0],['Mo','00',100,1000],['Mo','01',200,2000]]});
 assert.equal(S.value(count,{},sparse.data.nodes[1].raw.get('["Tu"]')),null,'missing tuple must not borrow Count from another pivot column');
 assert.equal(sparse.dom.bodyRows[1].cells[2].style.background.toLowerCase(),'#ffd900','a Sum cell formatted by Count preserves blank/asZero at missing tuples');

 assert.equal(S.gradientColor(gradient,null,[null,100],{}).toLowerCase(),'#ffd900');assert.equal(S.gradientColor(gradient,50,[null,100],{}).toLowerCase(),'#ad1914');
 const noBlank=structuredClone(gradient);delete noBlank.FillRule.linearGradient3.nullColoringStrategy;assert.equal(S.gradientColor(noBlank,null,[1,100],{}),undefined);assert.equal(S.gradientColor(noBlank,5,[null,NaN,Infinity,'5',5],{}).toLowerCase(),'#ffd900');assert.equal(S.gradientColor(noBlank,5,[null,NaN,Infinity,'5'],{}),undefined);
 const fixed=structuredClone(gradient);fixed.FillRule.linearGradient3.min.value=literal(10);fixed.FillRule.linearGradient3.mid.value=literal(30);fixed.FillRule.linearGradient3.max.value=literal(100);assert.equal(S.gradientColor(fixed,30,[0,200],{}).toLowerCase(),'#ad1914');assert.equal(S.gradientColor(fixed,-1,[0,200],{}).toLowerCase(),'#ffd900');assert.equal(S.gradientColor(fixed,999,[0,200],{}).toLowerCase(),'#4b0000');
 assert.equal(S.gradientColor(gradient,50,Array.from({length:200000},(_,i)=>i%101),{}).toLowerCase(),'#ad1914','large domains do not exceed JS argument limits');

 // Preparing each rule/projection once bounds 10k-row painting to linear setup.
 // Local sorting reuses the prepared scale; a fresh render gets a fresh domain.
 const large={definition:{objects:{columnFormatting:[{properties:{backColor:background}}]},query:{queryState:{Values:{projections:[projection(count,'Count')]}}}}},largeRows=Array.from({length:10000},(_,i)=>[i]),dom=mockTable(['Count'],largeRows),previousDocument=global.document;
 let preparations=0,inputReads=0,paintCalls=0;
 const api={...S,px:()=>12,value(x,theme,datum){if(x===count)inputReads++;return S.value(x,theme,datum)},prepareGradientColor(rule,numbers,theme){preparations++;const paint=S.prepareGradientColor(rule,numbers,theme);return input=>{paintCalls++;return paint(input)}}};
 global.document={createElement:node};try{T.styleTable(dom,{theme:{}},large,['Count'],largeRows,api);assert.equal(preparations,1);assert.equal(inputReads,10000);assert.equal(paintCalls,10000);dom.headers[0].onclick();assert.equal(preparations,1);assert.equal(inputReads,10000);assert.equal(paintCalls,20000)}finally{global.document=previousDocument}
 assert.equal(dom.bodyRows[0].cells[0].style.background.toLowerCase(),'#ffd900');assert.equal(dom.bodyRows.at(-1).cells[0].style.background.toLowerCase(),'#4b0000');
 const filtered=render(large,['Count'],[[10],[20]]);assert.equal(filtered.bodyRows[0].cells[0].style.background.toLowerCase(),'#ffd900');assert.equal(filtered.bodyRows[1].cells[0].style.background.toLowerCase(),'#4b0000','new filtered render rebuilds its automatic range');
 console.log('PASS matrix/table three-color gradients, original Count bindings, pivot cells, projection-specific ranges, total/subtotal scopes, blank/invalid values, automatic/explicit stops and cached sorts');
}
if(require.main===module)run();module.exports={pivot,render,gradient};


