const assert=require('node:assert/strict'),M=require('./matrix-rendering'),E=require('./report-engine'),T=require('./table-rendering'),S=require('./report-style');
const field=p=>({Column:{Expression:{SourceRef:{Entity:'Facts'}},Property:p}});
const v={type:'pivotTable',definition:{query:{queryState:{
 Rows:{projections:[{field:field('Year')},{field:field('Category'),active:false}]},
 Columns:{projections:[{field:field('Region')}]},
 Values:{projections:[{field:{Aggregation:{Expression:field('Amount'),Function:0}}}]}
}}}};
assert.deepEqual(M.plan(v).definition.query.queryState.Rows.projections.map(p=>p.active),[true,false]);
const child=M.plan(v,1,[2025]);assert.deepEqual(child.definition.query.queryState.Rows.projections.map(p=>p.active),[true,true]);assert.equal(child.filters[0].filter.Where[0].Condition.In.Values[0][0].Literal.Value,'2025');assert.equal(v.filters,undefined);
assert.equal(M.plan(v,1,["O'Brien"]).filters[0].filter.Where[0].Condition.In.Values[0][0].Literal.Value,"'O''Brien'");
assert.equal(M.plan(v,1,[null]).filters[0].filter.Where[0].Condition.In.Values[0][0].Literal.Value,'null');
assert.equal(M.plan({...v,filters:{filters:[{name:'Saved filter'}]}},1,[2025]).filters.length,2);
const data=M.groups({rows:[[2025,'East',7],[2025,'West',9],[2026,'East',2]]},{roles:['Rows','Columns','Values']},0);
assert.equal(data.nodes.length,2);assert.equal(data.columns.size,2);assert.deepEqual(data.nodes[0].cells.get('["West"]'),[9]);
assert.notEqual(T.rowColors({}, {}, S,0),T.rowColors({}, {}, S,1));
const props={backColorPrimary:'#abcdef',backColorSecondary:'#123456'};assert.equal(T.rowColors(props,{},S,0),'#abcdef');assert.equal(T.rowColors(props,{},S,1),'#123456');
assert.equal(T.rowColors({...props,bandedRows:false},{},S,1),'#abcdef');assert.equal(T.rowColors({backColorPrimary:'#fafafa',backColorSecondary:'#fafafa'},{},S,1),'#fafafa');
console.log('PASS matrix hierarchy plans, parent/blank/escaped filters, column pivot grouping and explicit/default banding');
const nodes=[{label:'Item 10',cells:new Map([['east',[5]]])},{label:'Item 2',cells:new Map([['east',[10]]])},{label:'Item 3',cells:new Map([['east',[null]]])},{label:'Item 4',cells:new Map([['east',[5]]])}];
assert.deepEqual(M.sortNodes(nodes,{columnKey:null,measure:0,descending:false}).map(n=>n.label),['Item 2','Item 3','Item 4','Item 10']);
assert.deepEqual(M.sortNodes(nodes,{columnKey:'east',measure:0,descending:true}).map(n=>n.label),['Item 2','Item 10','Item 4','Item 3']);
assert.deepEqual(M.sortNodes(nodes,{columnKey:'east',measure:0,descending:false}).map(n=>n.label),['Item 10','Item 4','Item 2','Item 3']);
assert.equal(nodes[0].label,'Item 10');
assert.equal(M.title({theme:{}},v),'');
const titled={...v,definition:{...v.definition,visualContainerObjects:{title:[{properties:{text:'Original title',show:true}}]}}};
assert.equal(M.title({theme:{}},titled),'Original title');
titled.definition.visualContainerObjects.title[0].properties.show=false;assert.equal(M.title({theme:{}},titled),'');
console.log('PASS cached Matrix sibling sorting, numeric/text/null/stable order and source-only titles');
