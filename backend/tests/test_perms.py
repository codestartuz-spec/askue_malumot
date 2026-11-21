"""Ruxsat tekshiruvi: katalog izchilligi, har bir route himoyalangani, ruxsatsiz foydalanuvchiga 403."""
import re
from pathlib import Path

import pytest

from app.perms import PERM_CODES, PRESETS, validate_catalog
from app.routers import (ag, appsettings, audit, auth, brigades, devices, drill, dynamics, home, meta, posts, reports,
                         republic, system, telegram, uploads, users)
from app.routers import map as map_router

ROUTERS = (ag, appsettings, audit, auth, brigades, devices, drill, dynamics, home, map_router, meta, posts, reports,
           republic, system, telegram, uploads, users)
PUBLIC = {("POST", "/api/auth/login"), ("POST", "/api/auth/ping"), ("POST", "/api/auth/forgot"),
          ("POST", "/api/auth/reset")}
FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _deps(dep):
    out = []
    for s in dep.dependencies:
        out.append(s.call)
        out += _deps(s)
    return out


def _routes():
    for mod in ROUTERS:
        for r in mod.router.routes:
            for m in r.methods - {"HEAD", "OPTIONS"}:
                yield m, "/api" + r.path, r


def test_catalog_is_consistent():
    assert validate_catalog() == []


def test_every_route_requires_auth_or_is_declared_public():
    open_routes = []
    for m, path, r in _routes():
        names = [getattr(c, "__qualname__", "") for c in _deps(r.dependant)]
        guarded = any(("need" in n) or ("current_user" in n) or ("sadmin_only" in n) for n in names)
        if not guarded and (m, path) not in PUBLIC:
            open_routes.append((m, path))
    assert open_routes == [], f"Himoyasiz route'lar: {open_routes}"


def test_login_only_routes_check_permission_inside():
    """current_user bilan kelgan (need yo'q) route'lar — ro'yxat qo'lda ko'rib chiqilgan, yangisi qo'shilsa shu test ogohlantiradi."""
    allowed = {"/api/auth/me", "/api/auth/logout", "/api/auth/change-password", "/api/auth/profile",
               "/api/meta/bootstrap", "/api/appsettings/public", "/api/dynamics"}
    found = set()
    for m, path, r in _routes():
        names = [getattr(c, "__qualname__", "") for c in _deps(r.dependant)]
        if any("current_user" in n for n in names) and not any(("need" in n) or ("sadmin_only" in n) for n in names):
            found.add(path.rstrip("/"))
    assert found <= allowed, f"Yangi faqat-login route'lar: {found - allowed}"


def test_frontend_permission_codes_exist_in_backend():
    codes = set()
    for f in FRONT.rglob("*.js*"):
        txt = f.read_text(encoding="utf-8")
        codes |= set(re.findall(r"""(?:can|perm|need)\(?[:=]?\s*\(?['"]([a-z_]+\.[a-z_]+)['"]""", txt))
        codes |= set(re.findall(r"""perm:\s*['"]([a-z_]+\.[a-z_]+)['"]""", txt))
    codes.add("export") if False else None
    missing = {c for c in codes if c not in PERM_CODES}
    assert not missing, f"Frontend'da bor, backend katalogida yo'q: {missing}"


def test_presets_only_use_known_codes():
    for p in PRESETS:
        assert set(p["codes"]) <= PERM_CODES, p["name"]


# (usul, yo'l, kerakli ruxsat) — ruxsatsiz foydalanuvchi 403 olishi, ruxsat bilan esa 403 olmasligi kerak
MATRIX = [
    ("GET", "/api/republic/compare", "republic.view"),
    ("GET", "/api/ag/compare", "ag.view"),
    ("GET", "/api/republic", "republic.view"),
    ("GET", "/api/ag", "ag.view"),
    ("GET", "/api/audit", "audit.view"),
    ("GET", "/api/audit/facets", "audit.view"),
    ("GET", "/api/appsettings", "settings.manage"),
    ("GET", "/api/telegram", "settings.manage"),
    ("GET", "/api/system/backups", "backup.manage"),
    ("GET", "/api/users", None),            # faqat sadmin
    ("GET", "/api/devices", None),          # faqat sadmin
]


@pytest.mark.parametrize("method,path,perm", MATRIX)
def test_endpoint_permission_matrix(client, make_user, method, path, perm):
    _, none_h = make_user([])
    assert client.request(method, path, headers=none_h).status_code == 403, f"{path}: ruxsatsiz 403 bo'lishi kerak"
    if perm:
        _, ok_h = make_user([perm])
        assert client.request(method, path, headers=ok_h).status_code != 403, f"{path}: {perm} bilan ruxsat berilishi kerak"
    assert client.request(method, path).status_code == 401


def test_original_pdf_requires_its_own_permission(client, make_user, admin):
    """Respublika /send va /download da «asl PDF» uchun alohida ruxsat (avval /send tekshirmas edi)."""
    for kind in ("republic", "ag"):
        _, h = make_user([f"{kind}.view", "report.download", "telegram.send"])
        r = client.get(f"/api/{kind}/download?fmt=orig", headers=h)
        assert r.status_code == 403
        r = client.post(f"/api/{kind}/send", json={"fmts": ["orig"], "chat_ids": [1]}, headers=h)
        assert r.status_code == 403, f"{kind}/send orig: ruxsat tekshirilmagan"


def test_dynamics_table_permissions(client, make_user):
    _, h = make_user(["view.konsentrator"])
    assert client.get("/api/dynamics?table=konsentrator", headers=h).status_code == 200
    assert client.get("/api/dynamics?table=aloqa", headers=h).status_code == 403
