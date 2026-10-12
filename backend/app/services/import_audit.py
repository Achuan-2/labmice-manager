"""Persist Excel import changes in the existing change log transaction."""

import datetime
from collections import defaultdict

from backend.app.models.models import TransferLog


IMPORT_ACTION = "导入数据"
STATUS_LABELS = {"added": "新增", "updated": "补充/更新", "removed": "清理无效记录"}


def display_value(value):
    return "空" if value is None or value == "" else str(value)


def record_import_logs(db, report, operator):
    """One entry per changed file; unchanged repeat imports produce no audit entry."""
    files = defaultdict(list)
    for record in report["records"]:
        files[record["filename"]].append(record)

    for filename, records in files.items():
        changed = [record for record in records if record["status"] in STATUS_LABELS]
        if not changed:
            continue
        counts = {status: sum(record["status"] == status for record in records)
                  for status in ("added", "updated", "removed", "skipped")}
        lines = [
            f"文件：{filename}",
            f"新增 {counts['added']} 项，补充/更新 {counts['updated']} 项，"
            f"清理无效记录 {counts['removed']} 项，重复跳过 {counts['skipped']} 项",
            "",
        ]
        mouse_codes = sorted({record["mouse_code"] for record in changed if record.get("mouse_code")})
        for record in changed:
            source = record["sheet"]
            if record["row"] is not None:
                source += f" · 第{record['row']}行"
            lines.append(f"【{STATUS_LABELS[record['status']]}】{record['type']}：{record['identifier']}（{source}）")
            for change in record["changes"]:
                lines.append(
                    f"  {change['field']}：{display_value(change['before'])} → {display_value(change['after'])}"
                )
        db.add(TransferLog(
            action_type=IMPORT_ACTION,
            mouse_codes=", ".join(mouse_codes),
            mouse_count=len(mouse_codes),
            operator=operator,
            date=datetime.date.today().isoformat(),
            status="已完成",
            notes="\n".join(lines),
        ))
