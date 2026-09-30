import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Mouse, TransferLog, User
from backend.app.routers.mice import batch_create_mice, create_mouse, get_mouse
from backend.app.routers.transfers import list_transfers
from backend.app.schemas.schemas import MouseBatchCreate, MouseCreate


class MouseCodeAutoRenameTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="test-admin", display_name="Test Admin")
        self.db.add_all([
            Mouse(mouse_code="X100", status="出笼"),
            Mouse(mouse_code="X100_2", status="出笼"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_single_create_uses_next_available_suffix(self):
        result = create_mouse(MouseCreate(
            mouse_code="X100", source_room="实验动物楼405B", cage_code="A1", owner_name="张三",
        ), self.db, self.admin)

        self.assertEqual(result["mouse_code"], "X100_3")
        self.assertEqual(result["renamed_from"], "X100")
        self.assertEqual(result["message"], "耳标编号 [X100] 已存在，已自动更名为 [X100_3]")
        log = self.db.query(TransferLog).one()
        self.assertEqual((log.action_type, log.mouse_codes, log.mouse_count), ("新增小鼠", "X100_3", 1))
        self.assertEqual((log.target_room, log.target_cage, log.claimer_name), ("实验动物楼405B", "A1", "张三"))
        self.assertEqual(get_mouse(result["id"], self.db, self.admin)["transfer_logs"][0]["action_type"], "新增小鼠")

    def test_batch_create_renames_duplicates_instead_of_skipping(self):
        result = batch_create_mice(
            MouseBatchCreate(mouse_codes=["X100", "X101"], source_room="东四105", cage_code="F4"),
            self.db, self.admin
        )

        self.assertEqual(result["created_codes"], ["X100_3", "X101"])
        self.assertEqual(result["skipped_codes"], [])
        self.assertEqual(result["renamed_codes"], [
            {"original_code": "X100", "new_code": "X100_3"}
        ])
        self.assertEqual(
            {mouse.mouse_code for mouse in self.db.query(Mouse).all()},
            {"X100", "X100_2", "X100_3", "X101"},
        )
        log = self.db.query(TransferLog).one()
        self.assertEqual((log.action_type, log.mouse_codes, log.mouse_count), ("新增小鼠", "X100_3, X101", 2))
        self.assertEqual((log.target_room, log.target_cage), ("东四105", "F4"))
        self.assertEqual(
            [item.mouse_codes for item in list_transfers(action_type="新增小鼠", limit=100, db=self.db, current_user=self.admin)],
            ["X100_3, X101"],
        )


if __name__ == "__main__":
    unittest.main()
