"""Reference examples and context regressions for every registered function."""
import datetime as dt
import math
from pathlib import Path
import sys
import unittest
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dax_engine import Evaluator, Parser
from dax_runtime import Table, support_catalog
from dax_functions import FUNCTIONS


SCALARS = {
    'ABS': ('ABS(-3)', 3), 'ACOS': ('ACOS(1)', 0), 'ACOSH': ('ACOSH(1)', 0),
    'ASIN': ('ASIN(0)', 0), 'ASINH': ('ASINH(0)', 0), 'ATAN': ('ATAN(1)', math.pi / 4),
    'ATANH': ('ATANH(0)', 0), 'COS': ('COS(0)', 1), 'COSH': ('COSH(0)', 1),
    'SIN': ('SIN(0)', 0), 'SINH': ('SINH(0)', 0), 'TAN': ('TAN(0)', 0), 'TANH': ('TANH(0)', 0),
    'SQRT': ('SQRT(9)', 3), 'EXP': ('EXP(0)', 1), 'LN': ('LN(1)', 0),
    'LOG10': ('LOG10(100)', 2), 'DEGREES': ('DEGREES(PI())', 180),
    'RADIANS': ('RADIANS(180)', math.pi), 'SIGN': ('SIGN(-2)', -1), 'INT': ('INT(-1.2)', -2),
    'PI': ('PI()', math.pi), 'POWER': ('POWER(2,3)', 8), 'LOG': ('LOG(8,2)', 3),
    'MOD': ('MOD(-3,2)', 1), 'QUOTIENT': ('QUOTIENT(-5,2)', -2),
    'ROUND': ('ROUND(-1.25,1)', -1.3), 'ROUNDUP': ('ROUNDUP(-1.21,1)', -1.3),
    'ROUNDDOWN': ('ROUNDDOWN(-1.29,1)', -1.2), 'TRUNC': ('TRUNC(-1.9)', -1),
    'MROUND': ('MROUND(10,3)', 9), 'CEILING': ('CEILING(-4.3,2)', -4),
    'FLOOR': ('FLOOR(-4.3,-2)', -4), 'EVEN': ('EVEN(-1.2)', -2), 'ODD': ('ODD(3)', 3),
    'FACT': ('FACT(5)', 120), 'COMBIN': ('COMBIN(5,2)', 10), 'GCD': ('GCD(12,8)', 4), 'LCM': ('LCM(4,6)', 12),
    'TRUE': ('TRUE()', True), 'FALSE': ('FALSE()', False), 'NOT': ('NOT(TRUE())', False),
    'AND': ('AND(TRUE(),FALSE())', False), 'OR': ('OR(FALSE(),TRUE())', True),
    'ISBLANK': ('ISBLANK(BLANK())', True), 'ISNUMBER': ('ISNUMBER(TRUE())', False),
    'ISTEXT': ('ISTEXT("abc")', True), 'ISNONTEXT': ('ISNONTEXT(BLANK())', True),
    'ISLOGICAL': ('ISLOGICAL(FALSE())', True), 'ISEVEN': ('ISEVEN(2.9)', True), 'ISODD': ('ISODD(-3.9)', True),
    'BLANK': ('BLANK()', None), 'VALUE': ('VALUE("12.5")', 12.5),
    'LEN': ('LEN("abc")', 3), 'LOWER': ('LOWER("ABC")', 'abc'), 'UPPER': ('UPPER("abc")', 'ABC'),
    'TRIM': ('TRIM(" a  b ")', 'a b'), 'CONCATENATE': ('CONCATENATE("a",2)', 'a2'),
    'EXACT': ('EXACT("a","A")', False), 'LEFT': ('LEFT("abcd",2)', 'ab'), 'RIGHT': ('RIGHT("abcd",2)', 'cd'),
    'MID': ('MID("abcd",2,2)', 'bc'), 'REPLACE': ('REPLACE("abcd",2,2,"X")', 'aXd'),
    'REPT': ('REPT("ab",2)', 'abab'), 'SUBSTITUTE': ('SUBSTITUTE("a-a-a","a","X",2)', 'a-X-a'),
    'FIND': ('FIND("B","aBc")', 2), 'SEARCH': ('SEARCH("B?","abcd")', 2),
    'CONTAINSSTRING': ('CONTAINSSTRING("abcd","a*d")', True),
    'CONTAINSSTRINGEXACT': ('CONTAINSSTRINGEXACT("abcd","a*d")', False),
    'UNICHAR': ('UNICHAR(65)', 'A'), 'UNICODE': ('UNICODE("AB")', 65),
    'DATE': ('DATE(2024,2,30)', dt.datetime(2024,3,1)),
    'TIME': ('TIME(25,0,0)', dt.datetime(1899,12,30,1)),
    'DATEVALUE': ('DATEVALUE("2024-02-03T12:00:00")', dt.datetime(2024,2,3)),
    'TIMEVALUE': ('TIMEVALUE("2024-02-03T12:30:00")', dt.datetime(1899,12,30,12,30)),
    'YEAR': ('YEAR(DATE(2024,2,3))', 2024), 'MONTH': ('MONTH(DATE(2024,2,3))', 2),
    'DAY': ('DAY(DATE(2024,2,3))', 3), 'HOUR': ('HOUR(TIME(12,30,45))', 12),
    'MINUTE': ('MINUTE(TIME(12,30,45))', 30), 'SECOND': ('SECOND(TIME(12,30,45))', 45),
    'QUARTER': ('QUARTER(DATE(2024,5,1))', 2),
    'EDATE': ('EDATE(DATE(2024,1,31),1)', dt.datetime(2024,2,29)),
    'EOMONTH': ('EOMONTH(DATE(2024,2,1),0)', dt.datetime(2024,2,29)),
    'WEEKDAY': ('WEEKDAY(DATE(2024,1,1),2)', 1),
    'WEEKNUM': ('WEEKNUM(DATE(2021,1,1),21)', 53),
    'DATEDIFF': ('DATEDIFF(DATE(2023,12,31),DATE(2024,1,1),YEAR)', 1),
    'PMT': ('PMT(0,10,100)', -10), 'FV': ('FV(0,10,-10)', 100),
    'PV': ('PV(0,10,-10)', 100), 'NPER': ('NPER(0,-10,100)', 10),
    'PATHLENGTH': ('PATHLENGTH("1|2|3")', 3), 'PATHCONTAINS': ('PATHCONTAINS("1|2|3",2)', True),
    'PATHITEM': ('PATHITEM("1|2|3",2,INTEGER)', 2), 'PATHITEMREVERSE': ('PATHITEMREVERSE("1|2|3",1)', '3'),
    'FORMAT': ('FORMAT(0.242,"0.00%")', '24.20%'),
}


