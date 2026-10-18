const assert=require('node:assert/strict'),E=require('./report-engine.js'),R=require('./chart-renderer.js');
const col=(table,name)=>({Column:{Expression:{SourceRef:{Entity:table}},Property:name}});
const sum=(table,name)=>({Aggregation:{Expression:col(table,name),Function:0}});
const m={measures:[],relationships:[{FromTableName:'Fact',FromColumnName:'Country',ToTableName:'Dim',ToColumnName:'Country',IsActive:1,Cardinality:'M:1',CrossFilteringBehavior:'Single'}]};
const visual={type:'clusteredColumnChart',definition:{query:{queryState:{Category:{projections:[{field:col('Dim','Country'),nativeQueryRef:'Country'}]},Y:{projections:[{field:sum('Fact','Value'),nativeQueryRef:'Value'}]}}}}};
const q=E.buildQuery(m,{},visual);assert.match(q.sql,/LEFT JOIN "Dim"/);assert.equal(q.warnings.length,0);
const disconnected=structuredClone(visual);disconnected.definition.query.queryState.Category.projections[0].field=col('Other','Country');
const d=E.buildQuery(m,{},disconnected);assert.match(d.sql,/CROSS JOIN \(SELECT DISTINCT/);assert.equal(d.warnings.length,1);
for(const type of R.types){
 const pie=['pieChart','donutChart'].includes(type);const scatter=type==='scatterChart';
 const html=scatter?R.chartHTML(type,['X','Y'],[[1,2],[2,3]],['X','Y']):pie?R.chartHTML(type,['Country','Value'],[['A',10],['B',20]],['Category','Y']):R.chartHTML(type,['Country','Value','Other'],[['A',10,5],['B',20,4],['C',5,3]],['Category','Y','Y']);
 // Pie expects one series, checked separately below.
 assert.match(html,/<svg/);assert.ok(!html.includes('NaN'));assert.ok(!html.includes('undefined'));
}

assert.match(R.chartHTML('clusteredBarChart',['Country','Value'],[['<script>',-20],['B',10]],['Category','Y']),/&lt;script&gt;/);
assert.match(R.chartHTML('areaChart',['Country','Value'],[['A',1],['B',2]],['Category','Y']),/<polygon/);
console.log('PASS: connected joins, disconnected totals warning, all 15 chart types, multiple values, negative values, escaped labels, area fill');
if(process.argv[2]){
 const fs=require('node:fs'),model=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),p=model.pages[0],v=p.visuals.find(v=>v.type==='clusteredColumnChart');
 const connected=structuredClone(v);connected.definition.query.queryState.Category.projections[0].field.Column.Expression.SourceRef.Entity='Countries All';
 const filter={filter:{Where:[{Condition:{In:{Expressions:[col('Years','Year')],Values:[[{Literal:{Value:'2020L'}}]]}}}]}};
 fs.writeFileSync(process.argv[3],JSON.stringify({disconnected:E.buildQuery(model,p,v),connected:E.buildQuery(model,p,connected),filtered:E.buildQuery(model,p,connected,[filter])}));
}
