from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models.models import Primer, User
from backend.app.schemas.schemas import PrimerCreate, PrimerUpdate, PrimerResponse
from backend.app.auth import require_auth, require_admin

router = APIRouter(prefix="/api/primers", tags=["Primers"])

@router.get("", response_model=List[PrimerResponse])
def list_primers(
    keyword: Optional[str] = None,
    strain: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(Primer)
    if keyword:
        k = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Primer.strain_short.ilike(k),
                Primer.strain_full.ilike(k),
                Primer.sequence.ilike(k),
                Primer.band_size.ilike(k),
                Primer.notes.ilike(k)
            )
        )
    if strain:
        query = query.filter(Primer.strain_short == strain)

    return query.order_by(Primer.id.asc()).all()

@router.post("", response_model=PrimerResponse)
def create_primer(data: PrimerCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    primer = Primer(
        primer_no=data.primer_no,
        strain_short=data.strain_short.strip(),
        strain_full=data.strain_full,
        source=data.source,
        gene_type=data.gene_type,
        sequence=data.sequence,
        band_size=data.band_size,
        url=data.url,
        notes=data.notes
    )
    db.add(primer)
    db.commit()
    db.refresh(primer)
    return primer

@router.put("/{primer_id}", response_model=PrimerResponse)
def update_primer(primer_id: int, data: PrimerUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    primer = db.query(Primer).filter(Primer.id == primer_id).first()
    if not primer:
        raise HTTPException(status_code=404, detail="引物未找到")

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(primer, k, v)

    db.commit()
    db.refresh(primer)
    return primer

@router.delete("/{primer_id}")
def delete_primer(primer_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    primer = db.query(Primer).filter(Primer.id == primer_id).first()
    if not primer:
        raise HTTPException(status_code=404, detail="引物未找到")

    db.delete(primer)
    db.commit()
    return {"message": "引物删除成功"}
