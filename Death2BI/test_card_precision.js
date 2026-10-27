const assert=require('node:assert/strict'),S=require('./report-style');
const v={type:'cardVisual',definition:{query:{queryState:{Data:{projections:[{queryRef:'Value'}]}}},objects:{}}};
assert.equal(S.cardValue({},v,0,1234567890,'0'),'1B');assert.equal(S.cardValue({},v,0,1234567890,'0.0'),'1.2B');assert.equal(S.cardValue({},v,0,1234567890,'0.000'),'1.235B');assert.equal(S.cardValue({},v,0,.1256,'0.0%'),'12.6%');assert.equal(S.cardValue({},v,0,1234567890,''),'1.23B');
v.definition.objects.value=[{properties:{decimalPlaces:3},selector:{metadata:'Value'}}];assert.equal(S.cardValue({},v,0,1234567890,'0'),'1.235B');
console.log('PASS authored card format precision, percentages, automatic units and explicit visual precision precedence');
