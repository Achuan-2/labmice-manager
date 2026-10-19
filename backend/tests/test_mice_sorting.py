import datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_admin, require_auth
from backend.app.database import Base, get_db
from backend.app.models.models import Mouse, User
from backend.app.routers.genotypes import router as genotype_router
from backend.app.routers.mice import router


class MouseSortingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                Mouse(mouse_code="R100", status="在笼", strain="B", dob="2026-05-01"),
                Mouse(mouse_code="R003", status="死亡", strain="A", dob=None, notes="R100 related"),
                Mouse(mouse_code="R020", status="出笼", strain="B", dob="2026-06-01"),
                Mouse(mouse_code="R004", status="实验中", strain=" ", dob=" "),
            ])
            db.commit()
        app = FastAPI()
        app.include_router(router)
        app.include_router(genotype_router)

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

    def listing(self, **params):
        response = self.client.get("/api/mice", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def codes(self, **params):
        return [mouse["mouse_code"] for mouse in self.listing(**params)["items"]]

    def test_default_is_reverse_entry_order_independent_of_status(self):
        self.assertEqual(self.codes(), ["R004", "R020", "R003", "R100"])
        self.assertEqual(self.codes(sort_order="asc"), ["R100", "R003", "R020", "R004"])

    def test_editing_existing_records_preserves_the_original_entry_order(self):
        with Session(self.engine) as db:
            old = db.query(Mouse).filter_by(mouse_code="R100").one()
            old.notes = "Edited today"
            old.status = "出笼"
            old.created_at = datetime.datetime(2099, 1, 1)
            db.commit()
        self.assertEqual(self.codes(), ["R004", "R020", "R003", "R100"])

    def test_new_mice_from_single_batch_and_genotype_entry_appear_first(self):
        response = self.client.post("/api/mice", json={"mouse_code": "New1"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.codes()[0], "New1")
        response = self.client.post("/api/mice/batch-create", json={"mouse_codes": ["New2", "New3"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.codes()[:3], ["New3", "New2", "New1"])
        response = self.client.post("/api/genotypes", json={"mouse_code": "New4"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.codes()[:4], ["New4", "New3", "New2", "New1"])
        self.assertEqual(self.codes(sort_order="asc")[-4:], ["New1", "New2", "New3", "New4"])

    def test_code_sorting_and_pagination_apply_to_the_entire_result(self):
        self.assertEqual(self.codes(sort_by="mouse_code", sort_order="asc"), ["R003", "R004", "R020", "R100"])
        first = self.listing(sort_by="mouse_code", sort_order="desc", page=1, page_size=2)
        second = self.listing(sort_by="mouse_code", sort_order="desc", page=2, page_size=2)
        self.assertEqual((first["total"], second["total"]), (4, 4))
        self.assertEqual([mouse["mouse_code"] for mouse in first["items"] + second["items"]],
                         ["R100", "R020", "R004", "R003"])

    def test_missing_birth_dates_stay_last_in_both_directions(self):
        self.assertEqual(self.codes(sort_by="dob", sort_order="asc"), ["R100", "R020", "R003", "R004"])
        self.assertEqual(self.codes(sort_by="dob", sort_order="desc"), ["R020", "R100", "R004", "R003"])

    def test_strain_sorting_has_stable_ties_and_blank_values_last(self):
        self.assertEqual(self.codes(sort_by="strain", sort_order="asc"), ["R003", "R100", "R020", "R004"])
        self.assertEqual(self.codes(sort_by="strain", sort_order="desc"), ["R020", "R100", "R003", "R004"])

    def test_status_sorting_supports_both_directions(self):
        ascending = self.codes(sort_by="status", sort_order="asc")
        self.assertEqual(self.codes(sort_by="status", sort_order="desc"), list(reversed(ascending)))
        statuses = [mouse["status"] for mouse in self.listing(sort_by="status", sort_order="asc")["items"]]
        self.assertEqual(statuses, sorted(statuses))

    def test_filters_and_search_relevance_are_preserved(self):
        self.assertEqual(self.codes(strain="B"), ["R020", "R100"])
        self.assertEqual(self.codes(strain="B", sort_order="asc"), ["R100", "R020"])
        self.assertEqual(self.codes(keyword="R100"), ["R100", "R003"])

    def test_unknown_sort_fields_and_directions_are_rejected(self):
        for params in ({"sort_by": "invalid"}, {"sort_order": "invalid"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/mice", params=params).status_code, 422)


if __name__ == "__main__":
    unittest.main()
