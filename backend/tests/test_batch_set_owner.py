import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Mouse, TransferLog, User
from backend.app.routers.mice import batch_set_owner, update_mouse
from backend.app.schemas.schemas import MouseBatchSetOwner, MouseUpdate
from backend.app.services.mouse_status_service import sync_mouse_statuses


class BatchSetOwnerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="admin", role="admin", display_name="管理员")
        self.source_cage = Cage(room="实验动物楼405B", cage_code="A1")
        self.mouse = Mouse(mouse_code="M01", cage=self.source_cage, status="在笼")
        self.db.add_all([self.source_cage, self.mouse])
        sync_mouse_statuses(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_room_without_cage_hands_mouse_to_recipient(self):
        batch_set_owner(MouseBatchSetOwner(
            mouse_ids=[self.mouse.id], owner_name="领取人甲", target_room="东五",
        ), self.db, self.admin)

        self.db.refresh(self.mouse)
        self.assertIsNone(self.mouse.cage_id)
        self.assertEqual(self.mouse.source_room, "东五")
        self.assertEqual(self.mouse.status, "出笼")
        self.assertEqual(self.mouse.owner_name, "领取人甲")
        log = self.db.query(TransferLog).one()
        self.assertEqual((log.source_room, log.source_cage), ("实验动物楼405B", "A1"))
        self.assertEqual((log.target_room, log.target_cage), ("东五", None))
        self.assertEqual(self.db.query(Cage).count(), 1)

    def test_no_target_room_preserves_current_cage(self):
        batch_set_owner(MouseBatchSetOwner(
            mouse_ids=[self.mouse.id], owner_name="领取人甲",
        ), self.db, self.admin)

        self.db.refresh(self.mouse)
        self.assertEqual(self.mouse.cage_id, self.source_cage.id)
        self.assertEqual(self.mouse.status, "已领用")

    def test_assigns_only_selected_mice_and_preserves_their_cage(self):
        second = Mouse(mouse_code="M02", cage=self.source_cage, status="在笼")
        unselected = Mouse(mouse_code="M03", cage=self.source_cage, status="在笼")
        self.db.add_all([second, unselected])
        self.db.commit()

        result = batch_set_owner(MouseBatchSetOwner(
            mouse_codes=[self.mouse.mouse_code, second.mouse_code],
            owner_name="领取人甲", claim_date="2026-10-08", claim_purpose="成像实验",
        ), self.db, self.admin)

        for mouse in [self.mouse, second]:
            self.db.refresh(mouse)
            self.assertEqual(mouse.owner_name, "领取人甲")
            self.assertEqual(mouse.owner.name, "领取人甲")
            self.assertEqual(mouse.cage_id, self.source_cage.id)
            self.assertEqual(mouse.status, "已领用")
            self.assertEqual(mouse.claim_date, "2026-10-08")
            self.assertEqual(mouse.claim_purpose, "成像实验")
        self.db.refresh(unselected)
        self.assertIsNone(unselected.owner_id)
        self.assertFalse(unselected.owner_name)
        self.assertEqual(unselected.status, "在笼")
        self.assertEqual(unselected.cage_id, self.source_cage.id)
        self.assertEqual(result["affected_count"], 2)
        self.assertCountEqual(result["affected_codes"], ["M01", "M02"])
        log = self.db.query(TransferLog).one()
        self.assertEqual(log.mouse_count, 2)
        self.assertEqual(log.claimer_name, "领取人甲")

    def test_target_cage_moves_mouse_to_managed_cage(self):
        batch_set_owner(MouseBatchSetOwner(
            mouse_ids=[self.mouse.id], owner_name="领取人甲",
            target_room="实验动物楼406B", target_cage_code=" B2 ",
        ), self.db, self.admin)

        self.db.refresh(self.mouse)
        self.assertEqual((self.mouse.cage.room, self.mouse.cage.cage_code), ("实验动物楼406B", "B2"))
        self.assertEqual(self.mouse.status, "已领用")
        self.assertEqual(self.db.query(TransferLog).one().target_cage, "B2")

    def test_archive_edit_moves_owned_mouse_to_room_without_cage(self):
        batch_set_owner(MouseBatchSetOwner(
            mouse_ids=[self.mouse.id], owner_name="领取人甲",
        ), self.db, self.admin)

        result = update_mouse(self.mouse.id, MouseUpdate(
            source_room="东五", cage_code=None, status="已领用",
        ), self.db, self.admin)

        self.assertEqual(result["source_room"], "东五")
        self.assertIsNone(result["cage_id"])
        self.assertEqual(result["status"], "出笼")
        self.assertEqual(self.db.query(Cage).count(), 1)


if __name__ == "__main__":
    unittest.main()
