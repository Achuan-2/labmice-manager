import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import require_auth
from backend.app.database import Base, get_db
from backend.app.models.models import GenotypeRecord, User
from backend.app.routers.genotypes import router


class GenotypeFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            for code, genotype_1, genotype_2, genotype_3 in (
                ("A1", "纯合子", "Ai93-杂合子", "RasN-杂合子"),
                ("A2", "杂合子", "Ai93-杂合子", "RasN-野生型"),
                ("A3", "野生型", "Ai93-野生型", "RasN-杂合子"),
                ("A4", None, None, None),
                ("A5", "", "", ""),
                ("A6", " 纯合子 ", "Ai93-野生型", "RasN-野生型"),
                ("A7", " ", " ", " "),
            ):
                db.add(GenotypeRecord(
                    mouse_code=code, strain="测试品系", test_date="2026-10-14",
                    genotype_1=genotype_1, genotype_2=genotype_2, genotype_3=genotype_3,
                ))
            db.commit()
        self.app = FastAPI()
        self.app.include_router(router)

        def test_db():
            with Session(self.engine) as db:
                yield db

        self.app.dependency_overrides[get_db] = test_db
        self.app.dependency_overrides[require_auth] = lambda: User(username="guest", role="guest")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def get_records(self, params=()):
        response = self.client.get("/api/genotypes", params=[("page", 1), ("page_size", 50), *params])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def codes(self, params):
        result = self.get_records(params)
        self.assertEqual(result["total"], len(result["items"]))
        return {item["mouse_code"] for item in result["items"]}

    def test_multiple_values_in_each_column_match_any_selected_value(self):
        for field, values, expected in (
            ("genotype_1_values", ["纯合子", "杂合子"], {"A1", "A2", "A6"}),
            ("genotype_2_values", ["Ai93-杂合子", "Ai93-野生型"], {"A1", "A2", "A3", "A6"}),
            ("genotype_3_values", ["RasN-杂合子", "RasN-野生型"], {"A1", "A2", "A3", "A6"}),
        ):
            with self.subTest(field=field):
                self.assertEqual(self.codes([(field, value) for value in values]), expected)

    def test_selections_across_columns_must_all_match(self):
        self.assertEqual(self.codes([
            ("genotype_1_values", "纯合子"), ("genotype_1_values", "杂合子"),
            ("genotype_2_values", "Ai93-杂合子"), ("genotype_3_values", "RasN-野生型"),
        ]), {"A2"})

    def test_empty_value_matches_null_empty_and_whitespace_records(self):
        for field in ("genotype_1_values", "genotype_2_values", "genotype_3_values"):
            with self.subTest(field=field):
                self.assertEqual(self.codes([(field, "")]), {"A4", "A5", "A7"})
        self.assertEqual(self.codes([
            ("genotype_1_values", ""), ("genotype_1_values", "野生型"),
        ]), {"A3", "A4", "A5", "A7"})

    def test_filters_apply_before_pagination_and_total(self):
        params = [("genotype_1_values", "纯合子"), ("page_size", 1)]
        first = self.get_records(params)
        second = self.get_records([*params, ("page", 2)])
        self.assertEqual((first["total"], second["total"]), (2, 2))
        self.assertEqual(len(first["items"]), 1)
        self.assertEqual(len(second["items"]), 1)
        self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])

    def test_options_cover_all_records_and_normalize_duplicates_and_blanks(self):
        self.get_records([("page_size", 1)])
        response = self.client.get("/api/genotypes/filter-options")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {
            "genotype_1": ["", "杂合子", "纯合子", "野生型"],
            "genotype_2": ["", "Ai93-杂合子", "Ai93-野生型"],
            "genotype_3": ["", "RasN-杂合子", "RasN-野生型"],
        })

    def test_keyword_and_existing_single_value_filter_remain_supported(self):
        self.assertEqual(self.codes([
            ("keyword", "A2"), ("genotype_1_values", "杂合子"),
        ]), {"A2"})
        self.assertEqual(self.codes([("genotype_1", "纯合子")]), {"A1"})
        self.assertEqual(self.codes([("keyword", "RasN-杂合子")]), {"A1", "A3"})
        unpaginated = self.client.get("/api/genotypes", params=[("genotype_3_values", "RasN-杂合子")])
        self.assertEqual(unpaginated.status_code, 200, unpaginated.text)
        self.assertEqual({item["mouse_code"] for item in unpaginated.json()}, {"A1", "A3"})

    def test_clearing_filters_restores_all_rows_and_unknown_value_returns_none(self):
        self.assertEqual(self.codes([("genotype_1_values", "不存在的结果")]), set())
        self.assertEqual(self.get_records()["total"], 7)

    def test_empty_database_has_empty_options(self):
        with Session(self.engine) as db:
            db.query(GenotypeRecord).delete()
            db.commit()
        self.assertEqual(self.client.get("/api/genotypes/filter-options").json(), {
            "genotype_1": [], "genotype_2": [], "genotype_3": [],
        })

    def test_filter_options_require_authentication(self):
        del self.app.dependency_overrides[require_auth]
        self.assertEqual(self.client.get("/api/genotypes/filter-options").status_code, 401)


if __name__ == "__main__":
    unittest.main()
