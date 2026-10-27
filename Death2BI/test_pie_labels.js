const assert=require('node:assert/strict'),R=require('./vega-renderer');
const rows=Array.from({length:14},(_,i)=>['Category '+i,i+1]);
for(const type of ['pieChart','donutChart']){
 const spec=R.buildSpec(type,['Category','Count'],rows,['Category','Y'],{width:384,height:272});
 assert.ok(spec.config.legend.columns>=1&&spec.config.legend.columns<14);
 assert.equal(spec.config.legend.symbolLimit,14);
 const text=spec.layer.find(l=>l.encoding.text);assert.equal(spec.data.values.filter(d=>d._pieLabel).length,14);
 for(const side of [-1,1]){const ys=spec.data.values.filter(d=>d._pieSide===side).map(d=>d._pieY).sort((a,b)=>a-b);for(let i=1;i<ys.length;i++)assert.ok(ys[i]-ys[i-1]>=text.mark.fontSize+1.99)}
 assert.ok(spec.layer[0].mark.outerRadius>0);
 assert.equal(!!R.buildSpec(type,['Category','Count'],rows,['Category','Y'],{dataLabels:{show:false}}).layer,false);
 const formatted=R.buildSpec(type,['Category','Count'],[['A',.25],['B',.75]],['Category','Y'],{formats:[null,'0.0%'],dataLabels:{show:true,labelStyle:'Category, data value, percent of total',precision:1}});
 assert.equal(formatted.data.values[0]._pieLabel,'A · 25.0% · 25.0%');
}
console.log('PASS pie/donut wrapped legends, collision-separated callouts, source label styles/formats and explicitly hidden labels');
