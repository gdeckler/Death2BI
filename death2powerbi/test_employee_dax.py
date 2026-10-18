import datetime as dt
import unittest
import duckdb
from dax_engine import Evaluator,Parser


class EmployeeDaxTests(unittest.TestCase):
    def test_unqualified_columns_use_each_measure_home_table(self):
        c=duckdb.connect()
        try:
            c.execute('CREATE TABLE A(N INTEGER); INSERT INTO A VALUES (2),(3); CREATE TABLE B(N INTEGER); INSERT INTO B VALUES (8)')
            m={'tables':[{'name':'A'},{'name':'B'}],'measures':[{'TableName':'A','Name':'A sum','Expression':'SUM([N])'},{'TableName':'B','Name':'B sum','Expression':'SUM([N])'},{'TableName':'A','Name':'Nested','Expression':'[B sum]+SUM([N])'}]}
            self.assertEqual(Evaluator(c,m,filters=[]).measure('A sum'),5)
            self.assertEqual(Evaluator(c,m,filters=[]).measure('Nested'),13)
            with self.assertRaisesRegex(ValueError,'outside a measure context'):
                Evaluator(c,m,filters=[]).run(Parser('SUM([N])').parse())
        finally:c.close()

    def test_large_fact_aggregates_and_filtered_rowset_are_not_materialized(self):
        c=duckdb.connect()
        try:
            c.execute("CREATE TABLE T AS SELECT i AS N, CASE WHEN i%10=0 THEN DATE '2024-01-01' END AS TermDate FROM range(120001) r(i)")
            definitions={'Count':'COUNT([N])','Total':'SUM([N])','Active':'CALCULATE(COUNT([N]),FILTER(T,ISBLANK(T[TermDate])))','Terminated':'CALCULATE(COUNT([N]),FILTER(T,NOT(ISBLANK(T[TermDate]))))','Captured':'CALCULATE(COUNT([N]),ALL(T),FILTER(T,ISBLANK(T[TermDate])))'}
            m={'tables':[{'name':'T'}],'measures':[{'TableName':'T','Name':n,'Expression':s} for n,s in definitions.items()]}
            for name,expected in [('Count',120001),('Total',7200060000),('Active',108000),('Terminated',12001)]:
                self.assertEqual(Evaluator(c,m,filters=[]).measure(name),expected)
            filters=[{'table':'T','columns':['N'],'sql':'"T"."N" < 100'}]
            self.assertEqual(Evaluator(c,m,filters=filters).measure('Captured'),90)
        finally:c.close()

    def test_previous_year_replaces_calendar_filters_and_extends_leap_month(self):
        c=duckdb.connect()
        try:
            c.execute("CREATE TABLE Dates AS SELECT CAST(d AS DATE) AS Date, year(d) AS Year FROM generate_series(DATE '2007-01-01',DATE '2009-12-31',INTERVAL 1 DAY) r(d)")
            c.execute("CREATE TABLE Events AS SELECT DATE '2008-02-29' AS Date, 7 AS Amount")
            m={'tables':[{'name':'Dates'},{'name':'Events'}],'relationships':[{'FromTableName':'Events','FromColumnName':'Date','ToTableName':'Dates','ToColumnName':'Date','IsActive':1,'Cardinality':'M:1','CrossFilteringBehavior':'Single'}],'measures':[{'TableName':'Events','Name':'Prior','Expression':'CALCULATE(SUM([Amount]),SAMEPERIODLASTYEAR(Dates[Date]))'}]}
            filters=[{'table':'Dates','columns':['Year'],'sql':'"Dates"."Year"=2009'},{'table':'Dates','columns':['Date'],'sql':"\"Dates\".\"Date\" BETWEEN DATE '2009-02-27' AND DATE '2009-02-28'"}]
            e=Evaluator(c,m,filters=filters)
            self.assertEqual(e.measure('Prior'),7)
            dates=e.run(Parser('SAMEPERIODLASTYEAR(Dates[Date])').parse())
            self.assertEqual([r[1]['Date'] for r in dates],[dt.date(2008,2,27),dt.date(2008,2,28),dt.date(2008,2,29)])
            scattered=[{'table':'Dates','columns':['Date'],'sql':"\"Dates\".\"Date\" IN (DATE '2009-01-01',DATE '2009-01-03')"}]
            with self.assertRaisesRegex(ValueError,'contiguous'):
                Evaluator(c,m,filters=scattered).run(Parser('SAMEPERIODLASTYEAR(Dates[Date])').parse())
        finally:c.close()


if __name__=='__main__':unittest.main()
