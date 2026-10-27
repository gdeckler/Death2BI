const assert=require('node:assert/strict'),E=require('./report-engine');
const column=(table,Property)=>({Column:{Expression:{SourceRef:{Entity:table}},Property}}),measure=Property=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property}}),literal=Value=>({Literal:{Value:typeof Value==='string'?"'"+Value.replaceAll("'","''")+"'":String(Value)}}),comparison=(Left,Right,ComparisonKind=0)=>({Comparison:{ComparisonKind,Left,Right:literal(Right)}}),entry=(Condition,name)=>({name,filter:{Version:2,Where:[{Condition}]}});
const category=column('Facts','Category'),stage=column('Facts','LifeStage'),amount=measure('Amount'),physical=comparison(stage,'Childhood'),result=comparison(amount,1,2),selection=entry({In:{Expressions:[category],Values:[[literal('Spiders')]]}},'point');
const model={tables:[{name:'Facts',columns:[{name:'Category',type:'VARCHAR'},{name:'LifeStage',type:'VARCHAR'},{name:'Value',type:'DOUBLE'}]}],relationships:[],measures:[{TableName:'M',Name:'Amount',Expression:'SUM(Facts[Value])'}]},tip={id:'tip',visuals:[],filters:[]},target={type:'clusteredColumnChart',definition:{query:{queryState:{Category:{projections:[{field:category}]},Y:{projections:[{field:amount}]}}}}};

// Family-style source: a physical life-stage predicate plus a measure predicate
// that already selected the hovered board row. The tooltip has a new grain.
const source={filters:{filters:[entry(physical,'life-stage'),entry(result,'on-board')]}},before=JSON.stringify({model,tip,source,selection}),context=E.tooltipContext({},tip,source,[],[selection]);
assert.deepEqual(context.filters.map(f=>f.name),['life-stage','point']);
const sql=E.buildQuery(model,context,target).sql;assert.match(sql,/LifeStage.*Childhood/);assert.match(sql,/Category.*Spiders/);assert.doesNotMatch(sql,/on-board/);
assert.throws(()=>E.buildQuery(model,{...tip,filters:[...source.filters.filters,selection]},target),/not a direct column/,'regression fixture must reject the old raw measure-filter inheritance');
assert.equal(JSON.stringify({model,tip,source,selection}),before);

// Preserve independent row predicates in conjunctions and across Where entries.
const mixed=entry({And:{Left:physical,Right:{And:{Left:result,Right:comparison(category,'Spiders')}}}},'mixed');
mixed.filter.Where.push({Condition:comparison(amount,0,1)},{Condition:{Not:{Expression:comparison(stage,'Adult')}}});
let plan=E.tooltipContext({},tip,{filters:[mixed]},[],[selection]);assert.equal(plan.filters.length,2);assert.deepEqual(plan.filters[0].filter.Where,[{Condition:{And:{Left:physical,Right:comparison(category,'Spiders')}}},{Condition:{Not:{Expression:comparison(stage,'Adult')}}}]);assert.doesNotThrow(()=>E.buildQuery(model,plan,target));

const physicalOr={Or:{Left:comparison(stage,'Childhood'),Right:comparison(stage,'Adult')}},physicalNot={Not:{Expression:comparison(category,'Other')}};
plan=E.tooltipContext({},tip,{filters:[entry(physicalOr,'row-or'),entry(physicalNot,'row-not'),entry({Or:{Left:physical,Right:result}},'mixed-or'),entry({Not:{Expression:{And:{Left:physical,Right:result}}}},'mixed-not')]},[],[selection]);
assert.deepEqual(plan.filters.map(f=>f.name),['row-or','row-not','point'],'mixed OR/NOT cannot invent a narrower retained dimension branch');assert.deepEqual(plan.filters[0].filter.Where[0].Condition,physicalOr);assert.deepEqual(plan.filters[1].filter.Where[0].Condition,physicalNot);assert.doesNotThrow(()=>E.buildQuery(model,plan,target));

