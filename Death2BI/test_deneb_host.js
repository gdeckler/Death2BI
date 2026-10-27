const assert=require('node:assert/strict'),F=require('./custom-frame');
for(const guid of ['deneb'+'A'.repeat(32),'STANDALONEdeneb'+'A'.repeat(32)])assert.match(F.documentFor({guid,js:'',css:''},'token'),/unsafe-eval/);
assert.doesNotMatch(F.documentFor({guid:'other',js:'',css:''},'token'),/unsafe-eval/);
assert.match(F.bootstrap.toString(),/exportStatus:async\(\)=>2/);
assert.match(F.bootstrap.toString(),/downloadCompleted:false/);
console.log('PASS Deneb identifiers and unsupported download permission responses');
