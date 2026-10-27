const assert=require('node:assert/strict'),R=require('./vega-renderer');
const column=(table,property)=>({Column:{Expression:{SourceRef:{Entity:table}},Property:property}}),measure=name=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property:name}}),projection=(field,label,queryRef)=>({field,nativeQueryRef:label,queryRef:queryRef||label});
const visual={type:'lineChart',definition:{query:{queryState:{Category:{projections:[projection(column('T','Year'),'Year'),projection(column('T','Month'),'Month')]},Tooltips:{projections:[projection(measure('Arrow'),'Enrollment Arrow','M.Enrollment Direction')]},Y:{projections:[projection(measure('Actual'),'Actual'),projection(measure('Prior'),'Prior')]}}}}};
const labels=['Year','Month','Enrollment Arrow','Actual','Prior'],roles=['Category','Category','Tooltips','Y','Y'],rows=[[2025,'Jan','↑',120,100],[2026,'Jan','↓',80,100]],formats=[['0','','','0.00','0.0'],['0','','','0.0%','0.000']];
const before=JSON.stringify({visual,rows,formats}),spec=R.buildSpec('lineChart',labels,rows,roles,{model:{},visual,rowFormats:formats});
assert.equal(spec.data.values.length,4);
for(const datum of spec.data.values){const index=rows.indexOf(datum._rowValues);assert.ok(index>=0);assert.equal(datum._rowFormats,formats[index]);assert.equal(datum._raw['Enrollment Arrow'],rows[index][2]);assert.equal(datum._rowIdentity.fields.length,2)}
assert.equal(JSON.stringify({visual,rows,formats}),before,'render metadata must not change source rows/definitions');

// Sampling retains the original row and its format even when invalid earlier rows are discarded.
const scatterRows=[[null,3,'Skip','x'],[2,4,'Point','↑']],scatterFormats=[['0','0.0','',''],['0.000','0.00%','','']];
const scatter=R.buildSpec('scatterChart',['X','Y','Item','Enrollment Arrow'],scatterRows,['X','Y','Details','Tooltips'],{rowFormats:scatterFormats});
assert.equal(scatter.data.values.length,1);assert.equal(scatter.data.values[0]._rowValues,scatterRows[1]);assert.equal(scatter.data.values[0]._rowFormats,scatterFormats[1]);
// Coordinate conversion is rendering-only; sentence fields keep their original query values.
const mapRows=[['45.5','2.25','Point','↑']],mapFormats=[['0.00','0.000','','']];
const map=R.buildSpec('pointMap',['Latitude','Longitude','Item','Enrollment Arrow'],mapRows,['Latitude','Longitude','Details','Tooltips'],{rowFormats:mapFormats});
assert.equal(map.data.values[0]._latitude,45.5);assert.equal(map.data.values[0]._rowValues,mapRows[0]);assert.equal(map.data.values[0]._rowFormats,mapFormats[0]);assert.equal(mapRows[0][0],'45.5');

// Small multiple projection removes its facet only from chart encodings, not the source row contract.
const multipleRows=[['West','A','↑',10],['East','B','↓',20]],multipleFormats=[['','','','0.00'],['','','','0%']],multipleLabels=['Region','Item','Arrow','Value'],multipleRoles=['SmallMultiples','Category','Tooltips','Y'];
const plan=R.smallMultiplePlan('clusteredColumnChart',multipleLabels,multipleRows,multipleRoles,{rowFormats:multipleFormats}),group=plan.groups.find(group=>group.title==='West');
const multiple=R.buildSpec('clusteredColumnChart',plan.labels,group.rows,plan.roles,{_rowFormatMap:plan.rowFormatMap,_rowValueMap:plan.rowValueMap,_sourceRowFormatMap:plan.sourceRowFormatMap});
assert.equal(multiple.data.values[0]._rowValues,multipleRows[0]);assert.equal(multiple.data.values[0]._rowFormats,multipleFormats[0]);
const unformatted=R.smallMultiplePlan('clusteredColumnChart',multipleLabels,multipleRows,multipleRoles,{formats:['','','','0.0']}),plain=R.buildSpec('clusteredColumnChart',unformatted.labels,unformatted.groups[0].rows,unformatted.roles,{_rowFormatMap:unformatted.rowFormatMap,_rowValueMap:unformatted.rowValueMap,_sourceRowFormatMap:unformatted.sourceRowFormatMap});
assert.equal(plain.data.values[0]._rowFormats,undefined,'projected format indices cannot be mistaken for original field indices');
const base=R.buildSpec('clusteredColumnChart',['Item','Value'],[['A',10]],['Category','Y']),hit=R.buildSpec('clusteredColumnChart',['Item','Value'],[['A',4]],['Category','Y'],{rowFormats:[['','0.0%']]}),highlight=R.highlightSpec(base,hit,'clusteredColumnChart');
assert.equal(highlight.layer[1].data.values[0]._rowValues[1],4);assert.equal(highlight.layer[1].data.values[0]._rowFormats[1],'0.0%');

