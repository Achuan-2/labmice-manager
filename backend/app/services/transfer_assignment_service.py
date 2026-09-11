import datetime
import re

from fastapi import HTTPException

from backend.app.models.models import Cage, Claimer, Mouse, TransferLog, TransferRequestAssignment
from backend.app.services.owner_service import apply_owner_status


STATE_FIELDS = ("cage_id", "status", "owner_id", "owner_name", "claim_date", "source_room")


def parse_codes(value):
    return list(dict.fromkeys(code for code in re.split(r"[,，、\s]+", value or "") if code))


def mouse_state(mouse):
    return {field: getattr(mouse, field) for field in STATE_FIELDS}


def reconcile_assignments(db, req, updates, operator):
    """Apply and reverse assignments in the caller's transaction."""
    next_status = updates.get("status", req.status)
    codes = parse_codes(updates.get("mouse_codes", req.mouse_codes))
    if next_status == "已转" and not codes and req.status == "已转" and parse_codes(req.mouse_codes):
        next_status = updates["status"] = "进行中"
    desired_codes = set(codes) if next_status == "已转" else set()
    if next_status == "已转" and not codes:
        raise HTTPException(400, "审批为已转时，请至少选择或输入一个小鼠编号")

    assignments = db.query(TransferRequestAssignment).filter_by(request_id=req.id).all()
    active = {}
    for assignment in assignments:
        mouse = db.get(Mouse, assignment.mouse_id)
        if mouse is not None:
            active[mouse.mouse_code] = (assignment, mouse)

    previous_codes = set(parse_codes(req.mouse_codes)) if req.status == "已转" else set()
    legacy_removed = previous_codes - set(active) - desired_codes
    if legacy_removed:
        raise HTTPException(409, f"以下历史分配没有审批前快照，无法自动恢复，请先核对原笼位和领取信息：{', '.join(sorted(legacy_removed))}")

    selected = db.query(Mouse).filter(Mouse.mouse_code.in_(desired_codes)).all() if desired_codes else []
    by_code = {mouse.mouse_code: mouse for mouse in selected}
    missing = desired_codes - set(by_code)
    if missing:
        raise HTTPException(400, f"以下小鼠编号不存在：{', '.join(sorted(missing))}")

    added = [by_code[code] for code in codes if code not in active] if desired_codes else []
    for mouse in added:
        other = db.query(TransferRequestAssignment).filter_by(mouse_id=mouse.id).first()
        if other:
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 已分配给其他转鼠申请")
        if not mouse.cage_id or mouse.status in {"出笼", "死亡"} or mouse.cage is None:
            raise HTTPException(400, f"小鼠 {mouse.mouse_code} 已出笼或死亡，不能分配")
        # Existing approvals can be saved once to capture their current location.
        if (mouse.owner_id or mouse.owner_name or mouse.status == "已领用") and mouse.mouse_code not in previous_codes:
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 已有领取人，不能重复分配")

    removed = [pair for code, pair in active.items() if code not in desired_codes]
    demander = (updates.get("demander", req.demander) or "").strip()
    if desired_codes and not demander:
        raise HTTPException(400, "需求者姓名不能为空")
    recipient_changed = demander != req.demander.strip()
    retained = [pair for code, pair in active.items() if code in desired_codes]
    for assignment, mouse in removed + (retained if recipient_changed else []):
        if mouse_state(mouse) != assignment.assigned_state:
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 的笼位、状态或领取信息已被其他操作修改，请先核对后再撤销或改派")
    for assignment, mouse in removed:
        original = assignment.original_state
        cage = db.get(Cage, original["cage_id"]) if original["cage_id"] else None
        if cage is None or (cage.room, cage.cage_code) != (assignment.source_room, assignment.source_cage):
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 的原笼位已删除或变更，请先恢复原笼位再撤销分配")
        if original["owner_id"] and db.get(Claimer, original["owner_id"]) is None:
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 的原领取人已删除，请先核对领取信息")

    today = datetime.date.today().isoformat()
    log_groups = {}

    def add_log(mouse, action, source_room, source_cage, target_room=None, target_cage=None, claimer_name=None):
        key = (action, source_room, source_cage, target_room, target_cage, claimer_name)
        if key in log_groups:
            log = log_groups[key]
            log.mouse_codes += f", {mouse.mouse_code}"
            log.mouse_count += 1
            return
        log_groups[key] = TransferLog(
            action_type=action, mouse_codes=mouse.mouse_code, mouse_count=1,
            source_room=source_room, source_cage=source_cage,
            target_room=target_room, target_cage=target_cage,
            claimer_name=claimer_name, operator=operator, date=today, status="已完成",
            notes=f"申请 #{req.seq or req.id}; {'审批通过，自动出笼' if action == '转鼠/审批处理' else action}; 反馈: {updates.get('feedback', req.feedback) or '无'}"
        )

    for assignment, mouse in removed:
        for field, value in assignment.original_state.items():
            setattr(mouse, field, value)
        add_log(mouse, "撤销分配/回笼", None, None, assignment.source_room, assignment.source_cage, mouse.owner_name)
        db.delete(assignment)

    if desired_codes and (added or recipient_changed):
        claimer = db.query(Claimer).filter_by(name=demander).first()
        if claimer is None:
            claimer = Claimer(name=demander)
            db.add(claimer)
            db.flush()
        for mouse in added:
            assignment = TransferRequestAssignment(
                request_id=req.id, mouse_id=mouse.id, original_state=mouse_state(mouse),
                source_room=mouse.cage.room, source_cage=mouse.cage.cage_code,
            )
            mouse.owner_id = claimer.id
            mouse.owner_name = claimer.name
            mouse.claim_date = today
            mouse.source_room = assignment.source_room
            mouse.status = "出笼"
            mouse.cage_id = None
            apply_owner_status(db, mouse)
            assignment.assigned_state = mouse_state(mouse)
            db.add(assignment)
            add_log(mouse, "转鼠/审批处理", assignment.source_room, assignment.source_cage,
                    target_room=updates.get("target_room", req.target_room), claimer_name=claimer.name)
        if recipient_changed:
            for assignment, mouse in retained:
                mouse.owner_id = claimer.id
                mouse.owner_name = claimer.name
                apply_owner_status(db, mouse)
                assignment.assigned_state = mouse_state(mouse)
                add_log(mouse, "转鼠/改派领取人", assignment.source_room, assignment.source_cage,
                        target_room=updates.get("target_room", req.target_room), claimer_name=claimer.name)

    db.add_all(log_groups.values())

    if "mouse_codes" in updates or next_status == "已转":
        updates["mouse_codes"] = ", ".join(codes)
