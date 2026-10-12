"""Collect committed Excel changes and distinguish reused records from new records."""

from backend.app.models.models import (
    Cage, Claimer, GenotypeRecord, Mouse, Primer, TransferLog, TransferRequest,
)


IMPORT_MODELS = {
    Mouse: ("小鼠", "mice_imported"),
    Cage: ("笼位", "cages_imported"),
    Claimer: ("领取人", "claimers_imported"),
    GenotypeRecord: ("基因鉴定", "genotypes_imported"),
    TransferRequest: ("转鼠申请", "transfer_requests_imported"),
    TransferLog: ("转鼠日志", "transfers_imported"),
    Primer: ("引物", "primers_imported"),
}
FIELD_LABELS = {
    "mouse_code": "小鼠编号", "cage_id": "笼位ID", "cage_code": "笼号",
    "room": "鼠房", "strain": "品系", "gender": "性别", "dob": "出生日期",
    "parents": "父母", "genotype_1": "基因型1", "genotype_2": "基因型2",
    "genotype_3": "基因型3", "test_date": "测试日期", "owner_id": "领取人ID",
    "owner_name": "领取人", "source_room": "来源鼠房", "status": "状态",
    "claim_date": "领取日期", "notes": "备注", "name": "姓名",
    "mating_date": "合笼日期", "observation": "观察记录",
    "default_room": "默认鼠房", "feedback": "反馈", "mouse_codes": "小鼠编号",
}


def record_state(record):
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
        if column.name not in {"id", "created_at", "updated_at"}
    }


def record_identifier(model, state):
    if model is Mouse:
        return state["mouse_code"]
    if model is Cage:
        return f"{state['room']} / {state['cage_code']}"
    if model is Claimer:
        return state["name"]
    if model is GenotypeRecord:
        genotypes = " / ".join(state.get(f"genotype_{i}") or "—" for i in (1, 2, 3))
        return f"{state['mouse_code']} / {state.get('test_date') or '无日期'} / {genotypes}"
    if model is Primer:
        return f"{state.get('strain_short') or '无品系'} / {state.get('sequence') or '无序列'}"
    if model is TransferRequest:
        return f"{state.get('seq') or '无序号'} / {state['demander']} / {state['request_date']}"
    return f"{state.get('claimer_name') or '无领取人'} / {state.get('date') or '无日期'} / {state['mouse_codes']}"


class ImportReport:
    def __init__(self, db, filename):
        db.flush()
        self.filename = filename
        self.sheet = ""
        self.row = None
        self.touched = []
        self.ignored_sheets = []
        self.before = self.snapshot(db)

    @staticmethod
    def snapshot(db):
        return {
            (model, record.id): record_state(record)
            for model in IMPORT_MODELS
            for record in db.query(model).all()
        }

    def track(self, record):
        self.touched.append((record, self.filename, self.sheet, self.row))

    def existed(self, record):
        return (type(record), record.id) in self.before

    def finish(self, db, results):
        db.flush()
        after = self.snapshot(db)
        locations = {}
        for record, filename, sheet, row in self.touched:
            locations.setdefault((type(record), record.id), (filename, sheet, row))
        details = []
        summary = {"added": 0, "updated": 0, "skipped": 0, "removed": 0}
        for model, (_, counter) in IMPORT_MODELS.items():
            results[counter] = sum(key[0] is model and key not in self.before for key in after)
        for key in dict.fromkeys([*after, *self.before]):
            old, new = self.before.get(key), after.get(key)
            if old == new and key not in locations:
                continue
            status = "added" if old is None else "removed" if new is None else "skipped" if old == new else "updated"
            model, _ = key
            changes = []
            if status == "updated":
                changes = [
                    {"field": FIELD_LABELS.get(field, field), "before": old.get(field), "after": value}
                    for field, value in new.items() if old.get(field) != value
                ]
            filename, sheet, row = locations.get(key, (self.filename, "导入后整理", None))
            details.append({
                "type": IMPORT_MODELS[model][0], "identifier": record_identifier(model, new or old),
                "status": status, "filename": filename, "sheet": sheet, "row": row,
                "changes": changes,
                "mouse_code": (new or old).get("mouse_code"),
            })
            summary[status] += 1
        results["report"] = {"summary": summary, "records": details, "ignored_sheets": self.ignored_sheets}


def track_import(db, record):
    db.flush()
    report = db.info.get("excel_import_report")
    if report and record is not None:
        report.track(record)


def is_existing_import_record(db, record):
    report = db.info.get("excel_import_report")
    return report.existed(record) if report else False


def rollback_import_row(db):
    savepoint = db.get_nested_transaction()
    if savepoint:
        savepoint.rollback()


def iter_import_rows(db, sheet, min_row=2):
    """Flush each row and isolate malformed rows without losing earlier imports."""
    report = db.info.get("excel_import_report")
    for row_number, row in enumerate(sheet.iter_rows(min_row=min_row, values_only=True), min_row):
        checkpoint = len(report.touched) if report else 0
        if report:
            report.sheet, report.row = sheet.title, row_number
        with db.begin_nested() as savepoint:
            yield row_number, row
            if not savepoint.is_active and report:
                del report.touched[checkpoint:]