// Tooltip-owned predicates and every external/security context remain intact.
const own=entry(result,'tooltip-owned'),pageFilter=entry(physical,'page'),report=entry(physical,'report'),extra=entry(physical,'security-extra'),scopedTip={...tip,filters:[own]},page={filters:[pageFilter],reportFilters:[report]};
plan=E.tooltipContext(page,scopedTip,source,[extra],[selection]);assert.deepEqual(plan.filters.map(f=>f.name),['tooltip-owned','page','life-stage','security-extra','point']);assert.deepEqual(plan.reportFilters,[report]);assert.deepEqual(plan.filters[0],own,'only source result-row predicates are projected away');
plan=E.tooltipContext(page,{...scopedTip,pageBinding:{acceptsFilterContext:'None'}},source,[extra],[selection]);assert.deepEqual(plan.filters,[own,selection]);assert.deepEqual(plan.reportFilters,[report]);

// A source Top N row-domain predicate is redundant only when the point fixes
// that ranked field. Scalar cards and missing/unproven identities retain it.
const top={name:'top',filter:{From:[{Name:'sub',Expression:{Subquery:{Query:{From:[{Name:'f',Entity:'Facts'},{Name:'m',Entity:'M'}],Select:[category],OrderBy:[{Direction:2,Expression:amount}],Top:7}}}},{Name:'f',Entity:'Facts'}],Where:[{Condition:{In:{Expressions:[category],Table:{SourceRef:{Source:'sub'}}}}}]}};
plan=E.tooltipContext({},tip,{filters:[top]},[],[selection]);assert.deepEqual(plan.filters,[selection]);assert.doesNotMatch(E.buildQuery(model,plan,target).sql,/RANK\(\)/);
for(const points of [[],[entry({In:{Expressions:[stage],Values:[[literal('Childhood')]]}},'other-field')],[entry({Or:{Left:{In:{Expressions:[category],Values:[[literal('Spiders')]]}},Right:physical}},'unproven-or')],[entry({In:{Expressions:[category],Values:[[literal('Spiders'),literal('extra')]]}},'invalid-tuple')]]){
 plan=E.tooltipContext({},tip,{filters:[top]},[],points);assert.deepEqual(plan.filters[0],top,'retain an unproven Top N domain rather than silently widen it');
}
const multiple=entry({In:{Expressions:[category,stage],Values:[[literal('Spiders'),literal('Childhood')],[literal('Snakes'),literal('Adult')]]}},'multiple-points');plan=E.tooltipContext({},tip,{filters:[top]},[],[multiple]);assert.deepEqual(plan.filters,[multiple]);
const aliasPoint={filter:{From:[{Name:'f',Entity:'Facts'}],Where:[{Condition:{In:{Expressions:[{Column:{Expression:{SourceRef:{Source:'f'}},Property:'Category'}}],Values:[[literal('Spiders')]]}}}]}};assert.deepEqual(E.tooltipContext({},tip,{filters:[top]},[],[aliasPoint]).filters,[aliasPoint]);
const unknown=entry({CustomPredicate:{field:category}},'unsupported');assert.deepEqual(E.tooltipContext({},tip,{filters:[unknown]}).filters,[unknown],'unsupported physical predicates remain fail-closed rather than disappearing');
const malformed=entry({And:{Left:physical}},'malformed');assert.deepEqual(E.tooltipContext({},tip,{filters:[malformed]}).filters,[malformed]);assert.throws(()=>E.buildQuery(model,E.tooltipContext({},tip,{filters:[malformed]}),target),'malformed filters must remain fail-closed rather than becoming a valid narrower branch');
console.log('PASS tooltip source result-predicate projection, physical AND/OR/NOT semantics, proven Top N identities, scalar/unproven domain retention, target/external/security scopes and source immutability');
