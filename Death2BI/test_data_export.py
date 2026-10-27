import csv,io,unittest
import duckdb
from data_export import make_csv
from test_accounts import AccountTests
class CsvTests(unittest.TestCase):
    def test_csv_rows_and_limits(self):
        con=duckdb.connect()
        try:
            content=make_csv(con,{'sql':"SELECT i AS n FROM range(1500) t(i)",'labels':['Number']})
            rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))));self.assertEqual(len(rows),1501);self.assertEqual(rows[0],['Number'])
            content=make_csv(con,{'columns':['Text','Value'],'rows':[['a,b\n"quote"',-5],['=SUM(A1)',None]]})
            rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))));self.assertEqual(rows[1],['a,b\n"quote"','-5']);self.assertEqual(rows[2],["'=SUM(A1)",''])
            with self.assertRaisesRegex(ValueError,'250,000'):make_csv(con,{'sql':'SELECT * FROM range(250001)'})
            with self.assertRaises(ValueError):make_csv(con,{'sql':'DELETE FROM Samples'})
        finally:con.close()
class TopNTests(unittest.TestCase):
    def test_context_ties_bottom_and_underlying_rows(self):
        import json,subprocess
        plans=json.loads(subprocess.check_output(['node','test_topn_plans.js'],text=True))
        con=duckdb.connect()
        try:
            con.execute("CREATE TABLE Sales(Country VARCHAR,Value DOUBLE); INSERT INTO Sales VALUES ('A',10),('A',10),('B',9),('C',9),('D',1),('E',2),('F',100)")
            con.execute("CREATE TABLE Countries(Country VARCHAR,Region VARCHAR); INSERT INTO Countries VALUES ('A','North'),('B','North'),('C','North'),('D','North'),('E','North'),('F','South')")
            self.assertEqual({r[0] for r in con.execute(plans['top']).fetchall()},{'A','B','C'})
            self.assertEqual([r[0] for r in con.execute(plans['bottom']).fetchall()],['D','E'])
            rows=con.execute(plans['underlying']).fetchall();self.assertEqual(len(rows),4);self.assertEqual({r[0] for r in rows},{'A','B','C'})
        finally:con.close()

class CsvHttpTests(unittest.TestCase):
    setUp=AccountTests.setUp
    tearDown=AccountTests.tearDown
    create_user=AccountTests.create_user
    def test_permissions_and_download(self):
        _,owner=self.create_user('csv-owner');_,other=self.create_user('csv-other')
        status,m=owner.upload(42);self.assertEqual(status,200)
        payload={'id':m['id'],'sql':'SELECT * FROM Samples','labels':['Value']}
        status,content=owner.request('POST','/api/export-data',payload);self.assertEqual(status,200);self.assertEqual(content.decode('utf-8-sig'),'Value\r\n42\r\n')
        self.assertEqual(other.request('POST','/api/export-data',payload)[0],404)
        self.assertEqual(owner.request('POST','/api/export-data',payload,csrf=False)[0],403)
        self.assertEqual(owner.request('POST','/api/export-data',{**payload,'sql':'DELETE FROM Samples'})[0],400)
if __name__=='__main__':unittest.main()
