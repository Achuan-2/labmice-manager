import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import get_current_user
from backend.app.database import Base, get_db
from backend.app.models.models import Cage, Mouse, TransferRequest, User
from backend.app.routers.transfer_requests import router
from backend.app.services.transfer_request_service import backfill_request_creators


class TransferRequestPermissionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.guest = User(username="guest-a", display_name="访客甲", role="guest")
        self.other_guest = User(username="guest-b", display_name="访客乙", role="guest")
        self.admin = User(username="admin", display_name="管理员", role="admin")
        self.current_user = self.guest
        app = FastAPI()
        app.include_router(router)

        def test_db():
            with Session(self.engine, autoflush=False) as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.fields = {
            "demander": "需求者", "strain": "测试品系", "age_gender_req": "成年/雄鼠",
            "target_room": "东五", "cage_count": 2, "requested_mouse_count": 7, "feedback": "原备注",
        }
        response = self.client.post("/api/transfer-requests", json=self.fields)
        self.assertEqual(response.status_code, 200, response.text)
        self.request_id = response.json()["id"]
        self.url = f"/api/transfer-requests/{self.request_id}"

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def edit(self, **fields):
        return self.client.put(self.url + "/application", json={**self.fields, **fields})

    def test_guest_can_edit_own_pending_application(self):
        response = self.edit(demander=" 新需求者 ", strain=" 新品系 ", target_room=" 东四 ",
                             cage_count=3, requested_mouse_count=10, age_gender_req="幼鼠/雌鼠", feedback="新备注")
        self.assertEqual(response.status_code, 200, response.text)
        edited = response.json()
        self.assertEqual(edited["created_by_username"], "guest-a")
        self.assertEqual((edited["demander"], edited["strain"], edited["target_room"]), ("新需求者", "新品系", "东四"))
        self.assertEqual((edited["cage_count"], edited["requested_mouse_count"]), (3, 10))
        self.assertEqual((edited["status"], edited["handler"]), ("申请中", "访客甲"))
        self.assertEqual(edited["feedback"], "新备注")
        self.assertEqual(edited["age_gender_req"], "幼鼠/雌鼠")
        self.assertIsNone(edited["mouse_codes"])
        self.assertEqual(self.client.get("/api/transfer-requests").json()[0], edited)

    def test_guest_can_delete_own_pending_application(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/transfer-requests").json(), [])

    def test_other_guest_cannot_edit_or_delete_even_with_same_display_name(self):
        self.other_guest.display_name = self.guest.display_name
        self.current_user = self.other_guest
        self.assertEqual(self.edit().status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.assertEqual(self.client.get("/api/transfer-requests").json()[0]["feedback"], "原备注")

    def test_guest_cannot_modify_processed_or_cancelled_requests(self):
        for status in ("进行中", "已完成", "已转", "取消"):
            with self.subTest(status=status):
                with Session(self.engine) as db:
                    db.get(TransferRequest, self.request_id).status = status
                    db.commit()
                self.assertEqual(self.edit().status_code, 409)
                self.assertEqual(self.client.delete(self.url).status_code, 409)

    def test_guest_cannot_change_approval_or_ownership_fields(self):
        for field, value in (("status", "已完成"), ("mouse_codes", "M001"), ("source_room", "东四"),
                             ("handler", "管理员"), ("created_by_username", "guest-b")):
            with self.subTest(field=field):
                self.assertEqual(self.edit(**{field: value}).status_code, 422)
                self.assertEqual(self.client.put(self.url, json={field: value}).status_code, 403)

    def test_guest_cannot_spoof_submitter_when_creating_request(self):
        response = self.client.post("/api/transfer-requests", json={
            **self.fields, "created_by_username": "guest-b",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["created_by_username"], "guest-a")

    def test_empty_required_fields_and_invalid_quantity_do_not_change_application(self):
        for fields, expected in (({"demander": " "}, 400), ({"strain": " "}, 400),
                                 ({"target_room": " "}, 400), ({"requested_mouse_count": 0}, 422)):
            with self.subTest(fields=fields):
                self.assertEqual(self.edit(**fields).status_code, expected)
        self.assertEqual(self.client.get("/api/transfer-requests").json()[0]["demander"], "需求者")

    def test_admin_can_edit_guest_application_and_delete_processed_request(self):
        self.current_user = self.admin
        response = self.edit(requested_mouse_count=9)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["created_by_username"], "guest-a")
        with Session(self.engine) as db:
            db.get(TransferRequest, self.request_id).status = "取消"
            db.commit()
        self.assertEqual(self.client.delete(self.url).status_code, 200)

    def test_stale_guest_form_cannot_change_or_delete_assigned_mice(self):
        with Session(self.engine) as db:
            cage = Cage(room="鼠房甲", cage_code="A1")
            db.add(cage)
            db.flush()
            db.add(Mouse(mouse_code="M001", status="在笼", cage_id=cage.id))
            db.commit()
        self.current_user = self.admin
        response = self.client.put(self.url, json={"status": "进行中", "mouse_codes": "M001"})
        self.assertEqual(response.status_code, 200, response.text)
        self.current_user = self.guest
        self.assertEqual(self.edit().status_code, 409)
        self.assertEqual(self.client.delete(self.url).status_code, 409)
        with Session(self.engine) as db:
            mouse = db.query(Mouse).filter_by(mouse_code="M001").one()
            self.assertEqual(mouse.owner_name, "需求者")
            self.assertIsNotNone(mouse.cage_id)

    def test_authentication_required_and_missing_request_returns_404(self):
        self.current_user = None
        self.assertEqual(self.edit().status_code, 401)
        self.assertEqual(self.client.delete(self.url).status_code, 401)
        self.current_user = self.guest
        self.url = "/api/transfer-requests/9999"
        self.assertEqual(self.edit().status_code, 404)
        self.assertEqual(self.client.delete(self.url).status_code, 404)


class LegacyRequestCreatorTests(unittest.TestCase):
    def test_backfill_only_unambiguous_pending_submitters(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                db.add_all([
                    User(username="guest-a", display_name="访客甲", hashed_password="hash", role="guest"),
                    User(username="guest-b", display_name="重名访客", hashed_password="hash", role="guest"),
                    User(username="guest-c", display_name="重名访客", hashed_password="hash", role="guest"),
                ])
                requests = [TransferRequest(
                    request_date="2026-10-14", demander="访客甲", strain="测试", status=status,
                    handler=handler, created_by_username=creator,
                ) for handler, status, creator in (
                    ("访客甲", "申请中", None),
                    ("guest-a", "申请中", None),
                    ("重名访客", "申请中", None),
                    (None, "申请中", None),
                    ("访客甲", "进行中", None),
                    ("访客甲", "申请中", "guest-b"),
                )]
                db.add_all(requests)
                db.commit()
                backfill_request_creators(db, db)
                db.commit()
                backfill_request_creators(db, db)
                self.assertEqual([req.created_by_username for req in requests], [
                    "guest-a", "guest-a", None, None, None, "guest-b",
                ])
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