class DaxReferenceTests(unittest.TestCase):
    covered = set()
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute('CREATE TABLE T (ID INTEGER, N DOUBLE, Category VARCHAR, Flag BOOLEAN)')
        self.con.execute("INSERT INTO T VALUES (1,1,'A',true),(2,2,'A',false),(3,3,'B',true),(4,NULL,'B',NULL)")
        self.con.execute('CREATE TABLE Products (ID INTEGER, Color VARCHAR, Price DOUBLE)')
        self.con.execute("INSERT INTO Products VALUES (1,'Red',2),(2,'Blue',3)")
        self.con.execute('CREATE TABLE Sales (ProductID INTEGER, Amount DOUBLE, Date DATE)')
        self.con.execute("INSERT INTO Sales VALUES (1,10,'2024-01-01'),(1,20,'2024-02-01'),(2,30,'2024-02-03')")
        self.con.execute("CREATE TABLE Dates AS SELECT CAST(d AS DATE) AS Date FROM generate_series(DATE '2024-01-01', DATE '2024-02-03', INTERVAL 1 DAY) t(d)")
        self.con.execute('CREATE TABLE People (ID INTEGER, Parent INTEGER)')
        self.con.execute('INSERT INTO People VALUES (1,NULL),(2,1),(3,2)')
        names = [r[0] for r in self.con.execute('SHOW TABLES').fetchall()]
        self.model = {'tables': [{'name': t} for t in names], 'measures': [{'TableName': 'Sales', 'Name': 'Revenue', 'Expression': 'SUM(Sales[Amount])'}], 'relationships': [
            {'FromTableName': 'Sales', 'FromColumnName': 'ProductID', 'ToTableName': 'Products', 'ToColumnName': 'ID', 'IsActive': True, 'Cardinality': 'M:1', 'CrossFilteringBehavior': 'Single'},
            {'FromTableName': 'Sales', 'FromColumnName': 'Date', 'ToTableName': 'Dates', 'ToColumnName': 'Date', 'IsActive': True, 'Cardinality': 'M:1', 'CrossFilteringBehavior': 'Single'},
        ]}

    def tearDown(self):
        self.con.close()

    def engine(self, filters=None):
        return Evaluator(self.con, self.model, {}, filters=[] if filters is None else filters)

    def evaluate(self, expression, filters=None):
        ast = Parser(expression).parse()
        def visit(node):
            if isinstance(node, tuple):
                if node and node[0] == 'call':
                    self.covered.add(node[1])
                for part in node:
                    if isinstance(part, (tuple, list)):
                        visit(part)
            elif isinstance(node, list):
                for part in node:
                    visit(part)
        visit(ast)
        return self.engine(filters).run(ast)

    def assert_result(self, expression, expected, filters=None):
        result = self.evaluate(expression, filters)
        if isinstance(expected, float):
            self.assertAlmostEqual(result, expected, places=9, msg=expression)
        else:
            self.assertEqual(result, expected, expression)

    def test_all_scalar_functions(self):
        for name, (expression, expected) in SCALARS.items():
            with self.subTest(function=name):
                self.assert_result(expression, expected)
        clocks = {'NOW', 'TODAY', 'UTCNOW', 'UTCTODAY'}
        for name in clocks:
            self.assertIsInstance(self.evaluate(name + '()'), dt.datetime)
        self.assertEqual(set(SCALARS) | clocks, set(FUNCTIONS))

    def test_aggregates(self):
        expressions = {
            'SUM(T[N])': 6, 'AVERAGE(T[N])': 2, 'MIN(T[N])': 1, 'MAX(T[N])': 3,
            'COUNT(T[N])': 3, 'COUNTA(T[Flag])': 3, 'COUNTBLANK(T[N])': 1,
            'DISTINCTCOUNT(T[N])': 4, 'DISTINCTCOUNTNOBLANK(T[N])': 3,
            'PRODUCT(T[N])': 6, 'MEDIAN(T[N])': 2, 'STDEV.S(T[N])': 1,
            'STDEV.P(T[N])': math.sqrt(2/3), 'VAR.S(T[N])': 1, 'VAR.P(T[N])': 2/3,
            'SUMX(T,[N]*2)': 12, 'AVERAGEX(T,[N])': 2,
            'MINX(T,[N])': 1, 'MAXX(T,[N])': 3, 'COUNTX(T,[N])': 3,
            'COUNTAX(T,[Flag])': 3, 'PRODUCTX(T,[N])': 6, 'MEDIANX(T,[N])': 1.5,
            'STDEVX.S(T,[N])': 1, 'STDEVX.P(T,[N])': math.sqrt(2/3),
            'VARX.S(T,[N])': 1, 'VARX.P(T,[N])': 2/3,
            'PERCENTILE.INC(T[N],0.25)': 1.5, 'PERCENTILE.EXC(T[N],0.5)': 2,
            'PERCENTILEX.INC(FILTER(T,NOT(ISBLANK([N]))),[N],0.25)': 1.5, 'PERCENTILEX.EXC(FILTER(T,NOT(ISBLANK([N]))),[N],0.5)': 2,
        }
        for expression, expected in expressions.items():
            with self.subTest(expression=expression):
                self.assert_result(expression, expected)

    def test_logic_blank_and_errors(self):
        for expression, expected in {
            'IF(TRUE(),3,ERROR("unused"))': 3, 'IF.EAGER(TRUE(),3,4)': 3,
            'SWITCH(TRUE(),1>2,10,2>1,20,30)': 20,
            'IFERROR(1/0,42)': 42, 'ISERROR(SQRT(-1))': True,
            'COALESCE(BLANK(),0,ERROR("unused"))': 0,
            'DIVIDE(1,0,7)': 7, 'BLANK()=0': True, 'BLANK()==0': False,
            'BLANK()*3': None, '"a" & 3': 'a3', '"Blue"="BLUE"': True,
        }.items():
            with self.subTest(expression=expression):
                self.assert_result(expression, expected)
        with self.assertRaisesRegex(ValueError, 'used'):
            self.evaluate('ERROR("used")')
        with self.assertRaisesRegex(ValueError, 'unused'):
            self.evaluate('IF.EAGER(TRUE(),3,ERROR("unused"))')

    def test_calculate_and_relationships(self):
        red = [{'table': 'Products', 'columns': ['Color'], 'sql': '"Products"."Color" = \'Red\''}]
        self.assert_result('[Revenue]', 30, red)
        self.assert_result('CALCULATE([Revenue],CROSSFILTER(Sales[ProductID],Products[ID],None))',60,red)
        fact=[{'table':'Sales','columns':['ProductID'],'sql':'Sales.ProductID=1'}]
        self.assert_result('CALCULATE(COUNTROWS(Products),CROSSFILTER(Sales[ProductID],Products[ID],Both))',1,fact)
        self.assert_result('COUNTROWS(Products)',2,fact)

        self.assert_result('CALCULATE([Revenue],Products[Color]="Blue")', 30, red)
        self.assert_result('CALCULATE([Revenue],KEEPFILTERS(Products[Color]="Blue"))', None, red)
        self.assert_result('CALCULATE([Revenue],REMOVEFILTERS(Products[Color]))', 60, red)
        self.assert_result('CALCULATE([Revenue],ALL(Products))', 60, red)
        self.assert_result('CALCULATE([Revenue],ALL())', 60, red)
        self.assert_result('CALCULATE([Revenue],Products[Color]="Blue",ALL(Products))', 30, red)
        self.assert_result('CALCULATE(SUM(T[N]),T[N]>1,T[N]<3)', 2)
        self.assert_result('CALCULATE(SUM(T[N]),T[N]=MAX(T[N]))', 3)
        self.assert_result('SUMX(VALUES(Products[Color]),[Revenue])', 60)
        self.assert_result('SUMX(Products,CALCULATE([Revenue]))', 60)
        self.assert_result('SUMX(Sales,Sales[Amount]*RELATED(Products[Price]))', 150)
        self.assert_result('SUMX(Products,COUNTROWS(RELATEDTABLE(Sales)))', 3)
        self.assert_result('LOOKUPVALUE(Products[Color],Products[ID],2)', 'Blue')
        self.assert_result('LOOKUPVALUE(Products[Color],Products[ID],9,"Missing")', 'Missing')
        self.assert_result('SELECTEDVALUE(Products[Color],"Many")', 'Many')
        self.assert_result('SELECTEDVALUE(Products[Color])', 'Red', red)
        self.assert_result('HASONEVALUE(Products[Color])', True, red)
        self.assert_result('ISFILTERED(Products[Color])', True, red)
        self.assert_result('ISCROSSFILTERED(Sales[Amount])', True, red)
        self.assert_result('HASONEFILTER(Products[Color])', True, red)
        self.assert_result('HASONEFILTER(Products[Color])', False)
        self.assert_result('COUNTROWS(FILTERS(Products[Color]))', 1, red)
        self.assert_result('COUNTROWS(ALL(Products[Color]))', 2, red)
        self.assert_result('COUNTROWS(ALLNOBLANKROW(Products[Color]))', 2, red)
        self.assert_result('CALCULATE([Revenue],ALLEXCEPT(Products,Products[ID]))', 60, red)
        self.assert_result('COUNTROWS(CALCULATETABLE(Sales,Products[Color]="Red"))', 2)
        e = self.engine(red + [{'table': 'Products', 'columns': ['Color'], 'sql': '"Products"."Color"=\'Blue\''}])
        e.external_filters = red
        self.covered.add('ALLSELECTED')
        self.assertEqual(e.run(Parser('CALCULATE([Revenue],ALLSELECTED(Products[Color]))').parse()), 30)
        self.assert_result('ISONORAFTER(2,3,DESC)', True)
        self.assert_result('ISONORAFTER("B","A",ASC)', True)
        self.model['measures'].append({'TableName': 'Sales', 'Name': 'Selected Revenue', 'Expression': 'CALCULATE([Revenue],ALLSELECTED(Products))'})
        with self.assertRaisesRegex(ValueError, 'iterator'):
            self.evaluate('SUMX(Products,[Selected Revenue])')

    def test_tables_ranking_and_paths(self):
        expressions = {
            'COUNTROWS(DATATABLE("Name",STRING,{{"a"},{"b"}}))':2,
            'COUNTROWS(FILTER(T,[N]>1))': 2, 'ISEMPTY(FILTER(T,[N]>9))': True,
            'COUNTROWS(VALUES(T[Category]))': 2, 'COUNTROWS(DISTINCT(T[Category]))': 2,
            'COUNTROWS(TOPN(1,T,T[Category],ASC))': 2,
            'RANKX(T,T[N],2,DESC,DENSE)': 2,
            'CONCATENATEX(T,[Category],",",T[ID],ASC)': 'A,A,B,B',
            'SUMX(ADDCOLUMNS(T,"Doubled",[N]*2),[Doubled])': 12,
            'SUMX(SELECTCOLUMNS(T,"X",[N]),[X])': 6,
            'SUMX(ROW("X",7),[X])': 7,
            'COUNTROWS(UNION(VALUES(T[Category]),VALUES(T[Category])))': 4,
            'COUNTROWS(INTERSECT(VALUES(T[Category]),VALUES(T[Category])))': 2,
            'ISEMPTY(EXCEPT(VALUES(T[Category]),VALUES(T[Category])))': True,
            'COUNTROWS(CROSSJOIN(VALUES(T[Category]),VALUES(Products[Color])))': 4,
            'COUNTROWS(GENERATE(VALUES(T[Category]),ROW("X",1)))': 2,
            'CONTAINS(T,T[Category],"A")': True,
            'COUNTROWS(GENERATEALL(VALUES(T[Category]),FILTER({1},FALSE())))': 2,
            'SUMX(GROUPBY(T,T[Category],"Total",SUMX(CURRENTGROUP(),T[N])),[Total])': 6,
            'SUMX(SUMMARIZE(T,T[Category],"Total",SUM(T[N])),[Total])': 6,
            'MAXX(SUMMARIZE(T,[Category],"Total",SUM(T[N])),[Total])': 3,
            'SUMX(GENERATESERIES(1,3),[Value])': 6,
            'COUNTROWS(CALENDAR(DATE(2024,2,28),DATE(2024,3,1)))': 3,
            'CONCATENATEX(People,PATH(People[ID],People[Parent]),",",People[ID],ASC)': '1,1|2,1|2|3',
        }
        for expression, expected in expressions.items():
            with self.subTest(expression=expression):
                self.assert_result(expression, expected)
        self.assert_result('ISINSCOPE(Products[Color])', False)
        e = self.engine()
        e.scope = [('Products', 'Color')]
        self.assertTrue(e.run(Parser('ISINSCOPE(Products[Color])').parse()))

    def test_classic_time_intelligence(self):
        filters = [{'table': 'Dates', 'columns': ['Date'], 'sql': '"Dates"."Date" = DATE \'2024-02-03\''}]
        self.assert_result('COUNTROWS(SAMEPERIODLASTYEAR(Dates[Date]))', None, filters)
        self.assert_result('COUNTROWS(DATESYTD(Dates[Date]))', 34, filters)
        self.assert_result('COUNTROWS(DATESQTD(Dates[Date]))', 34, filters)
        self.assert_result('COUNTROWS(DATESMTD(Dates[Date]))', 3, filters)
        self.assert_result('TOTALYTD([Revenue],Dates[Date])', 60, filters)
        self.assert_result('TOTALQTD([Revenue],Dates[Date])', 60, filters)
        self.assert_result('TOTALMTD([Revenue],Dates[Date])', 50, filters)
        self.assert_result('CALCULATE([Revenue],DATESBETWEEN(Dates[Date],DATE(2024,2,1),DATE(2024,2,3)))', 50)
        self.assert_result('YEAR(FIRSTDATE(Dates[Date]))', 2024)
        self.assert_result('DAY(LASTDATE(Dates[Date]))', 3)

    def test_guards_and_edge_cases(self):
        for expression in ['REPT("x",40000)', 'FACT(1000000)', 'SUMX(GENERATESERIES(1,100001),[Value])', 'CALENDAR(DATE(2024,2,1),DATE(2024,1,1))', 'RANKX(T,T[N],2,DESC,"invalid")', 'PERCENTILE.EXC(T[N],0)', 'USERELATIONSHIP(Sales[ProductID],Products[ID])']:
            with self.subTest(expression=expression):
                with self.assertRaises((ValueError, RuntimeError)):
                    self.evaluate(expression)
        e = self.engine()
        e.budget['deadline'] = 0
        with self.assertRaises(RuntimeError):
            e.run(Parser('IFERROR(1,0)').parse())
        compound = [{'table': 'T', 'columns': ['N', 'Category'], 'sql': '"T"."N">1 AND "T"."Category"=\'A\''}]
        self.assert_result('CALCULATE(SUM(T[N]),REMOVEFILTERS(T[N]))',3,compound)
        self.assert_result('SUMX(T,COUNTROWS(FILTER(T,T[ID]<=EARLIER(T[ID]))))',10)
        self.assert_result('CALCULATE(SUM(T[N]),TREATAS({"A"},T[Category]))',3)
        self.assert_result('ROUND(2.5,0)', 3)
        self.assert_result('ROUND(-2.5,0)', -3)
        self.assert_result('SEARCH("~*","a*b")', 2)
        self.assert_result('SEARCH("missing","abc",1,BLANK())', None)
        self.assert_result('MEDIANX(FILTER(T,ISBLANK([N])),[N])', 0)
        self.assert_result('RIGHT("abc",0)', '')
        self.assert_result('FORMAT(-1234.5,"$#,##0.00;($#,##0.00)")', '($1,234.50)')
        self.assert_result('FORMAT(DATE(2024,2,3),"yyyy-mm-dd")', '2024-02-03')
        self.assert_result('YEAR(dt"2024-02-03")', 2024)
        self.assert_result('DATE(2024,2,29)+1', dt.datetime(2024,3,1))
        self.assert_result('DATE(2024,3,1)-DATE(2024,2,28)', 2)
        self.assert_result('ROUND(.125,2)', .13)
        self.assert_result('COUNTROWS(FILTER(T,[Category] in {"A"}))', 2)
        self.assert_result('("A",2) IN {("A",1),("A",2)}', True)
        self.assert_result('BLANK() IN {0}', False)
        self.assert_result('SUBSTITUTE("a-a-a","a","X",9)', 'a-a-a')
        self.assert_result('SUMX(FILTER(T,FALSE()),[N])', None)
        # A nonzero-interest finance round trip must recover the principal.
        self.assertAlmostEqual(self.evaluate('PV(0.01,12,PMT(0.01,12,1000))'), 1000, places=8)

    def test_selected_measure_format_context(self):
        e=self.engine();e.selected_measure=42;e.selected_measure_name='Revenue';e.selected_measure_format='$0.00'
        for fn,expected in [('SELECTEDMEASURE',42),('SELECTEDMEASURENAME','Revenue'),('SELECTEDMEASUREFORMATSTRING','$0.00')]:
            self.assertEqual(e.run(Parser(fn+'()').parse(),{},None),expected);self.covered.add(fn)

    def test_zz_registry_has_examples(self):
        registered = {f['name'] for f in support_catalog()}
        self.assertFalse(registered - self.covered, 'Missing function examples: ' + ', '.join(sorted(registered - self.covered)))


if __name__ == '__main__':
    unittest.main()
