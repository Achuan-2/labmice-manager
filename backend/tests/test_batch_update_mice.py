import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Mouse, User
from backend.app.routers.mice import batch_update_fields
from backend.app.schemas.schemas import MouseBatchUpdateFields


class BatchUpdateMiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
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
