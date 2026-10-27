"""Personal report containers. Placements never grant access to a report."""
import sqlite3
import time
import uuid


class WorkspaceAccounts:
    def init_workspaces(self, db):
        db.executescript('''
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE, is_default INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                UNIQUE(user_id,name),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
            CREATE UNIQUE INDEX IF NOT EXISTS workspace_default ON workspaces(user_id) WHERE is_default=1;
            CREATE TABLE IF NOT EXISTS workspace_reports (
                user_id TEXT NOT NULL, report_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                PRIMARY KEY(user_id,report_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE);
        ''')

    def _default_workspace(self, db, user_id):
        row = db.execute('SELECT id FROM workspaces WHERE user_id=? AND is_default=1', (user_id,)).fetchone()
        if row:
            return row['id']
        ident = uuid.uuid4().hex
        db.execute('INSERT INTO workspaces VALUES (?,?,?,?,?)', (ident, user_id, 'My Workspace', 1, time.time()))
        return ident

    def _workspace(self, db, actor, ident):
        from accounts import AuthError
        row = db.execute('SELECT * FROM workspaces WHERE id=? AND user_id=?', (ident, actor['id'])).fetchone()
        if row is None:
            raise AuthError('Workspace not found.', 404)
        return row

    @staticmethod
    def _workspace_name(name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
            raise ValueError('Workspace names must contain 1 to 80 characters, without control characters.')
        return name.strip()

    def list_workspaces(self, actor):
        self.user(actor['id'])
        with self.lock, self.connect() as db:
            self._default_workspace(db, actor['id'])
            return [{'id': r['id'], 'name': r['name'], 'isDefault': bool(r['is_default'])}
                    for r in db.execute('SELECT * FROM workspaces WHERE user_id=? ORDER BY is_default DESC,name COLLATE NOCASE', (actor['id'],))]

    def save_workspace(self, actor, name, ident=None):
        name = self._workspace_name(name)
        self.user(actor['id'])
        try:
            with self.lock, self.connect() as db:
                self._default_workspace(db, actor['id'])
                if ident:
                    row = self._workspace(db, actor, ident)
                    if row['is_default']:
                        raise ValueError('My Workspace is the permanent default. Create another workspace to use a different name.')
                    db.execute('UPDATE workspaces SET name=? WHERE id=?', (name, ident))
                else:
                    ident = uuid.uuid4().hex
                    db.execute('INSERT INTO workspaces VALUES (?,?,?,?,?)', (ident, actor['id'], name, 0, time.time()))
        except sqlite3.IntegrityError:
            raise ValueError('You already have a workspace with that name.') from None
        return {'id': ident, 'name': name, 'isDefault': False}

    def delete_workspace(self, actor, ident):
        self.user(actor['id'])
        with self.lock, self.connect() as db:
            row = self._workspace(db, actor, ident)
            if row['is_default']:
                raise ValueError('My Workspace cannot be deleted.')
            target = self._default_workspace(db, actor['id'])
            db.execute('UPDATE workspace_reports SET workspace_id=? WHERE user_id=? AND workspace_id=?', (target, actor['id'], ident))
            db.execute('DELETE FROM workspaces WHERE id=?', (ident,))
        return {'ok': True, 'workspaceId': target}

    def workspace_for_report(self, actor, report_id):
        with self.lock, self.connect() as db:
            default = self._default_workspace(db, actor['id'])
            row = db.execute('SELECT workspace_id FROM workspace_reports WHERE user_id=? AND report_id=?', (actor['id'], report_id)).fetchone()
            return row['workspace_id'] if row else default

    def check_workspace(self, actor, ident):
        with self.lock, self.connect() as db:
            return self._workspace(db, actor, ident)['id']

    def move_report_workspace(self, actor, report_id, ident):
        self.report_access(report_id, actor)
        with self.lock, self.connect() as db:
            self._workspace(db, actor, ident)
            db.execute('INSERT INTO workspace_reports VALUES (?,?,?) ON CONFLICT(user_id,report_id) DO UPDATE SET workspace_id=excluded.workspace_id', (actor['id'], report_id, ident))
        return {'id': report_id, 'workspaceId': ident}
