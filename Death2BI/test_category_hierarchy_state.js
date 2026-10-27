const assert=require('node:assert/strict'),B=require('./report-behavior'),E=require('./report-engine'),I=require('./chart-interactions');
const col=Property=>({Column:{Expression:{SourceRef:{Entity:'Calendar'}},Property}}),sum={Aggregation:{Expression:col('Amount'),Function:0}};
const model={id:'hierarchy',tables:[{name:'Calendar',columns:[{name:'Year'},{name:'M'},{name:'Amount'}]}],relationships:[],measures:[]},page={id:'page'};
const source={id:'line',type:'lineChart',definition:{query:{queryState:{Category:{projections:[{field:col('Year'),nativeQueryRef:'Year',active:true},{field:col('M'),nativeQueryRef:'M',active:true}]},Y:{projections:[{field:sum,nativeQueryRef:'Amount'}]}},sortDefinition:{sort:[{field:col('M'),direction:'Descending'}]}}}};
const active=v=>v.definition.query.queryState.Category.projections.map(p=>p.active),before=JSON.stringify(source),state=new B.ExplorationState();
const planned=state.plan(model,page,source);
assert.deepEqual(active(planned),[true,true]);assert.equal(planned._hierarchy.depth,1);
assert.equal(state.get(model,page,source).expanded,true);
const sql=E.buildQuery(model,page,planned).sql;
assert.match(sql,/ORDER BY "v0" ASC, "v1" DESC$/);
assert.equal(JSON.stringify(source),before);

// An explicit authored drill state wins over individual expansion-node metadata.
const leaf=structuredClone(source);leaf.definition.query.queryState.Category.projections[0].active=false;leaf.definition.expansionStates=[{roles:['Category'],levels:[{isCollapsed:false}]}];
assert.deepEqual(active(new B.ExplorationState().plan(model,page,leaf)),[false,true]);
const off=structuredClone(source);off.definition.query.queryState.Category.projections.forEach(p=>p.active=false);
assert.deepEqual(active(new B.ExplorationState().plan(model,page,off)),[false,false]);
const legacy=structuredClone(source);legacy.definition.query.queryState.Category.projections.forEach(p=>delete p.active);legacy.definition.expansionStates=[{roles:['Category'],levels:[{isCollapsed:false}]}];
assert.deepEqual(active(new B.ExplorationState().plan(model,page,legacy)),[true,true]);
state.set(model,page,source,{...state.get(model,page,source),depth:0,path:[]});
assert.deepEqual(active(state.plan(model,page,source)),[true,false]);
state.set(model,page,source,{depth:1,path:[2023],expanded:false});
const drilled=state.plan(model,page,source);assert.deepEqual(active(drilled),[false,true]);
assert.equal(drilled.filters[0].filter.Where[0].Condition.In.Values[0][0].Literal.Value,'2023');

const descendingParents=structuredClone(source);descendingParents.definition.query.sortDefinition.sort.push({field:col('Year'),direction:'Descending'});
assert.match(E.buildQuery(model,page,descendingParents).sql,/ORDER BY "v0" DESC, "v1" DESC$/);
const noSort=structuredClone(source);delete noSort.definition.query.sortDefinition;
assert.match(E.buildQuery(model,page,noSort).sql,/ORDER BY "v0" ASC, "v1" ASC$/);
const metricSort=structuredClone(source);metricSort.definition.query.sortDefinition.sort=[{field:sum,direction:'Descending'}];
assert.match(E.buildQuery(model,page,metricSort).sql,/ORDER BY "v2" DESC, "v0" ASC, "v1" ASC$/);

(async()=>{
 const short='\u200bJ',long='\u200b\u200bJ',rows=[[2024,short,1],[2023,long,2],[2023,short,3],[2024,long,4]],expected=[[2023,long,2],[2023,short,3],[2024,long,4],[2024,short,1]];
 let request;
 const query=async sql=>({rows:structuredClone(rows),columns:['v0','v1','v2'],types:['INTEGER','VARCHAR','DOUBLE'],truncated:false});
 const api=async(path,options)=>{assert.equal(path,'/api/dax');request=JSON.parse(options.body);return {rows:structuredClone(rows),columns:['v0','v1','v2'],types:['INTEGER','VARCHAR','DOUBLE'],truncated:false}};
 const result=await E.pythonQuery(model,page,source,[],query,api);
 assert.deepEqual(result.result.rows,expected);assert.deepEqual(result.compiled.roles,['Category','Category','Y']);
 assert(request.groups.every(g=>g.scope.length===2&&g.filters.length===2));
 const identity=I.compoundIdentity(source,expected[0]);assert.deepEqual(identity.fields.map(f=>f.column),['Year','M']);
 const hover=E.tooltipPointFilters(source,{_rowIdentity:identity});
 assert.deepEqual(hover[0].filter.Where[0].Condition.In.Expressions,[col('Year'),col('M')]);
 assert.equal(hover[0].filter.Where[0].Condition.In.Values[0][1].Literal.Value,"'"+long+"'");
 assert.equal(JSON.stringify(source),before);
 console.log('PASS authored hierarchy activity, explicit drill changes, fallback expansion states, parent/descendant ordering, invisible sort prefixes, compound filters and source immutability');
})().catch(error=>{console.error(error);process.exitCode=1});
