import datetime
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.auth import require_admin
from backend.app.models.models import Cage, Claimer, GenotypeRecord, Mouse, TransferLog, User
from backend.app.routers.mice import batch_update_fields, router
from backend.app.schemas.schemas import MouseBatchUpdateFields
from backend.app.services.mouse_status_service import sync_mouse_statuses


class BatchUpdateMiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="test-admin", display_name="Test Admin")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_batch_update_strain_success(self):
        cage = Cage(room="测试鼠房", cage_code="C1", strain="旧品系")
        self.db.add(cage)
        self.db.flush()

        m1 = Mouse(mouse_code="M01", cage_id=cage.id, strain="旧品系", status="在笼")
        m2 = Mouse(mouse_code="M02", cage_id=cage.id, strain="旧品系", status="在笼")
        self.db.add_all([m1, m2])
        self.db.commit()

        result = batch_update_fields(
            MouseBatchUpdateFields(mouse_ids=[m1.id, m2.id], strain="新品系"),
            self.db,
            self.admin
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["affected_count"], 2)

        self.db.refresh(m1)
        self.db.refresh(m2)
        self.assertEqual(m1.strain, "新品系")
        self.assertEqual(m2.strain, "新品系")

    def test_batch_update_strain_with_canonical_normalization(self):
        cage = Cage(room="测试鼠房", cage_code="C2", strain="")
        self.db.add(cage)
        self.db.flush()

        m1 = Mouse(mouse_code="M03", cage_id=cage.id, strain="WildType", status="在笼")
        self.db.add(m1)
        self.db.commit()

        batch_update_fields(
            MouseBatchUpdateFields(mouse_ids=[m1.id], strain="5xfad"),
            self.db,
            self.admin
        )
        self.db.refresh(m1)
        self.assertEqual(m1.strain, "5xFAD")

    def test_batch_update_strain_and_gender_and_dob(self):
        cage = Cage(room="测试鼠房", cage_code="C3", strain="")
        self.db.add(cage)
        self.db.flush()

        m1 = Mouse(mouse_code="M04", cage_id=cage.id, strain="A", gender="未知", dob=None, status="在笼")
        m2 = Mouse(mouse_code="M05", cage_id=cage.id, strain="A", gender="未知", dob=None, status="在笼")
        self.db.add_all([m1, m2])
        self.db.commit()

        result = batch_update_fields(
            MouseBatchUpdateFields(
                mouse_ids=[m1.id, m2.id],
                strain="C57BL/6J",
                gender="F",
                dob="2026-03-01"
            ),
            self.db,
            self.admin
        )
        self.assertTrue(result["success"])
        self.db.refresh(m1)
        self.db.refresh(m2)
        self.assertEqual(m1.strain, "C57BL/6J")
        self.assertEqual(m1.gender, "F")
        self.assertEqual(m1.dob, "2026-03-01")
        self.assertEqual(m2.strain, "C57BL/6J")
        self.assertEqual(m2.gender, "F")
        self.assertEqual(m2.dob, "2026-03-01")

    def test_batch_update_clear_strain(self):
        cage = Cage(room="测试鼠房", cage_code="C4", strain="")
        self.db.add(cage)
        self.db.flush()

        m1 = Mouse(mouse_code="M06", cage_id=cage.id, strain="有品系", status="在笼")
        self.db.add(m1)
        self.db.commit()

        batch_update_fields(
            MouseBatchUpdateFields(mouse_ids=[m1.id], strain=""),
            self.db,
            self.admin
        )
        self.db.refresh(m1)
        self.assertEqual(m1.strain, "")

    def test_batch_update_validation_errors(self):
        with self.assertRaises(HTTPException) as ctx:
            batch_update_fields(MouseBatchUpdateFields(mouse_ids=[]), self.db, self.admin)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            batch_update_fields(MouseBatchUpdateFields(mouse_ids=[9999]), self.db, self.admin)
        self.assertEqual(ctx.exception.status_code, 400)  # No fields specified

        with self.assertRaises(HTTPException) as ctx:
            batch_update_fields(MouseBatchUpdateFields(mouse_ids=[9999], strain="Test"), self.db, self.admin)
        self.assertEqual(ctx.exception.status_code, 404)  # Mouse not found

    def create_mice(self):
        cage = Cage(room="测试鼠房", cage_code="C1")
        mice = [Mouse(mouse_code=f"M{i}", cage=cage, strain="旧品系", gender="F", status="在笼", notes="原备注") for i in range(3)]
        self.db.add_all(mice)
        sync_mouse_statuses(self.db)
        return mice

    def test_inline_fill_returns_normalized_values_age_and_preserves_unselected_mice(self):
        selected, second, untouched = self.create_mice()
        self.db.add_all([Mouse(mouse_code="P001", gender="M"), Mouse(mouse_code="P002", gender="F")])
        self.db.commit()
        result = batch_update_fields(MouseBatchUpdateFields(
            mouse_ids=[selected.id, second.id, selected.id], dob="2026-03-01", strain="5xfad",
            parents="P001+P002", claim_purpose="成像实验", notes="新备注",
        ), self.db, self.admin)
        self.assertEqual(result["affected_count"], 2)
        self.assertEqual({row["id"] for row in result["items"]}, {selected.id, second.id})
        for row in result["items"]:
            self.assertEqual((row["strain"], row["parents"], row["notes"], row["claim_purpose"]),
                             ("5xFAD", "P001M+P002F", "新备注", "成像实验"))
            self.assertEqual(row["age_days"], (datetime.date.today() - datetime.date(2026, 3, 1)).days)
            self.assertEqual(row["cage_id"], selected.cage_id)
        self.db.refresh(untouched)
        self.assertEqual((untouched.strain, untouched.notes, untouched.gender), ("旧品系", "原备注", "F"))
        self.assertIsNone(untouched.dob)

    def test_inline_fill_clears_optional_columns(self):
        selected, *_ = self.create_mice()
        selected.dob, selected.parents, selected.claim_purpose = "2026-03-01", "P001M", "实验"
        self.db.commit()
        result = batch_update_fields(MouseBatchUpdateFields(
            mouse_ids=[selected.id], dob=None, parents=None, claim_purpose=None, notes=None, strain=None,
        ), self.db, self.admin)
        row, = result["items"]
        self.assertTrue(all(not row[field] for field in ("dob", "parents", "claim_purpose", "notes", "strain")))
        self.assertIsNone(row["age_weeks"])

    def test_owner_fill_and_clear_preserve_cage_and_record_changes(self):
        selected, second, untouched = self.create_mice()
        for owner_name in ("领取人甲", None):
            result = batch_update_fields(MouseBatchUpdateFields(
                mouse_ids=[selected.id, second.id], owner_name=owner_name,
            ), self.db, self.admin)
            for row in result["items"]:
                self.assertEqual(row["owner_name"], owner_name)
                self.assertEqual(row["status"], "已领用" if owner_name else "在笼")
                self.assertEqual(row["cage_id"], untouched.cage_id)
                self.assertEqual(row["claim_date"], datetime.date.today().isoformat() if owner_name else None)
        self.assertEqual(self.db.query(Claimer).filter_by(name="领取人甲").count(), 1)
        self.assertEqual(self.db.query(TransferLog).filter_by(action_type="设置领取人").count(), 4)
        self.assertIsNone(untouched.owner_name)

    def test_status_fill_preserves_original_cage_in_audit_and_pending_history(self):
        selected, second, untouched = self.create_mice()
        result = batch_update_fields(MouseBatchUpdateFields(mouse_ids=[selected.id], status="待鉴定"), self.db, self.admin)
        self.assertEqual(result["items"][0]["status"], "待鉴定")
        self.assertEqual(len(result["items"][0]["genotypes"]), 1)
        batch_update_fields(MouseBatchUpdateFields(mouse_ids=[selected.id], status="待鉴定"), self.db, self.admin)
        self.assertEqual(self.db.query(GenotypeRecord).count(), 1)
        result = batch_update_fields(MouseBatchUpdateFields(mouse_ids=[second.id], status="死亡"), self.db, self.admin)
        row, = result["items"]
        self.assertEqual(row["status"], "死亡")
        self.assertIsNone(row["cage_id"])
        log = self.db.query(TransferLog).filter_by(mouse_codes=second.mouse_code).one()
        self.assertEqual((log.source_room, log.source_cage), ("测试鼠房", "C1"))
        self.assertEqual(untouched.status, "在笼")

    def test_euthanasia_owner_forces_death_and_clears_cage(self):
        selected, *_ = self.create_mice()
        result = batch_update_fields(MouseBatchUpdateFields(
            mouse_ids=[selected.id], owner_name="安乐死", status="在笼",
        ), self.db, self.admin)
        row, = result["items"]
        self.assertEqual((row["owner_name"], row["status"], row["cage_id"]), ("安乐死", "死亡", None))

    def test_invalid_and_missing_rows_leave_all_data_unchanged(self):
        selected, *_ = self.create_mice()
        for extra in ({"dob": "2026-02-30"}, {"dob": "20261019"}, {"gender": None}, {"status": ""}, {"status": "淘汰"}):
            with self.subTest(extra=extra), self.assertRaises(HTTPException):
                batch_update_fields(MouseBatchUpdateFields(mouse_ids=[selected.id], notes="不应写入", **extra), self.db, self.admin)
            self.db.refresh(selected)
            self.assertEqual(selected.notes, "原备注")
        with self.assertRaises(HTTPException):
            batch_update_fields(MouseBatchUpdateFields(mouse_ids=[selected.id, 999999], notes="不应写入", owner_name="不应创建"), self.db, self.admin)
        self.assertEqual(self.db.query(Claimer).count(), 0)
        self.db.refresh(selected)
        self.assertEqual(selected.notes, "原备注")

    def test_failed_second_row_rolls_back_entire_fill_and_audit(self):
        first, second, _ = self.create_mice()
        from backend.app.routers.mice import apply_mouse_status

        def fail_second(db, mouse, name):
            if mouse.id == second.id:
                raise ValueError("模拟失败")
            return apply_mouse_status(db, mouse, name)

        with patch('backend.app.routers.mice.apply_mouse_status', side_effect=fail_second):
            with self.assertRaises(HTTPException):
                batch_update_fields(MouseBatchUpdateFields(
                    mouse_ids=[first.id, second.id], status="实验中", owner_name="不应创建", notes="不应写入",
                ), self.db, self.admin)
        self.db.refresh(first)
        self.assertEqual((first.status, first.notes, first.owner_name), ("在笼", "原备注", None))
        self.assertEqual(self.db.query(TransferLog).count(), 0)
        self.assertEqual(self.db.query(Claimer).count(), 0)

    def test_inline_api_response_validation_and_admin_permission(self):
        mouse, *_ = self.create_mice()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[require_admin] = lambda: self.admin
        with TestClient(app) as client:
            response = client.post('/api/mice/batch-update-fields', json={
                'mouse_ids': [mouse.id], 'dob': '2026-08-01', 'parents': 'P001M+P002F', 'notes': '测试备注',
            })
            self.assertEqual(response.status_code, 200, response.text)
            row, = response.json()['items']
            self.assertEqual((row['dob'], row['parents'], row['notes']), ('2026-08-01', 'P001M+P002F', '测试备注'))
            invalid = client.post('/api/mice/batch-update-fields', json={'mouse_ids': [mouse.id], 'parents': 'X' * 129})
            self.assertEqual(invalid.status_code, 422)
            del app.dependency_overrides[require_admin]
            for field, value in (('dob', '2026-08-02'), ('parents', 'P003M'), ('owner_name', '领取人甲'), ('status', '死亡')):
                denied = client.post('/api/mice/batch-update-fields', json={'mouse_ids': [mouse.id], field: value})
                self.assertIn(denied.status_code, (401, 403))
            self.db.refresh(mouse)
            self.assertEqual((mouse.dob, mouse.status, mouse.owner_name), ('2026-08-01', '在笼', None))
