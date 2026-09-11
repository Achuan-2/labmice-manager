import os
import re
import datetime
from typing import Dict, Any, List, Optional, Tuple
import openpyxl
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.models import Mouse, Cage, Claimer, TransferLog, Primer, GenotypeRecord, TransferRequest
from backend.app.services.strain_service import normalize_strain_name
from backend.app.services.owner_service import sync_euthanasia_owner

INFERRED_PARENT_PLACEHOLDER_NOTE = "由基因鉴定父母关系推测录入"
SYNTHETIC_IMPORT_ROOMS = {"常规鼠房", "枫林繁育", "枫林老鼠房"}

GENOTYPE_OUTCOME_STRINGS = {
    "HOM", "HET", "WT", "WT?", "HET?", "HOM?", "？", "?", "+", "-", "+/-", "+/+", "-/-",
    "纯合", "纯合子", "杂合", "杂合子", "野生", "野生型", "阳性", "阴性",
    "待鉴定", "待测", "未测", "未鉴定", "已测", "POS", "NEG", "MUT", "NULL",
    "POS/NEG", "NEG/POS", "HET/WT", "HOM/WT"
}

INVALID_MOUSE_CODE_TERMS = {
    "ALDH1L1-CRE", "ALDH1L1", "AI148", "AI93", "AI9", "5XFAD", "CAMK-TTA",
    "CAMK2A-TTA", "CMAK-TTA", "TRAP2", "TRAP 2", "PV-CRE", "RASGRF2", "TETO",
    "TETO-GCAMP6S", "GCAMP6S", "CRE", "PDYN-CRE", "PDYN", "SST", "VIP",
    "BFP", "GFP", "TDTOMATO", "TOMATO", "C57", "C57BL/6",
    "编号", "小鼠编号", "耳标", "父母", "基因型", "品系", "生日", "DOB",
    "性别", "GENOTYPE 1", "GENOTYPE 2", "GENOTYPE 3", "操作记录", "备注",
    "TEST", "DEMO", "示例", "无耳标", "待", "待分笼", "待查", "无"
}

def is_valid_mouse_code(val: Any) -> bool:
    """
    Validate that a value is a legitimate mouse code/ear tag, and reject
    genotype test outcomes (HOM, HET, WT, etc.) and primer/gene/marker names
    (Aldh1l1-Cre, Ai148, 5XFAD, Camk-TTA, Ai93, Ai9, Trap2, etc.).
    """
    if val is None:
        return False
    s = str(val).strip()
    if not s or s in ["/", "-", "\\", "无", "nan", "None", "?", "？", "已测", "待测", "未知"]:
        return False
    if s.upper() in GENOTYPE_OUTCOME_STRINGS or s in GENOTYPE_OUTCOME_STRINGS:
        return False
    clean = re.sub(r'[\s_]+', '-', s.upper())
    if clean in INVALID_MOUSE_CODE_TERMS or s in INVALID_MOUSE_CODE_TERMS:
        return False
    if "/" in s:
        parts = [p.strip().upper().replace(" ", "-") for p in s.split("/")]
        if any(p in INVALID_MOUSE_CODE_TERMS or p in GENOTYPE_OUTCOME_STRINGS for p in parts):
            return False
    return True

def parse_date(val: Any) -> Optional[str]:
    """Parse various Excel date formats into YYYY-MM-DD"""
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s or s in ["/", "-", "无", "None", "nan"]:
        return None
    compact = re.fullmatch(r"\d{6}|\d{8}", s)
    if compact:
        year_digits = 4 if len(s) == 8 else 2
        year = int(s[:year_digits])
        if year_digits == 2:
            year += 2000
        try:
            return datetime.date(year, int(s[year_digits:year_digits + 2]), int(s[year_digits + 2:])).isoformat()
        except ValueError:
            return None
    s = s.replace("年", "-").replace("月", "-").replace("日", "").replace(".", "-").replace("/", "-")
    parts = s.split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000
            return datetime.date(y, m, d).isoformat()
        except ValueError:
            return None
    return s

def extract_mating_date(*values: Any) -> Optional[str]:
    """Extract compact or separated mating dates from observation/notes text."""
    pattern = re.compile(r"合笼(?:日期|时间)?\s*[：:]\s*(\d{6,8}|\d{2,4}[年./-]\d{1,2}[月./-]\d{1,2}日?)")
    for value in values:
        if value is None:
            continue
        match = pattern.search(str(value).strip())
        if match:
            parsed = parse_date(match.group(1))
            if parsed:
                return parsed
    return None

def merge_cage_observation(*values: Any) -> str:
    parts = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in parts:
            parts.append(text)
    return "\n".join(parts)

def parse_parent_genders(text: Any) -> List[Tuple[str, str]]:
    """
    Intelligently infer mouse ear tag and gender from parents expression.
    Example: 'E925M+E822F、E824F' -> [('E925', 'M'), ('E822', 'F'), ('E824', 'F')]
             'B311M+B354F、B362F' -> [('B311', 'M'), ('B354', 'F'), ('B362', 'F')]
    """
    if not text:
        return []
    cleaned = re.sub(r'[\(（].*?[\)）]', '', str(text).strip())
    parts = re.split(r'[+、/,，\s\\]+', cleaned)
    results = []
    for p in parts:
        p = p.strip()
        if not p or '无耳标' in p or '新品系' in p or '不明' in p:
            continue
        m = re.match(r'^([A-Za-z0-9_-]+?)([MFmf])$', p)
        if m:
            code = m.group(1).strip()
            gender = m.group(2).upper()
            if code.upper() not in ['HO', 'CAS', 'GF', 'BF', 'W', 'KO', 'T2']:
                results.append((code, gender))
    return results

