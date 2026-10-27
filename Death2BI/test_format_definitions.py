import json
import sqlite3
import unittest
import pandas as pd
from semantic_model import extract_formats
from presentation import enrich_report

class FormatDefinitionTests(unittest.TestCase):
    def test_constant_definition_and_dynamic_expression_preservation(self):
        connection=sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.executescript('''CREATE TABLE [Table](ID INTEGER,Name TEXT);
            CREATE TABLE [Column](TableID INTEGER,ExplicitName TEXT,InferredName TEXT,FormatString TEXT,ID INTEGER,SortByColumnID INTEGER);
            CREATE TABLE Measure(TableID INTEGER,Name TEXT,FormatString TEXT,FormatStringDefinitionID INTEGER);
            CREATE TABLE FormatStringDefinition(ID INTEGER,Expression TEXT);
            INSERT INTO [Table] VALUES(1,'Measures');
            INSERT INTO [Column] VALUES(1,'Category',NULL,'',10,11),(1,'Order',NULL,'0',11,NULL);
            INSERT INTO Measure VALUES(1,'Delta','',11),(1,'Dynamic','0.0',12);''')
        connection.executemany('INSERT INTO FormatStringDefinition VALUES(?,?)',[(11,'"+\\$#,0.##;-\\$#,0.##;"'),(12,'IF([X]>0,"0.0","0.00")')])
        class Database:
            def query(self,sql):return pd.read_sql_query(sql,connection)
        class Source:_db=Database()
        class Metadata:source=Source()
        class Model:_metadata=Metadata()
        result={'tables':[{'name':'Measures','columns':[{'name':'Category'},{'name':'Order'}]}],'measures':[{'TableName':'Measures','Name':'Delta'},{'TableName':'Measures','Name':'Dynamic'}]}
        extract_formats(Model(),result)
        self.assertEqual(result['tables'][0]['columns'][0]['sortByColumn'],'Order')
        self.assertEqual(result['measures'][0]['FormatString'],'+\\$#,0.##;-\\$#,0.##;')
        self.assertEqual(result['measures'][1]['FormatString'],'0.0')
        self.assertEqual(result['measures'][1]['FormatStringExpression'],'IF([X]>0,"0.0","0.00")')

    def test_button_slicer_preserves_roles_and_identity(self):
        definition={'visualType':'advancedSlicerVisual','query':{'queryState':{'Label':{'projections':[{'field':{'Measure':{'Property':'Total'}}}]},'Values':{'projections':[{'field':{'Column':{'Property':'Category'}}}]}}}}
        visual={'id':'button','type':'advancedSlicerVisual','definition':definition}
        result={'pages':[{'id':'page','visuals':[visual]}]}
        enrich_report(result,{})
        self.assertEqual(visual['type'],'slicer')
        self.assertEqual(visual['originalType'],'advancedSlicerVisual')
        self.assertEqual(next(iter(visual['definition']['query']['queryState'])),'Values')
        self.assertIn('Label',visual['definition']['query']['queryState'])
        self.assertEqual(next(iter(definition['query']['queryState'])),'Label')

if __name__=='__main__':unittest.main()
