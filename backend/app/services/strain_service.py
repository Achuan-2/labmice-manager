from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.models import Strain, Mouse, Cage, GenotypeRecord

# Canonical laboratory nomenclature mappings for case merging
CANONICAL_STRAIN_MAP = {
    "5fad": "5xFAD",
    "5xfad": "5xFAD",
    "ras-n/ai93": "Ras-N/Ai93",
    "rasgrf2-t2a-dcre": "Rasgrf2-T2A-dCre",
    "teto-gcamp6s": "tetO-GCaMP6s",
    "pv-cre": "PV-cre",
    "pv-cre/ai148": "PV-cre/Ai148",
    "aldh1l1-cre": "Aldh1l1-Cre",
    "aldh1l1-cre/ ai148": "Aldh1l1-Cre/Ai148",
    "aldh1l1-cre/ai148": "Aldh1l1-Cre/Ai148",
    "ai148/aldh1l1-cre": "Ai148/Aldh1l1-Cre",
    "trap2/ai9": "Trap2/Ai9",
    "bfp/trap2": "BFP/Trap2",
    "camk2a-tta": "Camk2a-tTA",
    "camk2a-tta/teto": "Camk2a-tTA/teto",
    "camk2a/teto": "Camk2a/teto",
    "pemt-ko cas9": "Pemt-KO CAS9",
    "pemt-ko/5xfad": "Pemt-KO/5xFAD",
    "jax-5xfad": "JAX-5XFAD-J",
    "jax-5xfad-j": "JAX-5XFAD-J",
    "cas9&5xfad": "Cas9&5xFAD",
    "cas9": "Cas9",
    "bxb1&psen1-es": "BXB1&PSEN1-ES",
    "psen1-fs": "PSEN1-FS",
    "gjc1-flox": "Gjc1-flox",
    "pdyn-cre": "Pdyn-Cre",
    "pdyn/ai148": "Pdyn/Ai148",
}

def get_or_create_strain_record(db: Session, target_name: str) -> Strain:
    """Safely get or create a Strain record without IntegrityError on unique name constraint"""
    target_name = target_name.strip()
    # 1. Exact match
    s = db.query(Strain).filter(Strain.name == target_name).first()
    if s:
        return s
    # 2. Case-insensitive match
    s = db.query(Strain).filter(func.lower(Strain.name) == target_name.lower()).first()
    if s:
        if s.name != target_name:
            s.name = target_name
            try:
                db.flush()
            except Exception:
                db.rollback()
        return s
    # 3. Create new
    try:
        s = Strain(name=target_name)
        db.add(s)
        db.flush()
        return s
    except Exception:
        db.rollback()
        s = db.query(Strain).filter(func.lower(Strain.name) == target_name.lower()).first()
        if not s:
            s = db.query(Strain).filter(Strain.name == target_name).first()
        return s

def normalize_strain_name(db: Session, raw_name: Optional[str]) -> str:
    """
    Normalize strain name and merge case discrepancies (e.g. 5XFAD and 5xFAD -> 5xFAD).
    Ensures canonical capitalization is preserved across Excel imports and mouse creations.
    """
    if not raw_name:
        return ""
    clean = str(raw_name).strip()
    if clean in ["/", "无", "None", "nan", "-", "不详", "不明"]:
        return ""

    lower_key = clean.lower()

    # 1. Check known canonical standard mapping
    if lower_key in CANONICAL_STRAIN_MAP:
        canonical_name = CANONICAL_STRAIN_MAP[lower_key]
        get_or_create_strain_record(db, canonical_name)
        return canonical_name

    # 2. Check if a strain already exists in DB matching case-insensitively
    existing = db.query(Strain).filter(func.lower(Strain.name) == lower_key).first()
    if existing:
        return existing.name

    # 3. Check Mouse or Cage for pre-existing casing
    m = db.query(Mouse.strain).filter(func.lower(Mouse.strain) == lower_key).first()
    if m and m[0]:
        canonical_name = m[0]
        get_or_create_strain_record(db, canonical_name)
        return canonical_name

    # 4. Brand new strain - register to Strain table
    get_or_create_strain_record(db, clean)
    return clean

def sync_and_normalize_all_strains(db: Session) -> Dict[str, Any]:
    """
    Run database migration to merge all case-inconsistent strains
    across mice, cages, and genotype_records.
    """
    merged_count = 0

    # 1. Gather all strains currently in mice, cages, genotypes
    mice_strains = db.query(Mouse.strain).filter(Mouse.strain != "").distinct().all()
    cage_strains = db.query(Cage.strain).filter(Cage.strain != "").distinct().all()
    gt_strains = db.query(GenotypeRecord.strain).filter(GenotypeRecord.strain != "").distinct().all()

    all_raw = set([r[0] for r in mice_strains if r[0]]) | \
              set([r[0] for r in cage_strains if r[0]]) | \
              set([r[0] for r in gt_strains if r[0]])

    for raw in all_raw:
        canonical = normalize_strain_name(db, raw)
        if canonical and canonical != raw:
            # Update mice
            db.query(Mouse).filter(Mouse.strain == raw).update({Mouse.strain: canonical}, synchronize_session=False)
            # Update cages
            db.query(Cage).filter(Cage.strain == raw).update({Cage.strain: canonical}, synchronize_session=False)
            # Update genotype records
            db.query(GenotypeRecord).filter(GenotypeRecord.strain == raw).update({GenotypeRecord.strain: canonical}, synchronize_session=False)
            merged_count += 1

    # Ensure all distinct strains have entries in Strain table
    distinct_strains = db.query(Mouse.strain).filter(Mouse.strain != "").distinct().all()
    for s_row in distinct_strains:
        s_name = s_row[0]
        if s_name:
            lower_k = s_name.lower()
            st = db.query(Strain).filter(func.lower(Strain.name) == lower_k).first()
            if not st:
                db.add(Strain(name=s_name))

    db.commit()
    return {"merged_count": merged_count}