def apply_inferred_parent_genders(db: Session, inferred_genders: Dict[str, str]) -> int:
    """Only supplement gender for mice that already have a real record."""
    updated_count = 0
    for code, inferred_gender in inferred_genders.items():
        mouse = db.query(Mouse).filter(Mouse.mouse_code == code).first()
        if mouse and (not mouse.gender or mouse.gender in ["未知", "None", ""]):
            mouse.gender = inferred_gender
            updated_count += 1
    return updated_count

def remove_inferred_parent_placeholders(db: Session) -> int:
    """Remove legacy mouse rows created only from a parent-code reference."""
    placeholders = db.query(Mouse).filter(
        Mouse.notes == INFERRED_PARENT_PLACEHOLDER_NOTE
    ).all()
    removed_count = 0
    for mouse in placeholders:
        has_real_record_data = any([
            mouse.strain,
            mouse.dob,
            mouse.parents,
            mouse.genotype_1,
            mouse.genotype_2,
            mouse.test_date,
            mouse.cage_id,
            mouse.owner_id,
            mouse.owner_name,
            mouse.claim_date,
            mouse.claim_purpose,
            mouse.source_room,
        ])
        if not has_real_record_data and mouse.status in [None, "", "在笼"]:
            db.delete(mouse)
            removed_count += 1
    return removed_count

def cleanup_synthetic_room_imports(db: Session) -> Dict[str, int]:
    """Remove current-colony records created from historical sheets with invented room names."""
    synthetic_cages = db.query(Cage).filter(Cage.room.in_(SYNTHETIC_IMPORT_ROOMS)).all()
    synthetic_cage_ids = [cage.id for cage in synthetic_cages]
    filters = [Mouse.source_room.in_(SYNTHETIC_IMPORT_ROOMS)]
    if synthetic_cage_ids:
        filters.append(Mouse.cage_id.in_(synthetic_cage_ids))

    affected_mice = db.query(Mouse).filter(or_(*filters)).all()
    removed_mice = 0
    archived_mice = 0
    for mouse in affected_mice:
        has_genotype_record = db.query(GenotypeRecord.id).filter(
            or_(
                GenotypeRecord.mouse_id == mouse.id,
                GenotypeRecord.mouse_code == mouse.mouse_code,
            )
        ).first() is not None
        has_assignment = any([
            mouse.owner_id,
            mouse.owner_name,
            mouse.claim_date,
            mouse.claim_purpose,
        ])
        is_historical_import_only = (
            mouse.source_room in SYNTHETIC_IMPORT_ROOMS
            and not has_genotype_record
            and not has_assignment
            and mouse.status in [None, "", "在笼", "繁育中"]
        )

        if is_historical_import_only:
            db.delete(mouse)
            removed_mice += 1
            continue

        mouse.cage_id = None
        if mouse.source_room in SYNTHETIC_IMPORT_ROOMS:
            mouse.source_room = None
        if not has_assignment and mouse.status in [None, "", "在笼", "繁育中"]:
            mouse.status = "出笼"
        archived_mice += 1

    db.flush()
    for cage in synthetic_cages:
        db.delete(cage)

    return {
        "removed_mice": removed_mice,
        "archived_mice": archived_mice,
        "removed_cages": len(synthetic_cages),
    }

def cleanup_invalid_genotype_mice(db: Session) -> Dict[str, int]:
    """
    Remove corrupted mice mistakenly created from genotype outcomes or marker names,
    delete their associated invalid genotype records, and ensure clean mouse code tracking.
    """
    all_mice = db.query(Mouse).all()
    invalid_mice = [m for m in all_mice if not is_valid_mouse_code(m.mouse_code)]
    cleaned_mice_count = len(invalid_mice)
    cleaned_gt_count = 0

    if invalid_mice:
        invalid_ids = [m.id for m in invalid_mice]
        invalid_codes = [m.mouse_code for m in invalid_mice]

        invalid_gt_records = db.query(GenotypeRecord).filter(
            or_(
                GenotypeRecord.mouse_id.in_(invalid_ids),
                GenotypeRecord.mouse_code.in_(invalid_codes)
            )
        ).all()
        cleaned_gt_count = len(invalid_gt_records)
        for gt in invalid_gt_records:
            db.delete(gt)

        for m in invalid_mice:
            db.delete(m)

        db.flush()

    # Also clean up any orphan genotype records where mouse_code is invalid
    all_gt = db.query(GenotypeRecord).all()
    for gt in all_gt:
        if not is_valid_mouse_code(gt.mouse_code):
            db.delete(gt)
            cleaned_gt_count += 1
    db.flush()

    return {
        "cleaned_mice": cleaned_mice_count,
        "cleaned_genotypes": cleaned_gt_count,
    }

def is_historical_reference_sheet(ws: openpyxl.worksheet.worksheet.Worksheet, name: str) -> bool:
    """Historical/reference sheets must not become current rooms, cages, or mice."""
    if name == "繁育小鼠" or "老鼠信息汇总" in name or "信息汇总" in name:
        return True
    if "基因鉴定" in name or "鉴定结果" in name:
        return False
    first_row = " ".join(str(cell.value) for cell in ws[1] if cell.value is not None)
    return all(header in first_row for header in ["基因", "编号", "性别", "生日"])

