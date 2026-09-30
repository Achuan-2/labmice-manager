import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_auth
from backend.app.database import get_db
from backend.app.models.models import TransferLog, User
from backend.app.routers.transfers import router


class TransfersPaginationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        TransferLog.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                TransferLog(
                    mouse_codes=str(index),
                    claimer_name="领取人甲" if index % 2 else "领取人乙",
                    action_type="新增小鼠" if index % 3 else "状态变更",
                    status="已完成" if index % 5 else "待处理",
                )
                for index in range(1, 124)
            ])
            db.commit()

        app = FastAPI()
        app.include_router(router)

        def test_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[require_auth] = lambda: User(username="test", role="admin")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def test_default_page_has_50_latest_logs(self):
        response = self.client.get("/api/transfers")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual((result["total"], result["page"], result["page_size"]), (123, 1, 50))
        self.assertEqual([item["id"] for item in result["items"]], list(range(123, 73, -1)))

    def test_pages_cover_all_logs_without_overlap(self):
        pages = [self.client.get("/api/transfers", params={"page": page}).json()
                 for page in (1, 2, 3)]
        self.assertEqual([len(page["items"]) for page in pages], [50, 50, 23])
        ids = [item["id"] for page in pages for item in page["items"]]
        self.assertEqual(ids, list(range(123, 0, -1)))

    def test_filters_apply_before_count_and_pagination(self):
        result = self.client.get("/api/transfers", params={
            "claimer_name": "领取人甲",
            "action_type": "新增小鼠",
            "status": "已完成",
            "page": 2,
            "page_size": 7,
        }).json()
        expected = [index for index in range(123, 0, -1)
                    if index % 2 and index % 3 and index % 5]
        self.assertEqual(result["total"], len(expected))
        self.assertEqual(result["page_size"], 7)
        self.assertEqual([item["id"] for item in result["items"]], expected[7:14])

    def test_empty_results_and_out_of_range_page(self):
        for params, total in [({"claimer_name": "不存在"}, 0), ({"page": 4}, 123)]:
            with self.subTest(params=params):
                result = self.client.get("/api/transfers", params=params).json()
                self.assertEqual(result["total"], total)
                self.assertEqual(result["items"], [])

    def test_invalid_pagination_is_rejected(self):
        for params in [{"page": 0}, {"page_size": 0}, {"page_size": 501}]:
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/transfers", params=params).status_code, 422)


if __name__ == "__main__":
    unittest.main()
