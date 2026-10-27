const assert=require('node:assert/strict'),A=require('./advanced-charts'),V=require('./vega-renderer');
const rows=Array.from({length:35000},(_,i)=>[i,i*2,'id'+i]);const sampled=A.sampleScatter(rows,0,1);assert.equal(sampled.length,3500);assert.equal(sampled[0],rows[0]);assert.equal(sampled.at(-1),rows.at(-1));assert.equal(new Set(sampled).size,3500);for(let i=1;i<sampled.length;i++)assert.ok([10,11].includes(sampled[i][0]-sampled[i-1][0]));assert.equal(rows.length,35000);
const invalid=[[null,1],['2',1],[1,'x'],[NaN,2],[1,Infinity],...rows.slice(0,3500),[2,null]];assert.deepEqual(A.sampleScatter(invalid,0,1),rows.slice(0,3500));assert.deepEqual(A.sampleScatter([[1,2,null],[2,3,-1],[3,4,2]],0,1,2),[[3,4,2]]);
const spec=V.buildSpec('scatterChart',['X','Y','Identity'],rows,['X','Y','Details']);assert.equal(spec.data.values.length,3500);assert.equal(spec.data.values[0]._detail,'id0');assert.equal(spec.data.values.at(-1)._detail,'id34999');assert.equal(spec.usermeta.scatterSampling.inputRows,35000);const empty=V.buildSpec('scatterChart',['X','Y'],[['bad',1],[2,null]],['X','Y']);assert.equal(empty.data.values.length,0);
console.log('PASS endpoint-preserving 3500-point scatter sampling, even spacing, invalid-row exclusion, identities, empty data and source immutability');

assert.equal(spec.mark.size,64);
