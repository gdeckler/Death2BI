import hashlib
import json
from pathlib import Path
import unittest
import uuid
import shutil
from unittest.mock import patch
import zipfile

import duckdb
import pandas as pd

import model_recovery as recovery


class Model:
    def __init__(self,path):
        self.closed=False
        self.read=[]
    def get_table(self,name):
        self.read.append(name)
        if name=='Bad':raise ValueError('Malformed inline IDFX storage: truncated footer')
        return pd.DataFrame({'Value':[3,7],'Label':['Then','Now']})
    def close(self):self.closed=True


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root=(Path(__file__).parent/'work'/('model-recovery-test-'+uuid.uuid4().hex)).resolve()
        self.root.mkdir()
        def cleanup():
            assert self.root.parent==(Path(__file__).parent/'work').resolve()
            shutil.rmtree(self.root)
        self.addCleanup(cleanup)
        con=duckdb.connect(str(self.root/'model.duckdb'))
        con.execute('CREATE TABLE Base AS SELECT 42 AS Value')
        con.close()
        with zipfile.ZipFile(self.root/'source.pbix','w') as archive:archive.writestr('Report/report.json','{}')
        self.metadata={'id':'original-id','name':'report.pbix','createdAt':'original-date','tables':[{'name':'Base','rows':1,'columns':[{'name':'Value','type':'INTEGER','description':'keep'}]}],
                       'measures':[{'Name':'Constant','Expression':'42'}],'pages':[{'id':'page','visuals':[]}], 'relationships':[],
                       'unavailableTables':[{'name':'Good','error':'old missing metadata'},{'name':'Bad','error':'old bad metadata'}],
                       'warnings':['keep warning','Table data could not be extracted for Good: old missing metadata','Table data could not be extracted for Bad: old bad metadata'],
                       'ownerId':'keep-owner','workspaceId':'keep-workspace','sharing':['keep-recipient']}
        (self.root/'manifest.json').write_text(json.dumps(self.metadata))
        self.original={name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in ('model.duckdb','source.pbix','manifest.json')}
        self.model=Model('unused')
        self.relationships=patch.object(recovery,'extract_relationships',return_value=pd.DataFrame(columns=['FromTableName','ToTableName']))
        self.formats=patch.object(recovery,'extract_formats')
        self.presentation=patch('presentation.enrich_report',side_effect=lambda result,files,data_dir:result)
        for item in (self.relationships,self.formats,self.presentation):item.start();self.addCleanup(item.stop)
    def recover(self):return recovery.recover_tables(self.root,self.metadata,model_factory=lambda path:self.model)
    def test_partial_recovery_retains_existing_rows_identity_and_failures(self):
        result=self.recover()
        self.assertEqual(self.model.read,['Good','Bad']);self.assertTrue(self.model.closed)
        con=duckdb.connect(str(self.root/'model.duckdb'),read_only=True)
        self.assertEqual(con.execute('SELECT * FROM Base').fetchall(),[(42,)])
        self.assertEqual(con.execute('SELECT * FROM Good').fetchall(),[(3,'Then'),(7,'Now')]);con.close()
        for key in ('id','name','createdAt','ownerId','workspaceId','sharing','measures','pages'):self.assertEqual(result[key],self.metadata[key])
        self.assertEqual(result['tables'][0]['columns'][0]['description'],'keep')
        self.assertEqual(result['unavailableTables'][0]['name'],'Bad')
        self.assertFalse(any('old missing metadata' in w for w in result['warnings']))
        self.assertTrue(any('truncated footer' in w for w in result['warnings']))
        self.assertEqual(hashlib.sha256((self.root/'source.pbix').read_bytes()).hexdigest(),self.original['source.pbix'])
        self.assertEqual(json.loads((self.root/'manifest.json').read_text()),result)
        self.assertEqual(len(list(self.root.glob('*.parquet'))),1)
        self.assertIs(recovery.recover_tables(self.root,result,model_factory=lambda path:1/0),result,'same decoder version does not retry')
    def test_failed_publication_rolls_back_database_and_new_parquet(self):
        original_replace=recovery.os.replace
        def replace(source,destination):
            if Path(destination)==self.root/'manifest.json':raise OSError('simulated manifest failure')
            return original_replace(source,destination)
        with patch.object(recovery.os,'replace',side_effect=replace),self.assertRaisesRegex(OSError,'manifest failure'):self.recover()
        for name,digest in self.original.items():self.assertEqual(hashlib.sha256((self.root/name).read_bytes()).hexdigest(),digest)
        self.assertEqual(list(self.root.glob('*.parquet')),[])
        self.assertTrue(self.model.closed)
    def test_stale_unavailable_entry_does_not_overwrite_table(self):
        self.metadata['unavailableTables']=[{'name':'Base','error':'stale error'}]
        result=self.recover();self.assertEqual(self.model.read,[])
        self.assertEqual(result['unavailableTables'],[])
        con=duckdb.connect(str(self.root/'model.duckdb'),read_only=True)
        self.assertEqual(con.execute('SELECT * FROM Base').fetchall(),[(42,)]);con.close()
    def test_error_translation_is_scoped_to_actual_known_missing_tables(self):
        con=duckdb.connect()
        try:
            con.execute('SELECT * FROM Good')
        except duckdb.CatalogException as error:
            translated=recovery.unavailable_table_error(error,self.metadata)
            self.assertIn('old missing metadata',str(translated))
            recovered={**self.metadata,'tables':[{'name':'Good'}]}
            self.assertIs(recovery.unavailable_table_error(error,recovered),error)
        try:
            con.execute('SELECT * FROM Typo')
        except duckdb.CatalogException as error:self.assertIs(recovery.unavailable_table_error(error,self.metadata),error)
        finally:con.close()
        ordinary=ValueError('Table with name Good does not exist!')
        self.assertIs(recovery.unavailable_table_error(ordinary,self.metadata),ordinary)
    def test_server_defers_recovery_during_queries(self):
        import server
        metadata={**self.metadata,'semanticParserVersion':server.SEMANTIC_PARSER_VERSION}
        with patch.dict(server.ACTIVE_QUERIES,{self.root.name:1},clear=True),patch.object(server,'recover_tables') as recover:
            self.assertIs(server.repair_semantic_metadata(self.root,metadata),metadata)
            recover.assert_not_called()
        updated={**metadata,'storageDecoderVersion':recovery.STORAGE_DECODER_VERSION}
        with patch.dict(server.ACTIVE_QUERIES,{},clear=True),patch.object(server,'recover_tables',return_value=updated) as recover:
            self.assertIs(server.repair_semantic_metadata(self.root,metadata),updated)
            recover.assert_called_once_with(self.root,metadata)
    def test_abf_only_recovery_preserves_authored_presentation(self):
        (self.root/'source.pbix').unlink()
        (self.root/'cache.abf').write_bytes(b'not-a-zip-ABF-fixture')
        self.metadata.update(theme={'background':'#123456'},assets={'poster':'original-asset'},bookmarks=[{'name':'keep-bookmark'}],reportSettings={'locale':'es-ES'})
        result=self.recover()
        for key in ('theme','assets','bookmarks','reportSettings','pages'):self.assertEqual(result[key],self.metadata[key])
        self.assertIn('Good',[t['name'] for t in result['tables']])
    def test_configuration_failure_closes_source_model(self):
        with patch.object(recovery,'configure_storage_decoder',side_effect=ValueError('bad storage adapter')),self.assertRaisesRegex(ValueError,'bad storage'):
            self.recover()
        self.assertTrue(self.model.closed)
        self.assertEqual(self.original['model.duckdb'],hashlib.sha256((self.root/'model.duckdb').read_bytes()).hexdigest())
    def test_invalid_relationship_endpoint_prevents_publication(self):
        relationships=pd.DataFrame([{'FromTableName':'Base','FromColumnName':'Missing','ToTableName':'Good','ToColumnName':'Value'}])
        with patch.object(recovery,'extract_relationships',return_value=relationships),self.assertRaisesRegex(ValueError,'Relationship endpoint missing'):
            self.recover()
        for name,digest in self.original.items():self.assertEqual(hashlib.sha256((self.root/name).read_bytes()).hexdigest(),digest)
        self.assertEqual(list(self.root.glob('*.parquet')),[])
        self.assertTrue(self.model.closed)


if __name__=='__main__':unittest.main()
