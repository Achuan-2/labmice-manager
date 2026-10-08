"""Exercise real startup against an isolated deployment database, without Excel files."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class StartupStrainRepairTests(unittest.TestCase):
    def test_existing_deployment_repairs_on_startup_without_reimport(self):
        script = r'''
from backend.app.main import startup_event
from backend.app.database import SessionLocal
from backend.app.models.models import GenotypeRecord, Mouse

with SessionLocal() as db:
    for code, strain, genotype in [('B829', '', 'WT'), ('B830', '人工确认品系', 'HET')]:
        mouse = Mouse(mouse_code=code, strain=strain, test_date='2023-02-07',
                      dob='2023-01-10', genotype_1=genotype, status='出笼', notes='保留备注')
        db.add(GenotypeRecord(mouse=mouse, mouse_code=code, strain=strain,
                             test_date=mouse.test_date, dob=mouse.dob, genotype_1=genotype))
    db.add(Mouse(mouse_code='F226', strain='', test_date='2026-05-18',
                 dob='2026-04-15', status='出笼'))
    db.commit()

# A nonempty deployment must repair without calling either Excel import or loading.
from unittest.mock import patch
with patch('backend.app.main.import_local_excel_folder', side_effect=AssertionError('Unexpected reimport')), \
     patch('openpyxl.load_workbook', side_effect=AssertionError('Unexpected Excel access')):
    startup_event()
    with SessionLocal() as db:
        assert db.query(Mouse).count() == 3
        assert db.query(GenotypeRecord).count() == 2
        for model in (Mouse, GenotypeRecord):
            row = db.query(model).filter_by(mouse_code='B829').one()
            assert row.strain == 'JAX-5XFAD-J' and row.genotype_1 == 'WT'
            assert row.dob == '2023-01-10' and row.test_date == '2023-02-07'
            assert db.query(model).filter_by(mouse_code='B830').one().strain == '人工确认品系'
        assert db.query(Mouse).filter_by(mouse_code='B829').one().notes == '保留备注'
        assert db.query(Mouse).filter_by(mouse_code='F226').one().strain == ''
        before = {
            model.__name__: [{column.name: getattr(row, column.name) for column in model.__table__.columns}
                             for row in db.query(model).order_by(model.id).all()]
            for model in (Mouse, GenotypeRecord)
        }
    startup_event()
    with SessionLocal() as db:
        after = {
            model.__name__: [{column.name: getattr(row, column.name) for column in model.__table__.columns}
                             for row in db.query(model).order_by(model.id).all()]
            for model in (Mouse, GenotypeRecord)
        }
        assert before == after, 'Repeated startup changed the repaired records'
print('startup repair verified without Excel import')
'''
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, DATA_DIR=directory, PYTHONUTF8="1",
                               ADMIN_PASSWORD="Isolated-strain-test-password",
                               SECRET_KEY="isolated-strain-test-secret-key-32")
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                env=environment, capture_output=True, text=True, encoding="utf-8", timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Automatically repaired 2 missing strain fields.", result.stdout)
        self.assertIn("startup repair verified without Excel import", result.stdout)


if __name__ == "__main__":
    unittest.main()
