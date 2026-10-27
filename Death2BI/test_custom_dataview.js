const assert=require('node:assert/strict'),D=require('./custom-dataview.js'),F=require('./custom-frame.js');
const col=(name)=>({Column:{Expression:{SourceRef:{Entity:'Data'}},Property:name}});
const visual={definition:{query:{queryState:{
 category:{projections:[{field:col('Country')}]},
 time:{projections:[{field:col('Year')}]},
 measure:{projections:[{field:{Aggregation:{Expression:col('Value'),Function:0}}}]}
}}}};
const pkg={capabilities:{dataRoles:[{name:'category'},{name:'time'},{name:'measure',kind:'Measure'}],dataViewMappings:[{categorical:{categories:{for:{in:'category'}},values:{group:{by:'time',select:[{for:{in:'measure'}}]}}}}]}};
const result={columns:['a','b','c'],types:['VARCHAR','INTEGER','DOUBLE'],rows:[['A',2020,1],['B',2020,2],['A',2021,3],['B',2021,4]]};
const view=D.build(pkg,visual,result,{labels:['Country','Year','Value'],formats:['','','0.0%']});
assert.deepEqual(view.categorical.categories[0].values,['A','B']);assert.deepEqual(view.categorical.values.map(c=>c.values),[[1,2],[3,4]]);assert.equal(view.categorical.values[1].source.groupName,2021);assert.equal(view.categorical.values[0].source.format,'0.0%');assert.deepEqual(view.categorical.categories[0].identity[0].rows,[0,2]);
assert.throws(()=>D.build(pkg,visual,{...result,rows:[...result.rows,result.rows[0]]},{labels:['Country','Year','Value']}),/duplicate category/);
const table=D.build({capabilities:{dataViewMappings:[{table:{}}]}},{definition:{query:{queryState:{date:{projections:[{field:col('Date')}]}}},objects:{axis:[{properties:{rowHeight:{expr:{Literal:{Value:'24D'}}}}}]}}},{columns:['Date'],types:['DATE'],rows:[['2024-01-01']]},{labels:['Date']});
assert(table.table.rows[0][0] instanceof Date);assert.equal(table.metadata.objects.axis.rowHeight,24);
const doc=F.documentFor({guid:'SampleGuid',js:'window.x="</script><img src=x>"',networkDomains:['https://*.tile.openstreetmap.org']},'token123');
assert.equal((doc.match(/<\/script>/gi)||[]).length,1);assert(!doc.includes('connect-src https:'));assert(doc.includes("connect-src 'none'"));assert(doc.includes('\\u003c/script'));
const networkDoc=F.documentFor({guid:'SampleGuid',js:'',networkDomains:['https://*.tile.openstreetmap.org']},'token123',true);assert(networkDoc.includes('connect-src https://*.tile.openstreetmap.org'));
console.log('PASS: table/date/format adapters, grouped categorical time series, stable row identities, duplicate rejection and isolated CSP document escaping');

const optional={capabilities:{dataRoles:[{name:'category'},{name:'measure',kind:'Measure'},{name:'legend'}],dataViewMappings:[{categorical:{categories:{for:{in:'category'}},values:{group:{by:'legend',select:[{bind:{to:'measure'}}]}}}}]}};
const noLegend=structuredClone(visual);delete noLegend.definition.query.queryState.time;
const optionalView=D.build(optional,noLegend,{columns:['Country','Value'],types:['VARCHAR','DOUBLE'],rows:[['A',1],['B',2]]},{labels:['Country','Value']});assert.deepEqual(optionalView.categorical.values[0].values,[1,2]);assert.equal(optionalView.categorical.values.source,undefined);
console.log('PASS: optional custom visual legend grouping (MAQ box/whisker)');
const posterDoc=F.documentFor({guid:'SampleGuid',js:''},'posterToken',false,{},['https://image.tmdb.org/poster.jpg','http://bad.test/a.jpg','https://bad.test/a.jpg;connect-src *','https://user:secret@bad.test/a.jpg'],true);
assert(posterDoc.includes('https://image.tmdb.org/poster.jpg'));
assert(!posterDoc.includes('bad.test'));
assert(posterDoc.includes("connect-src 'none'"));
assert(posterDoc.includes('"reportTooltip":true'));
assert(posterDoc.includes("send('tooltipLeave')"));
assert(posterDoc.includes('rows:hoverRows'));
console.log('PASS: exact HTTPS poster CSP, credential/directive rejection and report-tooltip identity bridge');
