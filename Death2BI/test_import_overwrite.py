"""Overwrite imports preserve report authorization and swap content safely."""
import io
import json
import unittest
import zipfile
from unittest.mock import patch
from test_accounts import AccountTests
import server


def upload(client, value, mode='new', ident=None, filename='Same.zip', workspace=None, broken=False):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('Samples.csv','Value\n'+str(value)+'\n')
        z.writestr('report.json',json.dumps({'sections':[{'name':'page'+str(value),'displayName':'Page '+str(value),'visualContainers':[]}]}))
        z.writestr('model.tmdl','table Samples\n\tmeasure NewMeasure = SUM(Samples[Value])')
    parts=[b'--overwrite-test\r\nContent-Disposition: form-data; name="file"; filename="'+filename.encode()+b'"\r\n\r\n'+(b'not a zip' if broken else output.getvalue())+b'\r\n']
    for key,val in [('mode',mode),('overwriteId',ident),('workspaceId',workspace)]:
        if val is not None:parts.append(b'--overwrite-test\r\nContent-Disposition: form-data; name="'+key.encode()+b'"\r\n\r\n'+val.encode()+b'\r\n')
    return client.request('POST','/api/import',raw=b''.join(parts)+b'--overwrite-test--\r\n',content_type='multipart/form-data; boundary=overwrite-test')


class OverwriteTests(unittest.TestCase):
    setUp=AccountTests.setUp
    tearDown=AccountTests.tearDown
    create_user=AccountTests.create_user

    def test_contents_and_permissions(self):
        owner,o=self.create_user('replace-owner')
        reader,r=self.create_user('replace-reader')
        member,m=self.create_user('replace-member')
        _,report=upload(o,111)
        rid=report['id']
        _,space=o.request('POST','/api/workspaces',{'name':'Original workspace'})
        o.request('POST','/api/workspaces/move-report',{'reportId':rid,'workspaceId':space['id']})
        _,group=self.admin.request('POST','/api/admin/groups',{'name':'Report readers','memberIds':[member['id']]})
        o.request('POST','/api/reports/'+rid+'/sharing',{'userIds':[reader['id']],'groupIds':[group['id']]})
        _,invite=o.request('POST','/api/reports/'+rid+'/invitations',{'hours':24})
        _,recipient_space=r.request('POST','/api/workspaces',{'name':'Received'})
        r.request('POST','/api/workspaces/move-report',{'reportId':rid,'workspaceId':recipient_space['id']})
        status,new=upload(o,222,'overwrite',rid)
        self.assertEqual(status,200)
        self.assertEqual(new['id'],rid)
        self.assertTrue(new['overwritten'])
        self.assertEqual(new['createdAt'],report['createdAt'])
        self.assertIn('updatedAt',new)
        self.assertEqual(new['workspaceId'],space['id'])
        self.assertEqual(new['ownerId'],owner['id'])
        self.assertEqual(new['pages'][0]['name'],'Page 222')
        self.assertTrue(new['measures'])
        self.assertEqual(len(o.request('GET','/api/models')[1]),1)
        self.assertEqual(r.request('GET','/api/models')[1][0]['workspaceId'],recipient_space['id'])
        for client in (o,r,m):
            self.assertEqual(client.request('POST','/api/query',{'id':rid,'sql':'SELECT * FROM Samples'})[1]['rows'],[[222]])
        self.assertTrue(next(u for u in o.request('GET','/api/reports/'+rid+'/sharing')[1] if u['id']==reader['id'])['shared'])
        self.assertTrue(o.request('GET','/api/reports/'+rid+'/group-sharing')[1][0]['shared'])
        token=invite['url'].split('#invite=')[1]
        self.assertEqual(self.admin.request('POST','/api/auth/invite-preview',{'token':token})[1]['reportId'],rid)

    def test_matches_new_copy_and_authorization(self):
        owner,o=self.create_user('match-owner')
        reader,r=self.create_user('match-reader')
        stranger,x=self.create_user('match-stranger')
        _,first=upload(o,10)
        self.assertEqual(x.request('POST','/api/import/check',{'filename':'Same.zip'})[1]['matches'],[])
        o.request('POST','/api/reports/'+first['id']+'/sharing',{'userIds':[reader['id']]})
        visible=r.request('POST','/api/import/check',{'filename':'same.ZIP'})[1]['matches']
        self.assertEqual(len(visible),1)
        self.assertFalse(visible[0]['canOverwrite'])
        self.assertEqual(upload(r,20,'overwrite',first['id'])[0],404)
        self.assertEqual(upload(x,20,'overwrite',first['id'])[0],404)
        self.assertEqual(upload(o,20,'overwrite',first['id'],filename='Different.zip')[0],400)
        self.assertEqual(upload(o,20,'auto')[0],409)
        # Older pages omit mode; they must not silently duplicate a saved name.
        status,conflict=upload(o,20,None)
        self.assertEqual(status,409)
        self.assertEqual(conflict['code'],'IMPORT_CONFLICT')
        self.assertEqual(conflict['matches'][0]['name'],first['name'])
        self.assertEqual(len(o.request('GET','/api/models')[1]),1)
        status,second=upload(o,20,'new')
        self.assertEqual(status,200)
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(len(o.request('POST','/api/import/check',{'filename':'Same.zip'})[1]['matches']),2)
        self.assertEqual(o.request('GET','/api/reports/'+second['id']+'/sharing')[1][0]['shared'],False)
        # An admin can replace another owner's content without taking ownership.
        status,replaced=upload(self.admin,30,'overwrite',first['id'])
        self.assertEqual(status,200)
        self.assertEqual(replaced['ownerId'],owner['id'])
        self.assertEqual(r.request('POST','/api/query',{'id':first['id'],'sql':'SELECT * FROM Samples'})[1]['rows'],[[30]])

    def test_failure_and_busy_leave_original(self):
        _,report=upload(self.admin,123)
        rid=report['id']
        self.assertEqual(upload(self.admin,456,'overwrite',rid,broken=True)[0],400)
        with patch.dict(server.ACTIVE_QUERIES,{rid:1}):
            self.assertEqual(upload(self.admin,456,'overwrite',rid)[0],409)
        from pathlib import Path
        rename=Path.rename
        def fail_staging(path,target):
            if Path(target)==server.DATA/rid and path.parent==server.DATA and path.name!=rid:
                raise OSError('simulated swap failure')
            return rename(path,target)
        with patch.object(Path,'rename',fail_staging):
            self.assertEqual(upload(self.admin,456,'overwrite',rid)[0],400)
        self.assertEqual(self.admin.request('POST','/api/query',{'id':rid,'sql':'SELECT * FROM Samples'})[1]['rows'],[[123]])
        models=self.admin.request('GET','/api/models')[1]
        self.assertEqual(len(models),1)
        self.assertEqual(models[0]['pages'][0]['name'],'Page 123')
        self.assertEqual(server.ACTIVE_QUERIES,{})

if __name__=='__main__':unittest.main()
