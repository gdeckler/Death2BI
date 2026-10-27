const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const B=require('./report-behavior'),E=require('./report-engine'),R=require('./vega-renderer');
const runtime=vm.createContext({console,setTimeout,clearTimeout,structuredClone});
for(const name of ['vega','vega-lite'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+name+'.min.js','utf8'),runtime);
const col=(table,Property)=>({Column:{Expression:{SourceRef:{Entity:table}},Property}}),literal=Value=>({expr:{Literal:{Value}}});
const model={id:'expanded-date-hierarchy',theme:{},measures:[],tables:[
 {name:'fuel_purchases',columns:[{name:'Year',type:'BIGINT'},{name:'Month Name',type:'VARCHAR',sortByColumn:'Month Number'},{name:'Month Number',type:'BIGINT'},{name:'total_cost',type:'DOUBLE'}]},
 {name:'Date',columns:[{name:'Date',type:'TIMESTAMP_NS'},{name:'Year',type:'BIGINT'},{name:'Month Name',type:'VARCHAR',sortByColumn:'Month Number'},{name:'Month Number',type:'BIGINT'}]},
 {name:'loads',columns:[{name:'load_date',type:'TIMESTAMP_NS'},{name:'load_id',type:'VARCHAR'}]}
],relationships:[{FromTableName:'loads',FromColumnName:'load_date',ToTableName:'Date',ToColumnName:'Date',IsActive:1,Cardinality:'M:1',CrossFilteringBehavior:'Single'}]};
const page={id:'page'},months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fixture(yFirst){
 const table=yFirst?'Date':'fuel_purchases',Category={projections:['Year','Month Name'].map(Property=>({queryRef:table+'.'+Property,nativeQueryRef:Property,active:true,field:col(table,Property)}))};
 const field={Aggregation:{Expression:col(yFirst?'loads':'fuel_purchases',yFirst?'load_id':'total_cost'),Function:yFirst?5:0}},Y={projections:[{field,nativeQueryRef:yFirst?'Count of load_id':'Sum of total_cost'}]};
 // Preserve the two source layouts: Monthly Fuel Cost Trend has Category first;
 // Load Volume Trend has Y first, so hierarchy columns are at indices 1 and 2.
 const visual={id:yFirst?'load-volume':'monthly-fuel',type:'areaChart',definition:{query:{queryState:yFirst?{Y,Category}:{Category,Y}},objects:{categoryAxis:[{properties:{showAxisTitle:literal('false')}}]}}};
 const rows=Array.from({length:36},(_,i)=>{const year=2022+Math.floor(i/12),month=months[i%12],value=1000+i;return yFirst?[value,year,month]:[year,month,value]});
 return {visual,rows,categoryOffset:yFirst?1:0,table};
}
function sceneAxisText(view){const found=[];function walk(node){if(!node)return;if(node.mark?.role==='axis-label'&&node.text!==undefined)found.push(Array.isArray(node.text)?node.text.join(' '):String(node.text));for(const item of node.items||[])walk(item)}walk(view.scenegraph().root);return found}
(async()=>{
 for(const yFirst of [false,true]){
  const {visual:source,rows,categoryOffset:ci,table}=fixture(yFirst),before=JSON.stringify({model,source,rows}),visual=E.formattingVisual(new B.ExplorationState().plan(model,page,source),model),compiled=E.buildQuery(model,page,visual);
  assert.deepEqual(visual.definition.query.queryState.Category.projections.map(p=>p.active),[true,true]);assert.equal(visual._hierarchy.depth,1);
  assert.deepEqual(compiled.roles,yFirst?['Y','Category','Category']:['Category','Category','Y']);
  assert.match(compiled.sql,new RegExp('GROUP BY "'+table+'"\\."Year", "'+table+'"\\."Month Name"'));
  assert.ok(compiled.sql.endsWith('ORDER BY "v'+ci+'" ASC, MIN("'+table+'"."Month Number") ASC'),'month names must follow the model sort column within each year');
  if(yFirst)assert.match(compiled.sql,/COUNT\("loads"\."load_id"\)/);else assert.match(compiled.sql,/SUM\("fuel_purchases"\."total_cost"\)/);
  const width=R.contentWidth(visual.type,compiled.labels,rows,compiled.roles,800,{model,visual}),spec=R.buildSpec(visual.type,compiled.labels,rows,compiled.roles,{model,visual,width,height:240,formats:compiled.formats});
  assert.equal(spec.data.values.length,36,'Year must remain a category instead of becoming another value series');assert.equal(spec.encoding.x.type,'ordinal');
  const expected=rows.map(row=>row[ci]+' / '+row[ci+1]);assert.deepEqual(spec.data.values.map(d=>d._category),expected);assert(width>800,'horizontal content includes every Year/Month position');
  for(const [i,datum] of spec.data.values.entries()){
   assert.deepEqual(datum._rowIdentity.fields.map(f=>f.column),['Year','Month Name']);
   const condition=E.tooltipPointFilters(visual,datum)[0].filter.Where[0].Condition.In;
   assert.deepEqual(condition.Expressions,[col(table,'Year'),col(table,'Month Name')]);
   assert.deepEqual(condition.Values,[[{Literal:{Value:String(rows[i][ci])}},{Literal:{Value:"'"+rows[i][ci+1]+"'"}}]]);
  }
  const view=new runtime.vega.View(runtime.vega.parse(runtime.vegaLite.compile(spec).spec),{renderer:'none'});
  try{await view.runAsync();assert.deepEqual(Array.from(view.scale('x').domain()),expected);const axis=sceneAxisText(view);for(const category of expected)assert(axis.includes(category),'both hierarchy levels must remain visible: '+category);const svg=await view.toSVG();assert(!svg.includes('NaN')&&!svg.includes('Infinity'))}finally{view.finalize()}
  assert.equal(JSON.stringify({model,source,rows}),before,'source projection activity, fields, rows and model sort metadata remain unchanged');
 }
 console.log('PASS source-equivalent area hierarchies in Category-first and Y-first queries: active Year/Month, model chronological sorting, 36 visible positions, compound hover identities and immutable inputs');
})().catch(error=>{console.error(error);process.exitCode=1});
