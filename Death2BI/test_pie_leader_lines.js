const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),R=require('./vega-renderer');
const c=vm.createContext({console,structuredClone,setTimeout,clearTimeout});for(const f of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync(__dirname+'/dist/vendor/'+f,'utf8'),c);
(async()=>{
 const rows=Array.from({length:30},(_,i)=>['Slice '+i,i+1]);
 for(const type of ['pieChart','donutChart']){
  const spec=R.buildSpec(type,['Category','Value'],rows,['Category','Y'],{width:500,height:400}),leader=spec.layer.find(l=>l.name==='pbi_pie_label_leaders');assert(leader);assert.equal(spec.data.values.filter(d=>d._pieLabel).length,12);
  const compiled=c.vegaLite.compile(spec).spec,rule=compiled.marks.find(m=>m.name==='pbi_pie_label_leaders_marks');for(const channel of ['x','y','x2','y2'])assert.match(rule.encode.update[channel].signal,/datum\._pie/);
  const view=new c.vega.View(c.vega.parse(compiled),{renderer:'none'});await view.runAsync();const items=[];function visit(n){if(n.mark?.name==='pbi_pie_label_leaders_marks')items.push(n);for(const child of n.items||[])visit(child)}visit(view.scenegraph().root);assert.equal(items.length,12);assert(items.every(d=>[d.x,d.y,d.x2,d.y2].every(Number.isFinite)));assert(items.every(d=>Math.hypot(d.x2-d.x,d.y2-d.y)>1));view.finalize();
  for(const dataLabels of [{show:true,position:'Inside'},{show:false,showSpecified:true}])assert(!R.buildSpec(type,['C','V'],rows,['Category','Y'],{dataLabels}).layer?.some(l=>l.name==='pbi_pie_label_leaders'));
 }
 console.log('PASS pie/donut compiled leader coordinates, twelve finite nonzero slice-to-label lines, inside/off label exclusions');
})().catch(e=>{console.error(e);process.exitCode=1});
