import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Mouse, User
from backend.app.routers.cages import update_cage
from backend.app.schemas.schemas import CageUpdate


class CageMergeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="test-admin", display_name="Test Admin")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_empty_target_receives_mice_and_source_cage_remains_empty(self):
        source = Cage(room="测试鼠房", cage_code="G5", strain="来源品系")
        empty_target = Cage(room="测试鼠房", cage_code="F5", strain="空笼品系")
        self.db.add_all([source, empty_target])
        self.db.flush()
        self.db.add(Mouse(mouse_code="M1", cage_id=source.id, status="在笼"))
        self.db.commit()

        result = update_cage(source.id, CageUpdate(cage_code="F5"), self.db, self.admin)

        self.assertEqual(self.db.query(Cage).count(), 2)
        self.assertEqual(result.id, empty_target.id)
        self.assertEqual(self.db.query(Mouse).filter_by(mouse_code="M1").one().cage_id, empty_target.id)
        self.assertEqual(self.db.query(Mouse).filter_by(cage_id=source.id).count(), 0)
        self.assertEqual(self.db.get(Cage, source.id).cage_code, "G5")

    def test_occupied_target_requires_confirmation_then_merges(self):
        source = Cage(room="测试鼠房", cage_code="G5", strain="来源品系")
        target = Cage(room="测试鼠房", cage_code="F5", strain="目标品系")
        self.db.add_all([source, target])
        self.db.flush()
        self.db.add_all([
            Mouse(mouse_code="M1", cage_id=source.id, status="在笼"),
            Mouse(mouse_code="M2", cage_id=target.id, status="在笼"),
        ])
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            update_cage(source.id, CageUpdate(cage_code="F5", strain="合并品系"), self.db, self.admin)
        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("确认合并", context.exception.detail)
        self.assertIn("将保留为空笼", context.exception.detail)
        self.assertEqual(self.db.query(Cage).count(), 2)

        result = update_cage(
            source.id,
            CageUpdate(cage_code="F5", strain="合并品系", merge_existing=True),
            self.db,
            self.admin,
        )

        self.assertEqual(result.id, target.id)
        self.assertEqual(self.db.query(Cage).count(), 2)
        self.assertEqual(self.db.get(Cage, target.id).strain, "合并品系")
        self.assertEqual(
            {mouse.cage_id for mouse in self.db.query(Mouse).all()},
            {target.id},
        )
        self.assertEqual(self.db.query(Mouse).filter_by(cage_id=source.id).count(), 0)
        self.assertEqual(self.db.get(Cage, source.id).cage_code, "G5")


if __name__ == "__main__":
    unittest.main()
