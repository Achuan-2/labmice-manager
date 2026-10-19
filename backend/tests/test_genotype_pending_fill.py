import datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_admin, require_auth
from backend.app.database import Base, get_db
from backend.app.models.models import GenotypeRecord, Mouse, User
from backend.app.routers.genotypes import router


class GenotypePendingFillTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([Mouse(mouse_code=f"H{i}", strain="5xFAD", gender="F") for i in range(489, 493)])
            db.commit()
        self.app = FastAPI()
        self.app.include_router(router)

        def test_db():
            with Session(self.engine, autoflush=False) as db:
                yield db

        self.app.dependency_overrides[get_db] = test_db
        self.admin = User(username="test", display_name="测试管理员", role="admin")
        self.app.dependency_overrides[require_auth] = lambda: self.admin
        self.app.dependency_overrides[require_admin] = lambda: self.admin
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def register(self):
        response = self.client.post("/api/genotypes/batch", json=[
            {"mouse_code": f"H{i}", "notes": f"备注{i}"} for i in range(489, 493)
        ])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def fill(self, ids, value, field="genotype_1"):
        return self.client.put("/api/genotypes/batch-fill", json={"record_ids": ids, "field": field, "value": value})

    def listing(self, **params):
        response = self.client.get("/api/genotypes", params={"page": 1, **params})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def check_entries(self, *codes):
        response = self.client.post("/api/genotypes/entry-check", json={"mouse_codes": list(codes)})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_entry_check_shows_h515_results_even_with_newer_pending_history(self):
        self.client.post("/api/genotypes", json={
            "mouse_code": "H515", "test_date": "2026-09-01", "genotype_1": "HET", "genotype_2": "WT",
        })
        self.client.post("/api/genotypes", json={"mouse_code": "H515", "test_date": "2099-01-01"})
        entry, = self.check_entries(" H515 ")
        self.assertEqual(entry["mouse_code"], "H515")
        self.assertEqual(entry["tested_records"], [{
            "test_date": "2026-09-01", "genotype_1": "HET", "genotype_2": "WT", "genotype_3": None,
        }])
        self.assertEqual(entry["pending_count"], 1)
        with Session(self.engine) as db:
            self.assertEqual(db.query(GenotypeRecord).count(), 2)
            self.assertIsNone(db.query(Mouse).filter_by(mouse_code="H515").first())

    def test_entry_check_includes_archive_only_results_and_basic_fields(self):
        with Session(self.engine) as db:
            mouse = db.query(Mouse).filter_by(mouse_code="H489").one()
            mouse.genotype_1, mouse.test_date = "WT", "2026-09-01"
            mouse.dob, mouse.parents = "2026-07-01", "P1M+P2F"
            db.commit()
        entry, = self.check_entries("H489")
        self.assertEqual((entry["strain"], entry["gender"], entry["dob"], entry["parents"]),
                         ("5xFAD", "F", "2026-07-01", "P1M+P2F"))
        self.assertEqual(entry["tested_records"][0]["genotype_1"], "WT")
        self.assertEqual(entry["pending_count"], 0)
        with Session(self.engine) as db:
            self.assertEqual(db.query(GenotypeRecord).count(), 0)

    def test_entry_check_uses_exact_codes_and_finds_history_without_archive(self):
        with Session(self.engine) as db:
            db.add(Mouse(mouse_code="H5150", genotype_1="WT"))
            db.add(GenotypeRecord(mouse_code="H515", genotype_3="阳性", strain="History strain"))
            db.commit()
        entries = self.check_entries("H51", "H515", "H5150", "New1", "H515")
        self.assertEqual([entry["mouse_code"] for entry in entries], ["H51", "H515", "H5150", "New1"])
        self.assertEqual(entries[0]["tested_records"], [])
        self.assertEqual(entries[1]["tested_records"][0]["genotype_3"], "阳性")
        self.assertEqual(entries[1]["strain"], "History strain")
        self.assertEqual(entries[2]["tested_records"][0]["genotype_1"], "WT")
        self.assertEqual(entries[3]["tested_records"], [])

    def test_entry_check_keeps_pending_markers_separate_from_tested_results(self):
        records = self.register()
        self.fill([records[0]["id"]], "待测")
        self.fill([records[1]["id"]], "/")
        self.fill([records[2]["id"]], "阳性", "genotype_3")
        entries = self.check_entries("H489", "H490", "H491", "H492")
        self.assertEqual([entry["pending_count"] for entry in entries], [1, 1, 0, 1])
        self.assertEqual([len(entry["tested_records"]) for entry in entries], [0, 0, 1, 0])

    def test_entry_check_validates_batch_and_requires_authentication(self):
        entries = self.check_entries(*(f"New{i}" for i in range(500)))
        self.assertEqual(len(entries), 500)
        for codes in ([], [" "], [f"New{i}" for i in range(501)]):
            response = self.client.post("/api/genotypes/entry-check", json={"mouse_codes": codes})
            self.assertEqual(response.status_code, 422)
        del self.app.dependency_overrides[require_auth]
        self.assertEqual(self.client.post("/api/genotypes/entry-check", json={"mouse_codes": ["H515"]}).status_code, 401)

    def test_register_fill_one_then_fill_down_updates_existing_records_and_archives(self):
        records = self.register()
        self.assertTrue(all(r["test_date"] is None and r["genotype_1"] is None for r in records))
        self.assertEqual(self.listing(test_status="pending")["total"], 4)
        self.assertEqual(self.fill([records[0]["id"]], "杂合子").json()["updated"], 1)
        ids = [r["id"] for r in records[1:3]]
        response = self.fill(ids, "杂合子")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["updated"], 2)
        self.assertEqual({r["id"] for r in response.json()["items"]}, set(ids))
        self.assertTrue(all(r["genotype_1"] == "杂合子" for r in response.json()["items"]))
        self.assertEqual(self.listing(test_status="pending")["total"], 1)
        tested = self.listing(test_status="tested", page_size=2)
        self.assertEqual((tested["total"], len(tested["items"])), (3, 2))
        self.assertEqual(self.listing(test_status="tested", genotype_1_values="野生型")["total"], 0)
        with Session(self.engine) as db:
            self.assertEqual(db.query(GenotypeRecord).count(), 4)
            for i in range(489, 492):
                mouse = db.query(Mouse).filter_by(mouse_code=f"H{i}").one()
                record = db.query(GenotypeRecord).filter_by(mouse_code=mouse.mouse_code).one()
                self.assertEqual((mouse.genotype_1, record.genotype_1), ("杂合子", "杂合子"))
                self.assertEqual(record.test_date, datetime.date.today().isoformat())
                self.assertEqual((record.notes, record.strain, record.gender), (f"备注{i}", "5xFAD", "F"))
            self.assertIsNone(db.query(Mouse).filter_by(mouse_code="H492").one().genotype_1)

    def test_each_column_fills_independently_and_can_be_cleared(self):
        ids = [r["id"] for r in self.register()]
        for field, value in (("genotype_1", "WT"), ("genotype_2", "Ai93-杂合子"), ("genotype_3", "RasN-阳性")):
            response = self.fill(ids, value, field)
            self.assertEqual(response.status_code, 200, response.text)
        rows = self.listing()["items"]
        self.assertTrue(all((r["genotype_1"], r["genotype_2"], r["genotype_3"]) == ("WT", "Ai93-杂合子", "RasN-阳性") for r in rows))
        self.fill(ids, "", "genotype_2")
        self.assertTrue(all(r["genotype_1"] == "WT" and r["genotype_2"] is None and r["genotype_3"] == "RasN-阳性" for r in self.listing()["items"]))

    def test_missing_record_rejects_entire_fill_and_invalid_fields_are_rejected(self):
        record = self.register()[0]
        response = self.fill([record["id"], 999999], "HET")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.listing(test_status="pending")["total"], 4)
        self.assertEqual(self.fill([record["id"]], "new notes", "notes").status_code, 422)
        self.assertEqual(self.fill([], "HET").status_code, 422)
        self.assertEqual(self.fill([record["id"]], "X" * 65).status_code, 422)

    def test_pending_markers_and_third_column_result_have_consistent_status(self):
        records = self.register()
        self.fill([records[0]["id"]], "待测")
        self.fill([records[1]["id"]], "  ")
        self.fill([records[2]["id"]], "阳性", "genotype_3")
        self.assertEqual(self.listing(test_status="pending")["total"], 3)
        self.assertEqual(self.listing(test_status="tested")["total"], 1)

    def test_pending_registration_edit_and_delete_preserve_existing_archive_result(self):
        with Session(self.engine) as db:
            mouse = db.query(Mouse).filter_by(mouse_code="H489").one()
            mouse.genotype_1, mouse.test_date = "WT", "2026-09-01"
            db.commit()
        record = self.register()[0]
        self.client.put(f'/api/genotypes/{record["id"]}', json={"notes": "待检验备注"})
        self.fill([record["id"]], "待测")
        self.client.delete(f'/api/genotypes/{record["id"]}')
        with Session(self.engine) as db:
            mouse = db.query(Mouse).filter_by(mouse_code="H489").one()
            self.assertEqual((mouse.genotype_1, mouse.test_date), ("WT", "2026-09-01"))

    def test_newer_pending_record_does_not_hide_previous_test_result(self):
        records = self.register()
        self.fill([records[0]["id"]], "WT")
        self.client.post("/api/genotypes", json={"mouse_code": "H489", "test_date": "2099-01-01"})
        self.fill([records[0]["id"]], "HET")
        with Session(self.engine) as db:
            self.assertEqual(db.query(Mouse).filter_by(mouse_code="H489").one().genotype_1, "HET")

    def test_fill_requires_admin(self):
        record = self.register()[0]
        del self.app.dependency_overrides[require_admin]
        self.app.dependency_overrides[require_auth] = lambda: User(username="guest", role="guest")
        self.assertIn(self.fill([record["id"]], "WT").status_code, (401, 403))

    def test_added_order_is_default_and_date_order_is_optional_with_blanks_last(self):
        records = self.register()
        for record, date in zip(records, ("2026-10-18", "2026-09-01", None, "2026-10-01")):
            if date:
                response = self.client.put(f'/api/genotypes/{record["id"]}', json={"test_date": date})
                self.assertEqual(response.status_code, 200)
        def codes(**params):
            return [r["mouse_code"] for r in self.listing(**params)["items"]]

        self.assertEqual(codes(), ["H492", "H491", "H490", "H489"])
        self.assertEqual(codes(sort_by="added", sort_order="asc"), ["H489", "H490", "H491", "H492"])
        self.assertEqual(codes(sort_by="test_date"), ["H489", "H492", "H490", "H491"])
        self.assertEqual(codes(sort_by="test_date", sort_order="asc"), ["H490", "H492", "H489", "H491"])
        self.assertEqual(codes(page_size=2, page=2), ["H490", "H489"])
        self.fill([records[0]["id"]], "HET")
        self.assertEqual(codes(), ["H492", "H491", "H490", "H489"])
        self.assertEqual(self.listing(test_status="pending", sort_by="added")["total"], 3)
        self.assertEqual(self.client.get('/api/genotypes', params={"sort_by": "invalid"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
