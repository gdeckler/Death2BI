import sys,unittest,duckdb
sys.path.insert(0,'outputs/Death2BI')
from dax_engine import Evaluator,Parser
DAX="""VAR __MinYear = MIN( 'Life satisfaction'[Year] )
VAR __MaxYear = MAX( 'Life satisfaction'[Year] )
VAR __MinYearScore = MAXX( FILTER( 'Life satisfaction', [Year] = __MinYear ), [Life satisfaction] )
VAR __MaxYearScore = MAXX( FILTER( 'Life satisfaction', [Year] = __MaxYear ), [Life satisfaction] )
VAR __Result = __MaxYearScore - __MinYearScore RETURN __Result"""
class Tests(unittest.TestCase):
 def test_contexts(self):
  c=duckdb.connect();c.execute('CREATE TABLE "Life satisfaction" (Country VARCHAR,Year INTEGER,"Life satisfaction" DOUBLE)');c.execute("INSERT INTO \"Life satisfaction\" VALUES ('A',2010,3),('A',2015,5),('A',2020,4),('B',2010,8),('B',2020,6)")
  model={'tables':[{'name':'Life satisfaction'}],'measures':[{'TableName':'Life satisfaction','Name':'Change','Expression':DAX}]}
  for where,expected in [("Country='A'",1),("Country='B'",-2),("Country='A' AND Year>=2015",-1),("Year=2010",0),("Country='missing'",None)]:
   self.assertEqual(Evaluator(c,model,{'Life satisfaction':where}).measure('Change'),expected)
  self.assertEqual(Evaluator(c,model,{}).run(Parser('CALCULATE(1)').parse(),{},None),1)
  with self.assertRaisesRegex(ValueError,'Unsupported DAX function'): Evaluator(c,model,{}).run(Parser('NONEXISTENTFUNCTION(1)').parse(),{},None)
  c.close()
if __name__=='__main__':unittest.main()
