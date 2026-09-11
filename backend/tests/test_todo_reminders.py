import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Mouse, TodoReminder, User
from backend.app.routers.mice import batch_split_transfer, batch_update_fields
from backend.app.routers.todos import create_todo, delete_todo, list_todos, update_todo
from backend.app.schemas.schemas import MouseBatchSplitTransfer, MouseBatchUpdateFields, MouseSplitTransferGroup, TodoReminderCreate, TodoReminderUpdate


class TodoReminderTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="todo-admin", display_name="Todo Admin")
        today = datetime.date.today()
        self.cage = Cage(
            room="测试鼠房",
            cage_code="M1",
            gender="M/F",
            litter_birth_date=(today - datetime.timedelta(days=21)).isoformat(),
        )
        self.db.add(self.cage)
        self.db.flush()
        self.mouse = Mouse(
            mouse_code="OLD-1",
            cage_id=self.cage.id,
            gender="F",
            dob=(today - datetime.timedelta(days=281)).isoformat(),
            status="在笼",
        )
        self.db.add(self.mouse)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_automatic_reminders_are_due_linked_and_deduplicated(self):
        future_birth_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        self.cage.litter_birth_dates = [self.cage.litter_birth_date, future_birth_date]
        self.db.commit()
        first = list_todos("today", False, self.db, self.admin)
        self.assertEqual({todo["source"] for todo in first}, {"litter_weaning", "mixed_aged"})
        self.assertTrue(all("T" not in todo["due_at"] for todo in first))
        self.assertTrue(all(todo["cage"]["id"] == self.cage.id for todo in first))
        future = list_todos("future", False, self.db, self.admin)
        self.assertEqual(len(future), 1)
        self.assertNotIn("T", future[0]["due_at"])
        self.assertIn(future_birth_date, future[0]["auto_key"])

        second = list_todos("today", False, self.db, self.admin)
        self.assertEqual(len(second), 2)
        self.assertEqual(self.db.query(TodoReminder).count(), 3)

        update_todo(first[0]["id"], TodoReminderUpdate(status="completed"), self.db, self.admin)
        self.assertEqual(len(list_todos("today", False, self.db, self.admin)), 1)
        self.assertEqual(self.db.query(TodoReminder).count(), 3)

    def test_manual_todos_split_between_today_and_inbox_and_keep_links(self):
        today = datetime.date.today()
        second_cage = Cage(room="测试鼠房", cage_code="M2", gender="M")
        self.db.add(second_cage)
        self.db.flush()
        second_mouse = Mouse(mouse_code="OLD-2", cage_id=second_cage.id, gender="M", status="在笼")
        self.db.add(second_mouse)
        self.db.commit()
        due = create_todo(TodoReminderCreate(
            title="今天处理",
            due_at=f"{today.isoformat()}T15:30",
            cage_ids=[self.cage.id, second_cage.id],
            mouse_ids=[self.mouse.id, second_mouse.id],
            notes="测试备注",
        ), self.db, self.admin)
        inbox = create_todo(TodoReminderCreate(title="稍后安排"), self.db, self.admin)

        today_items = list_todos("today", False, self.db, self.admin)
        inbox_items = list_todos("inbox", False, self.db, self.admin)
        self.assertIn(due["id"], {todo["id"] for todo in today_items})
        self.assertIn(inbox["id"], {todo["id"] for todo in inbox_items})
        self.assertEqual(due["cage"]["cage_code"], "M1")
        self.assertEqual(due["mouse"]["mouse_code"], "OLD-1")
        self.assertEqual(due["cage_ids"], [self.cage.id, second_cage.id])
        self.assertEqual(due["mouse_ids"], [self.mouse.id, second_mouse.id])
        self.assertEqual([cage["cage_code"] for cage in due["cages"]], ["M1", "M2"])
        self.assertEqual([mouse["mouse_code"] for mouse in due["mice"]], ["OLD-1", "OLD-2"])

        updated = update_todo(due["id"], TodoReminderUpdate(cage_ids=[second_cage.id], mouse_ids=[]), self.db, self.admin)
        self.assertEqual(updated["cage_ids"], [second_cage.id])
        self.assertEqual(updated["mouse_ids"], [])
        self.assertIsNone(updated["mouse"])

        delete_todo(inbox["id"], self.db, self.admin)
        self.assertIsNone(self.db.get(TodoReminder, inbox["id"]))

    def test_deleting_automatic_reminder_dismisses_without_recreating(self):
        todo = list_todos("today", False, self.db, self.admin)[0]
        todo_id = todo["id"]
        delete_todo(todo_id, self.db, self.admin)
        self.assertEqual(self.db.get(TodoReminder, todo_id).status, "completed")
        list_todos("today", False, self.db, self.admin)
        self.assertEqual(self.db.get(TodoReminder, todo_id).status, "completed")

    def test_litter_batch_can_split_mice_into_multiple_cages_atomically(self):
        second = Mouse(mouse_code="OLD-2", cage_id=self.cage.id, gender="M", dob=self.mouse.dob, status="在笼")
        self.db.add(second)
        self.db.commit()
        result = batch_split_transfer(MouseBatchSplitTransfer(groups=[
            MouseSplitTransferGroup(mouse_ids=[self.mouse.id], target_room="测试鼠房", target_cage_code="X1"),
            MouseSplitTransferGroup(mouse_ids=[second.id], target_room="测试鼠房", target_cage_code="Y1"),
        ]), self.db, self.admin)
        self.db.refresh(self.mouse)
        self.db.refresh(second)
        self.assertEqual(result["affected_count"], 2)
        self.assertEqual(self.db.get(Cage, self.mouse.cage_id).cage_code, "X1")
        self.assertEqual(self.db.get(Cage, second.cage_id).cage_code, "Y1")

    def test_batch_edit_updates_selected_mouse_dates_and_genders_atomically(self):
        second = Mouse(mouse_code="EDIT-2", cage_id=self.cage.id, gender="M", dob="2026-01-01", status="在笼")
        self.db.add(second)
        self.db.commit()

        result = batch_update_fields(MouseBatchUpdateFields(
            mouse_ids=[self.mouse.id, second.id],
            dob="2026-02-03",
            gender="F",
        ), self.db, self.admin)
        self.db.refresh(self.mouse)
        self.db.refresh(second)
        self.assertEqual(result["affected_count"], 2)
        self.assertEqual({self.mouse.dob, second.dob}, {"2026-02-03"})
        self.assertEqual({self.mouse.gender, second.gender}, {"F"})

        with self.assertRaises(HTTPException):
            batch_update_fields(MouseBatchUpdateFields(
                mouse_ids=[self.mouse.id, second.id],
                dob="2026-02-30",
                gender="M",
            ), self.db, self.admin)
        self.db.refresh(self.mouse)
        self.db.refresh(second)
        self.assertEqual({self.mouse.gender, second.gender}, {"F"})


if __name__ == "__main__":
    unittest.main()
