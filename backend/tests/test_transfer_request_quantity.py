import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_admin, require_auth
from backend.app.database import Base, get_db, migrate_transfer_request_fields
from backend.app.models.models import Cage, Mouse, TransferRequest, User
from backend.app.routers.stats import router as stats_router
from backend.app.routers.transfer_requests import router


class TransferRequestQuantityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        app = FastAPI()
        app.include_router(router)
        app.include_router(stats_router)

        def test_db():
            with Session(self.engine, autoflush=False) as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[require_auth] = lambda: User(username="test", role="guest")
        app.dependency_overrides[require_admin] = lambda: User(username="admin", role="admin")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def submit(self, **fields):
        return self.client.post("/api/transfer-requests", json={
            "demander": "测试需求者", "strain": "测试品系", "cage_count": 2, **fields,
        })

    def test_quantity_is_saved_and_visible_in_list_and_dashboard(self):
        response = self.submit(requested_mouse_count=7)
        self.assertEqual(response.status_code, 200, response.text)
        request_id = response.json()["id"]
        with Session(self.engine) as db:
            request = db.get(TransferRequest, request_id)
            self.assertEqual((request.cage_count, request.requested_mouse_count), (2, 7))
        listed = self.client.get("/api/transfer-requests").json()[0]
        pending = self.client.get("/api/stats/dashboard").json()["pending_requests"][0]
        self.assertEqual(listed["requested_mouse_count"], 7)
        self.assertEqual(pending["requested_mouse_count"], 7)

    def test_quantity_is_optional_for_existing_clients(self):
        for fields in ({}, {"requested_mouse_count": None}):
            with self.subTest(fields=fields):
                response = self.submit(**fields)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIsNone(response.json()["requested_mouse_count"])
                self.assertEqual(response.json()["cage_count"], 2)

    def test_invalid_quantities_are_rejected_on_create_and_update(self):
        request_id = self.submit(requested_mouse_count=7).json()["id"]
        for invalid in (0, -1, 1.5, True, "abc"):
            with self.subTest(quantity=invalid):
                self.assertEqual(self.submit(requested_mouse_count=invalid).status_code, 422)
                response = self.client.put(f"/api/transfer-requests/{request_id}", json={
                    "requested_mouse_count": invalid,
                })
                self.assertEqual(response.status_code, 422, response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.query(TransferRequest).count(), 1)
            self.assertEqual(db.get(TransferRequest, request_id).requested_mouse_count, 7)

    def test_quantity_can_be_updated_and_cleared(self):
        request_id = self.submit(requested_mouse_count=7).json()["id"]
        for quantity in (12, None):
            with self.subTest(quantity=quantity):
                response = self.client.put(f"/api/transfer-requests/{request_id}", json={
                    "requested_mouse_count": quantity,
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["requested_mouse_count"], quantity)
                self.assertEqual(response.json()["cage_count"], 2)

    def test_requested_quantity_survives_assignment_and_completion(self):
        request_id = self.submit(requested_mouse_count=7).json()["id"]
        with Session(self.engine) as db:
            cage = Cage(room="测试鼠房", cage_code="A1")
            db.add(cage)
            db.flush()
            db.add(Mouse(mouse_code="M001", strain="测试品系", status="在笼", cage_id=cage.id))
            db.commit()
        # The requested quantity remains separate from the actual assigned mice.
        for status in ("进行中", "已完成"):
            with self.subTest(status=status):
                response = self.client.put(f"/api/transfer-requests/{request_id}", json={
                    "status": status, "mouse_codes": "M001",
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["requested_mouse_count"], 7)
                self.assertEqual(response.json()["mouse_codes"], "M001")


class TransferRequestQuantityMigrationTests(unittest.TestCase):
    def test_legacy_database_preserves_requests_and_migration_is_repeatable(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE transfer_requests (id INTEGER PRIMARY KEY, demander TEXT, cage_count INTEGER)"
                )
                connection.exec_driver_sql("INSERT INTO transfer_requests VALUES (1, '原需求者', 2)")
            with patch("backend.app.database.engine", engine):
                migrate_transfer_request_fields()
                migrate_transfer_request_fields()
            with engine.connect() as connection:
                row = connection.exec_driver_sql(
                    "SELECT id, demander, cage_count, requested_mouse_count, created_by_username FROM transfer_requests"
                ).one()
                self.assertEqual(tuple(row), (1, "原需求者", 2, None, None))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
