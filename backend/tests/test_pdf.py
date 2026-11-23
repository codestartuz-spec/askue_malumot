"""PDF yuklash: xavfsizlik tekshiruvi, parser, Respublika/AG to'liq jarayoni."""
import io

import pytest
from fastapi import HTTPException

from app.config import settings
from app.services import ag, ag_report, pdfcheck
from tests.conftest import FIX

AG1, AG2 = FIX / "ag_2026-01-05.pdf", FIX / "ag_2026-11-17.pdf"
REP = FIX / "republic_2026-11-20.pdf"            # eski format (2-sahifa: 9 katak)
REP_NEW = FIX / "republic_2026-11-23.pdf"        # yangi format (2-sahifa: + «Billingda otkl. status»)


def _files(path, name=None, mime="application/pdf"):
    return {"file": (name or path.name, path.read_bytes(), mime)}


# ------------------------------------------------------------- statik tekshiruv
@pytest.mark.parametrize("data,why", [
    (b"hello world" * 50, "sarlavha yo'q"),
    (b"%PDF-1.4\n" + b"x" * 300, "%%EOF yo'q"),
    (b"%PDF-1.4\n/Encrypt 5 0 R\n" + b"x" * 300 + b"\n%%EOF", "shifrlangan"),
    (b"%PDF-1.7\n1 0 obj<</S/JavaScript/JS(app.alert(1))>>\n" + b"x" * 300 + b"\n%%EOF", "JavaScript"),
    (b"%PDF-1.7\n1 0 obj<</S/J#61vaScript>>\n" + b"x" * 300 + b"\n%%EOF", "yashirilgan JavaScript (#61)"),
    (b"%PDF-1.7\n1 0 obj<</Type/Action/S/Launch>>\n" + b"x" * 300 + b"\n%%EOF", "Launch"),
    (b"%PDF-1.7\n1 0 obj<</Type/EmbeddedFile>>\n" + b"x" * 300 + b"\n%%EOF", "ilova"),
])
def test_static_check_rejects(data, why):
    with pytest.raises(HTTPException) as e:
        pdfcheck.static_check(data)
    assert e.value.status_code == 400, why


def test_static_check_accepts_real_pdfs():
    for p in (AG1, AG2, REP):
        pdfcheck.static_check(p.read_bytes())


def test_json_like_name_is_not_flagged():
    pdfcheck.static_check(b"%PDF-1.7\n/JSONData 1 0 R /Jsx\n" + b"x" * 300 + b"\n%%EOF")


# ------------------------------------------------------------- parser (alohida jarayonda)
def test_ag_parse_isolated_and_sums():
    rep = pdfcheck.parse_isolated("ag", AG2.read_bytes())
    assert str(rep["end"]) == "2026-11-17" and len(rep["rows"]) == 17
    for g in range(ag.NG):                      # tumanlar yig'indisi = Jami
        assert sum((r["cells"][g]["v"] or 0) for r in rep["rows"]) == (rep["total"][g]["v"] or 0)


def test_isolated_parse_times_out(monkeypatch):
    monkeypatch.setattr(settings, "pdf_parse_timeout", 0.05)
    with pytest.raises(HTTPException) as e:
        pdfcheck.parse_isolated("ag", AG2.read_bytes())
    assert "uzoq" in e.value.detail


def test_garbage_pdf_does_not_crash_server():
    bad = b"%PDF-1.4\n" + b"\x00garbage" * 200 + b"\n%%EOF"
    with pytest.raises(HTTPException):
        pdfcheck.parse_isolated("ag", bad)


def test_ag_generated_pdf_is_readable():
    """Generator chiqargan PDF o'qiladigan bo'lishi kerak (qatorlar nomi va birinchi guruhlar qiymati mos).
    Eslatma: generator chiziqlarni to'rtburchak qilib chizadi, shuning uchun parser faqat asl (CAS) PDF'lar uchun mo'ljallangan."""
    rep = pdfcheck.parse_isolated("ag", AG2.read_bytes())
    res = ag.compare(None, {k: rep[k] for k in ("title", "region", "total", "rows")}, str(rep["start"]), str(rep["end"]))
    pdf = ag_report.build_pdf(res)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000
    again = pdfcheck.parse_isolated("ag", pdf)
    assert [r["name"] for r in again["rows"]] == [r["name"] for r in rep["rows"]]
    for g in range(4):
        assert [c["v"] for c in again["total"]][g] == rep["total"][g]["v"]