def get_or_create_claimer(db: Session, name: str, default_room: Optional[str] = None) -> Claimer:
    clean_name = str(name).strip()
    claimer = db.query(Claimer).filter(Claimer.name == clean_name).first()
    if not claimer:
        from backend.app.routers.claimers import pick_random_color
        color = pick_random_color(db)
        claimer = Claimer(name=clean_name, default_room=default_room, color=color)
        db.add(claimer)
        db.flush()
    return claimer

def get_or_create_cage(db: Session, cage_code: str, room: str, strain: str = "", gender: str = "M", **kwargs) -> Cage:
    clean_code = str(cage_code).strip()
    clean_room = str(room).strip()
    cage = db.query(Cage).filter(Cage.cage_code == clean_code, Cage.room == clean_room).first()
    if not cage:
        cage = Cage(
            cage_code=clean_code,
            room=clean_room,
            strain=str(strain).strip() if strain else "",
            gender=str(gender).strip() if gender else "M",
            **kwargs
        )
        db.add(cage)
        db.flush()
    else:
        if strain and not cage.strain:
            cage.strain = str(strain).strip()
        if gender and not cage.gender:
            cage.gender = str(gender).strip()
        for k, v in kwargs.items():
            if v and not getattr(cage, k, None):
                setattr(cage, k, v)
    return cage

def disambiguate_mouse_code(db: Session, code: str, cage_code: str, room: str, index: int) -> str:
    """Ensure mice without unique physical ear tags (e.g. '无耳标', 'C57') get distinct tracked codes"""
    candidate = str(code).strip()
    if any(k in candidate.upper() for k in ["无耳标", "待", "C57", "WT", "野生", "纯合", "杂合", "未知"]) or candidate in ["F", "M", "未知"]:
        candidate = f"{candidate}_{room}_{cage_code}_{index}"
    
    base_candidate = candidate
    counter = 1
    while db.query(Mouse).filter(Mouse.mouse_code == candidate).first():
        counter += 1
        candidate = f"{base_candidate}_{counter}"
    return candidate

def split_mouse_codes(raw_val: Any) -> List[str]:
    """Split comma / 顿号 / semicolon / space separated mouse codes"""
    if raw_val is None:
        return []
    s = str(raw_val).strip()
    if not s or s in ["/", "无", "nan", "None", "-"]:
        return []
    if "无耳标" in s or "待" in s:
        return [s]
    parts = re.split(r'[,，、;\s/]+', s)
    res = [p.strip() for p in parts if p.strip() and p.strip() not in ["/", "无", "nan", "None", "-"]]
    return res if res else [s]

