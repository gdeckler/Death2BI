"""Contain native model-decoder failures outside the HTTP server process."""
from pathlib import Path
import json,subprocess,sys,uuid

def isolated_import(filename,content,data_dir,custom_dir):
    jobs=Path(data_dir)/'.import-jobs';jobs.mkdir(exist_ok=True)
    job=jobs/uuid.uuid4().hex;job.mkdir()
    source=job/'source.bin';config=job/'job.json';result=job/'result.json'
    try:
        source.write_bytes(content)
        config.write_text(json.dumps({'filename':filename,'data':str(Path(data_dir).resolve()),'custom':str(Path(custom_dir).resolve())}),encoding='utf-8')
        completed=subprocess.run([sys.executable,'-X','utf8','-X','faulthandler',str(Path(__file__).resolve()),str(job.resolve())],capture_output=True,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if completed.returncode or not result.exists():
            detail=completed.stderr.decode('utf-8',errors='replace')[-2000:]
            raise ValueError('Import worker failed (exit '+str(completed.returncode)+'). The server remains available. '+detail)
        output=json.loads(result.read_text(encoding='utf-8'))
        if 'error' in output:raise ValueError(output['error'])
        return output['model']
    except subprocess.TimeoutExpired:
        raise ValueError('Import worker exceeded the 300-second import limit') from None
    finally:
        # Only the task-owned staging files are removed; report folders remain.
        for path in (source,config,result):path.unlink(missing_ok=True)
        job.rmdir()

if __name__=='__main__':
    import server
    job=Path(sys.argv[1]);settings=json.loads((job/'job.json').read_text(encoding='utf-8'))
    server.DATA=Path(settings['data']);server.CUSTOM_VISUALS=Path(settings['custom'])
    try:output={'model':server.import_model(settings['filename'],(job/'source.bin').read_bytes())}
    except Exception as error:output={'error':str(error)}
    (job/'result.json').write_text(json.dumps(output,default=str),encoding='utf-8')
