const assert=require('node:assert/strict'),R=require('./vega-renderer');
const rows=Array.from({length:80},(_,i)=>['Category '+i,i+1]);
for(const type of ['waterfallChart','columnChart','clusteredColumnChart','lineChart','areaChart','ribbonChart'])assert.ok(R.contentWidth(type,['Category','Value'],rows,['Category','Y'],400)>400,type);
assert.equal(R.contentWidth('lineChart',['A','B'],[['One',1],['Two',2]],['Category','Y'],800),800);
assert.equal(R.contentWidth('map',['A','B'],rows,['Category','Size'],400),400);
const one=R.contentWidth('clusteredColumnChart',['A','B'],rows,['Category','Y'],400),many=R.contentWidth('clusteredColumnChart',['A','S','B'],rows.flatMap(r=>Array.from({length:8},(_,i)=>[r[0],'S'+i,r[1]])),['Category','Series','Y'],400);assert.ok(many>one);
assert.ok(R.contentWidth('lineChart',['A','B'],rows,['Category','Y'],5000)>=5000);console.log('PASS horizontal category capacity, clustered series spacing, short-chart fit and map isolation');