def import_workbook(db: Session, wb: openpyxl.Workbook, results: Dict[str, Any], inferred_genders: Dict[str, str], file_label: str = ""):
    """Intelligently detect sheets in workbook and import them into database"""
    sheetnames = wb.sheetnames
    processed_sheets = set()

    # These sheets are historical/reference material without a real current room.
    # Mark them as processed so they cannot fall through to a generic current-mouse import.
    for name in sheetnames:
        if is_historical_reference_sheet(wb[name], name):
            processed_sheets.add(name)

    # 1. Sheet '小鼠档案'
    for name in sheetnames:
        if name == "小鼠档案":
            processed_sheets.add(name)
            ws = wb[name]
            header_row = [str(c).strip() if c is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), [])]
            code_col = next((i for i, h in enumerate(header_row) if "编号" in h or "耳标" in h or "小鼠编号" in h), 5)
            strain_col = next((i for i, h in enumerate(header_row) if h in ["基因型", "品系", "基因"] or ("品系" in h and "编号" not in h)), 1)
            dob_col = next((i for i, h in enumerate(header_row) if "DOB" in h.upper() or "生日" in h or "出生" in h), 2)
            gender_col = next((i for i, h in enumerate(header_row) if "性别" in h), 3)
            parents_col = next((i for i, h in enumerate(header_row) if "父母" in h or "亲代" in h), 4)
            g1_col = next((i for i, h in enumerate(header_row) if "GENOTYPE 1" in h.upper() or "基因型1" in h), 6)
            g2_col = next((i for i, h in enumerate(header_row) if "GENOTYPE 2" in h.upper() or "基因型2" in h), 7)
            op_col = next((i for i, h in enumerate(header_row) if "操作" in h), 8)
            notes_col = next((i for i, h in enumerate(header_row) if "备注" in h), 9)
            date_col = next((i for i, h in enumerate(header_row) if "测试日期" in h or h == "日期"), 0)

            for row in ws.iter_rows(min_row=2, values_only=True):
                try:
                    code_raw = row[code_col] if len(row) > code_col else None
                    if code_raw is None: continue
                    code = str(code_raw).strip()
                    if not code or not is_valid_mouse_code(code): continue

                    mouse = db.query(Mouse).filter(Mouse.mouse_code == code).first()
                    strain = normalize_strain_name(db, row[strain_col]) if len(row) > strain_col and row[strain_col] else ""
                    dob = parse_date(row[dob_col]) if len(row) > dob_col else None
                    gender = str(row[gender_col]).strip() if len(row) > gender_col and row[gender_col] else "未知"
                    parents = str(row[parents_col]).strip() if len(row) > parents_col and row[parents_col] else ""
                    g1 = str(row[g1_col]).strip() if len(row) > g1_col and row[g1_col] else ""
                    g2 = str(row[g2_col]).strip() if len(row) > g2_col and row[g2_col] else ""
                    op_rec = str(row[op_col]).strip() if len(row) > op_col and row[op_col] else ""
                    notes = str(row[notes_col]).strip() if len(row) > notes_col and row[notes_col] else ""
                    test_date = parse_date(row[date_col]) if len(row) > date_col else None

                    if parents:
                        for p_code, p_gender in parse_parent_genders(parents):
                            inferred_genders[p_code] = p_gender

                    status = "在笼"
                    if "死亡" in op_rec or "死亡" in notes:
                        status = "死亡"
                    elif "抽检" in op_rec:
                        status = "待鉴定"

                    if not mouse:
                        mouse = Mouse(
                            mouse_code=code,
                            strain=strain,
                            gender=gender,
                            dob=dob,
                            parents=parents,
                            genotype_1=g1,
                            genotype_2=g2,
                            test_date=test_date,
                            status=status,
                            source_room="江湾发育所",
                            notes=(f"{op_rec} {notes}").strip()
                        )
                        db.add(mouse)
                        results["mice_imported"] += 1
                    else:
                        if strain and not mouse.strain: mouse.strain = strain
                        if dob and not mouse.dob: mouse.dob = dob
                        if gender and mouse.gender == "未知": mouse.gender = gender
                        if g1 and not mouse.genotype_1: mouse.genotype_1 = g1
                        if g2 and not mouse.genotype_2: mouse.genotype_2 = g2
                        if not mouse.source_room: mouse.source_room = "江湾发育所"
                except Exception as e:
                    results["errors"].append(f"小鼠档案行解析错误: {str(e)}")
            db.flush()

    # 2. Sheet '小鼠笼位信息'
    for name in sheetnames:
        if name == "小鼠笼位信息":
            processed_sheets.add(name)
            ws_cage = wb[name]
            for row in ws_cage.iter_rows(min_row=2, values_only=True):
                try:
                    cage_raw = row[0] if len(row) > 0 else None
                    if not cage_raw: continue
                    cage_code = str(cage_raw).strip()
                    strain = normalize_strain_name(db, row[1]) if len(row) > 1 and row[1] else ""
                    gender = str(row[3]).strip() if len(row) > 3 and row[3] else "M"
                    dob = parse_date(row[10]) if len(row) > 10 else None
                    obs = str(row[11]).strip() if len(row) > 11 and row[11] else ""
                    notes = str(row[12]).strip() if len(row) > 12 and row[12] else ""

                    cage = get_or_create_cage(
                        db, cage_code=cage_code, room="江湾发育所",
                        strain=strain, gender=gender, observation=merge_cage_observation(obs, notes), notes=notes,
                        mating_date=extract_mating_date(obs, notes)
                    )
                    results["cages_imported"] += 1

                    for idx, c in enumerate(row[4:10]):
                        if c is not None and str(c).strip():
                            m_code = str(c).strip()
                            mouse = db.query(Mouse).filter(Mouse.mouse_code == m_code).first()
                            if not mouse:
                                prefix = f"{m_code}_江湾_{cage_code}_{idx+1}"
                                existing_in_cage = db.query(Mouse).filter(
                                    Mouse.cage_id == cage.id,
                                    Mouse.mouse_code.like(f"{prefix}%")
                                ).first()
                                if existing_in_cage:
                                    mouse = existing_in_cage
                                else:
                                    final_code = disambiguate_mouse_code(db, m_code, cage_code, "江湾", idx+1)
                                    mouse = Mouse(
                                        mouse_code=final_code,
                                        strain=strain,
                                        gender=gender,
                                        dob=dob,
                                        cage_id=cage.id,
                                        source_room="江湾发育所",
                                        status="在笼"
                                    )
                                    db.add(mouse)
                                    results["mice_imported"] += 1
                            else:
                                mouse.cage_id = cage.id
                                if not mouse.dob and dob: mouse.dob = dob
                                if not mouse.strain and strain: mouse.strain = strain
                except Exception as e:
                    db.rollback()
                    results["errors"].append(f"小鼠笼位信息解析错误: {str(e)}")
            db.flush()

    # 3. Sheet '基因鉴定结果2306' or matching '基因鉴定'
    for name in sheetnames:
        if "基因鉴定" in name or "鉴定结果" in name:
            processed_sheets.add(name)
            ws_gt = wb[name]
            header_row = [str(c).strip() if c is not None else "" for c in next(ws_gt.iter_rows(min_row=1, max_row=1, values_only=True), [])]

            def find_idx(predicate):
                for i, h in enumerate(header_row):
                    if predicate(h): return i
                return None

            date_col = find_idx(lambda h: "测试日期" in h or h == "日期")
            code_col = find_idx(lambda h: "编号" in h or "耳标" in h or "小鼠编号" in h)
            strain_col = find_idx(lambda h: h in ["基因型", "品系", "基因"] or ("品系" in h and "编号" not in h))
            dob_col = find_idx(lambda h: "DOB" in h.upper() or "生日" in h or "出生" in h)
            gender_col = find_idx(lambda h: "性别" in h)
            parents_col = find_idx(lambda h: "父母" in h or "亲代" in h)
            g1_col = find_idx(lambda h: "GENOTYPE 1" in h.upper() or "基因型1" in h or h.upper() == "GENOTYPE1")
            g2_col = find_idx(lambda h: "GENOTYPE 2" in h.upper() or "基因型2" in h or h.upper() == "GENOTYPE2")
            g3_col = find_idx(lambda h: "GENOTYPE 3" in h.upper() or "基因型3" in h or h.upper() == "GENOTYPE3")
            op_col = find_idx(lambda h: "操作" in h)
            notes_col = find_idx(lambda h: "备注" in h)

            current_date = None
            current_strain = ""
            current_dob = None

            for row in ws_gt.iter_rows(min_row=2, values_only=True):
                try:
                    # Update date if present in date_col
                    raw_date = row[date_col] if date_col is not None and len(row) > date_col else None
                    parsed_d = parse_date(raw_date)
                    if parsed_d:
                        current_date = parsed_d
                        current_strain = ""
                        current_dob = None

                    # Update strain if present in strain_col
                    raw_strain = row[strain_col] if strain_col is not None and len(row) > strain_col else None
                    if raw_strain and str(raw_strain).strip() and not is_valid_mouse_code(str(raw_strain).strip()):
                        current_strain = normalize_strain_name(db, raw_strain)

                    # Update DOB if present in dob_col
                    raw_dob = row[dob_col] if dob_col is not None and len(row) > dob_col else None
                    parsed_dob = parse_date(raw_dob)
                    if parsed_dob:
                        current_dob = parsed_dob

                    # Check mouse code
                    code_raw = row[code_col] if code_col is not None and len(row) > code_col else None
                    if not code_raw:
                        continue

                    m_code = str(code_raw).strip()
                    if not is_valid_mouse_code(m_code):
                        continue

                    test_date = parsed_d or current_date
                    strain = current_strain
                    dob = parsed_dob or current_dob
                    gender = str(row[gender_col]).strip() if gender_col is not None and len(row) > gender_col and row[gender_col] else None
                    parents = str(row[parents_col]).strip() if parents_col is not None and len(row) > parents_col and row[parents_col] and str(row[parents_col]).strip() != m_code else ""

                    if parents:
                        for p_code, p_gender in parse_parent_genders(parents):
                            inferred_genders[p_code] = p_gender

                    g1 = str(row[g1_col]).strip() if g1_col is not None and len(row) > g1_col and row[g1_col] is not None else None
                    if g1 in ["", "/", "-", "无", "None", "nan"]: g1 = None
                    g2 = str(row[g2_col]).strip() if g2_col is not None and len(row) > g2_col and row[g2_col] is not None else None
                    if g2 in ["", "/", "-", "无", "None", "nan"]: g2 = None
                    g3 = str(row[g3_col]).strip() if g3_col is not None and len(row) > g3_col and row[g3_col] is not None else None
                    if g3 in ["", "/", "-", "无", "None", "nan"]: g3 = None

                    op_rec = str(row[op_col]).strip() if op_col is not None and len(row) > op_col and row[op_col] is not None else None
                    notes = str(row[notes_col]).strip() if notes_col is not None and len(row) > notes_col and row[notes_col] is not None else None

                    mouse = db.query(Mouse).filter(Mouse.mouse_code == m_code).first()
                    if not mouse:
                        mouse = Mouse(
                            mouse_code=m_code,
                            strain=strain,
                            gender=gender or "未知",
                            dob=dob,
                            parents=parents,
                            genotype_1=g1,
                            genotype_2=g2,
                            test_date=test_date,
                            status="在笼"
                        )
                        db.add(mouse)
                        db.flush()
                        results["mice_imported"] += 1
                    else:
                        if gender and mouse.gender in ["未知", None, ""]: mouse.gender = gender
                        if not mouse.genotype_1 and g1: mouse.genotype_1 = g1
                        if not mouse.genotype_2 and g2: mouse.genotype_2 = g2
                        if not mouse.parents and parents: mouse.parents = parents
                        if not mouse.test_date and test_date: mouse.test_date = test_date
                        if not mouse.dob and dob: mouse.dob = dob
                        if not mouse.strain and strain: mouse.strain = strain

                    existing_gt = db.query(GenotypeRecord).filter(
                        GenotypeRecord.mouse_code == m_code,
                        GenotypeRecord.test_date == test_date,
                        GenotypeRecord.genotype_1 == g1,
                        GenotypeRecord.genotype_2 == g2
                    ).first()
                    if not existing_gt:
                        gt_record = GenotypeRecord(
                            mouse_code=m_code,
                            mouse_id=mouse.id,
                            test_date=test_date,
                            strain=strain,
                            dob=dob,
                            gender=gender,
                            parents=parents,
                            genotype_1=g1,
                            genotype_2=g2,
                            genotype_3=g3,
                            op_record=op_rec,
                            notes=notes
                        )
                        db.add(gt_record)
                        results["genotypes_imported"] += 1
                except Exception as e:
                    results["errors"].append(f"基因鉴定行解析错误: {str(e)}")
            db.flush()

    # 4. Sheet '东四小鼠信息105-实时更新' or matching '东四'
    for name in sheetnames:
        if "东四" in name:
            processed_sheets.add(name)
            ws_ds = wb[name]
            for row in ws_ds.iter_rows(min_row=2, values_only=True):
                try:
                    cage_raw = row[1] if len(row) > 1 else None
                    if not cage_raw: continue
                    cage_code = str(cage_raw).strip()
                    room_no = str(row[0]).strip() if len(row) > 0 and row[0] else "105"
                    room = f"东四{room_no}"
                    strain = normalize_strain_name(db, row[2]) if len(row) > 2 and row[2] else ""
                    gender = str(row[4]).strip() if len(row) > 4 and row[4] else "M"
                    dob = parse_date(row[10]) if len(row) > 10 else None
                    owner_raw = row[11] if len(row) > 11 else None
                    notes = str(row[12]).strip() if len(row) > 12 and row[12] else ""

                    owner = None
                    if owner_raw and str(owner_raw).strip():
                        owner_name = str(owner_raw).strip()
                        owner = get_or_create_claimer(db, name=owner_name, default_room=room)
                        results["claimers_imported"] += 1

                    cage = get_or_create_cage(
                        db, cage_code=cage_code, room=room,
                        strain=strain, gender=gender, observation=merge_cage_observation(notes), notes=notes,
                        mating_date=extract_mating_date(notes)
                    )
                    results["cages_imported"] += 1

                    for idx, c in enumerate(row[5:10]):
                        if c is not None and str(c).strip():
                            m_code = str(c).strip()
                            mouse = db.query(Mouse).filter(Mouse.mouse_code == m_code).first()
                            if not mouse:
                                prefix = f"{m_code}_{room}_{cage_code}_{idx+1}"
                                existing_in_cage = db.query(Mouse).filter(
                                    Mouse.cage_id == cage.id,
                                    Mouse.mouse_code.like(f"{prefix}%")
                                ).first()
                                if existing_in_cage:
                                    mouse = existing_in_cage
                                else:
                                    final_code = disambiguate_mouse_code(db, m_code, cage_code, "东四", idx+1)
                                    mouse = Mouse(
                                        mouse_code=final_code,
                                        strain=strain,
                                        gender=gender,
                                        dob=dob,
                                        cage_id=cage.id,
                                        owner_id=owner.id if owner else None,
                                        owner_name=owner.name if owner else None,
                                        status="已领用" if owner else "在笼",
                                        source_room=room
                                    )
                                    db.add(mouse)
                                    results["mice_imported"] += 1
                            else:
                                mouse.cage_id = cage.id
                                if owner:
                                    mouse.owner_id = owner.id
                                    mouse.owner_name = owner.name
                                    mouse.status = "已领用"
                except Exception as e:
                    db.rollback()
                    results["errors"].append(f"东四信息解析错误: {str(e)}")
            db.flush()

    # 5. Sheet '实验动物楼小鼠信息405B-实时更新' or matching '405B'
    for name in sheetnames:
        if "405B" in name or "实验动物楼" in name:
            processed_sheets.add(name)
            ws_405 = wb[name]
            for row in ws_405.iter_rows(min_row=2, values_only=True):
                try:
                    cage_raw = row[0] if len(row) > 0 else None
                    if not cage_raw: continue
                    cage_code = str(cage_raw).strip()
                    strain = normalize_strain_name(db, row[1]) if len(row) > 1 and row[1] else ""
                    gender = str(row[3]).strip() if len(row) > 3 and row[3] else "M"
                    obs = str(row[14]).strip() if len(row) > 14 and row[14] else ""
                    notes = str(row[15]).strip() if len(row) > 15 and row[15] else ""
                    dob = parse_date(row[13]) if len(row) > 13 else None

                    mating_date = extract_mating_date(obs, notes)

                    cage = get_or_create_cage(
                        db, cage_code=cage_code, room="实验动物楼405B",
                        strain=strain, gender=gender, observation=merge_cage_observation(obs, notes), notes=notes,
                        mating_date=mating_date
                    )
                    results["cages_imported"] += 1

                    for idx, c in enumerate(row[4:13]):
                        if c is not None and str(c).strip():
                            m_code = str(c).strip()
                            mouse = db.query(Mouse).filter(Mouse.mouse_code == m_code).first()
                            if not mouse:
                                prefix = f"{m_code}_405B_{cage_code}_{idx+1}"
                                existing_in_cage = db.query(Mouse).filter(
                                    Mouse.cage_id == cage.id,
                                    Mouse.mouse_code.like(f"{prefix}%")
                                ).first()
                                if existing_in_cage:
                                    mouse = existing_in_cage
                                else:
                                    final_code = disambiguate_mouse_code(db, m_code, cage_code, "405B", idx+1)
                                    mouse = Mouse(
                                        mouse_code=final_code,
                                        strain=strain,
                                        gender=gender,
                                        dob=dob,
                                        cage_id=cage.id,
                                        source_room="实验动物楼405B",
                                        status="繁育中" if mating_date else "在笼"
                                    )
                                    db.add(mouse)
                                    results["mice_imported"] += 1
                            else:
                                mouse.cage_id = cage.id
                except Exception as e:
                    db.rollback()
                    results["errors"].append(f"405B信息解析错误: {str(e)}")
            db.flush()

    # 6. Sheet '转鼠需求及反馈表' or matching '转鼠'
    for name in sheetnames:
        if "转鼠" in name:
            processed_sheets.add(name)
            ws_tr = wb[name]
            for row in ws_tr.iter_rows(min_row=3, values_only=True):
                try:
                    claimer_raw = row[2] if len(row) > 2 else None
                    if not claimer_raw: continue
                    claimer_name = str(claimer_raw).strip()
                    if not claimer_name or claimer_name in ["示例", "无"]: continue

                    claimer = get_or_create_claimer(db, claimer_name, default_room=str(row[5]).strip() if len(row) > 5 and row[5] else None)
                    results["claimers_imported"] += 1

                    seq_val = str(row[0]).strip() if row[0] is not None else ""
                    date_str = parse_date(row[1]) if len(row) > 1 else ""
                    strain = normalize_strain_name(db, row[3]) if len(row) > 3 and row[3] else ""
                    age_gender_req = str(row[4]).strip() if len(row) > 4 and row[4] else "成年/无要求"
                    in_room = str(row[5]).strip() if len(row) > 5 and row[5] else ""
                    cage_cnt = 1
                    try:
                        if len(row) > 6 and row[6] is not None:
                            cage_cnt = int(row[6])
                    except Exception:
                        pass
                    out_room = str(row[7]).strip() if len(row) > 7 and row[7] else ""
                    m_gender = str(row[8]).strip() if len(row) > 8 and row[8] else ""
                    
                    codes = []
                    for c in row[9:20]:
                        if c is not None:
                            val = str(c).strip()
                            if val and val not in ["已转", "取消", "无", "已完成"]:
                                codes.append(val)

                    status = "已转"
                    row_str = " ".join([str(c) for c in row if c])
                    if "取消" in row_str:
                        status = "取消"
                    elif not codes and "已转" not in row_str:
                        status = "申请中"

                    feedback_notes = str(row[15]).strip() if len(row) > 15 and row[15] else ""

                    tr_req = TransferRequest(
                        seq=seq_val,
                        request_date=date_str or datetime.date.today().strftime("%Y-%m-%d"),
                        demander=claimer_name,
                        strain=strain,
                        age_gender_req=age_gender_req,
                        target_room=in_room,
                        cage_count=cage_cnt,
                        source_room=out_room,
                        mouse_gender=m_gender,
                        mouse_codes=", ".join(codes),
                        status=status,
                        feedback=feedback_notes,
                        handler="系统导入"
                    )
                    db.add(tr_req)
                    results["transfer_requests_imported"] += 1

                    if codes:
                        log = TransferLog(
                            action_type="转鼠/领用",
                            mouse_codes=", ".join(codes),
                            mouse_count=len(codes),
                            claimer_name=claimer_name,
                            source_room=out_room,
                            target_room=in_room,
                            date=date_str or "",
                            status=status,
                            notes=f"品系: {strain}; 要求: {age_gender_req}"
                        )
                        db.add(log)
                        results["transfers_imported"] += 1

                        if status == "已转":
                            for code in codes:
                                mouse = db.query(Mouse).filter(Mouse.mouse_code == code).first()
                                if mouse and not mouse.owner_id:
                                    mouse.owner_id = claimer.id
                                    mouse.owner_name = claimer.name
                                    mouse.status = "已领用"
                                    mouse.claim_date = date_str
                except Exception as e:
                    results["errors"].append(f"转鼠申请行解析错误: {str(e)}")
            db.flush()

    # 7. Sheet '引物总表' or matching '引物'
    for name in sheetnames:
        if "引物" in name:
            processed_sheets.add(name)
            ws_pm = wb[name]
            for row in ws_pm.iter_rows(min_row=2, values_only=True):
                try:
                    strain_short = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                    seq = str(row[7]).strip() if len(row) > 7 and row[7] else ""
                    if not strain_short and not seq: continue
                    
                    p_no = None
                    try:
                        if row[0] is not None: p_no = int(row[0])
                    except (ValueError, TypeError):
                        pass

                    strain_full = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                    source = str(row[4]).strip() if len(row) > 4 and row[4] else ""
                    gene_type = str(row[5]).strip() if len(row) > 5 and row[5] else ""
                    band = str(row[8]).strip() if len(row) > 8 and row[8] else ""
                    url = str(row[9]).strip() if len(row) > 9 and row[9] else ""

                    existing = db.query(Primer).filter(Primer.sequence == seq, Primer.strain_short == strain_short).first()
                    if not existing:
                        primer = Primer(
                            primer_no=p_no,
                            strain_short=strain_short,
                            strain_full=strain_full,
                            source=source,
                            gene_type=gene_type,
                            sequence=seq,
                            band_size=band,
                            url=url
                        )
                        db.add(primer)
                        results["primers_imported"] += 1
                except Exception as e:
                    results["errors"].append(f"引物行解析错误: {str(e)}")
            db.flush()

    # Historical breeding, old summary, and strain-reference sheets were already
    # marked as processed above. They are intentionally excluded from current-colony data.

    # 8. Generic Sheet Fallback
    for name in sheetnames:
        if name in processed_sheets:
            continue
        ws = wb[name]
        first_row = [str(c.value) for c in ws[1] if c.value is not None]
        first_row_str = " ".join(first_row)

        if "编号" in first_row_str and ("品系" in first_row_str or "基因" in first_row_str):
            processed_sheets.add(name)
            code_col = next((i for i, c in enumerate(ws[1]) if c.value and "编号" in str(c.value)), None)
            strain_col = next((i for i, c in enumerate(ws[1]) if c.value and ("品系" in str(c.value) or "基因" in str(c.value))), None)
            gender_col = next((i for i, c in enumerate(ws[1]) if c.value and "性别" in str(c.value)), None)
            dob_col = next((i for i, c in enumerate(ws[1]) if c.value and ("DOB" in str(c.value) or "出生" in str(c.value) or "生日" in str(c.value))), None)
            owner_col = next((i for i, c in enumerate(ws[1]) if c.value and ("拥有者" in str(c.value) or "领取" in str(c.value) or "责任人" in str(c.value))), None)
            parents_col = next((i for i, c in enumerate(ws[1]) if c.value and "父母" in str(c.value)), None)

            for r in ws.iter_rows(min_row=2, values_only=True):
                try:
                    if code_col is not None and len(r) > code_col and r[code_col]:
                        raw_codes = split_mouse_codes(r[code_col])
                        raw_strain = str(r[strain_col]).strip() if strain_col is not None and len(r) > strain_col and r[strain_col] else ""
                        strain = normalize_strain_name(db, raw_strain)
                        gender = str(r[gender_col]).strip() if gender_col is not None and len(r) > gender_col and r[gender_col] else "未知"
                        dob = parse_date(r[dob_col]) if dob_col is not None and len(r) > dob_col else None
                        parents = str(r[parents_col]).strip() if parents_col is not None and len(r) > parents_col and r[parents_col] else ""
                        owner_name = str(r[owner_col]).strip() if owner_col is not None and len(r) > owner_col and r[owner_col] else None

                        if parents:
                            for p_code, p_gender in parse_parent_genders(parents):
                                inferred_genders[p_code] = p_gender

                        owner_id = None
                        if owner_name:
                            cl = get_or_create_claimer(db, owner_name)
                            owner_id = cl.id
                            results["claimers_imported"] += 1

                        for idx, code in enumerate(raw_codes):
                            if not is_valid_mouse_code(code) and not any(k in code.upper() for k in ["无耳标", "待"]):
                                continue
                            final_code = disambiguate_mouse_code(db, code, "常规", "常规鼠房", idx+1) if (any(k in code.upper() for k in ["无耳标", "待", "C57", "WT", "野生", "纯合", "杂合", "未知"]) or code in ["F", "M", "未知"]) else code
                            existing = db.query(Mouse).filter(Mouse.mouse_code == final_code).first()
                            if not existing:
                                m = Mouse(
                                    mouse_code=final_code,
                                    strain=strain,
                                    gender=gender,
                                    dob=dob,
                                    parents=parents,
                                    owner_id=owner_id,
                                    owner_name=owner_name,
                                    status="已领用" if owner_id else "在笼"
                                )
                                db.add(m)
                                db.flush()
                                results["mice_imported"] += 1
                            else:
                                if not existing.strain and strain: existing.strain = strain
                                if not existing.dob and dob: existing.dob = dob
                                if not existing.parents and parents: existing.parents = parents
                                if owner_id and not existing.owner_id:
                                    existing.owner_id = owner_id
                                    existing.owner_name = owner_name
                                    existing.status = "已领用"
                except Exception as e:
                    db.rollback()
                    results["errors"].append(f"表格 {name} 行解析错误: {str(e)}")
            db.flush()

