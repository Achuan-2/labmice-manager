import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_admin, require_auth
from backend.app.database import Base, get_db, migrate_mouse_genotyping_status
from backend.app.models.models import Cage, GenotypeRecord, Mouse, User
from backend.app.routers.genotypes import router as genotype_router
from backend.app.routers.mice import router as mouse_router
from backend.app.services.genotype_service import sync_existing_genotyping_statuses


class GenotypeStatusLinkTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            cage = Cage(room="Room", cage_code="C1")
            db.add(cage)
            db.flush()
            db.add_all([
                Mouse(mouse_code="M1", cage_id=cage.id, status="在笼"),
                Mouse(mouse_code="M2", cage_id=cage.id, status="实验中"),
                Mouse(mouse_code="M3", status="死亡"),
            ])
            db.commit()
        app = FastAPI()
        app.include_router(genotype_router)
        app.include_router(mouse_router)

        def test_db():
            with Session(self.engine, autoflush=False) as db:
                yield db

        admin = User(username="test", display_name="Test", role="admin")
        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[require_auth] = lambda: admin
        app.dependency_overrides[require_admin] = lambda: admin
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def create_record(self, code="M1", **values):
        response = self.client.post("/api/genotypes", json={"mouse_code": code, **values})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def mouse(self, code="M1"):
        response = self.client.get(f"/api/mice/by-code/{code}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def fill(self, ids, value, field="genotype_1"):
        response = self.client.put("/api/genotypes/batch-fill", json={
            "record_ids": ids, "field": field, "value": value,
        })
        self.assertEqual(response.status_code, 200, response.text)

    def test_blank_registration_links_pending_filters_and_fill_restores_status(self):
        record = self.create_record()
        self.assertEqual(self.mouse()["status"], "待鉴定")
        self.assertEqual(self.client.get("/api/mice", params={"status": "待鉴定"}).json()["total"], 1)
        self.assertEqual(self.client.get("/api/genotypes", params={"page": 1, "test_status": "pending"}).json()["total"], 1)
        self.fill([record["id"]], "WT")
        self.assertEqual(self.mouse()["status"], "在笼")
        self.assertEqual(self.client.get("/api/mice", params={"status": "待鉴定"}).json()["total"], 0)

    def test_bulk_fill_restores_original_custom_status_and_preserves_cages(self):
        first, second = self.create_record(), self.create_record("M2")
        self.fill([first["id"], second["id"]], "阳性", "genotype_3")
        self.assertEqual((self.mouse()["status"], self.mouse("M2")["status"]), ("在笼", "实验中"))
        self.assertIsNotNone(self.mouse("M2")["cage_id"])

    def test_pending_markers_and_clearing_all_results_reopen_pending_status(self):
        record = self.create_record()
        self.fill([record["id"]], "待检验")
        self.assertEqual(self.mouse()["status"], "待鉴定")
        self.fill([record["id"]], "WT")
        self.assertEqual(self.mouse()["status"], "在笼")
        self.fill([record["id"]], "")
        self.assertEqual(self.mouse()["status"], "待鉴定")

    def test_retest_keeps_previous_results_and_remains_pending_until_all_open_tests_finish(self):
        self.create_record(genotype_1="WT")
        first = self.create_record(confirm_existing=True)
        second = self.create_record(confirm_existing=True)
        self.assertEqual((self.mouse()["status"], self.mouse()["genotype_1"]), ("待鉴定", "WT"))
        self.fill([first["id"]], "HET")
        self.assertEqual(self.mouse()["status"], "待鉴定")
        self.fill([second["id"]], "WT")
        self.assertEqual(self.mouse()["status"], "在笼")

    def test_manual_pending_status_creates_only_one_open_record(self):
        mouse_id = self.mouse()["id"]
        for _ in range(2):
            response = self.client.post("/api/mice/batch-update-status", json={"mouse_ids": [mouse_id], "status": "待鉴定"})
            self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.query(GenotypeRecord).count(), 1)
        self.assertEqual(self.client.get("/api/genotypes", params={"page": 1, "test_status": "pending"}).json()["total"], 1)

    def test_mouse_archive_result_edit_completes_its_pending_record(self):
        mouse_id = self.mouse()["id"]
        response = self.client.put(f"/api/mice/{mouse_id}", json={"status": "待鉴定"})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.put(f"/api/mice/{mouse_id}", json={"genotype_1": "HET", "status": "待鉴定"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "在笼")
        with Session(self.engine) as db:
            record = db.query(GenotypeRecord).one()
            self.assertEqual(record.genotype_1, "HET")
            self.assertTrue(record.test_date)

    def test_manual_retest_does_not_copy_old_results_into_the_new_open_record(self):
        self.create_record(genotype_1="WT")
        mouse_id = self.mouse()["id"]
        response = self.client.put(f"/api/mice/{mouse_id}", json={"status": "待鉴定", "genotype_1": "WT"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "待鉴定")
        self.assertEqual(len(response.json()["genotypes"]), 2)
        with Session(self.engine) as db:
            self.assertEqual(db.query(GenotypeRecord).filter(GenotypeRecord.genotype_1.is_(None)).count(), 1)

    def test_new_mouse_pending_status_is_linked_for_single_and_batch_creation(self):
        response = self.client.post("/api/mice", json={"mouse_code": "New1", "status": "待鉴定"})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post("/api/mice/batch-create", json={"mouse_codes": ["New2", "New3"], "status": "待鉴定"})
        self.assertEqual(response.status_code, 200, response.text)
        pending = self.client.get("/api/genotypes", params={"page": 1, "test_status": "pending"}).json()
        self.assertEqual({record["mouse_code"] for record in pending["items"]}, {"New1", "New2", "New3"})

    def test_deleting_an_open_record_restores_status_and_death_is_never_overwritten(self):
        record = self.create_record("M2")
        self.assertEqual(self.mouse("M2")["status"], "待鉴定")
        self.assertEqual(self.client.delete(f'/api/genotypes/{record["id"]}').status_code, 200)
        self.assertEqual(self.mouse("M2")["status"], "实验中")
        dead = self.create_record("M3")
        self.assertEqual(self.mouse("M3")["status"], "死亡")
        self.fill([dead["id"]], "WT")
        self.assertEqual(self.mouse("M3")["status"], "死亡")

    def test_original_status_is_preserved_across_sessions_and_startup_backfill_is_idempotent(self):
        self.create_record("M2")
        with Session(self.engine) as db:
            self.assertEqual(db.query(Mouse).filter_by(mouse_code="M2").one().status_before_genotyping, "实验中")
            db.add(Mouse(mouse_code="Legacy", status="待鉴定"))
            db.commit()
            sync_existing_genotyping_statuses(db)
            db.commit()
            count = db.query(GenotypeRecord).count()
            sync_existing_genotyping_statuses(db)
            db.commit()
            self.assertEqual(db.query(GenotypeRecord).count(), count)
            self.assertEqual(db.query(GenotypeRecord).filter_by(mouse_code="Legacy").count(), 1)

    def test_legacy_database_migration_preserves_data_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.db"
            with closing(sqlite3.connect(path)) as db:
                db.execute("CREATE TABLE mice (id INTEGER PRIMARY KEY, mouse_code TEXT, status TEXT)")
                db.execute("INSERT INTO mice VALUES (1, 'Legacy', '实验中')")
                db.commit()
            engine = create_engine(f"sqlite:///{path}")
            try:
                migrate_mouse_genotyping_status(engine)
                migrate_mouse_genotyping_status(engine)
                with engine.connect() as db:
                    self.assertEqual(db.exec_driver_sql("SELECT mouse_code, status, status_before_genotyping FROM mice").one(),
                                     ("Legacy", "实验中", None))
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
