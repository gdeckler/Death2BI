const assert=require('node:assert/strict'),E=require('./report-engine');
const col=(table,Property)=>({Column:{Expression:{SourceRef:{Entity:table}},Property}}),measure=Property=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property}});
const title=col('Movies','Title'),vote=measure('Votes'),svg=measure('SVG');
const top={filter:{From:[{Name:'sub',Expression:{Subquery:{Query:{From:[{Name:'m',Entity:'Movies'}],Select:[title],OrderBy:[{Direction:2,Expression:vote}],Top:7}}}},{Name:'m',Entity:'Movies'}],Where:[{Condition:{In:{Expressions:[title],Table:{SourceRef:{Source:'sub'}}}}}]}};
const predicate={filter:{From:[{Name:'m',Entity:'M'}],Where:[{Condition:{Comparison:{ComparisonKind:2,Left:{Measure:{Expression:{SourceRef:{Source:'m'}},Property:'Votes'}},Right:{Literal:{Value:'10000L'}}}}}]}};
const visual={type:'tableEx',filters:{filters:[top,predicate]},definition:{query:{queryState:{Values:{projections:[{field:title,nativeQueryRef:'Title'},{field:vote,nativeQueryRef:'Votes'},{field:svg,nativeQueryRef:'Rating'}]}}}}};
const model={id:'fixture',tables:[{name:'Movies',columns:[{name:'Title'},{name:'Votes'}]}],relationships:[],measures:[{TableName:'M',Name:'Votes',Expression:'SUM(Movies[Votes])'},{TableName:'M',Name:'SVG',Expression:'FORMAT([Votes],"0")'}]};
(async()=>{
 const before=JSON.stringify(visual),queryCalls=[],requests=[];
 const query=async sql=>{queryCalls.push(sql);assert.match(sql,/RANK\(\) OVER/);assert.match(sql,/_rank" <= 7/);return {rows:[['A'],['B']]}};
 const api=async(path,options)=>{const request=JSON.parse(options.body);requests.push(request);assert.equal(request.operation,undefined);assert.equal(request.groups.length,2);assert.equal(request.fields.length,4);assert.equal(request.fields[3].Measure.Property,'Votes');return {rows:[['A',12000,'<svg/>',12000],['B',9000,'<svg/>',9000]],columns:['v0','v1','v2','v3'],types:['VARCHAR','DOUBLE','VARCHAR','DOUBLE']}};
 const data=await E.pythonQuery(model,{},visual,[],query,api);
 assert.equal(queryCalls.length,1);assert.equal(requests.length,1);assert.deepEqual(data.result.rows,[['A',12000,'<svg/>']]);assert.deepEqual(data.compiled.roles,['Values','Values','Values']);assert.equal(data.compiled.labels.length,3);assert.equal(data.result.types.length,3);assert.equal(JSON.stringify(visual),before);
 // The same filter ordering also works when the Top N score needs Python DAX.
 const complex=structuredClone(model);complex.measures[0].Expression='MEDIANX(Movies,Movies[Votes])';let rankCalls=0;
 const complexApi=async(path,options)=>{const request=JSON.parse(options.body);if(request.operation==='topN'){rankCalls++;assert.equal(request.filters.length,0);return {values:['A','B']}}return api(path,options)};
 const selected=await E.pythonQuery(complex,{},visual,[],async sql=>{assert.match(sql,/IN| OR /);return {rows:[['A'],['B']]}},complexApi);
 assert.equal(rankCalls,1);assert.deepEqual(selected.result.rows,[['A',12000,'<svg/>']]);assert.equal(JSON.stringify(visual),before);
 console.log('PASS Top N plus aggregate/measure filters resolve before direct-column parsing, narrow SVG evaluation, preserve SQL/DAX ranking and hide helper fields');
})().catch(error=>{console.error(error);process.exitCode=1});
