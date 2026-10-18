"""Test lifecycle APIs on an isolated service with disposable reports only."""
from pathlib import Path
import http.client,json,threading,uuid,shutil
import server
from accounts import Accounts, DEFAULT_PASSWORD

base=(Path.cwd()/'work').resolve();base.mkdir(exist_ok=True)
temp=base/('lifecycle-'+uuid.uuid4().hex);temp.mkdir()
original=server.DATA;original_auth=server.AUTH;server.DATA=temp;server.AUTH=Accounts(temp/'security'/'accounts.sqlite3')
httpd=server.LocalServer(('127.0.0.1',0),server.Handler)
worker=threading.Thread(target=httpd.serve_forever,daemon=True);worker.start()
cookie='';csrf=''
def post(path,value,origin='http://127.0.0.1:8765'):
    global cookie,csrf
    con=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
    con.request('POST',path,json.dumps(value),{'Host':'127.0.0.1:8765','Origin':origin,'Content-Type':'application/json','Cookie':cookie,'X-CSRF-Token':csrf})
    response=con.getresponse();status=response.status;result=json.loads(response.read());header=response.getheader('Set-Cookie');cookie=header.split(';')[0] if header else cookie;csrf=result.get('csrf',csrf);con.close()
    return status,result
try:
    assert post('/api/auth/login',{'username':'admin','password':DEFAULT_PASSWORD})[0]==200
    ids=[uuid.uuid4().hex for _ in range(2)]
    for ident in ids:
        folder=temp/ident;folder.mkdir()
        (folder/'manifest.json').write_text(json.dumps({'id':ident,'name':'Same.pbix','pages':[]}))
        for name in ['source.pbix','table_0.parquet','model.duckdb']:(folder/name).write_bytes(b'test')
    assert post('/api/delete',{'id':ids[0],'confirmName':'Wrong'})[0]==400
    assert (temp/ids[0]).exists()
    assert post('/api/delete',{'id':'../outside','confirmName':'Same.pbix'})[0]==400
    assert post('/api/delete',{'id':ids[0],'confirmName':'Same.pbix'},'http://other.example')[0]==403
    assert post('/api/delete',{'id':ids[0],'confirmName':'Same.pbix'})==(200,{'deleted':ids[0]})
    assert not (temp/ids[0]).exists() and (temp/ids[1]/'model.duckdb').read_bytes()==b'test'
    assert post('/api/shutdown',{'confirm':False})[0]==400
    assert post('/api/shutdown',{'confirm':True},'http://other.example')[0]==403
    assert post('/api/shutdown',{'confirm':True})==(200,{'shuttingDown':True})
    worker.join(timeout=5);assert not worker.is_alive()
    assert (temp/ids[1]/'manifest.json').exists()
    print('PASS: confirmed deletion, duplicate-name isolation, invalid paths, foreign origins, confirmed shutdown, remaining data preserved')
finally:
    httpd.shutdown();httpd.server_close();server.DATA=original;server.AUTH=original_auth
    assert temp.resolve().parent==base
    shutil.rmtree(temp)
