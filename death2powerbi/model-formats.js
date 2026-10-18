(function(root){
function d3(format){
 if(!format)return null;
 const s=String(format).split(';')[0],named={percent:'.2%', 'whole number':',.0f','decimal number':',.2f',general:null};
 if(Object.hasOwn(named,s.toLowerCase()))return named[s.toLowerCase()];
 if(!/[0#]/.test(s)||/[dy]/i.test(s.replace(/"[^"]*"/g,'')))return null;
 const m=s.match(/\.([0#]+)/),digits=m?m[1].length:0;
 if(digits>20)return null;
 return (s.includes(',')?',':'')+'.'+digits+(s.includes('%')?'%':'f');
}
function text(value,format){
 if(value==null)return '—';if(typeof value!=='number'||!format)return String(value);
 const f=d3(format);if(!f)return String(value);
 const digits=Number(f.match(/\.(\d+)/)[1]);return new Intl.NumberFormat('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits,useGrouping:f.startsWith(','),style:f.endsWith('%')?'percent':'decimal'}).format(value);
}
const api={d3,text};if(typeof module!=='undefined')module.exports=api;root.ModelFormats=api;
})(globalThis);
