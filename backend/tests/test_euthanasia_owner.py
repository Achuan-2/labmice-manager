import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Claimer, Mouse, User
from backend.app.routers.claimers import delete_claimer, list_claimers
from backend.app.routers.mice import batch_set_owner, create_mouse, update_mouse
from backend.app.schemas.schemas import MouseBatchSetOwner, MouseCreate, MouseUpdate
from backend.app.services.mouse_status_service import sync_mouse_statuses
from backend.app.services.owner_service import EUTHANASIA_OWNER_NAME, sync_euthanasia_owner


class EuthanasiaOwnerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="admin", role="admin", display_name="管理员")
        self.cage = Cage(room="测试鼠房", cage_code="A1")
        self.mice = [Mouse(mouse_code=f"EUTH-{index}", cage=self.cage, status="在笼") for index in range(1, 3)]
        self.db.add_all([self.cage, *self.mice])
        sync_mouse_statuses(self.db)
        self.owner = sync_euthanasia_owner(self.db)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def assert_euthanized(self, mouse):
        self.db.refresh(mouse)
        self.assertEqual(mouse.owner_name, EUTHANASIA_OWNER_NAME)
        self.assertEqual(mouse.owner_id, self.owner.id)
        self.assertEqual(mouse.status, "死亡")
        self.assertIsNone(mouse.cage_id)

    def test_default_owner_is_seeded_and_cannot_be_deleted(self):
        self.db.add_all([Claimer(name="阿甲"), Claimer(name="赵乙")])
        self.db.commit()
        self.assertEqual(self.db.query(Claimer).filter_by(name=EUTHANASIA_OWNER_NAME).count(), 1)
        self.assertEqual(list_claimers(self.db, self.admin)[-1]["name"], EUTHANASIA_OWNER_NAME)
        with self.assertRaises(HTTPException):
            delete_claimer(self.owner.id, self.db, self.admin)

    def test_batch_and_single_assignment_force_death_and_clear_cage(self):
        batch_set_owner(MouseBatchSetOwner(
            mouse_ids=[self.mice[0].id],
            owner_name=EUTHANASIA_OWNER_NAME,
            status="在笼",
        ), self.db, self.admin)
        self.assert_euthanized(self.mice[0])

        update_mouse(self.mice[1].id, MouseUpdate(
            owner_name=EUTHANASIA_OWNER_NAME,
            status="已领用",
        ), self.db, self.admin)
        self.assert_euthanized(self.mice[1])

    def test_new_mouse_with_euthanasia_owner_is_never_left_in_cage(self):
        result = create_mouse(MouseCreate(
            mouse_code="EUTH-NEW",
            cage_id=self.cage.id,
            owner_id=self.owner.id,
            status="在笼",
        ), self.db, self.admin)
        mouse = self.db.get(Mouse, result["id"])
        self.assert_euthanized(mouse)


if __name__ == "__main__":
    unittest.main()
