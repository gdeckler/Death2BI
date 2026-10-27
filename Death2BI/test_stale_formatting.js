const assert=require('node:assert/strict'),E=require('./report-engine');
const field=name=>({Measure:{Expression:{SourceRef:{Entity:'M'}},Property:name}}),v={definition:{query:{queryState:{Y:{projections:[{field:field('Value')}]}}},objects:{dataPoint:[{properties:{FillRule:{Input:field('Deleted')}}}],filledMap:[{properties:{FillRule:{Input:field('Color')}}}]}}};
const m={measures:[{Name:'Value',TableName:'M'},{Name:'Color',TableName:'M'}]},r=E.formattingVisual(v,m);
assert.deepEqual(r.definition.query.queryState.Formatting.projections.map(p=>p.field.Measure.Property),['Color']);assert.equal(v.definition.query.queryState.Formatting,undefined);console.log('PASS stale formatting references do not enter chart data plans');
