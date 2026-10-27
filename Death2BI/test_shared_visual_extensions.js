const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const R=require('./vega-renderer'),C=require('./report-controls'),S=require('./report-style'),E=require('./report-engine'),I=require('./chart-interactions');
const context=vm.createContext({console,setTimeout,clearTimeout,structuredClone});for(const f of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+f,'utf8'),context);
const col=(table,column)=>({Column:{Expression:{SourceRef:{Entity:table}},Property:column}});
(async()=>{
 const area=R.buildSpec('hundredPercentStackedAreaChart',['Country','Series','Value'],[['A','x',2],['A','y',3],['B','x',1],['B','y',3]],['Category','Series','Y'],{formats:['','','0.00']});
 assert.equal(area.mark.type,'area');assert.equal(area.encoding.y.stack,'normalize');assert.equal(area.encoding.y.axis.format,'.0%');
 for(const spec of [area,R.buildSpec('gauge',['Value','Minimum','Maximum','Target'],[[30,10,50,35]],['Y','MinValue','MaxValue','TargetValue'])]){const compiled=context.vegaLite.compile(spec).spec;const view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'});await view.runAsync();view.finalize()}
 assert.throws(()=>R.buildSpec('gauge',['V','Min','Max'],[[1,2,2]],['Y','MinValue','MaxValue']),/increasing range/);
 const rows=Array.from({length:80},(_,i)=>['Category '+i,i]);const line=R.buildSpec('lineChart',['C','V'],rows,['Category','Y'],{width:4000});const runtime=context.vegaLite.compile(line).spec,view=new context.vega.View(context.vega.parse(runtime),{renderer:'none'});await view.runAsync();assert.equal(view.scale('x')('Category 0'),0);view.finalize();
 const bar=R.buildSpec('clusteredColumnChart',['C','V'],rows,['Category','Y']);assert.equal(bar.encoding.x.scale.paddingOuter,0);
 const v={type:'clusteredColumnChart',definition:{query:{queryState:{Category:{projections:[{field:col('Facts','Year')}]},Rows:{projections:[{field:col('Facts','Country')}]},Y:{projections:[{field:{Aggregation:{Expression:col('Facts','Value'),Function:0}}}]}}}}};
 const plan=R.smallMultiplePlan(v.type,['Year','Country','Value'],[[2020,'A',1],[2021,'A',2],[2020,'B',3]],['Category','Rows','Y'],{visual:v});assert.equal(plan.groups.length,2);assert.deepEqual(plan.groups[0].rows,[[2020,1],[2021,2]]);assert.equal(plan.visual.definition.query.queryState.Rows,undefined);assert.equal(v.definition.query.queryState.Rows.projections.length,1);assert.equal(I.bindings(v)[1].dataField,'_facet0');
 const slicer={type:'slicer',definition:{query:{queryState:{Values:{projections:[{field:col('Countries','Country')},{field:col('Population','Value')}]}}}}};
 const filter=C.hierarchyFilter(slicer,[['Finland',123],['Sweden']]);const parsed=E.parseFilters(filter);assert.equal(parsed[0].alternatives.length,2);assert.equal(parsed[0].alternatives[0].length,2);assert.equal(parsed[0].alternatives[1].length,1);assert.equal(C.hierarchyPlan(slicer,1,['Finland']).definition.query.queryState.Values.projections[0].field.Column.Property,'Value');
 const card={type:'multiRowCard',definition:slicer.definition};const html=S.cardResultMarkup({theme:{}},card,{labels:['Country','Population'],roles:['Values','Values'],formats:['','0.00']},{rows:[['Finland',12],['Sweden',15]]});assert.equal((html.match(/card-group/g)||[]).length,2);assert.match(html,/flex:none/);assert.match(html,/12.00/);
 console.log('PASS normalized area compilation, gauge range/target, zero-offset scale, facet partition/identity, hierarchy tuple filters, multi-row card groups');
})().catch(e=>{console.error(e);process.exitCode=1});


