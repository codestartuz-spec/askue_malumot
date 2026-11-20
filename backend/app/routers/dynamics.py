from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, has_perm
from ..models import User
from ..services.dyn import compute

router = APIRouter(prefix="/dynamics", tags=["dynamics"])

TABLES = {"konsentrator": "view.konsentrator", "aloqa": "view.aloqa", "obxod": "view.obxod"}


@router.get("")
def dynamics(table: str, esp_id: int | None = None,
             date_from: str | None = Query(None), date_to: str | None = Query(None),
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    if table not in TABLES:
        raise HTTPException(404, "Noma'lum jadval")
    if not has_perm(user, TABLES[table]):
        raise HTTPException(403, "Bu jadvalni ko'rish uchun ruxsat yo'q")
    return compute(db, esp_id, date_from, date_to, has_perm(user, "dynamics.compare"))
