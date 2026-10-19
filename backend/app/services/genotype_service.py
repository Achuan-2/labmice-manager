"""Shared genotype history and mouse-summary behavior."""

import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.models.models import GenotypeRecord, Mouse


EMPTY_GENOTYPE_VALUES = ("", "/", "-", "无", "None", "nan")
PENDING_GENOTYPE_VALUES = (*EMPTY_GENOTYPE_VALUES, "待检验", "待鉴定", "待测", "未测", "未鉴定")


def has_genotype_result(*values) -> bool:
    return any(str(value).strip() not in PENDING_GENOTYPE_VALUES for value in values if value is not None)


def genotype_result_condition():
    """A record is tested once at least one result column contains an outcome."""
    return or_(*(
        func.coalesce(func.trim(getattr(GenotypeRecord, field)), "").notin_(PENDING_GENOTYPE_VALUES)
        for field in ("genotype_1", "genotype_2", "genotype_3")
    ))


def normalize_genotype_value(value):
    if value is None:
        return None
    value = str(value).strip()
    return None if value in EMPTY_GENOTYPE_VALUES else value


def match_import_value(column, value):
    if value is None:
        return or_(column.is_(None), func.trim(column).in_(EMPTY_GENOTYPE_VALUES))
    return func.trim(column) == value


def next_genotype_entry_order(db: Session) -> int:
    db.flush()
    return (db.query(func.max(func.coalesce(GenotypeRecord.entry_order, GenotypeRecord.id))).scalar() or 0) + 1


def align_genotype_entry_order(records) -> int:
    """Reorder matched records within their existing slots, leaving other records in place."""
    records = list({record.id: record for record in records}.values())
    slots = sorted(record.entry_order if record.entry_order is not None else record.id for record in records)
    changed = 0
    for record, slot in zip(records, slots):
        current = record.entry_order if record.entry_order is not None else record.id
        if current != slot:
            record.entry_order = slot
            changed += 1
    return changed


def upsert_imported_genotype(db: Session, mouse: Mouse, **values):
    """Match date and all three outcomes, treating Excel empty markers as NULL."""
    for field in ("genotype_1", "genotype_2", "genotype_3"):
        values[field] = normalize_genotype_value(values.get(field))
    values["test_date"] = normalize_genotype_value(values.get("test_date"))
    record = db.query(GenotypeRecord).filter(
        GenotypeRecord.mouse_code == mouse.mouse_code,
        *(match_import_value(getattr(GenotypeRecord, field), values[field])
          for field in ("test_date", "genotype_1", "genotype_2", "genotype_3")),
    ).first()
    created = record is None
    if created:
        record = GenotypeRecord(
            mouse_code=mouse.mouse_code, mouse_id=mouse.id,
            entry_order=next_genotype_entry_order(db), **values,
        )
        db.add(record)
    else:
        if record.mouse_id is None:
            record.mouse_id = mouse.id
        for field in ("strain", "dob", "gender", "parents", "op_record", "notes"):
            incoming = values.get(field)
            if normalize_genotype_value(incoming) and not normalize_genotype_value(getattr(record, field)):
                setattr(record, field, incoming)
    db.flush()
    return record, created


def sync_mouse_genotype_summary(
    mouse: Optional[Mouse], db: Session, *, preserve_empty_values: bool = False,
) -> None:
    """Keep the mouse archive summary aligned with its latest genotype record."""
    if not mouse:
        return
    latest = (
        db.query(GenotypeRecord)
        .filter(or_(
            GenotypeRecord.mouse_id == mouse.id,
            GenotypeRecord.mouse_code == mouse.mouse_code,
        ))
        .filter(genotype_result_condition())
        .order_by(GenotypeRecord.test_date.desc(), GenotypeRecord.id.desc())
        .first()
    )
    for field in ("genotype_1", "genotype_2", "test_date"):
        value = getattr(latest, field) if latest else None
        if (
            preserve_empty_values
            and normalize_genotype_value(value) is None
        ):
            continue
        setattr(mouse, field, value)
    # Excel reimports must preserve manually edited lifecycle states.
    if not preserve_empty_values:
        sync_mouse_genotyping_status(mouse, db)


def latest_pending_mouse_genotype(mouse: Mouse, db: Session):
    query = db.query(GenotypeRecord).filter(or_(
        GenotypeRecord.mouse_id == mouse.id,
        GenotypeRecord.mouse_code == mouse.mouse_code,
    ))
    return query.filter(~genotype_result_condition()).order_by(
        func.coalesce(GenotypeRecord.entry_order, GenotypeRecord.id).desc(),
        GenotypeRecord.id.desc(),
    ).first()


def ensure_pending_genotype_record(mouse: Mouse, db: Session):
    """A manual pending status starts a test without duplicating an open record."""
    db.flush()
    latest = latest_pending_mouse_genotype(mouse, db)
    if latest:
        return latest
    record = GenotypeRecord(
        mouse_id=mouse.id, mouse_code=mouse.mouse_code,
        entry_order=next_genotype_entry_order(db),
        strain=mouse.strain, dob=mouse.dob, gender=mouse.gender, parents=mouse.parents,
    )
    db.add(record)
    db.flush()
    return record


def sync_mouse_genotyping_status(mouse: Optional[Mouse], db: Session):
    """Link the current test to status without discarding historical results."""
    if not mouse:
        return
    if mouse.status == "死亡" or mouse.owner_name == "安乐死":
        mouse.status_before_genotyping = None
        return
    pending = latest_pending_mouse_genotype(mouse, db)
    if pending:
        if mouse.status != "待鉴定":
            from backend.app.services.mouse_status_service import ensure_mouse_status
            ensure_mouse_status(db, "待鉴定")
            mouse.status_before_genotyping = mouse.status
            mouse.status = "待鉴定"
    else:
        if mouse.status == "待鉴定":
            previous = mouse.status_before_genotyping
            if previous not in (None, "待鉴定", "在笼", "已领用", "出笼"):
                mouse.status = previous
            else:
                mouse.status = ("已领用" if mouse.owner_id or mouse.owner_name else "在笼") if mouse.cage_id else "出笼"
        mouse.status_before_genotyping = None


def update_pending_genotype_from_mouse(mouse: Mouse, db: Session, values: dict):
    """Complete an open test when its results are edited from the mouse archive."""
    if not values:
        return
    db.flush()
    latest = latest_pending_mouse_genotype(mouse, db)
    if not latest:
        return
    for field, value in values.items():
        setattr(latest, field, normalize_genotype_value(value))
    is_tested = has_genotype_result(latest.genotype_1, latest.genotype_2, latest.genotype_3)
    if is_tested and not latest.test_date:
        latest.test_date = datetime.date.today().isoformat()
    db.flush()
    if is_tested:
        sync_mouse_genotype_summary(mouse, db)
    else:
        sync_mouse_genotyping_status(mouse, db)


def sync_existing_genotyping_statuses(db: Session):
    """Backfill legacy pending flags and records idempotently during startup."""
    mice = db.query(Mouse).filter(or_(
        Mouse.status == "待鉴定",
        Mouse.genotype_records.any(),
        Mouse.mouse_code.in_(db.query(GenotypeRecord.mouse_code)),
    )).all()
    for mouse in mice:
        if mouse.status == "待鉴定":
            ensure_pending_genotype_record(mouse, db)
        sync_mouse_genotyping_status(mouse, db)
