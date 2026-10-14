"""Ownership and application editing rules shared by transfer request routes."""
from collections import defaultdict

from fastapi import HTTPException

from backend.app.models.models import TransferRequest, TransferRequestAssignment, User


def require_request_owner(req, user):
    if user.role != "admin" and req.created_by_username != user.username:
        raise HTTPException(403, "只能编辑或删除自己提交的申请")


def require_pending_application(db, req):
    if req.status != "申请中" or db.query(TransferRequestAssignment).filter_by(request_id=req.id).first():
        raise HTTPException(409, "该申请已进入处理流程，请联系管理员修改")


def backfill_request_creators(db, auth_db):
    """Recover only unambiguous legacy submitters; never use the demander as ownership."""
    usernames_by_label = defaultdict(set)
    for user in auth_db.query(User).all():
        usernames_by_label[user.username].add(user.username)
        if user.display_name:
            usernames_by_label[user.display_name].add(user.username)

    requests = db.query(TransferRequest).filter(
        TransferRequest.created_by_username.is_(None),
        TransferRequest.status == "申请中",
        ~TransferRequest.id.in_(db.query(TransferRequestAssignment.request_id)),
    ).all()
    for req in requests:
        candidates = usernames_by_label.get(req.handler, set())
        if len(candidates) == 1:
            req.created_by_username = next(iter(candidates))
