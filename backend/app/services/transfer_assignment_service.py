import datetime
import re

from fastapi import HTTPException

from backend.app.models.models import Cage, Claimer, Mouse, TransferLog, TransferRequestAssignment


STATE_FIELDS = ("cage_id", "status", "owner_id", "owner_name", "claim_date", "source_room")
COMPLETED_STATUSES = {"已完成", "已转"}
ASSIGNED_STATUSES = {"进行中", *COMPLETED_STATUSES}


def parse_codes(value):
    return list(dict.fromkeys(code for code in re.split(r"[,，、\s]+", value or "") if code))


def mouse_state(mouse):
    return {field: getattr(mouse, field) for field in STATE_FIELDS}


def is_completed(status):
    return status in COMPLETED_STATUSES


def assignment_state_matches(mouse, assigned_state):
    """Allow the normal caged-recipient status normalization done at startup."""
    current = mouse_state(mouse)
    expected = dict(assigned_state)
    if (
        expected.get("status") == "在笼"
        and expected.get("cage_id")
        and (expected.get("owner_id") or expected.get("owner_name"))
    ):
        expected["status"] = "已领用"
    return current == expected


def reconcile_assignments(db, req, updates, operator):
    """Reconcile staged/completed mouse assignments in the caller's transaction."""
    next_status = updates.get("status", req.status)
    if next_status == "已转":
        next_status = updates["status"] = "已完成"

    codes = parse_codes(updates.get("mouse_codes", req.mouse_codes))
    if next_status == "已完成" and not codes:
        raise HTTPException(400, "完成转鼠前，请至少选择或输入一个小鼠编号")
    if next_status == "进行中" and not codes:
        raise HTTPException(400, "进入备鼠阶段前，请至少选择或输入一个小鼠编号")
    desired_order = codes if next_status in ASSIGNED_STATUSES else []
    desired_codes = set(desired_order)

    assignments = db.query(TransferRequestAssignment).filter_by(request_id=req.id).all()
    active = {}
    for assignment in assignments:
        mouse = db.get(Mouse, assignment.mouse_id)
        if mouse is not None:
            active[mouse.mouse_code] = (assignment, mouse)

    previous_codes = set(parse_codes(req.mouse_codes)) if req.status in ASSIGNED_STATUSES else set()
    legacy_untracked = previous_codes - set(active)
    demander = (updates.get("demander", req.demander) or "").strip()
    if legacy_untracked:
        metadata_only = (
            is_completed(req.status)
            and is_completed(next_status)
            and desired_codes == previous_codes
            and demander == req.demander.strip()
        )
        if metadata_only:
            updates["mouse_codes"] = ", ".join(codes)
            return
        raise HTTPException(409, f"以下历史分配没有审批前快照，无法自动恢复，请先核对原笼位和领取信息：{', '.join(sorted(legacy_untracked))}")

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
        if mouse.owner_id or mouse.owner_name or mouse.status == "已领用":
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 已有领取人，不能重复分配")

    removed = [pair for code, pair in active.items() if code not in desired_codes]
    retained = [pair for code, pair in active.items() if code in desired_codes]
    if desired_codes and not demander:
        raise HTTPException(400, "需求者姓名不能为空")
    recipient_changed = demander != req.demander.strip()
    phase_changed = is_completed(next_status) != is_completed(req.status)

    for assignment, mouse in removed + (retained if recipient_changed or phase_changed else []):
        if not assignment_state_matches(mouse, assignment.assigned_state):
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 的笼位、状态或领取信息已被其他操作修改，请先核对后再继续")

    for assignment, mouse in removed:
        original = assignment.original_state
        cage = db.get(Cage, original["cage_id"]) if original["cage_id"] else None
        if cage is None or (cage.room, cage.cage_code) != (assignment.source_room, assignment.source_cage):
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 的原笼位已删除或变更，请先恢复原笼位再撤销分配")
        if original["owner_id"] and db.get(Claimer, original["owner_id"]) is None:
            raise HTTPException(409, f"小鼠 {mouse.mouse_code} 的原领取人已删除，请先核对领取信息")

    today = datetime.date.today().isoformat()
    log_groups = {}

    def add_log(mouse, action, source_room, source_cage, target_room=None, target_cage=None, claimer_name=None, note=None):
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
            notes=f"申请 #{req.seq or req.id}; {note or action}; 反馈: {updates.get('feedback', req.feedback) or '无'}"
        )

    for assignment, mouse in removed:
        was_completed = is_completed(req.status)
        previous_owner = mouse.owner_name
        for field, value in assignment.original_state.items():
            setattr(mouse, field, value)
        action = "撤销分配/回笼" if was_completed else "撤销备鼠分配"
        add_log(mouse, action, None, None, assignment.source_room, assignment.source_cage, previous_owner)
        db.delete(assignment)

    claimer = None
    if desired_codes:
        claimer = db.query(Claimer).filter_by(name=demander).first()
        if claimer is None:
            claimer = Claimer(name=demander)
            db.add(claimer)
            db.flush()

    for mouse in added:
        assignment = TransferRequestAssignment(
            request_id=req.id, mouse_id=mouse.id, original_state=mouse_state(mouse),
            source_room=mouse.cage.room, source_cage=mouse.cage.cage_code,
            assigned_state={},
        )
        db.add(assignment)
        active[mouse.mouse_code] = (assignment, mouse)

    for code in desired_order:
        assignment, mouse = active[code]
        was_added = mouse in added
        if next_status == "进行中":
            original = assignment.original_state
            for field in ("cage_id", "status", "claim_date", "source_room"):
                setattr(mouse, field, original[field])
            mouse.owner_id = claimer.id
            mouse.owner_name = claimer.name
            if mouse.cage_id and mouse.status == "在笼":
                mouse.status = "已领用"
            if was_added:
                add_log(mouse, "备鼠/设置领取人", assignment.source_room, assignment.source_cage,
                        claimer_name=claimer.name, note="备鼠中，已设置领取人，小鼠保留在原笼位")
            elif phase_changed:
                add_log(mouse, "撤回完成/回笼", None, None, assignment.source_room, assignment.source_cage,
                        claimer.name, note="需求恢复为进行中，小鼠回到原笼位并保留领取人")
        else:
            mouse.owner_id = claimer.id
            mouse.owner_name = claimer.name
            mouse.claim_date = mouse.claim_date if is_completed(req.status) and not phase_changed else today
            mouse.source_room = assignment.source_room
            mouse.status = "出笼"
            mouse.cage_id = None
            if was_added or phase_changed:
                add_log(mouse, "转鼠/完成领取", assignment.source_room, assignment.source_cage,
                        target_room=updates.get("target_room", req.target_room), claimer_name=claimer.name,
                        note="确认已交付，自动出笼")

        if recipient_changed and not was_added:
            add_log(mouse, "转鼠/改派领取人", assignment.source_room, assignment.source_cage,
                    target_room=updates.get("target_room", req.target_room), claimer_name=claimer.name)
        assignment.assigned_state = mouse_state(mouse)

    db.add_all(log_groups.values())

    if "mouse_codes" in updates or next_status in ASSIGNED_STATUSES:
        updates["mouse_codes"] = ", ".join(codes)
