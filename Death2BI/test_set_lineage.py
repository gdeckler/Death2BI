import unittest,duckdb
from dax_engine import Evaluator,Parser
class SetLineageTests(unittest.TestCase):
 def test_different_aliases_first_lineage_and_duplicates(self):
  c=duckdb.connect();c.execute("CREATE TABLE T AS SELECT * FROM (VALUES ('a',1),('b',2),('b',3)) t(K,N)")
  m={'tables':[{'name':'T'}],'relationships':[],'measures':[]};e=Evaluator(c,m,filters=[])
  try:
   for fn,want in [('EXCEPT',5),('INTERSECT',1)]:
    expression='CALCULATE(SUM(T[N]),'+fn+'(ALL(T[K]),SELECTCOLUMNS(FILTER(T,T[K]="a"),"alias",T[K])))'
    self.assertEqual(e.run(Parser(expression).parse()),want)
   self.assertEqual(e.run(Parser('COUNTROWS(EXCEPT(T,FILTER(T,T[K]="a")))').parse()),2)
  finally:c.close()
if __name__=='__main__':unittest.main()
