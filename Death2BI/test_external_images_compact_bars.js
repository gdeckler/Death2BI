const assert=require('node:assert/strict'),F=require('./custom-frame'),R=require('./vega-renderer');
const pkg={guid:'Example',js:''};const enabled=F.documentFor(pkg,'token',false,{},[],false,true),disabled=F.documentFor(pkg,'token');assert(enabled.includes('img-src data: blob:  https: http:'));assert(enabled.includes("connect-src 'none'"));assert(!disabled.includes('https: http:'));assert(!enabled.includes('script-src https:'));
assert.equal(R.barWindow('barChart',['Category','Value'],[['A',1],['B',2],['C',3],['D',4]],['Category','Y'],80),null);
const spec=R.buildSpec('barChart',['Category','Value'],[['A',1],['B',2],['C',3],['D',4]],['Category','Y'],{height:123});assert.equal(spec.encoding.y.scale.paddingInner,.4);
console.log('PASS admin image policy retains network isolation; compact bar charts fit four categories with readable gaps');
const html=require('node:fs').readFileSync(require('node:path').join(__dirname,'dist/index.html'),'utf8');assert(html.includes("String(ReportStyle.value(image.sourceType,model.theme)||'').toLowerCase()==='imageurl'?null:image.sourceField?.expr"));
console.log('PASS URL image source mode takes precedence over stale dynamic field bindings');
