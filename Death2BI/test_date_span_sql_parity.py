"""Execute both query and grouped predicate paths for static date spans."""
import json
from pathlib import Path
import subprocess
import unittest
import duckdb


class DateSpanParityTests(unittest.TestCase):
    def test_sql_and_grouped_predicate_agree(self):
        script = r"""
const E=require('./report-engine'),column={Column:{Expression:{SourceRef:{Entity:'Calendar'}},Property:'Date'}};
const sets=[[null,'not-a-date','1899-12-30','1899-12-31T23:59:35','2024-02-29T12:34:56.500','2024-03-01'],[null,0,1.9997,2,45351.5]];
const cases=[];
for(const rows of sets)for(const unit of [0,2,3,4,5,6,7])for(let kind=0;kind<6;kind++){
 const entry={filter:{Where:[{Condition:{Comparison:{ComparisonKind:kind,Left:column,Right:{DateSpan:{Expression:{Literal:{Value:"datetime'2024-02-29T12:34:56.123'"}},TimeUnit:unit}}}}}]}},v={type:'tableEx',filters:[entry],definition:{query:{queryState:{Values:{projections:[]}}}}};
 const aggregate=structuredClone(entry);aggregate.filter.Where[0].Condition.Comparison.Left={Aggregation:{Function:3,Expression:column}};v.filters=[aggregate];
 const predicate=E.measureFilterPlan(v).predicates[0];cases.push({rows,sql:E.parseFilters([entry])[0].sql,expected:rows.map((x,i)=>predicate([x])?i:null).filter(x=>x!==null)});
}
console.log(JSON.stringify(cases));
"""
        cases = json.loads(subprocess.check_output(['node', '-e', script], cwd=Path(__file__).parent, text=True))
        con = duckdb.connect()
        try:
            for case in cases:
                con.execute('CREATE OR REPLACE TABLE "Calendar"("Date" '+('DOUBLE' if any(isinstance(v, (int, float)) for v in case['rows']) else 'VARCHAR')+', i INTEGER)')
                con.executemany('INSERT INTO "Calendar" VALUES (?,?)', [(v, i) for i, v in enumerate(case['rows'])])
                actual = [row[0] for row in con.execute('SELECT i FROM "Calendar" WHERE '+case['sql']+' ORDER BY i').fetchall()]
                self.assertEqual(actual, case['expected'], case)
        finally:
            con.close()


if __name__ == '__main__':
    unittest.main()
