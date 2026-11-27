"""Respublika dinamikasi (barcha viloyatlar): PDF o'qish, yuklash, solishtirish, fayllar, rasm, ruxsatlar."""
import io
import time
import zipfile
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
N25, N26, N27 = (FIX / f"nation_2026-11-{d}.pdf" for d in (25, 26, 27))
PERM = ["nation.upload", "nation.view", "report.download", "nation.original", "data.delete"]


def _files(p: Path):
    return {"file": (p.name, p.read_bytes(), "application/pdf")}


@pytest.fixture(scope="module")
def parsed():
    from app.services import nation
    return nation.parse_report(N27.read_bytes())


def test_parse_pages_and_regions(parsed):
    assert str(parsed["start"]) == "2026-11-01" and str(parsed["end"]) == "2026-11-27"
    sizes = {p["n"]: len(p["cells"]) for p in parsed["pages"]}
    assert sizes == {1: 11, 2: 10, 3: 7, 4: 12, 6: 12, 7: 9, 8: 11}      # 5 (diagramma) va SmartApp o'tkazib yuboriladi
    for p in parsed["pages"]:
        assert len(p["rows"]) == 14 and all(len(r["cells"]) == sizes[p["n"]] for r in p["rows"])
    names = [r["name"] for r in parsed["pages"][0]["rows"]]
    assert "Qashqadaryo HETK" in names and "Toshkent shahar ETK" in names and "Farg‘ona HETK" in names


def test_parse_values_and_deltas(parsed):
    p1 = next(p for p in parsed["pages"] if p["n"] == 1)
    jami = [c["v"] for c in p1["cells"]]
    assert jami[:3] == [172946, 108123, 107947] and p1["cells"][4]["d"] == 5 and p1["cells"][5]["d"] == -35
    q = next(r for r in p1["rows"] if r["name"] == "Qashqadaryo HETK")
    assert [c["v"] for c in q["cells"]][:4] == [17562, 11358, 11353, 5] and q["cells"][10]["v"] is None
    p2 = next(p for p in parsed["pages"] if p["n"] == 2)
    assert p2["cells"][2]["p"] == "3,6%" and p2["cells"][2]["d"] == -11540
    # viloyatlar yig'indisi «Жами» ga teng (PDF ichki izchilligi)
    assert sum(r["cells"][0]["v"] for r in p1["rows"]) == jami[0]


def test_upload_compare_downloads_and_ranking_labels(client, make_user):
    _, h = make_user(PERM)
    for f in (N25, N26, N27):
        r = client.post("/api/nation/upload", files=_files(f), headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["pages"] == 7
    month = client.get("/api/nation/compare?mode=oy", headers=h).json()
    day = client.get("/api/nation/compare?mode=kunlik&b=2026-11-27", headers=h).json()
    assert month["a"] is None and day["a"] == "2026-11-26" and month["b"] == "2026-11-27"
    p = next(x for x in month["pages"] if x["n"] == 1)
    assert len(p["rows"]) == 14 and p["labels"][0] == "Dasturda mavjud transformatorlar"
    for fmt, magic in (("pdf", b"%PDF"), ("xlsx", b"PK"), ("orig", b"%PDF")):
        r = client.get(f"/api/nation/download?fmt={fmt}&mode=oy", headers=h)
        assert r.status_code == 200 and r.content[:4].startswith(magic), fmt
    z = client.get("/api/nation/download?fmt=png&mode=oy", headers=h)
    assert z.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert len(names) == 7 and all(n.endswith(".png") for n in names)
    lst = client.get("/api/nation", headers=h).json()
    assert len(lst) == 3 and client.get(f"/api/nation/{lst[0]['id']}/file?inline=1", headers=h).content[:4] == b"%PDF"
    home = client.get("/api/home/nation", headers=h).json()
    assert len(home["reports"]) == 3


def test_wrong_pdf_and_permissions(client, make_user):
    _, h = make_user(["nation.upload"])
    ag = _files(FIX / "ag_2026-11-17.pdf")
    assert client.post("/api/nation/upload", files=ag, headers=h).status_code == 400
    rep = _files(FIX / "republic_2026-11-23.pdf")
    r = client.post("/api/nation/upload", files=rep, headers=h)
    assert r.status_code == 400 and "respublika" in r.json()["detail"].lower()
    _, hr = make_user(["republic.upload"])
    r = client.post("/api/republic/upload", files=_files(N27), headers=hr)
    assert r.status_code == 400 and "Respublika dinamikasi" in r.json()["detail"]
    _, none = make_user(["republic.upload", "republic.view"])
    assert client.post("/api/nation/upload", files=_files(N27), headers=none).status_code == 403
    assert client.get("/api/nation/compare", headers=none).status_code == 403


def test_send_pdf_excel_and_image_album(client, make_user, fake_tg):
    from sqlalchemy import text
    from app.db import engine, upsert_kv
    from app.services import telegram as tgs
    _, h = make_user(PERM + ["telegram.send"])
    for f in (N26, N27):
        client.post("/api/nation/upload", files=_files(f), headers=h)
    with engine.begin() as c:
        upsert_kv(c, "tg_token", "x")
    tgs.upsert_chat({"id": -100999, "title": "Resp", "type": "channel"}, source="manual")
    with engine.begin() as c:
        cid = c.execute(text("SELECT id FROM tg_chats WHERE chat_id='-100999'")).scalar()
    r = client.post("/api/nation/send", json={"fmts": ["png", "pdf", "xlsx"], "chat_ids": [cid], "ack": False,
                                              "mode": "kunlik", "a": "2026-11-26", "b": "2026-11-27"}, headers=h)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    for _ in range(150):
        st = client.get(f"/api/reports/send/{jid}", headers=h)
        if st.status_code == 200 and st.json()["status"] != "running":
            break
        time.sleep(0.2)
    assert st.json()["status"] == "done", st.json()
    sent = [s[1] for s in fake_tg if s[0] == "-100999"]
    assert any(n.startswith("ALBUM:") and n.count("+") == 6 for n in sent), sent
    assert "Respublika_dinamikasi_2026-11-27.pdf" in sent and "Respublika_dinamikasi_2026-11-27.xlsx" in sent
