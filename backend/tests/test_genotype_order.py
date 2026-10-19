import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import openpyxl
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from backend.app.auth import require_admin
from backend.app.database import Base, get_db, migrate_genotype_entry_order, get_business_tables
from backend.app.models.models import GenotypeRecord, User
from backend.app.routers import import_export
from backend.app.services.database_backup import restore_database, snapshot
from backend.app.services.genotype_order import apply_genotype_order, plan_genotype_order
from backend.app.services.genotype_service import next_genotype_entry_order
from backend.app.services.importer import import_single_excel_file


class GenotypeOrderTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'live.db'
        self.engine = create_engine(f'sqlite:///{self.path}', connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        # Simulate an older import that skipped A2 and backfilled it later.
        self.db.add_all([
            GenotypeRecord(mouse_code='A1', genotype_1='WT', test_date='2026-10-18'),
            GenotypeRecord(mouse_code='A3', genotype_1='HET', test_date='2026-09-01'),
            GenotypeRecord(mouse_code='A2', genotype_1='人工更新的结果', notes='人工备注'),
            GenotypeRecord(mouse_code='Other', genotype_1='WT'),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.folder.cleanup()

    @staticmethod
    def workbook():
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = '小鼠档案'
        sheet.append(['测试日期', '品系', 'DOB', '性别', '父母', '编号', 'Genotype 1', 'Genotype 2'])
        sheet.append(['2026-10-18', '5xFAD', None, 'F', None, 'A1', 'WT'])
        sheet.append([None, '5xFAD', None, 'F', None, 'A2'])
        sheet.append(['2026-09-01', '5xFAD', None, 'F', None, 'A3', 'HET'])
        return workbook

    def states(self):
        return [tuple(getattr(record, column.name) for column in GenotypeRecord.__table__.columns
                      if column.name != 'entry_order')
                for record in self.db.query(GenotypeRecord).order_by(GenotypeRecord.id)]

    def order(self):
        return [r.mouse_code for r in self.db.query(GenotypeRecord).order_by(
            func.coalesce(GenotypeRecord.entry_order, GenotypeRecord.id).desc(), GenotypeRecord.id.desc())]

    def test_recovery_only_changes_sort_positions_and_is_idempotent(self):
        before = self.states()
        records, report = plan_genotype_order(self.db, self.workbook())
        self.assertEqual(report, {'matched': 3, 'missing': [], 'ambiguous': []})
        apply_genotype_order(records, report)
        self.db.commit()
        self.assertEqual(report['changed'], 2)
        self.assertEqual(self.order(), ['Other', 'A3', 'A2', 'A1'])
        self.assertEqual(self.states(), before)
        apply_genotype_order(records, report)
        self.assertEqual(report['changed'], 0)
        new = GenotypeRecord(mouse_code='New', entry_order=next_genotype_entry_order(self.db))
        self.db.add(new)
        self.db.commit()
        self.assertEqual(self.order()[0], 'New')

    def test_ordinary_reimport_also_recovers_excel_order(self):
        # Original file result matches the existing record, so no duplicate test is created.
        self.db.query(GenotypeRecord).filter_by(mouse_code='A2').update({'genotype_1': None})
        self.db.commit()
        path = Path(self.folder.name) / 'original.xlsx'
        self.workbook().save(path)
        result = import_single_excel_file(self.db, str(path))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['genotypes_imported'], 0)
        self.assertEqual(self.order(), ['Other', 'A3', 'A2', 'A1'])
        repeat = import_single_excel_file(self.db, str(path))
        self.assertEqual(repeat['report']['summary']['updated'], 0)

    def test_ambiguous_records_and_missing_codes_are_reported_without_guessing(self):
        self.db.add(GenotypeRecord(mouse_code='A2', genotype_1='另一次结果'))
        self.db.commit()
        workbook = self.workbook()
        workbook.active.append([None, None, None, None, None, 'Missing1'])
        records, report = plan_genotype_order(self.db, workbook)
        self.assertEqual([record.mouse_code for record in records], ['A1', 'A3'])
        self.assertEqual(report['ambiguous'][0]['mouse_code'], 'A2')
        self.assertEqual(report['missing'][0]['mouse_code'], 'Missing1')

    def test_endpoint_backs_up_before_reordering_and_rejects_invalid_files(self):
        app = FastAPI()
        app.include_router(import_export.router)
        def test_db():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[require_admin] = lambda: User(username='test', role='admin')
        stream = io.BytesIO()
        self.workbook().save(stream)
        before = self.states()
        with patch.multiple(import_export, DB_PATH=str(self.path), DATA_DIR=self.folder.name):
            with TestClient(app) as client:
                response = client.post('/api/import-export/genotype-order', files={'file': ('original.xlsx', stream.getvalue())})
                self.assertEqual(response.status_code, 200, response.text)
                report = response.json()
                self.assertEqual(report['changed'], 2)
                backup = Path(self.folder.name) / 'backups' / report['safety_backup']
                with closing(sqlite3.connect(backup)) as db:
                    self.assertEqual(db.execute('select entry_order from genotype_records where mouse_code="A2"').fetchone(), (None,))
                self.assertEqual(client.post('/api/import-export/genotype-order', files={'file': ('bad.xlsx', b'bad')}).status_code, 400)
                del app.dependency_overrides[require_admin]
                self.assertEqual(client.post('/api/import-export/genotype-order', files={'file': ('original.xlsx', stream.getvalue())}).status_code, 401)
        self.db.expire_all()
        self.assertEqual(self.order(), ['Other', 'A3', 'A2', 'A1'])
        self.assertEqual(self.states(), before)

    def test_migration_and_old_backup_restore_preserve_existing_data(self):
        old = Path(self.folder.name) / 'old.db'
        snapshot(self.path, old)
        with closing(sqlite3.connect(old)) as db:
            db.execute('ALTER TABLE genotype_records DROP COLUMN entry_order')
            db.commit()
        old_engine = create_engine(f'sqlite:///{old}')
        migrate_genotype_entry_order(old_engine)
        migrate_genotype_entry_order(old_engine)
        with Session(old_engine) as db:
            self.assertEqual(db.query(GenotypeRecord).count(), 4)
        old_engine.dispose()
        with closing(sqlite3.connect(old)) as db:
            db.execute('ALTER TABLE genotype_records DROP COLUMN entry_order')
            db.commit()
        self.db.close()
        restore_database(old, self.path, Path(self.folder.name) / 'safety.db', get_business_tables(), self.engine)
        with Session(self.engine) as db:
            self.assertEqual(db.query(GenotypeRecord).count(), 4)
            self.assertEqual(db.query(GenotypeRecord).filter_by(mouse_code='A2').one().notes, '人工备注')


if __name__ == '__main__':
    unittest.main()
