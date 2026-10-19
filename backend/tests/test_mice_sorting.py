import datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_admin, require_auth
from backend.app.database import Base, get_db
from backend.app.models.models import Cage, GenotypeRecord, Mouse, User
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

    def test_column_menu_date_range_is_inclusive_and_excludes_blank_dates(self):
        self.assertEqual(self.codes(dob_from="2026-05-01", dob_to="2026-06-01"), ["R020", "R100"])
        self.assertEqual(self.codes(dob_from="2026-06-01"), ["R020"])
        self.assertEqual(self.codes(dob_to="2026-05-01"), ["R100"])
        self.assertEqual(self.codes(dob_from="2026-06-02"), [])
        for params in ({"dob_from": "2026-02-30"}, {"dob_from": "2026-06-01", "dob_to": "2026-05-01"}):
            self.assertEqual(self.client.get("/api/mice", params=params).status_code, 422)

    def test_column_menus_combine_filters_before_paginating(self):
        with Session(self.engine) as db:
            mouse = db.query(Mouse).filter_by(mouse_code="R100").one()
            mouse.claim_purpose, mouse.notes, mouse.gender = "成像实验", "待复查", "F"
            db.commit()
        self.assertEqual(self.codes(claim_purpose="成像", notes="复查", gender="F", strain="B"), ["R100"])
        self.assertEqual(self.codes(claim_purpose="成像", notes="related"), [])
        self.assertEqual(self.codes(notes="related"), ["R003"])
        result = self.listing(strain="B", dob_from="2026-05-01", page_size=1, page=2, sort_by="dob", sort_order="desc")
        self.assertEqual(result["total"], 2)
        self.assertEqual([row["mouse_code"] for row in result["items"]], ["R100"])

    def test_column_menu_ownership_handles_legacy_names_and_unknown_gender(self):
        with Session(self.engine) as db:
            mouse = db.query(Mouse).filter_by(mouse_code="R100").one()
            mouse.owner_name, mouse.gender = "领取人甲", None
            db.query(Mouse).filter_by(mouse_code="R003").one().gender = ""
            db.query(Mouse).filter_by(mouse_code="R020").one().gender = "M"
            db.commit()
        self.assertEqual(self.codes(owner_name="领取人甲", has_owner=True), ["R100"])
        self.assertNotIn("R100", self.codes(has_owner=False))
        self.assertEqual(set(self.codes(gender="未知")), {"R100", "R003", "R004"})

    def test_genotype_menu_searches_history_and_matches_visible_pending_status(self):
        with Session(self.engine) as db:
            mice = {mouse.mouse_code: mouse for mouse in db.query(Mouse)}
            mice["R100"].genotype_1 = "HET"
            mice["R003"].genotype_1 = "待测"
            mice["R020"].status = "待鉴定"
            mice["R020"].genotype_1 = "WT"
            db.add_all([
                GenotypeRecord(mouse=mice["R004"], mouse_code="R004", genotype_3="第三基因阳性"),
                GenotypeRecord(mouse=mice["R020"], mouse_code="R020", genotype_1="WT"),
            ])
            db.commit()
        self.assertEqual(set(self.codes(test_status="tested")), {"R100", "R004"})
        self.assertEqual(set(self.codes(test_status="pending")), {"R003", "R020"})
        self.assertEqual(self.codes(genotype="第三基因", test_status="tested"), ["R004"])
        self.assertEqual(self.codes(genotype="HET"), ["R100"])

    def test_each_new_column_sorts_all_rows_and_keeps_blanks_last(self):
        with Session(self.engine) as db:
            mice = {mouse.mouse_code: mouse for mouse in db.query(Mouse)}
            first, second = mice["R100"], mice["R020"]
            for field in ("gender", "parents", "owner_name", "claim_purpose", "notes", "genotype_1"):
                for mouse in mice.values():
                    setattr(mouse, field, None)
                setattr(first, field, "A")
                setattr(second, field, "B")
            first.cage = Cage(room="测试鼠房", cage_code="A1")
            second.cage = Cage(room="测试鼠房", cage_code="B1")
            db.commit()
        for field in ("gender", "parents", "owner_name", "claim_purpose", "notes", "genotype_1", "cage_code"):
            with self.subTest(field=field):
                self.assertEqual(self.codes(sort_by=field, sort_order="asc"), ["R100", "R020", "R003", "R004"])
                self.assertEqual(self.codes(sort_by=field, sort_order="desc"), ["R020", "R100", "R004", "R003"])


if __name__ == "__main__":
    unittest.main()