async function tooltipFlags(){
 const previous={document:global.document,vegaEmbed:global.vegaEmbed,ResizeObserver:global.ResizeObserver};
 const captures=[];global.ResizeObserver=undefined;
 global.document={createElement:()=>({style:{},className:'',querySelectorAll:()=>[]})};
 // Match VegaEmbed's contract: false leaves Vega's native title handler in place;
 // only a callable tooltip replaces it. The app's custom hover runs separately.
 global.vegaEmbed=async(surface,spec,options)=>{const listeners=[],handlers={};let tooltip=(_handler,_event,_item,value)=>{surface.title=String(value)};if(typeof options.tooltip==='function')tooltip=options.tooltip;const capture={options,listeners,handlers,surface,hover:value=>tooltip(null,{},null,value)};captures.push(capture);return {view:{addEventListener:(name,handler)=>{listeners.push(name);handlers[name]=handler},finalize(){}}}};
 const element=()=>({style:{},clientWidth:400,clientHeight:240,isConnected:true,replaceChildren(){},setAttribute(){},addEventListener(){},removeEventListener(){}});
 try{
  await R.mount(element(),'lineChart',['Item','Value'],[['A',1]],['Category','Y'],{tooltip:false,onHover:()=>assert.fail('disabled hover')});
  assert.equal(typeof captures[0].options.tooltip,'function');captures[0].hover('Native tooltip must not appear');assert.equal(captures[0].surface.title,undefined);assert(!captures[0].listeners.includes('mousemove'));
  await R.mount(element(),'lineChart',['Item','Value'],[['A',1]],['Category','Y'],{});assert.equal(captures[1].options.tooltip,true);
  const custom=[];await R.mount(element(),'lineChart',['Item','Value'],[['A',1]],['Category','Y'],{onHover:datum=>custom.push(datum)});assert.equal(typeof captures[2].options.tooltip,'function');assert(captures[2].listeners.includes('mousemove'));
  captures[2].hover('Native tooltip must not accompany sentence/report-page tooltip');assert.equal(captures[2].surface.title,undefined);const datum={_rowValues:['A',1]};captures[2].handlers.mousemove({}, {datum,mark:{role:'mark'}});assert.deepEqual(custom,[datum]);
  await R.mount(element(),'scatterChart',['X','Y'],[[1,2]],['X','Y'],{onHover(){}});assert.equal(typeof captures[3].options.tooltip,'function');captures[3].hover('Advanced chart native tooltip');assert.equal(captures[3].surface.title,undefined);assert(captures[3].listeners.includes('mousemove'));
  await R.mount(element(),'scatterChart',['X','Y'],[[1,2]],['X','Y'],{tooltip:false});assert.equal(typeof captures[4].options.tooltip,'function');captures[4].hover('Disabled advanced chart native tooltip');assert.equal(captures[4].surface.title,undefined);assert(!captures[4].listeners.includes('mousemove'));
 }finally{R.disposeAll();Object.assign(global,previous)}
}
tooltipFlags().then(()=>console.log('PASS original chart row/alias metadata, dynamic formats, hierarchy/multi-series context, filtered scatter, coordinate maps, facets/highlights and explicit tooltip disable')).catch(error=>{console.error(error);process.exitCode=1});
