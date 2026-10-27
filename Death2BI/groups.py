"""Administrator-managed local account groups and report grants."""
import sqlite3
import time
import uuid


class GroupAccounts:
    def init_groups(self, db):
        db.executescript('''
            CREATE TABLE IF NOT EXISTS local_groups (
                id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS group_members (
                group_id TEXT NOT NULL, user_id TEXT NOT NULL,
                PRIMARY KEY(group_id,user_id),
                FOREIGN KEY(group_id) REFERENCES local_groups(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS report_group_shares (
                report_id TEXT NOT NULL, group_id TEXT NOT NULL,
                PRIMARY KEY(report_id,group_id),
                FOREIGN KEY(group_id) REFERENCES local_groups(id) ON DELETE CASCADE);
        ''')

    def list_groups(self, actor):
        self.require_admin(actor)
        with self.connect() as db:
            return [{'id':r['id'], 'name':r['name'], 'createdAt':r['created_at'],
                     'memberIds':[m['user_id'] for m in db.execute('SELECT user_id FROM group_members WHERE group_id=? ORDER BY user_id',(r['id'],))],
                     'reportCount':db.execute('SELECT count(*) FROM report_group_shares WHERE group_id=?',(r['id'],)).fetchone()[0]}
                    for r in db.execute('SELECT * FROM local_groups ORDER BY name COLLATE NOCASE')]

    def save_group(self, actor, name, members, ident=None):
        from accounts import AuthError
        self.require_admin(actor)
        if not isinstance(name,str) or not 1<=len(name.strip())<=80 or any(ord(c)<32 for c in name):
            raise ValueError('Group names must contain 1 to 80 characters, without control characters.')
        if not isinstance(members,list) or len(members)>10000 or any(not isinstance(m,str) for m in members):
            raise ValueError('Choose a list of account IDs.')
        name=name.strip()
        try:
            with self.lock,self.connect() as db:
                if ident is not None and not db.execute('SELECT 1 FROM local_groups WHERE id=?',(ident,)).fetchone():
                    raise AuthError('Group not found.',404)
                valid={r['id'] for r in db.execute('SELECT id FROM users')}
                if set(members)-valid: raise ValueError('One or more selected accounts are unavailable.')
                if ident is None:
                    ident=uuid.uuid4().hex
                    db.execute('INSERT INTO local_groups VALUES (?,?,?)',(ident,name,time.time()))
                else:
                    db.execute('UPDATE local_groups SET name=? WHERE id=?',(name,ident))
                db.execute('DELETE FROM group_members WHERE group_id=?',(ident,))
                db.executemany('INSERT INTO group_members VALUES (?,?)',[(ident,u) for u in set(members)])
        except sqlite3.IntegrityError:
            raise ValueError('A group with that name already exists.') from None
        return {'id':ident,'name':name,'memberIds':sorted(set(members))}

    def delete_group(self, actor, ident, confirm):
        from accounts import AuthError
        self.require_admin(actor)
        with self.lock,self.connect() as db:
            row=db.execute('SELECT name FROM local_groups WHERE id=?',(ident,)).fetchone()
            if row is None: raise AuthError('Group not found.',404)
            if confirm!=row['name']: raise ValueError('Type the exact group name to confirm deletion.')
            db.execute('DELETE FROM local_groups WHERE id=?',(ident,))
        return {'deleted':ident}

    def group_sharing(self, report_id, actor):
        self.report_access(report_id,actor,manage=True)
        with self.connect() as db:
            shared={r[0] for r in db.execute('SELECT group_id FROM report_group_shares WHERE report_id=?',(report_id,))}
            return [{'id':r['id'],'name':r['name'],'shared':r['id'] in shared,
                     'memberCount':db.execute('SELECT count(*) FROM group_members WHERE group_id=?',(r['id'],)).fetchone()[0]}
                    for r in db.execute('SELECT id,name FROM local_groups ORDER BY name COLLATE NOCASE')]
