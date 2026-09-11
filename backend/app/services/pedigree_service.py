import re
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.models import Mouse

SPECIAL_TEXTS = {
    '新品系引入', '外购', '无', '不明', '不详', '集萃',
    '常州卡文斯', '邓娟组', '/', '-', '无耳标'
}

def parse_parents_detail(db: Session, parents_str: Optional[str]) -> Dict[str, Any]:
    """
    Parse a parents string (e.g. 'E925+E822' or 'E925M+E822F、E824F' or 'D022, D023'),
    look up mouse genders in the database for ear tags without explicit M/F suffix,
    and format the canonical pedigree representation.
    """
    if not parents_str:
        return {
            "raw": parents_str or "",
            "normalized": parents_str or "",
            "has_changes": False,
            "details": []
        }

    text = str(parents_str).strip()
    if not text:
        return {
            "raw": "",
            "normalized": "",
            "has_changes": False,
            "details": []
        }

    for spec in SPECIAL_TEXTS:
        if spec in text:
            return {
                "raw": text,
                "normalized": text,
                "has_changes": False,
                "details": []
            }

    # Split by delimiters: +, 、, ,, ，, space, /, \
    raw_tokens = [p.strip() for p in re.split(r'[+、/,，\s\\]+', text) if p.strip()]
    if not raw_tokens:
        return {
            "raw": text,
            "normalized": text,
            "has_changes": False,
            "details": []
        }

    parsed_info: List[Dict[str, Any]] = []

    for t in raw_tokens:
        if t in SPECIAL_TEXTS or t in ['无', '新品系', '不明', '不详', '集萃', '外购']:
            parsed_info.append({
                "raw": t,
                "code": t,
                "gender": None,
                "found": False,
                "role": "parent"
            })
            continue

        # 1. Check if token already ends with M/F (e.g. E925M, E822F, 111F)
        mf_match = re.match(r'^([A-Za-z0-9_-]+?)([MFmf])$', t)
        if mf_match and mf_match.group(1).upper() not in ['HO', 'KO', 'CAS', 'GF', 'BF', 'WT']:
            code = mf_match.group(1).strip()
            gender = mf_match.group(2).upper()
            # Canonicalize mouse code case if found in DB
            db_mouse = db.query(Mouse).filter(Mouse.mouse_code.ilike(code)).first()
            if db_mouse:
                code = db_mouse.mouse_code
                if not gender and db_mouse.gender in ['M', 'F']:
                    gender = db_mouse.gender
            parsed_info.append({
                "raw": t,
                "code": code,
                "gender": gender,
                "found": bool(db_mouse),
                "role": "father" if gender == "M" else ("mother" if gender == "F" else "parent")
            })
            continue

        # 2. Token without suffix (e.g. E925, D022) -> Look up in DB
        db_mouse = db.query(Mouse).filter(Mouse.mouse_code.ilike(t)).first()
        if db_mouse and db_mouse.gender in ['M', 'F']:
            gender = db_mouse.gender
            parsed_info.append({
                "raw": t,
                "code": db_mouse.mouse_code,
                "gender": gender,
                "found": True,
                "role": "father" if gender == "M" else "mother"
            })
        else:
            parsed_info.append({
                "raw": t,
                "code": t,
                "gender": None,
                "found": False,
                "role": "parent"
            })

    # Assemble canonical pedigree format: <Father>M + <Mother1>F、<Mother2>F + <Unknown>
    males = [p for p in parsed_info if p["gender"] == "M"]
    females = [p for p in parsed_info if p["gender"] == "F"]
    unknowns = [p for p in parsed_info if p["gender"] is None]

    if males or females:
        components = []
        if males:
            components.append("、".join([f"{m['code']}M" for m in males]))
        if females:
            components.append("、".join([f"{f['code']}F" for f in females]))
        if unknowns:
            components.append("、".join([u['code'] for u in unknowns]))
        normalized = "+".join(components)
    else:
        normalized = text

    return {
        "raw": text,
        "normalized": normalized,
        "has_changes": normalized != text,
        "details": parsed_info
    }

def normalize_parents_pedigree(db: Session, parents_str: Optional[str]) -> Optional[str]:
    """
    Returns the normalized canonical parents pedigree string.
    """
    if not parents_str:
        return parents_str
    result = parse_parents_detail(db, parents_str)
    return result["normalized"]
