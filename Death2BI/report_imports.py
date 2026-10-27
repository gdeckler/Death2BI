"""Stage and replace imported report contents while retaining report identity."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import uuid


def replace_contents(data, store, actor, ident, filename, content, importer, previous):
    # Caller serializes imports and ensures no active database queries for this ID.
    target=data/ident
    if target.is_symlink() or target.is_junction() or target.resolve()!=data.resolve()/ident:
        raise ValueError('Unsafe report directory.')
    staged=importer(filename,content)
    staging=data/staged['id']
    backup=data/'.replacements'/uuid.uuid4().hex
    backup.parent.mkdir(exist_ok=True)
    moved_old=False
    moved_new=False
    try:
        staged.update(id=ident,createdAt=previous.get('createdAt',staged['createdAt']),updatedAt=datetime.now(timezone.utc).isoformat(),revision=uuid.uuid4().hex)
        (staging/'manifest.json').write_text(json.dumps(staged,default=str),encoding='utf-8')
        owner=store.report_owner(ident)
        # Commit new package associations only when the directory swap succeeds.
        with store.lock,store.connect() as db:
            target.rename(backup);moved_old=True
            staging.rename(target);moved_new=True
            db.execute('DELETE FROM report_packages WHERE report_id=?',(ident,))
            db.executemany('INSERT OR IGNORE INTO report_packages VALUES (?,?)',[(ident,p['id']) for p in staged.get('customVisuals',[])])
            db.executemany('INSERT OR IGNORE INTO package_access VALUES (?,?)',[(p['id'],owner) for p in staged.get('customVisuals',[])])
    except Exception:
        if moved_new:
            target.rename(staging)
        if moved_old:
            backup.rename(target)
        if staging.exists():shutil.rmtree(staging,ignore_errors=True)
        raise
    shutil.rmtree(backup,ignore_errors=True)
    return staged
