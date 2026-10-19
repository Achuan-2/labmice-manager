"""Recover Excel row order without importing or overwriting business data."""

from collections import defaultdict

from backend.app.models.models import GenotypeRecord
from backend.app.services.genotype_service import align_genotype_entry_order, normalize_genotype_value
from backend.app.services.importer import is_valid_mouse_code, parse_date


def plan_genotype_order(db, workbook):
    by_code = defaultdict(list)
    for record in db.query(GenotypeRecord).all():
        by_code[record.mouse_code].append(record)
    ordered, seen, missing, ambiguous = [], set(), [], []
    for sheet in workbook:
        if sheet.title != '小鼠档案' and not any(word in sheet.title for word in ('基因鉴定', '鉴定结果')):
            continue
        headers = [str(cell.value or '').strip() for cell in sheet[1]]
        code_col = next((i for i, header in enumerate(headers) if '编号' in header or '耳标' in header), None)
        if code_col is None:
            continue
        date_col = next((i for i, header in enumerate(headers) if '测试日期' in header or header == '日期'), None)
        result_cols = [next((i for i, header in enumerate(headers)
                            if header.upper().replace(' ', '') == f'GENOTYPE{n}' or header == f'基因型{n}'), None)
                       for n in (1, 2, 3)]
        current_date = None
        for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
            raw_date = row[date_col] if date_col is not None else None
            date = parse_date(raw_date)
            if raw_date is not None:
                current_date = date
            if sheet.title != '小鼠档案':
                date = date or current_date
            if not is_valid_mouse_code(row[code_col]):
                continue
            code = str(row[code_col]).strip()
            candidates = by_code[code]
            location = {'sheet': sheet.title, 'row': row_number, 'mouse_code': code}
            if not candidates:
                missing.append(location)
                continue
            if len(candidates) > 1:
                values = [normalize_genotype_value(row[column]) if column is not None else None for column in result_cols]
                candidates = [record for record in candidates
                              if normalize_genotype_value(record.test_date) == date
                              and [normalize_genotype_value(getattr(record, f'genotype_{n}')) for n in (1, 2, 3)] == values]
            if len(candidates) != 1:
                ambiguous.append(location)
                continue
            record = candidates[0]
            if record.id not in seen:
                ordered.append(record)
                seen.add(record.id)
    if not ordered:
        raise ValueError('未匹配到可恢复顺序的鉴定记录，请选择原始小鼠档案或基因鉴定 Excel')
    return ordered, {'matched': len(ordered), 'missing': missing, 'ambiguous': ambiguous}


def apply_genotype_order(records, report):
    report['changed'] = align_genotype_entry_order(records)
    return report
