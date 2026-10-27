import tempfile
import uuid
import shutil
import unittest
from pathlib import Path
import duckdb
from presentation import enrich_report

class ParameterMetadataTests(unittest.TestCase):
    def test_source_field_parameters_import_without_report_specific_names(self):
        path=Path.cwd()/('parameter-test-'+uuid.uuid4().hex)
        path.mkdir()
        try:
            con=duckdb.connect(str(path/'model.duckdb'))
            con.execute('CREATE TABLE Choices (Label VARCHAR, Fields VARCHAR, Ord INTEGER)')
            con.execute('INSERT INTO Choices VALUES (?, ?, ?)', ['A', "'Facts'[Score]", 0]);con.close()
            expr={'Column':{'Expression':{'SourceRef':{'Entity':'Choices'}},'Property':'Fields'}}
            model={'pages':[{'id':'p','visuals':[{'id':'chart','type':'scatterChart','definition':{'query':{'queryState':{'X':{'fieldParameters':[{'parameterExpr':expr,'index':0,'length':1}]}}}}}]}]}
            enriched=enrich_report(model,{},path)
            self.assertEqual(enriched['fieldParameters']['Choices']['rows'],[('A',"'Facts'[Score]",0)])
            self.assertEqual(enriched['fieldParameters']['Choices']['fieldColumn'],'Fields')
        finally:
            shutil.rmtree(path)

if __name__=='__main__':unittest.main()