def normalize_cage_statuses(db: Session) -> int:
    """Reconcile status only after all cage and historical sheets have been merged."""
    db.flush()
    mice = db.query(Mouse).filter(Mouse.cage_id.is_(None)).all()
    changed = 0
    for mouse in mice:
        if mouse.status != "出笼":
            mouse.status = "出笼"
            changed += 1
    for mouse in db.query(Mouse).filter(Mouse.cage_id.isnot(None), Mouse.status == "出笼").all():
        mouse.status = "已领用" if mouse.owner_id or mouse.owner_name else "在笼"
    sync_euthanasia_owner(db)
    return changed


def import_single_excel_file(db: Session, file_path: str, original_filename: str = "") -> Dict[str, Any]:
    """Import a single uploaded Excel file"""
    results = {
        "mice_imported": 0,
        "cages_imported": 0,
        "claimers_imported": 0,
        "transfers_imported": 0,
        "transfer_requests_imported": 0,
        "genotypes_imported": 0,
        "inferred_genders_count": 0,
        "primers_imported": 0,
        "errors": []
    }
    inferred_genders: Dict[str, str] = {}
    label = original_filename or os.path.basename(file_path)

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        import_workbook(db, wb, results, inferred_genders, label)
    except Exception as e:
        results["errors"].append(f"{label} 加载失败: {str(e)}")

    results["inferred_genders_count"] += apply_inferred_parent_genders(db, inferred_genders)
    remove_inferred_parent_placeholders(db)
    cleanup_synthetic_room_imports(db)
    cleanup_invalid_genotype_mice(db)
    results["out_of_cage_updated"] = normalize_cage_statuses(db)

    db.commit()
    return results

