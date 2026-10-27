const A=require('node:assert/strict'),S=require('./report-style');
const lit=Value=>({expr:{Literal:{Value:String(Value)}}}),quoted=value=>lit("'"+value+"'"),element=()=>({style:{},innerHTML:''});
const model={pages:[{id:'third',name:'Third'},{id:'hidden',name:'Hidden',hidden:true},{id:'tooltip',name:'Tooltip',isTooltip:true},{id:'first',name:'First'}],bookmarks:[{name:'outside',displayName:'Outside'},{name:'first',displayName:'First'},{name:'second',displayName:'Second'}],bookmarkGroups:[{name:'selected',children:['second','nested','missing']},{name:'nested',children:['first','selected']}],theme:{foreground:'#333333'}};
function visual(type,orientation,gap='0D'){
 const objects={layout:[{properties:{...(orientation===undefined?{}:{orientation:lit(orientation)}),cellPadding:lit(gap)}}],pages:[{properties:{showHiddenPages:lit('true')}}],bookmarks:[{properties:{bookmarkGroup:quoted('selected')}}],text:[{properties:{fontColor:'#abcdef',fontFamily:quoted('Segoe UI'),fontSize:lit('12D')}}],fill:[{properties:{show:lit('false')}}]};
 return {type,definition:{objects}};
}
const actions=(html,type)=>Array.from(html.matchAll(new RegExp('data-report-'+(type==='pageNavigator'?'page':'bookmark')+'="([^"]+)"','g')),m=>m[1]);
const snapshot=JSON.stringify(model);
for(const type of ['pageNavigator','bookmarkNavigator']){
 const expected=type==='pageNavigator'?['third','hidden','first']:['second','first'];
 for(const [orientation,direction] of [['1D','column'],["'Vertical'",'column'],["'vertical'",'column'],["'Horizontal'",'row'],["'horizontal'",'row'],[undefined,'row']]){
  const v=visual(type,orientation),before=JSON.stringify(v),el=element();
  A.equal(S.staticVisual(el,model,v,{allowHidden:true}),true);A.equal(el.style.display,'flex');A.equal(el.style.flexDirection,direction);A.equal(el.style.gap,'0px');A.equal(el.style.padding,'0');
  A.deepEqual(actions(el.innerHTML,type),expected);A.doesNotMatch(el.innerHTML,/data-report-(?:page|bookmark)="(?:tooltip|outside|missing|nested|selected)"/);A.match(el.innerHTML,/type="button"/);A.match(el.innerHTML,/background:transparent/);A.match(el.innerHTML,/color:#abcdef/);A.match(el.innerHTML,/font-size:16px/);A.equal(JSON.stringify(v),before);
 }
 const el=element();S.staticVisual(el,model,visual(type,'1D','4D'),{allowHidden:true});A.equal(el.style.flexDirection,'column');A.equal(el.style.gap,'4px');
 S.staticVisual(el,model,visual(type,"'Horizontal'"),{allowHidden:true});A.equal(el.style.flexDirection,'row');A.equal(el.style.gap,'0px');A.deepEqual(actions(el.innerHTML,type),expected);
 S.staticVisual(el,model,visual(type,'1D'),{allowHidden:true});S.staticVisual(el,model,visual(type,undefined),{allowHidden:true});A.equal(el.style.flexDirection,'row');
 const themed=structuredClone(model);themed.theme.visualStyles={[type]:{'*':{layout:[{properties:{orientation:lit('1D'),cellPadding:lit('6D')}}]}}};
 const inherited={type,definition:{objects:{...(type==='bookmarkNavigator'?{bookmarks:[{properties:{bookmarkGroup:quoted('selected')}}]}:{})}}};
 const target=element();S.staticVisual(target,themed,inherited);A.equal(target.style.flexDirection,'column');A.equal(target.style.gap,'6px');
}
const pageEl=element();S.staticVisual(pageEl,model,visual('pageNavigator','1D'));A.deepEqual(actions(pageEl.innerHTML,'pageNavigator'),['third','first']);
const onlyHidden=visual('pageNavigator','1D');onlyHidden.definition.objects.pages=[{properties:{showByDefault:lit('false')}},{selector:{id:'hidden'},properties:{showPage:lit('true')}}];A.equal(S.staticVisual(pageEl,model,onlyHidden),false);A.deepEqual(actions(pageEl.innerHTML,'pageNavigator'),[]);A.equal(S.staticVisual(pageEl,model,onlyHidden,{allowHidden:true}),true);A.deepEqual(actions(pageEl.innerHTML,'pageNavigator'),['hidden']);
const missingGroup=visual('bookmarkNavigator','1D');missingGroup.definition.objects.bookmarks=[{properties:{bookmarkGroup:quoted('absent')}}];const empty=element();A.equal(S.staticVisual(empty,model,missingGroup),false);A.equal(empty.innerHTML,'');
A.equal(JSON.stringify(model),snapshot);
console.log('PASS page/bookmark navigator vertical/horizontal/default orientation, rerender resets, zero/authored gaps, inherited styles, authorized page order/group filtering and immutable sources');
