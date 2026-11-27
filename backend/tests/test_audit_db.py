"""Audit jurnali (qidiruv, eksport, saqlash muddati), Alembic migratsiyalari, katta fayllar."""
import csv
import gzip
import io
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.db import engine


def _seed(n=30):
    with engine.begin() as c:
        for i in range(n):
            c.execute(text("INSERT INTO audit (username,action,detail,ip,created_at) VALUES (:u,:a,:d,:ip,:t)"),
                      {"u": "ali" if i % 2 else "vali", "a": "kirish" if i % 3 else "upload", "d": f"=SUM(A1) yozuv {i}",
                       "ip": f"10.0.0.{i % 5}", "t": datetime.now() - timedelta(days=i)})


def test_audit_search_filters_and_pagination(client, admin):
    _seed()
    allr = client.get("/api/audit?size=10", headers=admin).json()
    assert allr["total"] >= 30 and len(allr["items"]) == 10
    r = client.get("/api/audit?user=ali&action=upload", headers=admin).json()
    assert r["total"] > 0 and all(x["username"] == "ali" and x["action"] == "upload" for x in r["items"])
    assert client.get("/api/audit?q=yozuv 7", headers=admin).json()["total"] >= 1
    assert client.get("/api/audit?ip=10.0.0.3", headers=admin).json()["total"] > 0
    d = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    recent = client.get(f"/api/audit?date_from={d}", headers=admin).json()["total"]
    assert 0 < recent < allr["total"]
    assert client.get("/api/audit?date_from=nota", headers=admin).status_code == 400
    f = client.get("/api/audit/facets", headers=admin).json()
    assert "kirish" in f["actions"] and "ali" in f["users"]


def test_audit_csv_export_escapes_formulas(client, admin):
    r = client.get("/api/audit/export?fmt=csv&q=yozuv", headers=admin)
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][:3] == ["ID", "Vaqt", "Foydalanuvchi"]
    details = [x[5] for x in rows[1:]]
    assert details and all(not d.startswith("=") for d in details)      # Excel formula in'ektsiyasidan himoya
    assert any(d.startswith("'=SUM") for d in details)


def test_audit_xlsx_export_and_permission(client, admin, make_user):
    r = client.get("/api/audit/export?fmt=xlsx", headers=admin)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert client.get("/api/audit/export?fmt=exe", headers=admin).status_code == 400
    _, h = make_user(["audit.view"])                    # report.download yo'q
    assert client.get("/api/audit/export?fmt=csv", headers=h).status_code == 403


def test_audit_retention_purges_old_rows(monkeypatch):
    from app.routers.audit import purge_old
    with engine.begin() as c:
        c.execute(text("INSERT INTO audit (username,action,detail,created_at) VALUES ('x','eski','old',:t)"),
                  {"t": datetime.now() - timedelta(days=900)})
    monkeypatch.setattr(settings, "audit_keep_days", 365)
    assert purge_old() >= 1
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM audit WHERE action='eski'")).scalar() == 0
    monkeypatch.setattr(settings, "audit_keep_days", 0)
    assert purge_old() == 0


# ------------------------------------------------------------------ migratsiyalar
def test_migrations_at_head_and_idempotent():
    from app import dbmigrate
    assert dbmigrate.current() == "0005"
    dbmigrate.upgrade()
    dbmigrate.upgrade()
    assert dbmigrate.current() == "0005"


def test_legacy_database_is_upgraded():
    """Alembic'siz, eski qo'lbola sxemadagi baza: yetishmagan ustun/indekslar qo'shiladi, ma'lumot saqlanadi."""
    from app import dbmigrate
    with engine.begin() as c:
        c.execute(text("INSERT INTO devices (uid,name,kind,ua,ip,first_seen,last_seen,last_user,is_blocked,blocked_by) "
                       "VALUES ('legacyuid1234567890','n','desktop','ua','1.1.1.1',NOW(),NOW(),'',0,'')"))
        c.execute(text("DROP INDEX ix_devices_ua_hash ON devices"))
        c.execute(text("ALTER TABLE devices DROP COLUMN ua_hash"))
        c.execute(text("DROP INDEX ix_audit_action ON audit"))
        c.execute(text("DROP TABLE alembic_version"))
    dbmigrate.upgrade()
    insp = inspect(engine)
    assert "ua_hash" in {c["name"] for c in insp.get_columns("devices")}
    assert "ix_audit_action" in {i["name"] for i in insp.get_indexes("audit")}
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM devices WHERE uid='legacyuid1234567890'")).scalar() == 1
    assert dbmigrate.current() == "0005"


def test_models_match_database_schema():
    """Model va baza orasida farq yo'q (migratsiya yetishmagan ustunni unutmagan)."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.models import Base
    with engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"compare_type": False}), Base.metadata)
    missing = [d for d in diff if d[0] in ("add_column", "add_table")]
    assert missing == [], f"Modelda bor, bazada yo'q: {missing}"


def test_mysql8_sql_mode_is_enforced():
    with engine.connect() as c:
        mode = c.execute(text("SELECT @@SESSION.sql_mode")).scalar()
    assert "ONLY_FULL_GROUP_BY" in mode and "STRICT_TRANS_TABLES" in mode


# ------------------------------------------------------------------ katta fayllar
def test_gzip_bomb_is_rejected(tmp_path, monkeypatch):
    from app.services import ingest
    monkeypatch.setattr(settings, "max_unzipped_mb", 1)
    p = tmp_path / "bomb.csv.gz"
    with gzip.open(p, "wb") as f:
        f.write(b"a,b\n" + b"1,2\n" * 600_000)          # ~2.4 MB ochilgach, siqilgan — bir necha KB
    raw, rd = ingest.open_csv(str(p))
    with raw, pytest.raises(ingest.IngestError):
        for _ in rd:
            pass


def test_upload_size_cap_and_gz_magic(client, make_user, monkeypatch):
    _, h = make_user(["data.upload"])
    r = client.post("/api/uploads", files={"details": ("Details_01-01-2026.csv.gz", b"not-gzip-data" * 10, "application/gzip")}, headers=h)
    assert r.status_code == 400 and ".gz" in r.json()["detail"]
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as g:
        g.write(b"x,y\n1,2\n")
    r = client.post("/api/uploads", files={"area": ("Area_01-01-2026.csv.gz", buf.getvalue(), "application/gzip")}, headers=h)
    assert r.status_code == 400 and "katta" in r.json()["detail"]
    assert not list((settings.data_dir / "uploads").glob("*bomb*"))


def test_streaming_ingest_small_roundtrip(tmp_path):
    """Details'ni oqim bilan o'qib yozish (4000 lik bo'laklar) — kichik namuna bilan to'liq yo'l."""
    from app.services import ingest
    from app.db import engine as eng
    rows = [ingest.DETAILS_COLS] + [[("Qarshi ShETK"), "TP-1", f"acc{i}", f"M{i:06d}", "t", "GPRS", "1", "1", "1", "38.8", "65.7",
                                     "1", f"Nom {i}", "Manzil", "2026-11-20 10:00:00", "1", "1", "0", "0", "0", "0", "0"]
                                    for i in range(50)]
    p = tmp_path / "Details.csv.gz"
    with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    seen = []
    res = ingest.ingest_details(str(p), 777001, lambda frac, stage, force=False: seen.append(frac))
    assert res["meters"] == 50
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM meters WHERE batch=777001")).scalar() == 50
        c.execute(text("SELECT 1"))
    with eng.begin() as c:
        c.execute(text("DELETE FROM meters WHERE batch=777001"))