# ------------------------------------------------------------- HTTP jarayoni
def test_upload_rejects_non_pdf_and_oversize(client, make_user, monkeypatch):
    _, h = make_user(["ag.upload"])
    assert client.post("/api/ag/upload", files={"file": ("x.txt", b"abc" * 100, "text/plain")}, headers=h).status_code == 400
    assert client.post("/api/ag/upload", files={"file": ("x.pdf", b"not a pdf" * 100, "application/pdf")}, headers=h).status_code == 400
    monkeypatch.setattr(settings, "max_pdf_mb", 0)
    r = client.post("/api/ag/upload", files=_files(AG1), headers=h)
    assert r.status_code == 400 and "katta" in r.json()["detail"]


def test_republic_rejects_ag_pdf_and_requires_permission(client, make_user):
    _, h = make_user(["republic.upload"])
    r = client.post("/api/republic/upload", files=_files(AG1), headers=h)
    assert r.status_code == 400 and "AG" in r.json()["detail"]
    _, none = make_user([])
    assert client.post("/api/republic/upload", files=_files(REP), headers=none).status_code == 403


def test_ag_full_flow(client, make_user, admin):
    _, h = make_user(["ag.upload", "ag.view", "report.download", "ag.original", "data.delete"])
    for p in (AG1, AG2):
        r = client.post("/api/ag/upload", files=_files(p), headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["pages"] == 17
    lst = client.get("/api/ag", headers=h).json()
    assert {x["end"] for x in lst} >= {"2026-01-05", "2026-11-17"}
    month = client.get("/api/ag/compare?mode=oy", headers=h).json()
    day = client.get("/api/ag/compare?mode=kunlik&b=2026-11-17", headers=h).json()
    assert month["a"] is None and day["a"] == "2026-01-05"
    assert len(month["rows"]) == len(day["rows"]) == 17
    for fmt, magic in (("pdf", b"%PDF"), ("xlsx", b"PK"), ("orig", b"%PDF")):
        r = client.get(f"/api/ag/download?fmt={fmt}&mode=oy", headers=h)
        assert r.status_code == 200 and r.content[:4].startswith(magic), fmt
    fid = next(x["id"] for x in lst if x["end"] == "2026-01-05")
    assert client.get(f"/api/ag/{fid}/file?inline=1", headers=h).content[:4] == b"%PDF"
    assert client.delete(f"/api/ag/{fid}", headers=h).status_code == 200
    assert client.delete(f"/api/ag/{fid}", headers=h).status_code == 404


def test_republic_full_flow(client, make_user):
    _, h = make_user(["republic.upload", "republic.view", "report.download", "republic.original"])
    r = client.post("/api/republic/upload", files=_files(REP), headers=h)
    assert r.status_code == 200, r.text
    c = client.get("/api/republic/compare?mode=oy", headers=h).json()
    assert c["pages"] and c["b"]
    for fmt in ("pdf", "xlsx", "orig"):
        assert client.get(f"/api/republic/download?fmt={fmt}", headers=h).status_code == 200


def _page(c, n):
    return next(p for p in c["pages"] if p["n"] == n)


def test_republic_new_column_and_daily_difference(client, make_user):
    """Eski va yangi PDF birga ishlaydi; kunlikda farq = tanlangan ikki sananing soni ayirmasi."""
    _, h = make_user(["republic.upload", "republic.view", "report.download", "republic.original"])
    for f in (REP, REP_NEW):
        r = client.post("/api/republic/upload", files=_files(f), headers=h)
        assert r.status_code == 200, r.text
    # oy boshidan: faqat PDF'ning o'z ↑↓ qiymati, yangi ustun bor (r2), «Jami» = 2 158
    m = client.get("/api/republic/compare?mode=oy&b=2026-11-23", headers=h).json()
    p2 = _page(m, 2)
    assert p2["key"] == "r2" and p2["cur"]["c9"] == 2158 and any(c["m"] == "c9" for c in p2["cols"])
    assert p2["cur"]["c1"] - p2["base"]["c1"] == -3316 and p2["warn"] == ""
    # eski PDF: yangi ustunsiz jadval (r2o)
    o = client.get("/api/republic/compare?mode=oy&b=2026-11-20", headers=h).json()
    assert _page(o, 2)["key"] == "r2o" and not any(c.get("m") == "c9" for c in _page(o, 2)["cols"])
    # kunlik: 23.11 − 20.11 (oy boshiga emas!)
    k = client.get("/api/republic/compare?mode=kunlik&a=2026-11-20&b=2026-11-23", headers=h).json()
    assert k["a"] == "2026-11-20" and k["b"] == "2026-11-23"
    p2 = _page(k, 2)
    assert p2["key"] == "r2" and p2["warn"] == ""
    assert p2["cur"]["c1"] - p2["base"]["c1"] == 23929 - 26013
    assert p2["cur"]["c3"] - p2["base"]["c3"] == 18025 - 17944
    assert p2["cur"]["c9"] == p2["base"]["c9"] == 2158          # eski PDF'da ustun yo'q → farq ko'rsatilmaydi
    row = next(r for r in p2["rows"] if r["name"].startswith("Qarshi sh"))
    assert row["cur"]["c1"] - row["base"]["c1"] == 3335 - 3447
    # a berilmasa — oldingi sana avtomatik tanlanadi
    k2 = client.get("/api/republic/compare?mode=kunlik&b=2026-11-23", headers=h).json()
    assert k2["a"] == "2026-11-20" and _page(k2, 2)["base"] == p2["base"]
    for fmt in ("pdf", "xlsx"):
        r = client.get(f"/api/republic/download?fmt={fmt}&mode=kunlik&a=2026-11-20&b=2026-11-23", headers=h)
        assert r.status_code == 200 and len(r.content) > 5000, fmt


def test_republic_compare_helpers():
    from app.services import republic as R
    assert R.comparable(2, 9, 10) and R.comparable(2, 10, 9) and R.comparable(1, 11, 11)
    assert not R.comparable(1, 11, 12) and not R.comparable(2, 9, 12)
    cells = [{"v": 100, "p": None, "d": 7}, {"v": 5, "p": None, "d": None}]
    cur, base = R.page_values(cells, None)                         # oy: PDF'ning o'z ↑↓
    assert base["c0"] == 93
    cur, base = R.page_values(cells, [{"v": 90}], strict=True)     # kunlik: boshqa sana bilan; yetmagan ustun → farqsiz
    assert base["c0"] == 90 and base["c1"] == 5
    cur, base = R.page_values(cells, None, strict=True)            # kunlik, taqqoslash yo'q → farq bo'sh (oy ↑↓ chiqmaydi)
    assert base["c0"] == 100


def test_send_runs_as_task_and_reports_progress(client, make_user, fake_tg):
    import time
    from sqlalchemy import text
    from app.db import engine
    _, h = make_user(["ag.upload", "ag.view", "telegram.send", "ag.original"])
    client.post("/api/ag/upload", files=_files(AG2), headers=h)
    from app.db import upsert_kv
    from app.services import telegram as tgs
    with engine.begin() as c:
        upsert_kv(c, "tg_token", "x")
    tgs.upsert_chat({"id": -100777, "title": "Test kanal", "type": "channel"}, source="manual")
    with engine.begin() as c:
        cid = c.execute(text("SELECT id FROM tg_chats WHERE chat_id='-100777'")).scalar()
    r = client.post("/api/ag/send", json={"fmts": ["pdf", "xlsx", "orig"], "chat_ids": [cid], "ack": False}, headers=h)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    for _ in range(60):
        st = client.get(f"/api/reports/send/{jid}", headers=h)
        if st.status_code == 200 and st.json()["status"] != "running":
            break
        time.sleep(0.2)
    assert st.json()["status"] == "done", st.json()
    assert [s[1] for s in fake_tg if s[0] == "-100777"].count("msg") == 0
    assert len([s for s in fake_tg if s[0] == "-100777"]) == 3


def test_republic_send_kunlik_files(client, make_user, fake_tg):
    """Respublika: kunlik rejimda PDF + Excel + asl PDF Telegramga yuboriladi (fon vazifasi)."""
    import time
    from sqlalchemy import text
    from app.db import engine, upsert_kv
    from app.services import telegram as tgs
    _, h = make_user(["republic.upload", "republic.view", "telegram.send", "republic.original"])
    for f in (REP, REP_NEW):
        client.post("/api/republic/upload", files=_files(f), headers=h)
    with engine.begin() as c:
        upsert_kv(c, "tg_token", "x")
    tgs.upsert_chat({"id": -100888, "title": "Resp kanal", "type": "channel"}, source="manual")
    with engine.begin() as c:
        cid = c.execute(text("SELECT id FROM tg_chats WHERE chat_id='-100888'")).scalar()
    r = client.post("/api/republic/send", json={"fmts": ["pdf", "xlsx", "orig"], "chat_ids": [cid], "ack": False,
                                                "mode": "kunlik", "a": "2026-11-20", "b": "2026-11-23"}, headers=h)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    for _ in range(80):
        st = client.get(f"/api/reports/send/{jid}", headers=h)
        if st.status_code == 200 and st.json()["status"] != "running":
            break
        time.sleep(0.2)
    assert st.json()["status"] == "done", st.json()
    assert len([s for s in fake_tg if s[0] == "-100888"]) == 3
