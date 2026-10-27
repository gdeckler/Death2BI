(function(root){
const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=v=>Number(v).toLocaleString(undefined,{maximumFractionDigits:2,notation:Math.abs(v)>=1000000?'compact':'standard'});
const colors=['#337b60','#9dbd67','#4e8fa6','#c89849','#8b6aa8','#ca7b70','#568475','#889ab5'];
const types=['clusteredColumnChart','clusteredBarChart','columnChart','barChart','stackedColumnChart','stackedBarChart','hundredPercentStackedColumnChart','hundredPercentStackedBarChart','lineChart','areaChart','stackedAreaChart','pieChart','donutChart','scatterChart'];
function chartHTML(type,labels,rows,roles=[]){
 if(!rows.length)return '<p>No data for the current filters.</p>';
 let svg='',note='';const W=900,H=400;
 const wrap=s=>'<svg role="img" aria-label="'+escape(labels.join(' / '))+'" viewBox="0 0 '+W+' '+H+'" style="width:100%;height:85%;min-height:100px">'+s+'</svg>'+note;
 if(type==='scatterChart'){
  let xi=roles.indexOf('X'),yi=roles.indexOf('Y');if(xi<0)xi=0;if(yi<0)yi=1;
  const pts=rows.filter(r=>r[xi]!==null&&r[yi]!==null&&Number.isFinite(Number(r[xi]))&&Number.isFinite(Number(r[yi])));
  if(!pts.length)throw Error('Scatter chart needs numeric X and Y fields.');
  const xmax=Math.max(1,...pts.map(r=>+r[xi])),xmin=Math.min(0,...pts.map(r=>+r[xi])),ymax=Math.max(1,...pts.map(r=>+r[yi])),ymin=Math.min(0,...pts.map(r=>+r[yi]));
  svg='<path d="M70 20V350H870" fill="none" stroke="#b5c4b5"/>';
  svg+=pts.map(r=>'<circle cx="'+(70+(r[xi]-xmin)/(xmax-xmin)*800)+'" cy="'+(350-(r[yi]-ymin)/(ymax-ymin)*330)+'" r="5" fill="'+colors[0]+'" opacity=".65"><title>'+escape(labels[xi]+': '+r[xi]+', '+labels[yi]+': '+r[yi])+'</title></circle>').join('');return wrap(svg);
 }
 const category=roles.findIndex(r=>['Category','Rows','Details'].includes(r));const ci=category<0?0:category;
 const si=roles.findIndex(r=>['Series','Legend'].includes(r));
 let values=labels.map((_,i)=>i).filter(i=>i!==ci&&i!==si&&rows.some(r=>r[i]!==null&&typeof r[i]==='number'));
 if(!values.length)throw Error('Chart needs at least one numeric value.');
 const cats=[...new Set(rows.map(r=>String(r[ci]??'(Blank)')))];
 const allSeries=si<0?values.map(i=>({key:labels[i],i})): [...new Set(rows.map(r=>String(r[si]??'(Blank)')))].flatMap(key=>values.map(i=>({key:key+(values.length>1?' · '+labels[i]:''),i,series:key})));
 const lookup=new Map();
 for(const r of rows)for(const s of allSeries)if(si<0||String(r[si]??'(Blank)')===s.series){const key=JSON.stringify([String(r[ci]??'(Blank)'),s.key]);if(lookup.has(key))throw Error('Multiple rows map to the same chart point; additional dimensions need grouping.');lookup.set(key,r[s.i]===null?null:Number(r[s.i]))}
 const get=(c,s)=>lookup.get(JSON.stringify([c,s.key]));
 if(['pieChart','donutChart'].includes(type)){
  if(allSeries.length!==1)throw Error('Pie/donut charts require one value series.');
  const vals=cats.map(c=>get(c,allSeries[0])||0);if(vals.some(v=>v<0))throw Error('Pie/donut charts cannot show negative values.');
  const total=vals.reduce((a,b)=>a+b,0);if(!total)return '<p>No nonzero values.</p>';
  let angle=-Math.PI/2;
  vals.forEach((v,i)=>{if(!v)return;const next=angle+v/total*2*Math.PI,x=300+145*Math.cos(angle),y=195+145*Math.sin(angle),nx=300+145*Math.cos(next),ny=195+145*Math.sin(next);svg+=v===total?'<circle cx="300" cy="195" r="145" fill="'+colors[i%colors.length]+'"/>':'<path d="M300 195L'+x+' '+y+'A145 145 0 '+(v/total>.5?1:0)+' 1 '+nx+' '+ny+'Z" fill="'+colors[i%colors.length]+'"><title>'+escape(cats[i])+': '+number(v)+'</title></path>';angle=next;});
  if(type==='donutChart')svg+='<circle cx="300" cy="195" r="83" fill="white"/>';
  svg+=cats.slice(0,14).map((c,i)=>'<rect x="515" y="'+(20+i*25)+'" width="12" height="12" fill="'+colors[i%colors.length]+'"/><text x="537" y="'+(31+i*25)+'" font-size="13">'+escape(c)+' · '+number(vals[i])+'</text>').join('');
  if(cats.length>14)note='<small>Hover slices for all '+cats.length+' categories.</small>';return wrap(svg);
 }
 const visible=cats.slice(0,60);if(visible.length<cats.length)note='<small>Showing 60 of '+cats.length+' categories.</small>';
 const horizontal=/BarChart$/.test(type)||type==='barChart',stacked=/stacked/i.test(type)||['columnChart','barChart'].includes(type),percent=/hundredPercent/.test(type);
 const matrix=visible.map(c=>{let a=allSeries.map(s=>get(c,s)||0);if(percent){const total=a.reduce((s,v)=>s+Math.abs(v),0);a=a.map(v=>total?v/total*100:0)}return a});
 const lows=matrix.map(a=>stacked?a.filter(v=>v<0).reduce((s,v)=>s+v,0):Math.min(0,...a));
 const highs=matrix.map(a=>stacked?a.filter(v=>v>0).reduce((s,v)=>s+v,0):Math.max(0,...a));
 const min=Math.min(0,...lows),max=Math.max(1,...highs),scale=n=>350-(n-min)/(max-min)*300;
 for(let i=0;i<=4;i++){const n=min+(max-min)*i/4,y=scale(n);if(!horizontal)svg+='<path d="M80 '+y+'H880" stroke="#e4eae0"/><text x="72" y="'+(y+4)+'" text-anchor="end" font-size="12">'+escape(number(n)+(percent?'%':''))+'</text>'}
 const line=['lineChart','areaChart','stackedAreaChart'].includes(type);
 if(line){
  allSeries.forEach((s,j)=>{
   const segments=[];let run=[];
   matrix.forEach((a,i)=>{if(get(visible[i],s)==null){if(run.length)segments.push(run);run=[];return}const lower=type==='stackedAreaChart'?a.slice(0,j).filter(v=>a[j]<0?v<0:v>0).reduce((x,y)=>x+y,0):0;run.push({x:80+i*800/Math.max(1,visible.length-1),upper:scale(lower+a[j]),lower:scale(lower),value:a[j],category:visible[i]})});if(run.length)segments.push(run);
   for(const points of segments){
    if(type!=='lineChart')svg+='<polygon points="'+points.map(p=>p.x+','+p.upper).concat([...points].reverse().map(p=>p.x+','+p.lower)).join(' ')+'" fill="'+colors[j%colors.length]+'" opacity=".25"/>';
    svg+='<polyline points="'+points.map(p=>p.x+','+p.upper).join(' ')+'" fill="none" stroke="'+colors[j%colors.length]+'" stroke-width="3"/>';
    svg+=points.map(p=>'<circle cx="'+p.x+'" cy="'+p.upper+'" r="3" fill="'+colors[j%colors.length]+'"><title>'+escape(p.category+' · '+s.key+': '+number(p.value))+'</title></circle>').join('');
   }
  });
 }else{
  matrix.forEach((a,i)=>{let positive=0,negative=0;a.forEach((v,j)=>{const start=stacked?(v<0?negative:positive):0,end=start+v;if(stacked){if(v<0)negative=end;else positive=end}
   const slot=800/visible.length,offset=stacked?0:j*slot*.8/allSeries.length,band=slot*.8/(stacked?1:allSeries.length);
   const x=80+i*slot+offset,y=Math.min(scale(start),scale(end)),height=Math.abs(scale(start)-scale(end));
   const attrs=horizontal?'x="'+(180+(Math.min(start,end)-min)/(max-min)*650)+'" y="'+(30+i*(300/visible.length)+offset/slot*(300/visible.length))+'" width="'+(Math.abs(v)/(max-min)*650)+'" height="'+(band/slot*(300/visible.length))+'"':'x="'+x+'" y="'+y+'" width="'+Math.max(1,band)+'" height="'+height+'"';
   svg+='<rect '+attrs+' fill="'+colors[j%colors.length]+'"><title>'+escape(visible[i]+' · '+allSeries[j].key+': '+number(v)+(percent?'%':''))+'</title></rect>';
  })});
 }
 const stride=Math.max(1,Math.ceil(visible.length/(horizontal?15:10)));
 svg+=visible.map((c,i)=>i%stride?'':horizontal?'<text x="170" y="'+(35+i*300/visible.length)+'" text-anchor="end" font-size="12">'+escape(c)+'</text>':'<text x="'+(80+i*800/(line?Math.max(1,visible.length-1):visible.length))+'" y="375" font-size="12">'+escape(c.slice(0,18))+'</text>').join('');
 svg+=allSeries.slice(0,6).map((s,i)=>'<rect x="'+(85+i*135)+'" y="8" width="10" height="10" fill="'+colors[i%colors.length]+'"/><text x="'+(100+i*135)+'" y="18" font-size="11">'+escape(s.key.slice(0,20))+'</text>').join('');
 return wrap(svg);
}
const api={chartHTML,types};if(typeof module!=='undefined')module.exports=api;root.ChartRenderer=api;
})(globalThis);
