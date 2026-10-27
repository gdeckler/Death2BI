const assert=require('node:assert/strict'),C=require('./custom-visuals');
assert(C.isHtmlContent('htmlContent443BE3AD55E043BF878BED274D3A6855'));assert(!C.isHtmlContent('arbitraryCustomVisual'));assert(!C.isHtmlContent('htmlContentInjectedScript'));
const source={customVisuals:[]};assert.equal(C.resolve('htmlContent443BE3AD55E043BF878BED274D3A6855',source).nativeHtml,true);
assert.deepEqual(C.htmlValues({rows:[['sample','<b>A</b>'],['sample',null],['sample','<svg></svg>']]},{roles:['sampling','content']}),['<b>A</b>','<svg></svg>']);assert.throws(()=>C.htmlValues({rows:[[1]]},{roles:['sampling']}),/content field/);assert.throws(()=>C.htmlValues({rows:[[1]]},{}),/content field/);
console.log('PASS known HTML Content identity, native fallback without package, role-based HTML values, blanks and unsupported-role rejection');
const S=require('./report-style');const svg="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'><circle r='5' fill='%23ff0000'/></svg>";assert.equal(decodeURIComponent(S.url(svg,{theme:{}}).split(',').slice(1).join(',')),decodeURIComponent(svg.split(',').slice(1).join(',')));assert.equal(S.url('javascript:alert(1)',{theme:{}}),null);assert.equal(S.url('data:text/html,<script>x</script>',{theme:{}}),null);console.log('PASS SVG image data URLs remain images and executable URL schemes are rejected');

assert(C.isHtmlContent("paraHTMLViewerC2AD224EF75E443AB988740A34F595EE"));assert.deepEqual(C.htmlValues({rows:[["<b>Viewer</b>"]]},{roles:["cvalue"]}),["<b>Viewer</b>"]);
const vm=require('node:vm'),events={},messages=[];let queued;
vm.runInNewContext('('+C.htmlHoverBridge.toString()+')('+JSON.stringify('test-token')+')',{addEventListener:(n,fn)=>events[n]=fn,parent:{postMessage:m=>messages.push(m)},innerWidth:200,innerHeight:100,requestAnimationFrame:fn=>{queued=fn;return 1},cancelAnimationFrame:()=>{}});
events.mousemove({target:{closest:()=>({getAttribute:()=> '2'})},clientX:100,clientY:25});queued();
assert.equal(messages[0].token,'test-token');assert.equal(messages[0].row,2);assert.equal(messages[0].x,.5);assert.equal(messages[0].y,.25);events.mouseleave();assert.equal(messages.at(-1).type,'htmlLeave');
console.log('PASS sandbox HTML tooltip bridge preserves row identity, coordinates and token');
