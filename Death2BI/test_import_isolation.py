import unittest,uuid,shutil
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from import_worker import isolated_import
class ImportIsolationTests(unittest.TestCase):
 def test_worker_failure_keeps_saved_reports(self):
  root=Path.cwd()/('worker-test-'+uuid.uuid4().hex);root.mkdir();saved=root/'saved';saved.mkdir();(saved/'marker').write_text('keep')
  try:
   with patch('import_worker.subprocess.run',return_value=SimpleNamespace(returncode=7,stderr=b'native decoder failed')):
    with self.assertRaisesRegex(ValueError,'server remains available'):isolated_import('test.pbix',b'data',root,root)
   self.assertEqual((saved/'marker').read_text(),'keep');self.assertEqual(list((root/'.import-jobs').iterdir()),[])
  finally:
   assert root.resolve().parent==Path.cwd().resolve();shutil.rmtree(root)
if __name__=='__main__':unittest.main()
