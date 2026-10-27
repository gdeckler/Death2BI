"""Real spawned-process tests; all databases and jobs are disposable fixtures."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import sys
import time
import unittest
from unittest.mock import patch,Mock
import uuid
import duckdb
from dax_pool import DaxProcessPool,PoolSettings,DaxPoolError,_Transport,_Slot


def fake_worker(pipe):
    try:
        while True:
            try:job=pipe.recv()
            except EOFError:return
            if job.get('diagnostic'):sys.stderr.write(job['diagnostic']);sys.stderr.flush()
            if job.get('crash'):os._exit(72)
            start=time.monotonic();time.sleep(job.get('delay',0))
            pipe.send({'ok':True,'result':{'rows':[[os.getpid(),start,time.monotonic()]]},'pid':os.getpid(),'elapsed':time.monotonic()-start})
    finally:pipe.close()


def wait_until(predicate,seconds=8):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.02)
    raise AssertionError('Expected pool state was not reached')


class SupervisionTests(unittest.TestCase):
    def pool(self,**settings):
        p=DaxProcessPool(PoolSettings(**settings),worker_command=[sys.executable,str(Path(__file__).resolve()),'--fake-worker']);self.addCleanup(p.close);return p

    def test_two_processes_execute_overlapping_jobs_and_are_reused(self):
        pool=self.pool(workers=2)
        with ThreadPoolExecutor(2) as threads:
            jobs=[threads.submit(pool.run,{'limits':(5,100),'delay':1},'user') for _ in range(2)]
            a,b=[job.result(10) for job in jobs]
        ar,br=a['rows'][0],b['rows'][0]
        self.assertNotEqual(ar[0],br[0]);self.assertLess(max(ar[1],br[1]),min(ar[2],br[2]))
        again=[pool.run({'limits':(5,100)},'user')['evaluation']['workerPid'] for _ in range(2)]
        self.assertEqual(set(again),{ar[0],br[0]})
        self.assertEqual(pool.status()['completed'],4)
        processes=[slot.process for slot in pool.slots];pool.close()
        self.assertTrue(all(process.poll() is not None for process in processes))

    def test_bounded_queue_owner_scoped_cancellation_and_early_abort(self):
        pool=self.pool(workers=1,queue_size=1);first,second=uuid.uuid4().hex,uuid.uuid4().hex
        with ThreadPoolExecutor(2) as threads:
            running=threads.submit(pool.run,{'limits':(10,100),'delay':5},'alice',first)
            wait_until(lambda:pool.status()['running']==1)
            waiting=threads.submit(pool.run,{'limits':(10,100)},'alice',second)
            wait_until(lambda:pool.status()['queued']==1)
            with self.assertRaisesRegex(DaxPoolError,'queue is full'):pool.run({'limits':(1,100)},'bob')
            self.assertFalse(pool.cancel('bob',first));self.assertEqual(pool.status()['running'],1)
            pool.cancel('alice',second)
            with self.assertRaises(DaxPoolError) as err:waiting.result(5)
            self.assertEqual(err.exception.status,499)
            pool.cancel('alice',first)
            with self.assertRaises(DaxPoolError) as err:running.result(5)
            self.assertEqual(err.exception.status,499)
        early=uuid.uuid4().hex;pool.cancel('alice',early)
        with self.assertRaisesRegex(DaxPoolError,'cancelled'):pool.run({'limits':(1,100)},'alice',early)
        self.assertEqual(pool.run({'limits':(3,100)},'alice')['evaluation']['executionMode'],'process pool')

    def test_hard_timeout_and_crash_replace_only_failed_workers(self):
        pool=self.pool(workers=2,hard_grace=.6)
        with self.assertRaises(DaxPoolError) as err:pool.run({'limits':(.4,100),'delay':30},'user')
        self.assertEqual(err.exception.status,504)
        with self.assertRaisesRegex(DaxPoolError,'stopped unexpectedly'):pool.run({'limits':(3,100),'crash':True},'user')
        good=pool.run({'limits':(3,100)},'user');self.assertTrue(good['rows'])
        self.assertEqual(pool.status()['running'],0);self.assertEqual(pool.status()['timedOut'],1)

    def test_queue_timeout_revalidation_and_shutdown(self):
        pool=self.pool(workers=1,queue_size=2,queue_seconds=.2)
        running_id=uuid.uuid4().hex;prepared=[]
        with ThreadPoolExecutor(3) as threads:
            running=threads.submit(pool.run,{'limits':(5,100),'delay':3},'user',running_id)
            wait_until(lambda:pool.status()['running']==1)
            waiting=threads.submit(pool.run,lambda:prepared.append(True),'user')
            with self.assertRaisesRegex(DaxPoolError,'queue wait limit'):waiting.result(3)
            self.assertFalse(prepared)
            pool.close()
            with self.assertRaisesRegex(DaxPoolError,'shutting down'):running.result(5)
        with self.assertRaisesRegex(DaxPoolError,'shutting down'):pool.run({},'user')
        other=self.pool(workers=1)
        def revoked():raise PermissionError('Access revoked while queued')
        with self.assertRaisesRegex(PermissionError,'Access revoked'):other.run(revoked,'user')
        self.assertTrue(other.run({'limits':(3,100)},'user')['rows'])

    def test_recycling_and_settings_validation(self):
        pool=self.pool(workers=1,recycle=1)
        a=pool.run({'limits':(3,100)},'u');b=pool.run({'limits':(3,100)},'u')
        self.assertNotEqual(a['evaluation']['workerPid'],b['evaluation']['workerPid'])
        with patch.dict(os.environ,{'D2BI_DAX_WORKERS':'0'}):
            with self.assertRaisesRegex(ValueError,'D2BI_DAX_WORKERS'):PoolSettings.from_env()

    def test_crash_diagnostics_are_bounded_private_and_do_not_block_worker(self):
        pool=self.pool(workers=1)
        with self.assertLogs('dax_pool',level='ERROR') as logs:
            with self.assertRaises(DaxPoolError) as error:
                pool.run({'limits':(5,100),'diagnostic':'x'*200000+'PRIVATE native traceback','crash':True},'user')
        self.assertIn('72',str(error.exception))
        self.assertNotIn('PRIVATE',str(error.exception))
        self.assertIn('PRIVATE native traceback','\n'.join(logs.output))
        self.assertLessEqual(len(pool.slots[0].stderr_tail),8192)
        status=pool.status()['lastWorkerFailure']
        self.assertEqual(status['exitCode'],72)
        self.assertEqual(status['reason'],'worker exited unexpectedly')
        self.assertNotIn('PRIVATE',str(status))
        self.assertTrue(pool.run({'limits':(3,100)},'user')['rows'])

    def test_windows_native_exit_has_a_sanitized_specific_reason(self):
        slot=_Slot([]);slot.process=Mock(pid=1234)
        slot.process.wait.return_value=3221225477
        slot.stderr_tail='PRIVATE traceback'
        with self.assertLogs('dax_pool',level='ERROR'):
            failure=slot.failure(EOFError())
        self.assertEqual(failure,{'workerPid':1234,'exitCode':3221225477,'exitCodeHex':'0xC0000005','reason':'native access violation'})


class DaxWorkerTests(unittest.TestCase):
    def setUp(self):
        self.folder=Path('work').resolve()/('dax-pool-test-'+uuid.uuid4().hex);self.folder.mkdir(parents=True)
        self.path=self.folder/'model.duckdb';con=duckdb.connect(str(self.path))
        con.execute("CREATE TABLE Sales(Owner VARCHAR,Amount DECIMAL(12,2)); INSERT INTO Sales VALUES('alice',10.25),('bob',20.50)");con.close()
        self.model={'tables':[{'name':'Sales','columns':[{'name':'Owner'},{'name':'Amount'}]}],'relationships':[],
                    'measures':[{'Name':'Total','TableName':'Sales','Expression':'CALCULATE(SUM(Sales[Amount]),ALL(Sales))','FormatStringExpression':'"0.00"'}]}
        self.field={'Measure':{'Expression':{'SourceRef':{'Entity':'Sales'}},'Property':'Total'}}
        self.pool=DaxProcessPool(PoolSettings(workers=1));self.addCleanup(self.cleanup)

    def cleanup(self):self.pool.close();shutil.rmtree(self.folder)

    def job(self,user=None):
        effective={'applied':user is not None,'config':{'bidirectional':False},'actor':{'id':user,'username':user},
                   'roles':[{'rules':[{'table':'Sales','column':'Owner','operator':'eq','values':[{'identity':'username'}]}]}]}
        return {'path':str(self.path),'model':self.model,'effective':effective,'limits':(10,5000000),
                'payload':{'fields':[self.field],'groups':[{'filters':[],'externalFilters':[],'scope':[],'contexts':{}}]}}

    def test_worker_reuse_does_not_share_rls_or_request_caches(self):
        pids=[]
        for user,expected in [('alice',10.25),('bob',20.5),(None,30.75),('alice',10.25)]:
            result=self.pool.run(self.job(user),user or 'admin')
            self.assertEqual(float(result['rows'][0][0]),expected)
            self.assertEqual(result['evaluation']['duckdbThreads'],1)
            pids.append(result['evaluation']['workerPid'])
        self.assertEqual(len(set(pids)),1)

    def test_limits_errors_formats_and_topn_are_preserved(self):
        limited=self.job();limited['limits']=(10,1)
        with self.assertRaisesRegex(DaxPoolError,'step limit exceeded'):self.pool.run(limited,'u')
        invalid=self.job();invalid['payload']['fields'][0]={'Measure':{'Property':'Missing'}}
        with self.assertRaises(DaxPoolError):self.pool.run(invalid,'u')
        formats=self.job();formats['payload']['operation']='formats'
        self.assertEqual(self.pool.run(formats,'u')['rowFormats'],[['0.00']])
        top=self.job('alice');top['payload']={'operation':'topN','category':{'Column':{'Expression':{'SourceRef':{'Entity':'Sales'}},'Property':'Owner'}},'by':self.field,'filters':[],'count':1,'descending':True}
        self.assertEqual(self.pool.run(top,'alice')['values'],['alice'])
        self.assertEqual(float(self.pool.run(self.job(),'u')['rows'][0][0]),30.75)


if __name__=='__main__':
    if sys.argv[1:]==['--fake-worker']:fake_worker(_Transport(sys.stdin,sys.stdout))
    else:unittest.main()
