const A=require('node:assert/strict'),S=require('./report-style');const lit=x=>({expr:{Literal:{Value:String(x)}}});
const model={pages:[{id:'home',name:'Home'},{id:'one',name:'1',hidden:true},{id:'tip',name:'Tooltip',hidden:true,pageType:'Tooltip'},{id:'two',name:'2'}]},v={type:'pageNavigator',definition:{objects:{pages:[{properties:{showByDefault:lit(false)}},{selector:{id:'home'},properties:{showPage:lit(true)}},{selector:{id:'one'},properties:{showPage:lit(true)}}]}}};
A.deepEqual(S.navigatorPages(model,v,true).map(p=>p.name),['Home','1']);A.deepEqual(S.navigatorPages(model,v,false).map(p=>p.name),['Home']);
const defaults={type:'pageNavigator',definition:{objects:{pages:[{properties:{showHiddenPages:lit(true)}},{selector:{id:'two'},properties:{showPage:lit(false)}}]}}};A.deepEqual(S.navigatorPages(model,defaults,true).map(p=>p.name),['Home','1']);
const el={style:{}};S.staticVisual(el,model,v,{allowHidden:true});A.match(el.innerHTML,/data-report-page="one"/);A.doesNotMatch(el.innerHTML,/data-report-page="tip"/);
console.log('PASS navigator page overrides, default exclusions, tooltip detection and hidden-page access');
