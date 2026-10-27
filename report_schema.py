"""Pinned offline PBIR validation. Imported annotations are data, never instructions."""
import json
from itertools import islice
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

@lru_cache(maxsize=1)
def schemas():
    return json.loads(Path(__file__).with_name('report-schema-bundle.json').read_text(encoding='utf-8'))['schemas']

def resource(uri):
    path=urlsplit(uri).path.removeprefix('/json-schemas/')
    doc=schemas().get(path)
    if doc is None: raise NoSuchResource(ref=uri)
    return Resource.from_contents(doc)

def audit_documents(docs):
    diagnostics=[]
    registry=Registry(retrieve=resource)
    for filename,doc in docs.items():
        if not isinstance(doc,dict) or not doc.get('$schema'):continue
        uri=doc['$schema']
        if not isinstance(uri,str):
            diagnostics.append({'file':filename,'path':'/$schema','code':'invalid-schema-reference','message':'Schema reference must be text; definition preserved.'});continue
        try:path=urlsplit(uri).path.removeprefix('/json-schemas/')
        except ValueError:
            diagnostics.append({'file':filename,'path':'/$schema','code':'invalid-schema-reference','message':'Invalid schema URI; definition preserved.'});continue
        if not path.startswith(('fabric/item/report/','fabric/pbip/')):continue
        schema=schemas().get(path)
        if schema is None:
            diagnostics.append({'file':filename,'path':'/$schema','code':'unsupported-schema-version','schema':uri,'message':'Definition preserved; schema version is not in the pinned compatibility bundle.'});continue
        try:
            errors=sorted(islice(Draft7Validator(schema,registry=registry).iter_errors(doc),20),key=lambda e:str(list(e.path)))
            for e in errors[:20]:
                diagnostics.append({'file':filename,'path':'/'+ '/'.join(str(x).replace('~','~0').replace('/','~1') for x in e.path),'code':'schema-validation','schema':uri,'message':e.message[:500]})
        except Exception as e:
            diagnostics.append({'file':filename,'path':'/','code':'schema-resolution','schema':uri,'message':str(e)[:500]})
        if len(diagnostics)>=100:break
    return {'bundleVersion':1,'mode':'non-destructive','diagnostics':diagnostics[:100]}

def normalize_definition(source,legacy=False):
    """Retain unknown properties while normalizing the legacy container aliases."""
    import copy
    out=copy.deepcopy(source)
    if legacy:
        for old,new in [('vcObjects','visualContainerObjects')]:
            if old in out and new not in out:out[new]=out[old]
    return out
