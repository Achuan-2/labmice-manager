from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.models import Strain, Mouse, Cage, User
from backend.app.schemas.schemas import StrainCreate, StrainUpdate, StrainResponse
from backend.app.auth import require_auth, require_admin
from backend.app.services.strain_service import normalize_strain_name, sync_and_normalize_all_strains

router = APIRouter(prefix="/api/strains", tags=["Strains"])

@router.get("", response_model=List[StrainResponse])
def list_strains(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """List all strains with notes and mouse counts"""
    # Count mice per strain
    counts = dict(db.query(Mouse.strain, func.count(Mouse.id)).filter(Mouse.strain != "").group_by(Mouse.strain).all())
    
    # Query all strain records
    strains = db.query(Strain).filter(~Strain.name.in_(["/", "无", "-", "None", "nan"])).order_by(Strain.name.asc()).all()
    
    # Also find any mice strains not yet in Strain table
    existing_names = set(s.name for s in strains)
    missing = set(counts.keys()) - existing_names - {"/", "无", "-", "None", "nan", ""}
    for m_strain in sorted(missing):
        if m_strain:
            st = Strain(name=m_strain)
            db.add(st)
            db.flush()
            strains.append(st)

    strains.sort(key=lambda x: x.name)

    results = []
    for s in strains:
        results.append(StrainResponse(
            id=s.id,
            name=s.name,
            notes=s.notes or "",
            mouse_count=counts.get(s.name, 0)
        ))
    return results

@router.get("/{strain_name:path}")
def get_strain_detail(
    strain_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get strain details and notes by strain name"""
    canonical_name = normalize_strain_name(db, strain_name)
    st = db.query(Strain).filter(func.lower(Strain.name) == canonical_name.lower()).first()
    mouse_count = db.query(Mouse).filter(Mouse.strain == canonical_name).count()
    cage_count = db.query(Cage).filter(Cage.strain == canonical_name).count()

    return {
        "id": st.id if st else None,
        "name": canonical_name,
        "notes": st.notes if st else "",
        "mouse_count": mouse_count,
        "cage_count": cage_count
    }

@router.post("", response_model=StrainResponse)
def create_or_update_strain(
    data: StrainCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new strain or update notes if already exists"""
    canonical_name = normalize_strain_name(db, data.name)
    st = db.query(Strain).filter(func.lower(Strain.name) == canonical_name.lower()).first()
    if not st:
        st = Strain(name=canonical_name, notes=data.notes)
        db.add(st)
    else:
        if data.notes is not None:
            st.notes = data.notes
    db.commit()
    db.refresh(st)

    mouse_count = db.query(Mouse).filter(Mouse.strain == st.name).count()
    return StrainResponse(
        id=st.id,
        name=st.name,
        notes=st.notes or "",
        mouse_count=mouse_count
    )

@router.put("/{strain_name:path}", response_model=StrainResponse)
def update_strain_notes(
    strain_name: str,
    data: StrainUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update remarks/notes for a specific strain"""
    canonical_name = normalize_strain_name(db, strain_name)
    st = db.query(Strain).filter(func.lower(Strain.name) == canonical_name.lower()).first()
    if not st:
        st = Strain(name=canonical_name, notes=data.notes)
        db.add(st)
    else:
        st.notes = data.notes
    db.commit()
    db.refresh(st)

    mouse_count = db.query(Mouse).filter(Mouse.strain == st.name).count()
    return StrainResponse(
        id=st.id,
        name=st.name,
        notes=st.notes or "",
        mouse_count=mouse_count
    )

@router.post("/sync/merge-cases")
def merge_strain_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Execute case unification migration (e.g. 5XFAD -> 5xFAD)"""
    res = sync_and_normalize_all_strains(db)
    return {
        "success": True,
        "message": f"成功合并规范化品系名称，共更新 {res['merged_count']} 条记录"
    }
