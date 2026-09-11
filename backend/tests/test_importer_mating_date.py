import unittest

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Mouse
from backend.app.services.importer import extract_mating_date, import_workbook, merge_cage_observation, parse_date


class ImporterMatingDateTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_compact_dates_are_normalized_and_validated(self):
        self.assertEqual(parse_date("260305"), "2026-03-05")
        self.assertEqual(parse_date(251205), "2025-12-05")
        self.assertEqual(extract_mating_date("合笼时间：260211"), "2026-02-11")
        self.assertIsNone(extract_mating_date("合笼日期：260230"))
        self.assertEqual(merge_cage_observation("状态正常", "合笼日期：260305"), "状态正常\n合笼日期：260305")

    def test_405b_import_reads_mating_date_from_notes_and_preserves_text(self):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "实验动物楼小鼠信息405B-实时更新"
        sheet.append(["笼位", "品系", "数量", "性别", "编号", None, None, None, None, None, None, None, None, "出生日期", "观察记录", "备注"])
        sheet.append(["DATE-1", "5xFAD", 1, "M/F", "DATE-MOUSE", None, None, None, None, None, None, None, None, "2026-01-01", "状态正常", "合笼日期：260305"])
        results = {key: 0 for key in ["mice_imported", "cages_imported", "claimers_imported", "transfers_imported", "transfer_requests_imported", "genotypes_imported", "inferred_genders_count", "primers_imported"]}
        results["errors"] = []

        import_workbook(self.db, workbook, results, {}, "test.xlsx")
        cage = self.db.query(Cage).filter(Cage.cage_code == "DATE-1").one()
        mouse = self.db.query(Mouse).filter(Mouse.mouse_code == "DATE-MOUSE").one()
        self.assertEqual(cage.mating_date, "2026-03-05")
        self.assertEqual(cage.observation, "状态正常\n合笼日期：260305")
        self.assertEqual(cage.notes, "合笼日期：260305")
        self.assertEqual(mouse.status, "繁育中")


if __name__ == "__main__":
    unittest.main()
