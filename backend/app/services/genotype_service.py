"""Shared genotype history and mouse-summary behavior."""

from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.models.models import GenotypeRecord, Mouse


EMPTY_GENOTYPE_VALUES = ("", "/", "-", "无", "None", "nan")


def normalize_genotype_value(value):
    if value is None:
        return None
    value = str(value).strip()
    return None if value in EMPTY_GENOTYPE_VALUES else value


def match_import_value(column, value):
    if value is None:
        return or_(column.is_(None), func.trim(column).in_(EMPTY_GENOTYPE_VALUES))
    return func.trim(column) == value


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
        record = GenotypeRecord(mouse_code=mouse.mouse_code, mouse_id=mouse.id, **values)
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
        .order_by(GenotypeRecord.test_date.desc(), GenotypeRecord.id.desc())
        .first()
    )
    for field in ("genotype_1", "genotype_2", "test_date"):
        value = getattr(latest, field) if latest else None
        if (
            preserve_empty_values
            and normalize_genotype_value(getattr(mouse, field)) is None
            and normalize_genotype_value(value) is None
        ):
            continue
        setattr(mouse, field, value)
