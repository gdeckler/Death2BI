"""Regression: duplicate filenames never overwrite reports or their table data."""
import io,json,zipfile,uuid,shutil
from contextlib import contextmanager
from pathlib import Path
import server

@contextmanager
def temporary_workspace():
    base=(Path.cwd()/'work').resolve()
    base.mkdir(exist_ok=True)
    path=base/('modelbridge-test-'+uuid.uuid4().hex)
    path.mkdir()
    try: yield path
    finally:
        assert path.resolve().parent==base
        shutil.rmtree(path)

original=server.DATA
with temporary_workspace() as temp:
    server.DATA=Path(temp)
    def content(value):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr('Report/definition/report.json','{"themeCollection":{}}')
            for i in range(7):
                z.writestr(f'Report/definition/pages/p{i}/page.json',json.dumps({'name':f'p{i}','displayName':f'Page {i+1}'}))
            z.writestr('data/Sales.csv',f'Amount\n{value}\n')
        return buffer.getvalue()
    try:
        a=server.import_model('Same.zip',content(10))
        before=(server.DATA/a['id']/'manifest.json').read_bytes()
        b=server.import_model('Same.zip',content(20))
        assert a['id']!=b['id']
        assert len(a['pages'])==len(b['pages'])==7
        assert len(list(server.DATA.glob('*/manifest.json')))==2
        assert (server.DATA/a['id']/'manifest.json').read_bytes()==before
        for m,total in [(a,10),(b,20)]:
            con=server.duckdb.connect(str(server.DATA/m['id']/'model.duckdb'),read_only=True)
            assert con.execute('SELECT sum(Amount) FROM Sales').fetchone()[0]==total
            con.close()
        print('PASS: same filename creates two independent IDs, seven-page manifests and separate DuckDB data')
    finally:
        server.DATA=original
