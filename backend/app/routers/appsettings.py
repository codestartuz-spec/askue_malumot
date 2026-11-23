"""Ilova sozlamalari: hudud nomi, AG sarlavhasi va h.k. (kodda qattiq yozilgan qiymatlar o'rniga)."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, log, need
from ..models import User
from ..services import filenames as FN
from ..settings_store import DEFAULTS, SCHEMA, app_cfg, app_cfg_all, set_cfg

router = APIRouter(prefix="/appsettings", tags=["appsettings"])


@router.get("")
def get_all(_: User = Depends(need("settings.manage"))):
    cur = app_cfg_all()
    region = cur["region_name"]
    out = []
    for k, lbl, d, g, t in SCHEMA:
        it = {"key": k, "label": lbl, "default": d, "group": g, "type": t, "value": cur[k]}
        if t == "filename":
            it["placeholders"] = {n: FN.PLACEHOLDERS[n] for n in sorted(FN.ALLOWED[k], key=list(FN.PLACEHOLDERS).index)}
            it["example"] = FN.preview(k, cur[k], region)
        out.append(it)
    return out


@router.get("/public")
def public(_: User = Depends(current_user)):
    return {"region_name": app_cfg("region_name")}


class CfgIn(BaseModel):
    values: dict[str, str]


class PreviewIn(BaseModel):
    key: str
    value: str


@router.post("/preview")
def preview(body: PreviewIn, _: User = Depends(need("settings.manage"))):
    """Fayl nomi shabloni uchun namuna (saqlamasdan)."""
    err = FN.validate(body.key, body.value)
    return {"ok": err is None, "error": err or "", "name": FN.preview(body.key, body.value, app_cfg("region_name")) if not err else ""}


@router.put("")
def put_all(body: CfgIn, me: User = Depends(need("settings.manage")), db: Session = Depends(get_db)):
    types = {k: t for k, _l, _d, _g, t in SCHEMA}
    for k, v in body.values.items():
        if k not in DEFAULTS:
            raise HTTPException(400, f"Noma'lum sozlama: {k}")
        v = v.strip()
        if not v:
            raise HTTPException(400, "Qiymat bo'sh bo'lmasin")
        if len(v) > 250:
            raise HTTPException(400, "Qiymat juda uzun")
        if types[k] == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise HTTPException(400, "Sana YYYY-MM-DD ko'rinishida bo'lsin")
        if types[k] == "filename" and (err := FN.validate(k, v)):
            raise HTTPException(400, f"«{k}»: {err}")
    for k, v in body.values.items():
        set_cfg(k, v)
    log(db, me.username, "sozlama", ", ".join(body.values))
    db.commit()
    return get_all(me)
