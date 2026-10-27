"""Data-cache recovery must retain already-imported report presentation metadata."""
import copy
from pathlib import Path
import shutil
import unittest
import uuid

import duckdb

from presentation import enrich_data


class PresentationDataTests(unittest.TestCase):
    def test_rebuild_caches_preserves_report_without_presentation_archive(self):
        folder=(Path(__file__).parent/'work'/('presentation-data-'+uuid.uuid4().hex)).resolve()
        folder.mkdir(parents=True)
        def cleanup():
            assert folder.parent==(Path(__file__).parent/'work').resolve()
            shutil.rmtree(folder)
        self.addCleanup(cleanup)
        con=duckdb.connect(str(folder/'model.duckdb'))
        con.execute('CREATE TABLE Category AS SELECT * FROM (VALUES (\'B\'),(\'A\'),(\'A\')) AS rows(Name)')
        con.execute('CREATE TABLE Parameter (Label VARCHAR, Field VARCHAR, Ordinal INTEGER)')
        con.execute('INSERT INTO Parameter VALUES (?, ?, ?)', ['Revenue', "'Sales'[Revenue]",0])
        con.close()
        column=lambda table,name:{'Column':{'Expression':{'SourceRef':{'Entity':table}},'Property':name}}
        model={'id':'same-id','theme':{'name':'preserved','dataColors':['#123456']},'reportSettings':{'locale':'de-DE'},
               'assets':{'logo.png':'original image'},'bookmarks':[{'name':'Keep me'}],
               'pages':[{'id':'page','visuals':[{'id':'visual','definition':{'query':{'queryState':{'Category':{
                   'projections':[{'field':column('Category','Name')}],
                   'fieldParameters':[{'parameterExpr':column('Parameter','Field')}]}}}}}]}],
               'colorDomains':{'stale':[]},'fieldParameters':{'stale':{}}}
        before=copy.deepcopy(model)
        self.assertIs(enrich_data(model,folder),model)
        self.assertEqual(model['colorDomains'],{'Category\x00Name':['A','B']})
        self.assertEqual(model['fieldParameters']['Parameter'],{'columns':['Label','Field','Ordinal'],'rows':[('Revenue',"'Sales'[Revenue]",0)],'fieldColumn':'Field'})
        for key in before.keys()-{'colorDomains','fieldParameters'}:
            self.assertEqual(model[key],before[key])
        self.assertIs(enrich_data(model,None),model)


if __name__=='__main__':unittest.main()
