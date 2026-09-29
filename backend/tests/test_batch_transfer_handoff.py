import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Mouse, TransferLog, User
from backend.app.routers.mice import batch_transfer
from backend.app.schemas.schemas import MouseBatchTransfer
from backend.app.services.mouse_status_service import sync_mouse_statuses


class BatchTransferHandoffTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="admin", role="admin", display_name="管理员")
        self.source_cage = Cage(room="东四105", cage_code="F4")
        self.owned_mice = [
            Mouse(mouse_code=code, cage=self.source_cage, owner_name="吴晨昀", status="已领用")
            for code in ("300", "297", "298")
        ]
        self.unowned_mouse = Mouse(mouse_code="299", cage=self.source_cage, status="在笼")
        self.db.add_all([self.source_cage, *self.owned_mice, self.unowned_mouse])
        sync_mouse_statuses(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_handoff_moves_all_owned_mice_out_without_creating_cage(self):
        result = batch_transfer(MouseBatchTransfer(
            mouse_ids=[mouse.id for mouse in self.owned_mice],
            target_room="东五", handoff_to_owner=True,
        ), self.db, self.admin)

        self.assertEqual(result["affected_count"], 3)
        for mouse in self.owned_mice:
            self.db.refresh(mouse)
            self.assertIsNone(mouse.cage_id)
            self.assertEqual((mouse.source_room, mouse.status, mouse.owner_name), ("东五", "出笼", "吴晨昀"))
        self.db.refresh(self.unowned_mouse)
        self.assertEqual(self.unowned_mouse.cage_id, self.source_cage.id)
        self.assertEqual(self.db.query(Cage).count(), 1)
        log = self.db.query(TransferLog).one()
        self.assertEqual((log.source_room, log.source_cage), ("东四105", "F4"))
        self.assertEqual((log.target_room, log.target_cage), ("东五", None))

    def test_handoff_rejects_unowned_mouse_before_any_change(self):
        with self.assertRaises(HTTPException) as error:
            batch_transfer(MouseBatchTransfer(
                mouse_ids=[self.owned_mice[0].id, self.unowned_mouse.id],
                target_room="东五", handoff_to_owner=True,
            ), self.db, self.admin)

        self.assertEqual(error.exception.status_code, 400)
        self.db.refresh(self.owned_mice[0])
        self.assertEqual(self.owned_mice[0].cage_id, self.source_cage.id)
        self.assertEqual(self.db.query(TransferLog).count(), 0)

    def test_regular_batch_move_still_uses_target_cage(self):
        batch_transfer(MouseBatchTransfer(
            mouse_ids=[self.owned_mice[0].id],
            target_room="实验动物楼405B", target_cage_code="B2",
        ), self.db, self.admin)

        self.db.refresh(self.owned_mice[0])
        self.assertEqual((self.owned_mice[0].cage.room, self.owned_mice[0].cage.cage_code),
                         ("实验动物楼405B", "B2"))
        self.assertEqual(self.owned_mice[0].status, "已领用")


if __name__ == "__main__":
    unittest.main()
