from concurrent.futures import ThreadPoolExecutor
import threading
import os
import unittest
from unittest.mock import patch
import uuid
import test_accounts


class DaxPoolHTTPTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ,{'D2BI_DAX_WORKERS':'2'}):test_accounts.AccountTests.setUp(self)
    tearDown=test_accounts.AccountTests.tearDown
    create_user=test_accounts.AccountTests.create_user

    def payload(self,ident):
        return {'id':ident,'fields':[{'Aggregation':{'Expression':{'Column':{'Expression':{'SourceRef':{'Entity':'Samples'}},'Property':'Value'}},'Function':0}}],
                'groups':[{'filters':[],'externalFilters':[],'scope':[],'contexts':{}}]}

    def policy(self,ident,user,value):
        config={'enabled':True,'roles':[{'name':'Own','userIds':[user['id']],'groupIds':[],'rules':[{'table':'Samples','column':'Value','operator':'eq','values':[value]}]}]}
        self.assertEqual(self.admin.request('POST','/api/admin/rls',{'id':ident,'config':config})[0],200)

    def test_real_process_results_security_and_admin_diagnostics(self):
        alice,a=self.create_user('alice');bob,b=self.create_user('bob')
        status,report=self.admin.upload(123);self.assertEqual(status,200);ident=report['id']
        self.assertEqual(self.admin.request('POST','/api/reports/'+ident+'/sharing',{'userIds':[alice['id'],bob['id']]})[0],200)
        self.policy(ident,alice,123)
        forged={**self.payload(ident),'effective':{'applied':False},'threads':8,'limits':[300,100000000],'path':'other.duckdb'}
        with ThreadPoolExecutor(2) as executor:
            futures=[executor.submit(client.request,'POST','/api/dax',forged) for client in (a,b)]
            results=[f.result(10) for f in futures]
        for status,result in results:self.assertEqual(status,200,result)
        self.assertEqual(results[0][1]['rows'],[[123]])
        self.assertEqual(results[1][1]['rows'],[[None]])
        self.assertNotEqual(results[0][1]['evaluation']['workerPid'],results[1][1]['evaluation']['workerPid'])
        self.assertTrue(all(r[1]['evaluation']['executionMode']=='process pool' and r[1]['evaluation']['duckdbThreads']==1 for r in results))
        self.assertEqual(a.request('GET','/api/admin/dax-pool')[0],403)
        status,stats=self.admin.request('GET','/api/admin/dax-pool');self.assertEqual(status,200)
        self.assertEqual(stats['completed'],2);self.assertEqual(stats['running'],0)
        self.assertEqual(a.request('POST','/api/dax/cancel',{'requestId':uuid.uuid4().hex},csrf=False)[0],403)
        self.assertEqual(a.request('POST','/api/dax/cancel',{'requestId':'invalid'})[0],400)
        self.assertEqual(a.request('POST','/api/dax/cancel',{'requestId':uuid.uuid4().hex})[0],200)

    def test_queued_request_revalidates_policy_and_blocks_report_deletion(self):
        alice,a=self.create_user('alice');status,report=self.admin.upload(123);ident=report['id']
        self.admin.request('POST','/api/reports/'+ident+'/sharing',{'userIds':[alice['id']]});self.policy(ident,alice,123)
        stamp=a.request('GET','/api/security-context?id='+ident)[1]['stamp']
        entered,release=threading.Event(),threading.Event();original=self.httpd.dax_pool.run
        def queued(prepare,*args):
            entered.set();release.wait(5);return original(prepare,*args)
        with ThreadPoolExecutor(1) as threads,patch.object(self.httpd.dax_pool,'run',side_effect=queued):
            future=threads.submit(a.request,'POST','/api/dax',{**self.payload(ident),'securityStamp':stamp})
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.admin.request('POST','/api/delete',{'id':ident,'confirmName':report['name']})[0],409)
                self.policy(ident,alice,999)
            finally:release.set()
            status,result=future.result(8)
        self.assertEqual(status,409,result);self.assertIn('policies changed',result['error'])
        self.assertFalse(self.httpd.dax_pool.status()['workerPids'])

    def test_result_is_discarded_if_policies_change_during_execution(self):
        alice,a=self.create_user('alice');status,report=self.admin.upload(123);ident=report['id']
        self.admin.request('POST','/api/reports/'+ident+'/sharing',{'userIds':[alice['id']]});self.policy(ident,alice,123)
        computed,release=threading.Event(),threading.Event();original=self.httpd.dax_pool.run
        def pause_delivery(prepare,*args):
            result=original(prepare,*args);computed.set();release.wait(5);return result
        with ThreadPoolExecutor(1) as threads,patch.object(self.httpd.dax_pool,'run',side_effect=pause_delivery):
            future=threads.submit(a.request,'POST','/api/dax',self.payload(ident))
            try:self.assertTrue(computed.wait(5));self.policy(ident,alice,999)
            finally:release.set()
            status,result=future.result(8)
        self.assertEqual(status,409,result);self.assertIn('during calculation',result['error'])
        self.assertEqual(a.request('POST','/api/dax',self.payload(ident))[1]['rows'],[[None]])


if __name__=='__main__':unittest.main()
