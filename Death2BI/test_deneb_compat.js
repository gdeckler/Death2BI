const assert=require('node:assert/strict'),F=require('./custom-frame');
const damaged='return e.replace(/(?)|(\\.\\.\\.)/g, "");';
const pkg={guid:'deneb7E15AEF80B9E4D4F8E12924291ECE89A',version:'2.0.0.0',js:damaged};
const fn=new Function('e',F.compatibleScript(pkg));assert.equal(fn('hello…...world'),'helloworld');assert.equal(F.compatibleScript({...pkg,guid:'other'}),damaged);assert.equal(F.compatibleScript({...pkg,version:'3'}),damaged);
console.log('PASS scoped Deneb ellipsis compatibility');
const denebHtml=F.documentFor({...pkg,js:''},'test-token');assert.match(denebHtml,/unsafe-eval/);assert.match(denebHtml,/connect-src 'none'/);assert.match(denebHtml,/default-src 'none'/);assert.doesNotMatch(F.documentFor({...pkg,guid:'other',js:''},'test-token'),/unsafe-eval/);
const source='var t={327:t=>{t.exports=Function("return this")()}};';assert.equal(F.compatibleScript({guid:'sound',js:source}),source.replace('Function("return this")()','globalThis'));
