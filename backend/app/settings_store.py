"""Ilova sozlamalari (kodda qattiq yozilgan qiymatlar o'rniga). kv jadvalida `cfg.<kalit>` ko'rinishida saqlanadi,
Redis/xotirada 60 soniya keshlanadi. Sozlamalar sahifasidan o'zgartiriladi."""
from sqlalchemy import text

from .db import engine, upsert_kv
from .services.filenames import FILES
from .store import get_store

SCHEMA = [
    # kalit, yorliq, boshlang'ich qiymat, guruh, tur
    ("region_name", "Hudud (filial) nomi", "Qashqadaryo hududiy filiali", "Umumiy", "text"),
    ("ag_region", "AG hisobotida hudud nomi", "Qashqadaryo HETK", "AG dinamikasi", "text"),
    ("ag_title", "AG hisobot sarlavhasi", "24.02.2023 dagi № 01-04-42-22 sonli topshiriq ijrosi bo'yicha", "AG dinamikasi", "text"),
    ("ag_start_date", "AG boshlang'ich sana (PDF o'zida bo'lmasa)", "2023-02-20", "AG dinamikasi", "date"),
]
SCHEMA += [(k, lbl, d, "Fayl nomlari", "filename") for k, lbl, d, _p in FILES]
DEFAULTS = {k: d for k, _l, d, _g, _t in SCHEMA}
TTL = 60


def app_cfg(key: str) -> str:
    s = get_store()
    ck = f"cfg:{key}"
    v = s.get(ck)
    if v is not None:
        return v
    with engine.connect() as c:
        v = c.execute(text("SELECT v FROM kv WHERE k=:k"), {"k": f"cfg.{key}"}).scalar()
    v = v if v not in (None, "") else DEFAULTS[key]
    s.set(ck, v, ex=TTL)
    return v


def app_cfg_all() -> dict:
    return {k: app_cfg(k) for k in DEFAULTS}


def set_cfg(key: str, value: str) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    with engine.begin() as c:
        upsert_kv(c, f"cfg.{key}", value.strip())
    get_store().delete(f"cfg:{key}")
