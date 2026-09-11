from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.models import Mouse, Cage, Claimer, Primer, Room, TransferRequest, GenotypeRecord, User
from backend.app.routers.cages import default_room_category, normalize_room_category
from backend.app.auth import require_auth

router = APIRouter(prefix="/api/stats", tags=["Stats"])
ROOM_CATEGORY_ORDER = {"繁育鼠房": 0, "临时鼠房": 1, "实验鼠房": 2}

@router.get("/dashboard")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    total_mice = db.query(Mouse).count()
    in_cage_mice = db.query(Mouse).filter(Mouse.cage_id.isnot(None)).count()
    claimed_mice = db.query(Mouse).filter(Mouse.owner_id.isnot(None)).count()
    total_cages = db.query(Cage).count()
    total_claimers = db.query(Claimer).count()
    total_primers = db.query(Primer).count()
    total_genotypes = db.query(GenotypeRecord).count()
    pending_requests_count = db.query(TransferRequest).filter(TransferRequest.status.in_(["申请中", "进行中"])).count()

    # Room breakdown (optimized using aggregated GROUP BY queries)
    cage_counts_by_room = dict(
        db.query(Cage.room, func.count(Cage.id))
        .filter(Cage.room.isnot(None), Cage.room != "")
        .group_by(Cage.room)
        .all()
    )
    room_categories = {
        room.name: normalize_room_category(room.category)
        for room in db.query(Room).all()
    }
    all_room_names = sorted(
        cage_counts_by_room.keys(),
        key=lambda name: (
            ROOM_CATEGORY_ORDER.get(room_categories.get(name) or default_room_category(name), 3),
            name
        )
    )
    rooms_data = [
        {
            "room": r_name,
            "cages": cage_counts_by_room.get(r_name, 0),
            "category": room_categories.get(r_name) or default_room_category(r_name)
        }
        for r_name in all_room_names
    ]

    pending_requests = (
        db.query(TransferRequest)
        .filter(TransferRequest.status.in_(["申请中", "进行中"]))
        .order_by(TransferRequest.id.desc())
        .limit(8)
        .all()
    )

    return {
        "total_mice": total_mice,
        "in_cage_mice": in_cage_mice,
        "claimed_mice": claimed_mice,
        "unclaimed_mice": max(0, in_cage_mice - claimed_mice),
        "total_cages": total_cages,
        "total_claimers": total_claimers,
        "total_primers": total_primers,
        "total_genotypes": total_genotypes,
        "pending_requests_count": pending_requests_count,
        "rooms": rooms_data,
        "pending_requests": pending_requests
    }