def import_local_excel_folder(db: Session, folder_path: str) -> Dict[str, Any]:
    """Import all Excel files from the given folder"""
    results = {
        "mice_imported": 0,
        "cages_imported": 0,
        "claimers_imported": 0,
        "transfers_imported": 0,
        "transfer_requests_imported": 0,
        "genotypes_imported": 0,
        "inferred_genders_count": 0,
        "primers_imported": 0,
        "errors": []
    }
    inferred_genders: Dict[str, str] = {}

    file_jw = os.path.join(folder_path, "0-江湾发育所小鼠档案.xlsx")
    if os.path.exists(file_jw):
        try:
            wb_jw = openpyxl.load_workbook(file_jw, data_only=True)
            import_workbook(db, wb_jw, results, inferred_genders, "0-江湾发育所小鼠档案.xlsx")
        except Exception as e:
            results["errors"].append(f"0-江湾发育所小鼠档案解析失败: {str(e)}")

    primer_files = sorted(
        name for name in os.listdir(folder_path)
        if name.lower().endswith(".xlsx") and "primer" in name.lower()
    )
    if primer_files:
        primer_name = primer_files[0]
        file_primer = os.path.join(folder_path, primer_name)
        try:
            wb_p = openpyxl.load_workbook(file_primer, data_only=True)
            import_workbook(db, wb_p, results, inferred_genders, primer_name)
        except Exception as e:
            results["errors"].append(f"{primer_name}解析失败: {str(e)}")

    results["inferred_genders_count"] += apply_inferred_parent_genders(db, inferred_genders)
    remove_inferred_parent_placeholders(db)
    cleanup_synthetic_room_imports(db)
    cleanup_invalid_genotype_mice(db)
    results["out_of_cage_updated"] = normalize_cage_statuses(db)

    db.commit()
    return results
