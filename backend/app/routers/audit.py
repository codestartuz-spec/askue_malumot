from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import sadmin_only
from ..models import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit(page: int = 1, size: int = 50, _: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    size = max(10, min(size, 200))
    total = db.execute(text("SELECT COUNT(*) FROM audit")).scalar()
    rows = db.execute(text("SELECT id, username, action, detail, created_at FROM audit "
                           "ORDER BY id DESC LIMIT :l OFFSET :o"),
                      {"l": size, "o": (max(page, 1) - 1) * size}).mappings()
    return {"total": total, "items": [dict(r) | {"created_at": r["created_at"].isoformat()} for r in rows]}
