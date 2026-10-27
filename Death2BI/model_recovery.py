"""Retry incomplete embedded-model imports with the current storage decoder."""
import copy
import json
import os
import shutil
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from semantic_model import (configure_date_decoder, configure_storage_decoder,
                            extract_formats, extract_relationships,
                            SEMANTIC_PARSER_VERSION, STORAGE_DECODER_VERSION)


def quote(name):
    return '"'+str(name).replace('"','""')+'"'


@contextmanager
def staging_directory(dest):
    # Inherit the report directory's ACL, including on Windows restricted tokens.
    path=dest/('storage-recovery-'+uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        assert path.resolve().parent==dest.resolve() and path.name.startswith('storage-recovery-')
        shutil.rmtree(path)


def recover_tables(dest, metadata, *, model_factory=None):
    """Publish recovered rows together, retaining the report ID and permissions.

    The caller serializes access and defers recovery while queries are active.
    Successful tables are read from the saved source snapshot, never refreshed.
    Existing converted tables are retained without being decoded or overwritten.
    """
    dest=Path(dest).resolve()
    if not metadata.get('unavailableTables') or metadata.get('storageDecoderVersion')==STORAGE_DECODER_VERSION:
        return metadata
    source=next((p for p in (dest/'source.pbix',dest/'cache.abf') if p.is_file()),None)
    if source is None or not (dest/'model.duckdb').is_file():
        return metadata
    import polars as pl
    if model_factory is None:
        from pbixray import PBIXRay
        model_factory=PBIXRay
    updated=copy.deepcopy(metadata)
    model=model_factory(str(source))
    try:
        configure_date_decoder(model)
        configure_storage_decoder(model)
        with staging_directory(dest) as temporary:
            staging=Path(temporary).resolve()
            assert staging.is_relative_to(dest)
            original_db=dest/'model.duckdb'
            backup=staging/'original.duckdb'
            shutil.copy2(original_db,backup)
            shutil.copy2(original_db,staging/'model.duckdb')
            recovered=[]
            failed=[]
            parquet=[]
            con=duckdb.connect(str(staging/'model.duckdb'))
            try:
                existing={row[0].casefold() for row in con.execute('SHOW TABLES').fetchall()}
                for unavailable in metadata['unavailableTables']:
                    name=unavailable['name']
                    if name.casefold() in existing:
                        recovered.append(name)
                        continue
                    try:
                        frame=pl.from_pandas(model.get_table(name))
                        filename='table_recovered_'+uuid.uuid4().hex+'.parquet'
                        path=staging/filename
                        frame.write_parquet(path)
                        con.execute('CREATE TABLE '+quote(name)+' AS SELECT * FROM read_parquet(?)',[str(path)])
                        parquet.append(filename)
                        recovered.append(name)
                        existing.add(name.casefold())
                    except (ValueError,NotImplementedError) as error:
                        failed.append({'name':name,'error':str(error)})
                updated['tables']=[{
                    'name':name,
                    'rows':con.execute('SELECT COUNT(*) FROM '+quote(name)).fetchone()[0],
                    'columns':[{'name':column[0],'type':column[1]} for column in con.execute('DESCRIBE '+quote(name)).fetchall()]
                } for (name,) in con.execute('SHOW TABLES').fetchall()]
            finally:
                con.close()
            # Keep existing column annotations and relationships when recovery is
            # partial; extraction refreshes metadata for every available endpoint.
            old_tables={t['name']:t for t in metadata.get('tables',[])}
            for table in updated['tables']:
                prior=old_tables.get(table['name'],{})
                table.update({k:v for k,v in prior.items() if k not in ('name','rows','columns')})
                prior_columns={c['name']:c for c in prior.get('columns',[])}
                table['columns']=[{**prior_columns.get(c['name'],{}),**c} for c in table['columns']]
            updated['relationships']=extract_relationships(model,[t['name'] for t in updated['tables']]).to_dict('records')
            schema={t['name']:{c['name'] for c in t['columns']} for t in updated['tables']}
            for relationship in updated['relationships']:
                for side in ('From','To'):
                    table=relationship[side+'TableName']
                    if relationship[side+'ColumnName'] not in schema.get(table,set()):
                        raise ValueError('Relationship endpoint missing from converted table: '+table)
            extract_formats(model,updated)
            updated['semanticParserVersion']=SEMANTIC_PARSER_VERSION
            updated['unavailableTables']=failed
            prefixes=tuple('Table data could not be extracted for '+name+': ' for name in recovered)
            updated['warnings']=[w for w in updated.get('warnings',[]) if not prefixes or not w.startswith(prefixes)]
            for failure in failed:
                prefix='Table data could not be extracted for '+failure['name']+': '
                updated['warnings']=[w for w in updated['warnings'] if not w.startswith(prefix)]
                updated['warnings'].append(prefix+failure['error'])
            updated['storageDecoderVersion']=STORAGE_DECODER_VERSION
            updated['storageRecovery']={'recoveredTables':recovered,'remainingTables':[t['name'] for t in failed]}
            if recovered:
                updated['revision']=uuid.uuid4().hex
                updated['updatedAt']=datetime.now(timezone.utc).isoformat()
                # Rebuild data-dependent color domains and field parameters from
                # the staged database, using the same import presentation path.
                from presentation import enrich_report, enrich_data
                presentation_source=next((p for p in (dest/'source.pbix',dest/'source.zip') if p.is_file()),None)
                if presentation_source:
                    with zipfile.ZipFile(presentation_source) as archive:
                        files={i.filename.replace('\\','/'):archive.read(i) for i in archive.infolist()
                               if not i.is_dir() and (i.filename.lower().endswith(('.json','.png','.jpg','.jpeg','.gif','.webp','.avif','.bmp','.svg')) or i.filename.lower()=='report/layout')}
                    enrich_report(updated,files,staging)
                else:
                    enrich_data(updated,staging)
            staged_manifest=staging/'manifest.json'
            staged_manifest.write_text(json.dumps(updated,default=str),encoding='utf-8')
            published=[]
            db_published=False
            try:
                for filename in parquet:
                    os.replace(staging/filename,dest/filename)
                    published.append(dest/filename)
                if recovered:
                    os.replace(staging/'model.duckdb',original_db)
                    db_published=True
                os.replace(staged_manifest,dest/'manifest.json')
            except BaseException:
                if db_published:
                    os.replace(backup,original_db)
                for path in published:
                    assert path.resolve().is_relative_to(dest)
                    path.unlink(missing_ok=True)
                raise
        return updated
    finally:
        close=getattr(model,'close',None)
        if close:
            close()


def unavailable_table_error(error, metadata):
    """Describe a known extraction failure only for a real missing-table error."""
    if not isinstance(error,duckdb.CatalogException):
        return error
    import re
    match=re.search(r'Table with name (.+?) does not exist!',str(error))
    if not match:
        return error
    name=match[1].strip('"')
    available={t['name'].casefold() for t in metadata.get('tables',[])}
    failure=next((t for t in metadata.get('unavailableTables',[]) if t['name'].casefold()==name.casefold() and name.casefold() not in available),None)
    if failure:
        return ValueError('Source data for table '+repr(failure['name'])+' could not be extracted from the imported report: '+failure['error'])
    return error
