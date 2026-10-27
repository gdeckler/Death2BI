/* Map native Power BI KPI fields/formatting without modifying stored reports. */
(function(root){
const DataView=typeof module!=='undefined'?require('./custom-dataview.js'):root.CustomDataView;
const guid='NativeStyleKpiB82C40E7A9414D3AA105F8C29D663AB1';
function adapt(visual){
 if(visual.type!=='kpi')return visual;
 const original=visual.definition||{},state=original.query?.queryState||{},queryState={};
 const mapping={Indicator:'value',Value:'value',TrendLine:'trend',TrendAxis:'trend',Goal:'target',Target:'target',value:'value',trend:'trend',target:'target'};
 for(const [name,data] of Object.entries(state)){
  const role=mapping[name];if(!role){if(data.projections?.some(p=>p.active!==false))throw Error('Unsupported native KPI role: '+name);continue}
  const projections=(data.projections||[]).filter(p=>p.active!==false);
  if(projections.length)queryState[role]={...data,projections:[...(queryState[role]?.projections||[]),...projections]};
 }
 if(queryState.value?.projections.length!==1)throw Error('A KPI needs exactly one indicator field.');
 for(const role of ['trend','target'])if(queryState[role]?.projections.length>1)throw Error('KPI '+role+' supports one field.');
 const source=DataView.objects(original.objects),objects={...original.objects};
 const put=(name,properties)=>{objects[name]=[{properties:{...source[name],...Object.fromEntries(Object.entries(properties).filter(([,v])=>v!==undefined))}}]};
 const indicator=source.indicator||{},trend=source.trendline||source.trendLine||{},goals=source.goals||{},status=source.status||{};
 put('callout',{fontSize:Math.min(indicator.fontSize||100,Math.max(12,((visual.height||160)-30)*.65)),decimals:indicator.indicatorPrecision??indicator.precision??indicator.decimalPlaces,icons:indicator.showIcon,displayUnits:indicator.displayUnits===undefined?undefined:String(indicator.displayUnits||1)});
 put('trend',{show:trend.show,lowGood:status.direction===undefined?undefined:/low|negative/i.test(String(status.direction)),good:status.goodColor,bad:status.badColor,neutral:status.neutralColor});
 put('goal',{show:!!queryState.target&&(goals.showGoal??goals.show)!==false,distance:goals.showDistance,label:goals.label,fontSize:goals.fontSize,goalDecimals:goals.precision??goals.decimalPlaces});
 put('layout',{title:false,date:false});
 return {...visual,_nativeKpi:true,definition:{...original,query:{...original.query,queryState},objects}};
}
function orderMonths(view){
 const category=view.categorical?.categories?.find(c=>c.source.roles?.trend);if(!category)return;
 const months=['january','february','march','april','may','june','july','august','september','october','november','december'];
 const indices=category.values.map(value=>typeof value==='string'?months.findIndex(month=>month===value.toLowerCase()||month.slice(0,3)===value.toLowerCase()):-1);
 if(indices.length&&indices.every(i=>i>=0))category.objects=indices.map(sortOrder=>({death2Kpi:{sortOrder}}));
}
const api={guid,adapt,orderMonths};root.NativeKPI=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
