(function(root){
function d3(format){
 if(!format)return null;
 if(/^[NnFfPpCc]\d*$/.test(format)){const n=Math.min(20,Number(format.slice(1)||2)),kind=format[0].toUpperCase();return (kind==='C'?'$':'')+(kind==='N'||kind==='C'?',':'')+'.'+n+(kind==='P'?'%':'f')}
 const s=String(format).split(';')[0],named={percent:'.2%', 'whole number':',.0f','decimal number':',.2f',general:null};
 if(Object.hasOwn(named,s.toLowerCase()))return named[s.toLowerCase()];
 if(!/[0#]/.test(s)||/[dy]/i.test(s.replace(/"[^"]*"/g,'')))return null;
 const m=s.match(/\.([0#]+)/),digits=m?m[1].length:0;
 if(digits>20)return null;
 return (s.includes(',')?',':'')+'.'+digits+(s.includes('%')?'%':'f');
}
function sections(format){
 const parts=[''];let quoted=false,escaped=false;
 for(const c of String(format)){if(c===';'&&!quoted&&!escaped){parts.push('');continue}parts[parts.length-1]+=c;if(c==='"'&&!escaped)quoted=!quoted;if(c==='\\'&&!escaped)escaped=true;else escaped=false}return parts;
}
// PBIR projection formats use .NET syntax; legacy visual column formats use
// model/VBA syntax. Bind the latter by the authored query reference, including
// implicit aggregate aliases, rather than guessing from a display label.
function visualFormat(visual,projection){
 if(typeof projection?.format==='string')return {format:projection.format,source:'visual',dialect:'dotnet'};
 const columns=visual?.definition?.columnProperties,key=projection?.queryRef;
 if(typeof key==='string'&&columns&&Object.hasOwn(columns,key)&&typeof columns[key]?.formatString==='string')return {format:columns[key].formatString,source:'visual',dialect:'vba'};
}
function resolve(model,visual,index,{element={},dynamicFormat}={}){
 const ps=Object.values(visual.definition?.query?.queryState||{}).flatMap(q=>(q.projections||[]).filter(p=>p.active!==false)),p=ps[index]||{};let f=p.field||{};while(f.Aggregation)f=f.Aggregation.Expression;
 const m=f.Measure&&model.measures?.find(m=>m.Name===f.Measure.Property&&(!f.Measure.Expression?.SourceRef?.Entity||m.TableName===f.Measure.Expression.SourceRef.Entity)),c=f.Column||f.GroupRef;
 let format=dynamicFormat??m?.FormatString??(c?model.tables?.find(t=>t.name===c.Expression?.SourceRef?.Entity)?.columns?.find(x=>x.name===c.Property)?.formatString:undefined)??'',source=dynamicFormat!==undefined?'dynamic-model':'model',dialect='vba';
 const authored=visualFormat(visual,p);if(authored)({format,source,dialect}=authored);
 const Style=typeof module!=='undefined'?require('./report-style'):root.ReportStyle;
 for(const key of ['formatString','labelFormatString','customFormatString','format'])if(Object.hasOwn(element,key)){const x=Style.value(element[key],model.theme);if(typeof x==='string'){format=x;source='element';dialect='vba';break}}
 return {format,source,dialect,locale:model.reportSettings?.locale||'en-US',units:model.reportSettings?.defaultDisplayUnitsToNone===true?1:undefined};
}
function vegaLocale(locale='en-US'){
 let number,date;try{number=new Intl.NumberFormat(locale);date=new Intl.DateTimeFormat(locale)}catch{locale='en-US';number=new Intl.NumberFormat(locale);date=new Intl.DateTimeFormat(locale)}
 const parts=number.formatToParts(1234567.89),part=(type,fallback)=>parts.find(p=>p.type===type)?.value??fallback,day=(i,style)=>new Intl.DateTimeFormat(locale,{weekday:style,timeZone:'UTC'}).format(new Date(Date.UTC(2023,0,1+i))),month=(i,style)=>new Intl.DateTimeFormat(locale,{month:style,timeZone:'UTC'}).format(new Date(Date.UTC(2023,i,1)));
 const integers=parts.filter(p=>p.type==='integer').map(p=>p.value.length).reverse(),grouping=integers.slice(0,-1);if(grouping.length===0)grouping.push(3);if(grouping.every(x=>x===grouping[0]))grouping.splice(1);
 return {number:{decimal:part('decimal','.'),thousands:part('group',','),grouping,currency:['$',''],minus:number.formatToParts(-1).find(p=>p.type==='minusSign')?.value||'-',percent:new Intl.NumberFormat(locale,{style:'percent'}).formatToParts(1).find(p=>p.type==='percentSign')?.value||'%'},time:{dateTime:'%x, %X',date:new Intl.DateTimeFormat(locale,{year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(Date.UTC(2023,0,2))).map(p=>({year:'%Y',month:'%m',day:'%d'}[p.type]||p.value)).join(''),time:'%H:%M:%S',periods:['AM','PM'],days:Array.from({length:7},(_,i)=>day(i,'long')),shortDays:Array.from({length:7},(_,i)=>day(i,'short')),months:Array.from({length:12},(_,i)=>month(i,'long')),shortMonths:Array.from({length:12},(_,i)=>month(i,'short'))}};
}
function dateText(input,format,options){
 const d=input instanceof Date?input:typeof input==='string'&&/^\d{4}-\d{2}-\d{2}/.test(input)?new Date(input):null;if(!d||!Number.isFinite(d.valueOf())||!/[yMdHhns]/.test(format))return null;
 const locale=options.locale||'en-US',pad=n=>String(n).padStart(2,'0'),month=d.getUTCMonth()+1,minute=d.getUTCMinutes(),hour=d.getUTCHours();
 const names=(field,style)=>new Intl.DateTimeFormat(locale,{[field]:style,timeZone:'UTC'}).format(d),tokens={yyyy:String(d.getUTCFullYear()),yy:String(d.getUTCFullYear()).slice(-2),MMMM:names('month','long'),MMM:names('month','short'),MM:pad(month),M:String(month),dddd:names('weekday','long'),ddd:names('weekday','short'),dd:pad(d.getUTCDate()),d:String(d.getUTCDate()),HH:pad(hour),H:String(hour),hh:pad(hour%12||12),h:String(hour%12||12),nn:pad(minute),n:String(minute),ss:pad(d.getUTCSeconds()),s:String(d.getUTCSeconds()),tt:hour<12?'AM':'PM'};
 if(options.dialect==='dotnet'){tokens.mm=pad(minute);tokens.m=String(minute)}else{tokens.mmmm=tokens.MMMM;tokens.mmm=tokens.MMM;tokens.mm=tokens.MM;tokens.m=tokens.M}
 return format.replace(/"[^"]*"|'[^']*'|yyyy|MMMM|mmmm|dddd|MMM|mmm|ddd|yy|MM|mm|dd|HH|hh|nn|ss|tt|[MmdHhns]/g,t=>t[0]==='"'||t[0]==="'"?t.slice(1,-1):tokens[t]??t);
}
function text(value,format,options={}){
 if(value==null)return '—';const date=dateText(value,format||'',options);if(date!==null)return date;if(typeof value!=='number'||!format)return String(value);
 if(options.dialect==='dotnet'&&/^[NnFfPpCc]\d*$/.test(format)){const digits=Number(format.slice(1)||2),kind=format[0].toUpperCase();format=(kind==='C'?'$':'')+(kind==='N'||kind==='C'?'#,##0':'0')+(digits?'.'+'0'.repeat(Math.min(20,digits)):'')+(kind==='P'?'%':'')}
 const named={percent:'0.00%', 'whole number':'#,0','decimal number':'#,0.00'};
 format=named[String(format).toLowerCase()]||format;
 const parts=sections(format),selected=value===0&&parts.length>2?2:value<0&&parts.length>1?1:0,section=parts[selected];
 if(section==='')return '';
 const tokens=[];let quoted=false;
 for(let i=0;i<section.length;i++){const c=section[i];if(c==='"'){quoted=!quoted;continue}if(!quoted&&c==='\\'){if(i+1<section.length)tokens.push({c:section[++i],literal:true});continue}if(!quoted&&(c==='_'||c==='*')){i++;continue}tokens.push({c,literal:quoted})}
 const first=tokens.findIndex(t=>!t.literal&&/[0#]/.test(t.c)),last=tokens.findLastIndex(t=>!t.literal&&/[0#]/.test(t.c));
 if(first<0)return tokens.some(t=>t.literal)?tokens.map(t=>t.c).join(''):String(value);
 const pattern=tokens.slice(first,last+1).filter(t=>!t.literal).map(t=>t.c).join('');
 if(!/^[0#,.]+$/.test(pattern))return String(value);
 const decimals=pattern.includes('.')?pattern.split('.')[1]:'',precision=Number.isInteger(options.precision)&&options.precision>=0?Math.min(20,options.precision):null;
 const min=precision??Math.min(20,(decimals.match(/0/g)||[]).length),max=precision??Math.min(20,decimals.length);
 let end=last+1,commas=0;while(tokens[end]?.c===','&&!tokens[end].literal){commas++;end++}
 const percent=tokens.some(t=>t.c==='%'&&!t.literal),units=!percent&&!commas&&Number(options.units)>1?Number(options.units):1;
 const number=Math.abs(value)*(percent?100:1)/1000**commas/units;
 const rendered=new Intl.NumberFormat(options.locale||'en-US',{minimumFractionDigits:min,maximumFractionDigits:max,useGrouping:pattern.split('.')[0].includes(',')}).format(number);
 const literal=items=>items.map(t=>t.c).join('').replace(/\[[^\]]*\]/g,'');
 const suffix={1000:'K',1000000:'M',1000000000:'B',1000000000000:'T'}[units]||'';
 return (value<0&&selected===0?'-':'')+literal(tokens.slice(0,first))+rendered+suffix+literal(tokens.slice(end));
}
const api={vegaLocale,visualFormat,resolve,dateText,d3,text};if(typeof module!=='undefined')module.exports=api;root.ModelFormats=api;
})(globalThis);
