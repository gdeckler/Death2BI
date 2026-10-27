const assert=require('node:assert/strict'),S=require('./report-style'),E=require('./report-engine');
const events={},el={addEventListener:(name,fn)=>events[name]=fn,contains:()=>true},rows=[[5,'Drama']],seen=[];
S.bindCardTooltips(el,{onHover:d=>seen.push(d),onLeave:()=>seen.push('leave')},rows);
const item={dataset:{cardIndex:'2'},closest:()=>({dataset:{cardRow:'0'}})};
events.mousemove({target:{closest:q=>q==='.card-item'?item:null}});assert.deepEqual(seen[0],{_cardIndex:2,_cardRow:rows[0]});events.mouseleave();assert.equal(seen[1],'leave');
const col={Column:{Expression:{SourceRef:{Entity:'Genres'}},Property:'Genre'}},v={definition:{query:{queryState:{Data:{projections:[{field:{Measure:{Property:'Total'}}}]},Rows:{projections:[{field:col}]}}}}};
assert.deepEqual(E.tooltipPointFilters(v,{_cardRow:[5,'Drama']},{scalar:true})[0].filter.Where[0].Condition.In.Values,[[{Literal:{Value:"'Drama'"}}]]);
assert.deepEqual(E.tooltipPointFilters(v,{_cardRow:[5]},{scalar:true}),[]);
const disabled={};S.bindCardTooltips({addEventListener:()=>assert.fail('Disabled tooltip bound events')},disabled,rows);
function fixture(count=1,group=false){const events={},items=Array.from({length:count},(_,i)=>({dataset:{cardIndex:String(i)},closest:()=>group?{dataset:{cardRow:'1'}}:null}));return {items,events,el:{querySelectorAll:()=>items,contains:item=>items.includes(item),addEventListener:(name,fn)=>events[name]=fn}}}
const scalar=fixture(),hovered=[];S.bindCardTooltips(scalar.el,{onHover:d=>hovered.push(d),onLeave:()=>hovered.push('leave')},[[7]]);scalar.events.mousemove({target:{closest:()=>null}});assert.deepEqual(hovered,[{_cardIndex:0,_cardRow:[7]}]);
scalar.events.mousemove({target:{closest:selector=>selector==='button,a,input,select'?{}:null}});assert.equal(hovered.at(-1),'leave');scalar.events.mouseleave();assert.equal(hovered.at(-1),'leave');
for(const [count,group,values] of [[2,false,[[7,8]]],[1,true,[[7],[8]]],[1,true,[[7]]]]){const f=fixture(count,group),seen=[];S.bindCardTooltips(f.el,{onHover:d=>seen.push(d)},values);f.events.mousemove({target:{closest:()=>null}});assert.deepEqual(seen,[]);f.events.mousemove({target:{closest:s=>s==='.card-item'?f.items[0]:null}});assert.deepEqual(seen,[{_cardIndex:0,_cardRow:values[group?1:0]}])}
console.log('PASS card hover/leave wiring, grouped row context and scalar cards without invented measure filters');
const tooltipFields={labels:['Value','Details'],roles:['Data','Tooltips'],formats:['0','']},tooltipData={rows:[[7,'Extra details']]},card={type:'cardVisual',definition:{query:{queryState:{Data:{projections:[{field:{Measure:{Property:'Value'}}}]},Tooltips:{projections:[{field:{Measure:{Property:'Details'}}}]}}}}};
assert.match(S.cardResultMarkup({},card,tooltipFields,tooltipData),/title="Details: Extra details"/);
assert.doesNotMatch(S.cardResultMarkup({},card,tooltipFields,tooltipData,{defaultTooltip:false}),/ title=/,'sentence and resolved report-page modes suppress native card titles before paint');
for(const handlers of [{onHover(){}},{tooltip:false}]){let removed=0;S.bindCardTooltips({querySelectorAll:()=>[{removeAttribute:name=>{assert.equal(name,'title');removed++},closest:()=>null}],addEventListener(){}},handlers,[[7]]);assert.equal(removed,1)}
console.log('PASS external/disabled card tooltip modes remove native titles while standard card tooltips remain available');
S.bindCardTooltips({addEventListener:()=>assert.fail('Disabled card tooltip cannot bind custom hover callbacks')},{tooltip:false,onHover:()=>assert.fail('Disabled card hover fired')},[[7]]);
