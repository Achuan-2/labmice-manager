import unittest
from unittest.mock import patch

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import GenotypeRecord, Mouse, Strain, User
from backend.app.routers.genotypes import list_genotypes
from backend.app.services.importer import import_single_excel_file, import_workbook
from backend.app.services.strain_service import backfill_known_pedigree_strains, infer_strain_from_genotypes, sync_and_normalize_all_strains


class GenotypeStrainTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def import_rows(self, *rows):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "基因鉴定结果"
        sheet.append(["测试日期", "小鼠编号", "品系", "DOB", "性别", "父母", "Genotype 1", "Genotype 2", "Genotype 3"])
        for row in rows:
            sheet.append(row)
        results = {key: 0 for key in [
            "mice_imported", "cages_imported", "claimers_imported", "transfers_imported",
            "transfer_requests_imported", "genotypes_imported", "inferred_genders_count", "primers_imported",
        ]}
        results["errors"] = []
        import_workbook(self.db, workbook, results, {}, "test.xlsx")
        self.assertEqual(results["errors"], [])

    def test_explicit_strain_is_not_validated_as_an_ear_tag(self):
        self.import_rows(
            ["2026-08-18", "F335", "Camk2/Ai93-Ras-N", "2026-07-05", "F", None, "Camk2a-阳性", "Ai93-杂合子", "RasN-杂合子"],
            ["2026-08-19", "F340", "自定义品系", None, "M", None, "WT", None, None],
        )
        for code, strain in [("F335", "Camk2/Ai93-Ras-N"), ("F340", "自定义品系")]:
            self.assertEqual(self.db.query(Mouse).filter_by(mouse_code=code).one().strain, strain)
            self.assertEqual(self.db.query(GenotypeRecord).filter_by(mouse_code=code).one().strain, strain)

    def test_same_date_inherits_merged_strain_but_new_date_resets_it(self):
        self.import_rows(
            ["2026-08-18", "F335", "Camk2/Ai93-Ras-N", "2026-07-05", "F", None, "WT", None, None],
            ["2026-08-18", "F336", None, None, "F", None, "HET", None, None],
            ["2026-08-19", "F337", None, None, "F", None, "HET", None, None],
        )
        same_date = self.db.query(GenotypeRecord).filter_by(mouse_code="F336").one()
        self.assertEqual((same_date.strain, same_date.dob), ("Camk2/Ai93-Ras-N", "2026-07-05"))
        new_date = self.db.query(GenotypeRecord).filter_by(mouse_code="F337").one()
        self.assertEqual(new_date.strain, "")
        self.assertIsNone(new_date.dob)

    def test_missing_strain_uses_only_the_three_named_markers(self):
        self.import_rows(
            ["2026-08-18", "F335", None, None, "F", None, "Camk2a-阳性", "Ai93-杂合子", "RasN-杂合子"],
            ["2026-08-18", "F336", None, None, "F", None, "阳性", "纯合子", "野生型"],
        )
        self.assertEqual(self.db.query(Mouse).filter_by(mouse_code="F335").one().strain, "Camk2/Ai93-Ras-N")
        self.assertEqual(self.db.query(Mouse).filter_by(mouse_code="F336").one().strain, "")

    def test_marker_recognition_does_not_require_positive_outcomes(self):
        self.assertEqual(infer_strain_from_genotypes("Camk2a-阴性", "Ai93-纯合子", "RasN-野生型"), "Camk2/Ai93-Ras-N")
        self.assertEqual(infer_strain_from_genotypes("camk2a-tTA: HET", "ai93: HOM", "Ras-N: WT"), "Camk2/Ai93-Ras-N")
        self.assertEqual(infer_strain_from_genotypes("Camk2a-阳性", "Ai93-纯合子", "Other-野生型"), "")
        self.assertEqual(infer_strain_from_genotypes("Camk2a-阳性", "Ai93-纯合子", None), "")

    def test_normalization_repairs_legacy_data_and_list_response(self):
        mouse = Mouse(mouse_code="F335", strain="")
        record = GenotypeRecord(
            mouse=mouse, mouse_code="F335", strain="", test_date="2026-08-18",
            genotype_1="Camk2a-阳性", genotype_2="Ai93-杂合子", genotype_3="RasN-杂合子",
        )
        self.db.add(record)
        self.db.commit()
        result = sync_and_normalize_all_strains(self.db)
        self.assertEqual(result["repaired_count"], 2)
        self.assertEqual((record.strain, mouse.strain), ("Camk2/Ai93-Ras-N", "Camk2/Ai93-Ras-N"))
        self.assertIsNotNone(self.db.query(Strain).filter_by(name="Camk2/Ai93-Ras-N").first())
        response = list_genotypes(page=1, page_size=50, limit=200, db=self.db, current_user=User())
        self.assertEqual(response["items"][0]["strain"], "Camk2/Ai93-Ras-N")
        self.assertEqual(response["items"][0]["genotype_3"], "RasN-杂合子")
        self.assertEqual(sync_and_normalize_all_strains(self.db)["repaired_count"], 0)

    def test_backfill_preserves_explicit_strains_and_handles_unlinked_record(self):
        mouse = Mouse(mouse_code="F335", strain="自定义品系")
        record = GenotypeRecord(
            mouse_code="F335", strain="", genotype_1="Camk2a-阳性",
            genotype_2="Ai93-杂合子", genotype_3="RasN-杂合子",
        )
        explicit = GenotypeRecord(
            mouse_code="F336", strain="已有品系", genotype_1="Camk2a-阳性",
            genotype_2="Ai93-杂合子", genotype_3="RasN-杂合子",
        )
        ambiguous = GenotypeRecord(mouse_code="F337", strain="", genotype_1="阳性", genotype_2="纯合子", genotype_3="野生型")
        self.db.add_all([mouse, record, explicit, ambiguous])
        self.db.commit()
        sync_and_normalize_all_strains(self.db)
        self.assertEqual((mouse.strain, record.strain), ("自定义品系", "自定义品系"))
        self.assertEqual(explicit.strain, "已有品系")
        self.assertEqual(ambiguous.strain, "")

    def test_th_cre_name_is_imported_without_named_genotype_results(self):
        self.import_rows(
            ["2026-03-01", "F066", "TH-Cre", "2026-02-09", "M", "E640M+E458F、E786F", "阴性", None, None],
        )
        mouse = self.db.query(Mouse).filter_by(mouse_code="F066").one()
        record = self.db.query(GenotypeRecord).filter_by(mouse_code="F066").one()
        self.assertEqual((mouse.strain, record.strain), ("TH-cre", "TH-cre"))
        self.assertEqual(record.genotype_1, "阴性")

    def test_confirmed_family_follows_exact_pedigrees_and_stops_at_crosses(self):
        definitions = [
            ("C663", "", "C288M+C283F"),
            ("C786", "", "C663M+C664F"),
            ("E458", "", "C786M+C787F"),
            ("F066", "", "E640M+E458F、E786F"),
            ("C288", "", None),
            ("C664", "", None),
            ("OTHER1", "", "C6630M+C664F"),
            ("OTHER2", "", "C663_2M+C664F"),
            ("CROSS1", "TH-cre/Ai148", "C663M+C664F"),
            ("CROSS2", "", "CROSS1M+C664F"),
        ]
        for code, strain, parents in definitions:
            mouse = Mouse(mouse_code=code, strain=strain, parents=parents)
            self.db.add(GenotypeRecord(mouse=mouse, mouse_code=code, strain=strain, parents=parents, genotype_1="阴性"))
        self.db.add(GenotypeRecord(mouse_code="ARCHIVE1", strain="", parents="c663f，C664M", genotype_1="阳性"))
        self.db.commit()

        result = sync_and_normalize_all_strains(self.db)
        self.assertEqual(result["repaired_count"], 9)
        for code in ["C663", "C786", "E458", "F066"]:
            self.assertEqual(self.db.query(Mouse).filter_by(mouse_code=code).one().strain, "TH-cre")
            record = self.db.query(GenotypeRecord).filter_by(mouse_code=code).one()
            self.assertEqual((record.strain, record.genotype_1), ("TH-cre", "阴性"))
        for code in ["C288", "C664", "OTHER1", "OTHER2", "CROSS2"]:
            self.assertEqual(self.db.query(Mouse).filter_by(mouse_code=code).one().strain, "")
        self.assertEqual(self.db.query(Mouse).filter_by(mouse_code="CROSS1").one().strain, "TH-cre/Ai148")
        self.assertEqual(self.db.query(GenotypeRecord).filter_by(mouse_code="ARCHIVE1").one().strain, "TH-cre")
        self.assertIsNone(self.db.query(Mouse).filter_by(mouse_code="ARCHIVE1").first())
        self.assertEqual(backfill_known_pedigree_strains(self.db), 0)

    def test_uploaded_workbook_repairs_family_without_creating_missing_founder(self):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "基因鉴定结果"
        sheet.append(["测试日期", "小鼠编号", "品系", "父母", "Genotype 1"])
        sheet.append(["2026-03-01", "C786", None, "C663M+C664F", "阴性"])
        with patch("backend.app.services.importer.openpyxl.load_workbook", return_value=workbook):
            result = import_single_excel_file(self.db, "test.xlsx")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["strains_repaired"], 2)
        self.assertEqual(self.db.query(Mouse).filter_by(mouse_code="C786").one().strain, "TH-cre")
        self.assertIsNone(self.db.query(Mouse).filter_by(mouse_code="C663").first())


if __name__ == "__main__":
    unittest.main()
