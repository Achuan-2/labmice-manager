import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, Claimer, Mouse, TransferLog, TransferRequest, TransferRequestAssignment, User
from backend.app.routers.mice import enrich_mouse_response
from backend.app.routers.transfer_requests import process_transfer_request, delete_transfer_request, get_assigned_mice
from backend.app.schemas.schemas import TransferRequestUpdate


class TransferAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.admin = User(username="test", display_name="管理员")
        self.cages = [Cage(room="鼠房甲", cage_code="A1"), Cage(room="鼠房乙", cage_code="A1")]
        self.db.add_all(self.cages)
        self.db.flush()
        self.mice = [Mouse(mouse_code=f"M{i}", cage_id=self.cages[i % 2].id, status="在笼", source_room="来源记录") for i in range(3)]
        self.req = TransferRequest(request_date="2026-09-09", demander="领取人甲", strain="测试", status="申请中", target_room="东五")
        self.db.add_all(self.mice + [self.req])
        self.db.commit()
        self.req_id = self.req.id
        self.original_cages = {mouse.mouse_code: mouse.cage_id for mouse in self.mice}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def save(self, **updates):
        return process_transfer_request(self.req_id, TransferRequestUpdate(**updates), self.db, self.admin)

    def approve(self, codes="M0, M1"):
        return self.save(status="已转", mouse_codes=codes)

    def test_approval_snapshot_logs_and_candidate_api(self):
        self.approve()
        for mouse in self.mice[:2]:
            self.assertIsNone(mouse.cage_id)
            self.assertEqual((mouse.status, mouse.owner_name), ("出笼", "领取人甲"))
            details = enrich_mouse_response(mouse, self.db)
            log = details["transfer_logs"][0]
            cage = self.db.get(Cage, self.original_cages[mouse.mouse_code])
            self.assertEqual((log["source_room"], log["source_cage"]), (cage.room, cage.cage_code))
            self.assertIn("自动出笼", log["notes"])
            self.assertEqual(log["target_room"], "东五")
        assigned = get_assigned_mice(self.req_id, self.db, self.admin)
        self.assertEqual({row["mouse_code"] for row in assigned}, {"M0", "M1"})
        self.assertTrue(all(row["assignment_source_cage"] == "A1" for row in assigned))

    def test_same_cage_logs_merge_and_remain_visible_in_each_mouse_archive(self):
        self.approve("M0, M1, M2")
        logs = self.db.query(TransferLog).order_by(TransferLog.id).all()
        self.assertEqual(len(logs), 2)
        merged = next(log for log in logs if log.source_room == "鼠房甲")
        self.assertEqual((merged.mouse_codes, merged.mouse_count, merged.target_room), ("M0, M2", 2, "东五"))
        for mouse in (self.mice[0], self.mice[2]):
            self.assertEqual(enrich_mouse_response(mouse, self.db)["transfer_logs"][0]["id"], merged.id)
        self.save(mouse_codes="M1")
        returns = self.db.query(TransferLog).filter_by(action_type="撤销分配/回笼").all()
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0].mouse_count, 2)
        self.assertEqual(self.mice[0].cage_id, self.original_cages["M0"])
        self.assertEqual(self.mice[2].cage_id, self.original_cages["M2"])

    def test_separate_approvals_do_not_merge_history(self):
        self.approve("M0")
        self.save(mouse_codes="M0, M2")
        logs = self.db.query(TransferLog).filter_by(action_type="转鼠/审批处理").all()
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(log.mouse_count == 1 for log in logs))

    def test_partial_replacement_survives_new_session_and_repeat_save(self):
        self.approve()
        self.db.close()
        self.db = Session(self.engine, autoflush=False)
        self.save(mouse_codes="M1, M2")
        restored = self.db.query(Mouse).filter_by(mouse_code="M0").one()
        self.assertEqual(restored.cage_id, self.original_cages["M0"])
        self.assertEqual((restored.status, restored.owner_id, restored.owner_name, restored.claim_date, restored.source_room), ("在笼", None, None, None, "来源记录"))
        logs_before = self.db.query(TransferLog).count()
        self.save(mouse_codes="M2，M1 M1", feedback="仅改反馈")
        self.assertEqual(self.db.query(TransferLog).count(), logs_before)
        self.assertEqual(self.db.query(TransferRequestAssignment).count(), 2)

    def test_cancel_and_reapprove_and_delete(self):
        self.approve()
        self.save(status="取消")
        self.assertEqual(self.db.query(TransferRequestAssignment).count(), 0)
        self.assertTrue(all(mouse.cage_id == self.original_cages[mouse.mouse_code] for mouse in self.mice))
        self.approve()
        delete_transfer_request(self.req_id, self.db, self.admin)
        self.assertEqual(self.db.query(TransferRequestAssignment).count(), 0)
        self.assertTrue(all(mouse.status == "在笼" for mouse in self.mice))

    def test_return_to_in_progress_restores_all(self):
        self.approve()
        self.save(status="进行中")
        self.assertTrue(all(mouse.cage_id for mouse in self.mice))

    def test_unselect_last_mouse_restores_and_reopens_request(self):
        self.approve("M0")
        self.save(status="已转", mouse_codes="")
        self.assertEqual(self.req.status, "进行中")
        self.assertEqual(self.mice[0].cage_id, self.original_cages["M0"])

    def test_reassignment_preserves_original_snapshot(self):
        self.approve()
        self.save(demander="领取人乙")
        self.assertEqual(self.mice[0].owner_name, "领取人乙")
        self.save(status="取消")
        self.assertIsNone(self.mice[0].owner_name)

    def test_other_request_cannot_take_assigned_mouse(self):
        self.approve()
        req = TransferRequest(request_date="2026-09-09", demander="领取人乙", strain="测试")
        self.db.add(req)
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            process_transfer_request(req.id, TransferRequestUpdate(status="已转", mouse_codes="M0"), self.db, self.admin)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.mice[0].owner_name, "领取人甲")

    def test_conflict_rolls_back_entire_edit(self):
        self.approve()
        self.mice[1].status = "死亡"
        self.db.commit()
        with self.assertRaises(HTTPException):
            self.save(status="取消")
        self.assertEqual(self.req.status, "已转")
        self.assertIsNone(self.mice[0].cage_id)
        self.assertEqual(self.mice[1].status, "死亡")
        self.assertEqual(self.db.query(TransferRequestAssignment).count(), 2)

    def test_missing_cage_does_not_guess_location(self):
        self.approve("M0")
        self.db.delete(self.db.get(Cage, self.original_cages["M0"]))
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            self.save(status="取消")
        self.assertIn("原笼位", error.exception.detail)
        self.assertIsNone(self.mice[0].cage_id)

    def test_invalid_replacement_does_not_restore_removed_mouse(self):
        self.approve()
        with self.assertRaises(HTTPException):
            self.save(mouse_codes="M1, 不存在")
        self.assertIsNone(self.mice[0].cage_id)
        self.assertEqual(self.req.mouse_codes, "M0, M1")

    def test_historical_missing_snapshot_is_explicit(self):
        self.req.status = "已转"
        self.req.mouse_codes = "M0"
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            self.save(status="取消")
        self.assertIn("历史分配", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
