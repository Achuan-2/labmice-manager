import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import get_business_tables, get_db
from backend.app.auth_database import get_auth_db
from backend.app.auth import create_access_token
from backend.app.routers import import_export
from backend.app.models.models import Cage, Claimer, Mouse, User
from backend.app.services.database_backup import (
    DatabaseMaintenanceMiddleware, restore_database, snapshot, validate_database,
)


class DatabaseBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.live = self.root / 'live.db'
        self.backup = self.root / 'export.db'
        self.safety = self.root / 'before.db'
        self.engine = create_engine(f'sqlite:///{self.live}')
        self.auth_engine = create_engine(f'sqlite:///{self.root / "accounts.db"}')
        for table in get_business_tables():
            table.create(self.engine)
        User.__table__.create(self.auth_engine)
        with Session(self.engine) as db:
            cage = Cage(room='测试鼠房', cage_code='A1')
            db.add(cage)
            db.flush()
            db.add(Mouse(mouse_code='001', cage_id=cage.id, notes='保留关系及中文'))
            db.commit()
        with Session(self.auth_engine) as db:
            db.add(User(username='backup-admin', hashed_password='hash', role='admin', is_active=True))
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.auth_engine.dispose()
        self.temp.cleanup()

    def dump(self, path):
        db = sqlite3.connect(path)
        try:
            return list(db.iterdump())
        finally:
            db.close()

    def test_wal_roundtrip_and_pre_restore_backup(self):
        writer = sqlite3.connect(self.live)
        try:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute("UPDATE mice SET notes='WAL中已提交的数据'")
            writer.commit()
            snapshot(self.live, self.backup)
            expected = self.dump(self.backup)
            self.assertEqual(self.dump(self.live), expected)
            writer.execute("UPDATE mice SET notes='恢复前的数据'")
            writer.commit()
        finally:
            writer.close()
        before = self.dump(self.live)
        restore_database(self.backup, self.live, self.safety, get_business_tables(), self.engine)
        self.assertEqual(self.dump(self.live), expected)
        self.assertEqual(self.dump(self.safety), before)
        with Session(self.engine) as db:
            self.assertEqual(db.query(Mouse).one().cage.cage_code, 'A1')

    def test_invalid_or_incompatible_file_does_not_modify_live_database(self):
        before = self.dump(self.live)
        for content in [b'not a database', b'']:
            self.backup.write_bytes(content)
            with self.assertRaises(ValueError):
                restore_database(self.backup, self.live, self.safety, get_business_tables(), self.engine)
            self.assertEqual(self.dump(self.live), before)
            self.assertFalse(self.safety.exists())

    def test_business_backup_does_not_contain_accounts(self):
        snapshot(self.live, self.backup)
        with closing(sqlite3.connect(self.backup)) as db:
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertNotIn('users', tables)
        validate_database(self.backup, get_business_tables())

    def test_authenticated_export_and_restore_endpoints(self):
        app = FastAPI()
        app.include_router(import_export.router)
        app.add_middleware(DatabaseMaintenanceMiddleware)

        def test_db():
            with Session(self.engine) as db:
                yield db

        def test_auth_db():
            with Session(self.auth_engine) as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_auth_db] = test_auth_db
        headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'backup-admin'})}
        with patch.multiple(import_export, DB_PATH=str(self.live), DATA_DIR=str(self.root), engine=self.engine):
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/import-export/database/export').status_code, 401)
                denied = client.post('/api/import-export/database/restore', files={'file': ('x.db', b'invalid')})
                self.assertEqual(denied.status_code, 401)
                response = client.get('/api/import-export/database/export', headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b'SQLite format 3'))
                with Session(self.engine) as db:
                    db.query(Mouse).update({'notes': 'modified'})
                    db.commit()
                response = client.post('/api/import-export/database/restore', headers=headers,
                                       files={'file': ('backup.db', response.content)})
                self.assertEqual(response.status_code, 200, response.text)
                with Session(self.engine) as db:
                    self.assertEqual(db.query(Mouse).one().notes, '保留关系及中文')
                    self.assertEqual(db.query(Claimer).filter_by(name='安乐死').count(), 1)
                normalized = self.dump(self.live)
                self.assertTrue((self.root / 'backups' / response.json()['safety_backup']).exists())
                rejected = client.post('/api/import-export/database/restore', headers=headers,
                                       files={'file': ('bad.db', b'broken')})
                self.assertEqual(rejected.status_code, 400)
                self.assertEqual(self.dump(self.live), normalized)


class MaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_waits_for_requests_and_blocks_new_requests(self):
        started = []
        releases = {name: asyncio.Event() for name in ['read', 'restore', 'later']}

        async def app(scope, receive, send):
            started.append(scope['name'])
            await releases[scope['name']].wait()

        middleware = DatabaseMaintenanceMiddleware(app)

        def request(name):
            return asyncio.create_task(middleware({
                'type': 'http', 'method': 'POST' if name == 'restore' else 'GET',
                'path': '/api/import-export/database/restore' if name == 'restore' else '/api/mice',
                'name': name,
            }, None, None))

        read = request('read')
        await asyncio.sleep(0)
        restore = request('restore')
        await asyncio.sleep(0)
        later = request('later')
        await asyncio.sleep(0)
        self.assertEqual(started, ['read'])
        releases['read'].set()
        await read
        await asyncio.sleep(0)
        self.assertEqual(started, ['read', 'restore'])
        releases['restore'].set()
        await restore
        await asyncio.sleep(0)
        self.assertEqual(started, ['read', 'restore', 'later'])
        releases['later'].set()
        await later
