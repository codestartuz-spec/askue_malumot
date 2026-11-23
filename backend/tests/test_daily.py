"""Kunlik topshiriq bo'limi: fayllarni tanish, hisoblash, Excel natijalari, arxiv, sozlamalar, Telegram."""
import io
import time
import zipfile
from datetime import date

import openpyxl
import pytest
import xlsxwriter

from app.services import daily as D

ESP1, ESP2 = "Baxoriston ETK", "G‘uzor TETK"


def _xlsx(title_rows, header, rows, sheet="sheet1") -> bytes:
    bio = io.BytesIO()
    wb = xlsxwriter.Workbook(bio, {"in_memory": True})
    ws = wb.add_worksheet(sheet)
    r = 0
    for t in title_rows:
        ws.write_row(r, 0, t)
        r += 1
    ws.write_row(r, 0, header)
    for row in rows:
        r += 1
        ws.write_row(r, 0, row)
    wb.close()
    return bio.getvalue()


def make_files(ctype2="Промышленные", offline_time="20/11/2026 10:00:00") -> dict[str, bytes]:
    """5 ta kichik fayl (haqiqiy eksport tuzilmasida)."""
    area_h = ["No.", "PTES Code", "PTES", "ESP Code", "ESP name", "Substation Code", "Substation", "Feeder Code", "Feeder",
              "TR Code", "TR", "Tr Owner", "Manager Name", "Managed Area Name", "ID number", "Phone number"]
    area = [[1, "1", "P", "1", ESP1, "1", "NS A", "1", "F1", "001", "1", "ESP", "ALI VALI, KARIM", "x", "1", "2"],
            [2, "1", "P", "1", ESP1, "1", "NS A", "1", "F1", "002", "2", "ESP", "", "x", "1", "2"],
            [3, "1", "P", "1", ESP2, "1", "NS B", "1", "F2", "003", "3", "ESP", "SOLIH", "x", "1", "2"]]
    st_h = ["№", "Название ЭСП", "Номер трансформатора", "Номер концентратора данных", "Дата установки", "Версия прошивки",
            "Связь Статус", "Установлено(pcs)", "Введено в эксплуатацию", "Устройства с <br>незавершенным", "Однодневный Опрос %"]
    status = [[1, ESP1, "001", "9001", "", "", "Онлайн", 5, 5, 0, 100],
              [2, ESP1, "002", "9002", "", "", "Офлайн", 3, 3, 0, 40],
              [3, ESP1, "003", "", "", "", "", 0, 0, 0, 100],
              [4, ESP2, "003", "9003", "", "", "Онлайн", 0, 0, 0, 0],
              [5, ESP2, "004", "9004", "", "", "Онлайн", 4, 4, 0, 0],
              [6, ESP2, "005", "9005", "", "", "Онлайн", 4, 4, 0, 75]]
    nm_h = ["№", "ЭСП", "Подстанция", "Фидер", "Номер трансформатора", "Лицевой счет потребителя", "Тип потребителя",
            "Имя потребителя", "Номер счетчика", "Тип связи", "Имя менеджера", "Телефон менеджера",
            "Несобранный период (день)", "Несобранный период (время)", "GPS(X,Y)", "Адрес установки"]
    nometer = [[1, ESP1, "NS A", "F1", "1", "A1", "Бытовые", "X", "M1", "PLC", "ALI VALI, KARIM", "", 3, "01:00:00", "38.8,65.7", "adr"],
               [2, ESP1, "NS A", "F1", "2", "A2", ctype2, "Y", "M2", "PLC", "", "", 10, "01:00:00", ",", "adr"],
               [3, ESP2, "NS B", "F2", "3", "A3", "Индикатор баланса", "Z", "M3", "GPRS", "SOLIH", "", 120, "01:00:00", "38.9,66.1", "adr"],
               [4, ESP2, "NS B", "F2", "3", "A4", "Бытовые", "W", "M4", "PLC", "SOLIH", "", 40, "01:00:00", ",", "adr"]]
    dm_h = ["No.", "ESP Name", "SOATO", "Substation", "Feeder", "TR", "Meter No.", "Account ID", "Customer Type", "Name",
            "Customer Address", "Meter Type", "GPS"]
    direct = [[1, ESP2, "1", "NS B", "F2", "3", "D1", "AD1", "Бытовые", "N", "addr", "Однофазный", ","]]
    on_h = ["ЭСП", "Подстанция", "Фидер", "ТП", "Тип устройства", "№ Устройства", "Статус", "Время онлайна/офлайна", "Оператор связи",
            "Широта", "Долгота", "IP-адрес устройства", "Порт оборудования", "Сервер IP", "Номер сим карты", "Имя менеджера",
            "Телефон менеджера", "Телефон", "Лицевой счет потребителя"]
    online = [[ESP1, "NS A", "F1", "1", "DCU", "9001", "Offline", offline_time, "UMS", "38.9", "66.0", "", "", "", "", "ALI", "", "", ""],
              [ESP2, "NS B", "F2", "3", "DCU", "9003", "Offline", "23/11/2026 02:00:00", "UMS", "", "", "", "", "", "", "SOLIH", "", "", ""]]
    return {
        "AreaInformationReport.xlsx": _xlsx([["Area Information Report"], [], ["Area:", "Q"]], area_h, area),
        "CommissioningStatus.xlsx": _xlsx([["Отчет о статусе ввода в эксплуатацию"], []], st_h, status),
        "DirectMeter.xlsx": _xlsx([["Сведения о прямых подключениях"], []], dm_h, direct),
        "NoMeterData.xlsx": _xlsx([["Нет информации счетчика Отчет"]], nm_h, nometer),
        "Online_Device_Monitroing_Report_23112026_154148.xlsx": _xlsx(
            [["Отчет по мониторингу сетевых"], ["Region / TR:Qashqadaryo HETK"]], on_h, online, "Device Network Info"),
    }


def _post(client, h, files: dict, day="2026-11-23"):
    parts = [("files", (n, b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) for n, b in files.items()]
    return client.post("/api/daily/upload", files=parts, data={"day": day}, headers=h)


def _wait(client, h, bid, want=("done", "ask", "error")):
    for _ in range(150):
        d = client.get(f"/api/daily/{bid}", headers=h).json()
        if d["status"] in want:
            return d
        time.sleep(0.2)
    raise AssertionError(d)


@pytest.fixture(autouse=True)
def _clean_settings(client):
    yield
    D.save_settings(D.DEFAULTS)           # sozlamalar testlar orasida o'tib ketmasin


@pytest.fixture
def ops(make_user):
    return make_user(["daily.view", "daily.upload", "daily.recompute", "daily.download", "daily.original", "daily.send", "daily.settings", "daily.delete",
                      "telegram.send"])[1]


def test_detect_kinds_by_header_and_name(tmp_path):
    for name, blob in make_files().items():
        p = tmp_path / name
        p.write_bytes(blob)
        kind, _ = D.detect(p, name)
        assert kind == {"AreaInformationReport": "area", "CommissioningStatus": "status", "DirectMeter": "direct",
                        "NoMeterData": "nometer", "Online_Device_Monitroing_Report_23112026_154148": "online"}[name[:-5]]
    p = tmp_path / "x.xlsx"
    p.write_bytes(_xlsx([["Boshqa"]], ["a", "b"], [[1, 2]]))
    with pytest.raises(D.DailyError):
        D.detect(p, "x.xlsx")


def test_detect_ignores_header_text(tmp_path):
    """Sarlavha matni butunlay o'zgargan (boshqa til / nom) bo'lsa ham — turi va ustunlar katak o'rni bo'yicha olinadi."""
    kinds = {"AreaInformationReport": "area", "CommissioningStatus": "status", "DirectMeter": "direct", "NoMeterData": "nometer",
             "Online_Device_Monitroing_Report_23112026_154148": "online"}
    for name, blob in make_files().items():
        wb = openpyxl.load_workbook(io.BytesIO(blob))
        ws = wb.worksheets[0]
        kind0 = kinds[name[:-5]]
        for row in ws.iter_rows(max_row=6):                    # sarlavha va sarlavha oldi qatorlari matnini almashtiramiz
            if not D._is_data(kind0, tuple(c.value for c in row)):
                for c in row:
                    if isinstance(c.value, str):
                        c.value = f"Zaglavie-{c.column}"
        p = tmp_path / "unknown_name.xlsx"
        wb.save(p)
        kind, _ = D.detect(p, "unknown_name.xlsx")
        assert kind == kinds[name[:-5]], name
        assert D.read(p, kind)


def test_edge_labels_and_categories():
    assert D.edge_labels([2, 7, 30, 90]) == ["2-7 kun", "7-30 kun", "1-3 oy", "3 oydan ortiq"]
    assert D.edge_labels([1, 5, 10]) == ["1-5 kun", "5-10 kun", "10 kundan ortiq"]
    assert D.categorize("Бытовые", {}) == "aholi" and D.categorize("Промышленные", {}) == "ulgurji"
    assert D.categorize("Индикатор баланса", {}) == "balans" and D.categorize("Boshqa tur", {}) is None
    assert D.categorize("Boshqa tur", {"boshqa tur": "ulgurji"}) == "ulgurji"


def test_full_flow_tables_and_files(client, ops):
    r = _post(client, ops, make_files())
    assert r.status_code == 200, r.text
    d = _wait(client, ops, r.json()["id"])
    assert d["status"] == "done", d
    t1, t2 = d["tables"]
    tot1, tot2 = t1["total"], t2["total"]
    # 1-jadval: 3 TP; 4 ta kontsentrator (ESP1: 2 ta, ESP2: 3 ta → jami 5); offline 2 ta (biri 20.11 — 3 kun, biri bugun)
    assert tot1["tp"] == 3 and tot1["cas"] == 5
    assert tot1["off"] == 2 and tot1["offgt"] == 1 and tot1["online"] == 3
    assert tot1["un"] == 1                                 # 0 ta hisoblagichli kontsentrator
    assert (tot1["p0"], tot1["p1"], tot1["p2"], tot1["p3"]) == (1, 1, 1, 1)   # 0%, 40%, 75%, 100%  (obxod 0 → 0%)
    # 2-jadval
    assert tot2["tot"] == 4 and (tot2["aho"], tot2["ulg"], tot2["bal"]) == (2, 1, 1)
    assert (tot2["k0"], tot2["k1"], tot2["k2"], tot2["k3"]) == (1, 1, 1, 1) and tot2["dir"] == 1
    assert [r["name"] for r in t1["rows"]][:2] == [ESP1, ESP2]          # tartib: sozlamadagidek
    # Excel fayllar nomi: jadval nomi + sana
    for which, name in (("t1", "Konsentratorlar_23.11.2026.xlsx"),
                        ("t2", "Aloqadan_chiqib_ketgan_hisoblagichlar_soni_23.11.2026.xlsx"),
                        ("task", "Kunlik_topshiriq_23.11.2026.xlsx")):
        f = client.get(f"/api/daily/{d['id']}/file/{which}", headers=ops)
        assert f.status_code == 200 and name in f.headers["content-disposition"], f.headers
        openpyxl.load_workbook(io.BytesIO(f.content))
    # 7 ta alohida nomma-nom fayl: offline (3 kundan ortiq) · obxod 0–50% · primichka · 2-7 / 7-30 / 30-90 / 90+ kun
    def rows_of(which):
        w = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/daily/{d['id']}/file/{which}", headers=ops).content)).worksheets[0]
        return [[c.value for c in r] for r in w.iter_rows(min_row=3) if r[0].value is not None]
    assert [len(rows_of(k)) for k in ("off", "low", "prim", "nm0", "nm1", "nm2", "nm3")] == [1, 2, 1, 1, 1, 1, 1]
    assert rows_of("low")[0][1:5] == [ESP1, "NS A", "F1", "2"]          # 002: 40% obxod; podstansiya/fider Area faylidan
    assert rows_of("off")[0][-1] == "ALI VALI, KARIM"           # 001 TP menejeri Area faylidan
    img = client.get(f"/api/daily/{d['id']}/file/img1", headers=ops)
    assert img.status_code == 200 and img.content[:8] == b"\x89PNG\r\n\x1a\n" and img.headers["content-type"] == "image/png"
    # Topshiriq fayli: 3 varaq, ustunlar tartibi, xodim bo'yicha tartiblash, bo'sh xodim oxirida, nusxasiz
    wb = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/daily/{d['id']}/file/task", headers=ops).content))
    assert wb.sheetnames == ["Offline kontsentratorlar", "Aloqasiz hisoblagichlar", "Primichka"]
    ws = wb["Aloqasiz hisoblagichlar"]
    head = [c.value for c in ws[2]]
    assert head[:5] == ["#", "Tuman", "Podstansiya", "Fider", "TP raqami"] and head[-2:] == ["Joylashuv", "Xodim(lar)"]
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=3)]
    assert len(rows) == 4 and [r[0] for r in rows] == [1, 2, 3, 4]
    mg = [r[-1] for r in rows]
    assert mg[-1] in (None, "") and mg[0] == "ALI VALI, KARIM"          # xodimi yo'q — oxirida, bo'sh
    assert any(c.hyperlink for r in ws.iter_rows(min_row=3) for c in r)    # joylashuv havolasi
    # Asl fayllar saqlangan va yuklab olinadi
    assert d["files"]["nometer"]["name"] == "NoMeterData.xlsx" and d["files"]["nometer"]["rows"] == 4
    o = client.get(f"/api/daily/{d['id']}/file/nometer", headers=ops)
    assert o.status_code == 200 and "NoMeterData.xlsx" in o.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/daily/{d['id']}/zip/orig", headers=ops).content))
    assert len(z.namelist()) == 5
    assert len(zipfile.ZipFile(io.BytesIO(client.get(f"/api/daily/{d['id']}/zip/out", headers=ops).content)).namelist()) == 12
    # Arxiv: ro'yxat, qayta yuklash (almashtiriladi), qayta hisoblash, o'chirish
    assert client.get("/api/daily", headers=ops).json()[0]["id"] == d["id"]
    r2 = _post(client, ops, make_files())
    assert r2.json()["replaced"] is True and r2.json()["id"] == d["id"]
    _wait(client, ops, d["id"])
    assert client.post(f"/api/daily/{d['id']}/recompute", headers=ops).status_code == 200
    assert _wait(client, ops, d["id"])["status"] == "done"
    assert client.delete(f"/api/daily/{d['id']}", headers=ops).status_code == 200
    assert client.get(f"/api/daily/{d['id']}", headers=ops).status_code == 404


def test_old_batch_is_rebuilt_when_opened(client, ops):
    import shutil
    d = _wait(client, ops, _post(client, ops, make_files(), day="2026-11-17").json()["id"])
    out = D.folder(date(2026, 11, 17)) / "out"
    for f in out.iterdir():                                       # eski versiya: faqat t1, t2, task
        if f.name not in ("t1.xlsx", "t2.xlsx", "task.xlsx"):
            f.unlink()
    again = _wait(client, ops, client.get(f"/api/daily/{d['id']}", headers=ops).json()["id"])
    assert again["status"] == "done" and [x["k"] for x in again["outs"]][:2] == ["img1", "img2"] and len(again["outs"]) == 12
    client.delete(f"/api/daily/{d['id']}", headers=ops)


def test_upload_validation_and_permissions(client, ops, make_user):
    f = make_files()
    names = list(f)
    assert _post(client, ops, {n: f[n] for n in names[:4]}).status_code == 400            # 5 tadan kam
    dup = {**{n: f[n] for n in names[:4]}, "Area2.xlsx": f[names[0]]}                     # ikkita Area
    r = _post(client, ops, dup)
    assert r.status_code == 400 and "Ikkita" in r.json()["detail"]
    junk = {**{n: f[n] for n in names[:4]}, "x.xlsx": b"PK\x03\x04 broken"}
    assert _post(client, ops, junk).status_code == 400
    assert _post(client, ops, {**{n: f[n] for n in names[:4]}, "x.txt": b"abc"}).status_code == 400
    assert _post(client, ops, f, day="2026-13-45").status_code == 400
    _, nop = make_user(["daily.view"])
    assert _post(client, nop, f).status_code == 403
    _, none = make_user(["view.konsentrator"])
    assert client.get("/api/daily", headers=none).status_code == 403
    assert client.get("/api/daily/settings", headers=none).status_code == 403
    _, noorig = make_user(["daily.view"])
    d = _wait(client, ops, _post(client, ops, f, day="2026-11-22").json()["id"])
    assert client.get(f"/api/daily/{d['id']}/file/area", headers=noorig).status_code == 403   # asl faylga ruxsat yo'q
    assert client.get(f"/api/daily/{d['id']}/file/t1", headers=noorig).status_code == 403    # yuklab olish alohida ruxsat
    assert client.get(f"/api/daily/{d['id']}/zip/out", headers=noorig).status_code == 403
    assert client.get(f"/api/daily/{d['id']}", headers=noorig).status_code == 200            # ko'rish mumkin
    _, dl = make_user(["daily.view", "daily.download"])
    assert client.get(f"/api/daily/{d['id']}/file/img1", headers=dl).status_code == 200
    assert client.get(f"/api/daily/{d['id']}/zip/out", headers=dl).status_code == 200
    assert client.get(f"/api/daily/{d['id']}/file/area", headers=dl).status_code == 403      # asl fayl — yana boshqa ruxsat
    assert client.post(f"/api/daily/{d['id']}/recompute", headers=dl).status_code == 403
    _, rc = make_user(["daily.view", "daily.recompute"])
    assert client.post(f"/api/daily/{d['id']}/recompute", headers=rc).status_code == 200
    assert client.post(f"/api/daily/{d['id']}/send", json={"files": ["img1"], "chat_ids": [1]}, headers=rc).status_code == 403
    assert client.put("/api/daily/settings", json={}, headers=rc).status_code in (403, 422) and \
        client.get("/api/daily/chats", headers=rc).status_code == 403
    _wait(client, ops, d["id"])
    assert client.delete(f"/api/daily/{d['id']}", headers=noorig).status_code == 403
    client.delete(f"/api/daily/{d['id']}", headers=ops)


def test_unknown_customer_type_is_asked_once_and_remembered(client, ops):
    r = _post(client, ops, make_files(ctype2="Yangi tur"), day="2026-11-21")
    d = _wait(client, ops, r.json()["id"])
    assert d["status"] == "ask" and d["ask"] == [{"value": "Yangi tur", "count": 1}]
    assert client.post(f"/api/daily/{d['id']}/types", json={"map": {"Yangi tur": "yaroqsiz"}}, headers=ops).status_code == 400
    assert client.post(f"/api/daily/{d['id']}/types", json={"map": {"Yangi tur": "ulgurji"}}, headers=ops).status_code == 200
    d = _wait(client, ops, d["id"])
    assert d["status"] == "done" and d["tables"][1]["total"]["ulg"] == 1 and d["tables"][1]["total"]["aho"] == 2
    # javob saqlangan: keyingi yuklashda qayta so'ralmaydi
    r = _post(client, ops, make_files(ctype2="Yangi tur"), day="2026-11-20")
    assert _wait(client, ops, r.json()["id"])["status"] == "done"
    assert client.get("/api/daily/settings", headers=ops).json()["types"]["Yangi tur"] == "ulgurji"
    for day in ("2026-11-21", "2026-11-20"):
        i = next(b["id"] for b in client.get("/api/daily", headers=ops).json() if b["date"] == day)
        client.delete(f"/api/daily/{i}", headers=ops)


def test_settings_change_offline_days_and_names(client, ops):
    s = client.get("/api/daily/settings", headers=ops).json()
    assert s["offline_days"] == 3 and s["labels"] == ["2-7 kun", "7-30 kun", "1-3 oy", "3 oydan ortiq"]
    body = {k: s[k] for k in ("region", "t1_title", "t2_title", "task_title", "offline_days", "time_edges", "esp_order",
                              "types", "fn_t1", "fn_t2", "fn_task", "chats")}
    bad = [("offline_days", 0), ("offline_days", 99), ("time_edges", [7, 2]), ("time_edges", [5]), ("fn_t1", "{nomalum}"),
           ("fn_t1", ""), ("t1_title", " ")]
    for k, v in bad:
        assert client.put("/api/daily/settings", json={**body, k: v}, headers=ops).status_code == 400, k
    s2 = client.put("/api/daily/settings", json={**body, "titles": {"low": "Past obxod", "bad": "x", "off": "  "}}, headers=ops)
    assert s2.status_code == 200 and s2.json()["titles"] == {"low": "Past obxod"}          # noma'lum va bo'sh nomlar tashlanadi
    assert s2.json()["examples"]["low"] == "Past_obxod_23.11.2026.xlsx"
    assert [x["k"] for x in s2.json()["list_titles"]][:3] == ["off", "low", "prim"] and len(s2.json()["list_titles"]) == 7
    client.put("/api/daily/settings", json={**body, "titles": {}}, headers=ops)
    ok = {**body, "offline_days": 1, "fn_task": "Topshiriq_{sana}", "t1_title": "Kontsentratorlar holati"}
    r = client.put("/api/daily/settings", json=ok, headers=ops)
    assert r.status_code == 200 and r.json()["examples"]["task"] == "Topshiriq_2026-11-23.xlsx"
    d = _wait(client, ops, _post(client, ops, make_files(), day="2026-11-23").json()["id"])
    assert d["tables"][0]["total"]["offgt"] == 1                 # faqat bugungisi chiqariladi, 20.11 qoladi
    assert d["tables"][0]["head"][2][2]["l"] == "shundan 1 kundan ortiq"
    assert "Topshiriq_2026-11-23.xlsx" in client.get(f"/api/daily/{d['id']}/file/task", headers=ops).headers["content-disposition"]
    client.delete(f"/api/daily/{d['id']}", headers=ops)


def test_send_files_to_selected_chats(client, ops, fake_tg):
    from sqlalchemy import text
    from app.db import engine, upsert_kv
    from app.services import telegram as tgs
    with engine.begin() as c:
        upsert_kv(c, "tg_token", "x")
    tgs.upsert_chat({"id": -100555, "title": "Kunlik guruh", "type": "supergroup"}, source="manual")
    with engine.begin() as c:
        cid = c.execute(text("SELECT id FROM tg_chats WHERE chat_id='-100555'")).scalar()
    assert any(c["id"] == cid for c in client.get("/api/daily/chats", headers=ops).json())
    d = _wait(client, ops, _post(client, ops, make_files(), day="2026-11-18").json()["id"])
    assert client.post(f"/api/daily/{d['id']}/send", json={"files": [], "chat_ids": [cid]}, headers=ops).status_code == 400
    assert client.post(f"/api/daily/{d['id']}/send", json={"files": ["bad"], "chat_ids": [cid]}, headers=ops).status_code == 400
    allf = [x["k"] for x in client.get(f"/api/daily/{d['id']}", headers=ops).json()["outs"] if x["default"]]
    assert allf == ["img1", "img2", "off", "low", "prim", "nm0", "nm1", "nm2", "nm3"]
    r = client.post(f"/api/daily/{d['id']}/send", json={"files": allf[::-1], "chat_ids": [cid], "ack": False}, headers=ops)
    assert r.status_code == 200, r.text
    for _ in range(60):
        st = client.get(f"/api/reports/send/{r.json()['id']}", headers=ops).json()
        if st["status"] != "running":
            break
        time.sleep(0.2)
    assert st["status"] == "done", st
    log = [l.split("\t") for l in st["log"].split("\n")]       # jonli progress oynasi shu formatni o'qiydi
    assert log[0][0] == "…" and ["✓", "img1+img2", "Kunlik guruh"] in log and ["✓", "nm3", "Kunlik guruh"] in log
    assert st["progress"] == 100
    sent = [s[1] for s in fake_tg if s[0] == "-100555"]            # tartib: avval 2 rasm, keyin 7 fayl
    assert sent == ["ALBUM:Konsentratorlar_18.11.2026.png+Aloqadan_chiqib_ketgan_hisoblagichlar_soni_18.11.2026.png",
                    "Offline_konsentratorlar_(3_kundan_ortiq)_18.11.2026.xlsx",
                    "Obxod_olish_darajasi_past_konsentratorlar_(0-50%)_18.11.2026.xlsx",
                    "Togridan_togri_ulanish_(Primichka)_18.11.2026.xlsx",
                    "Aloqadan_chiqib_ketgan_hisoblagichlar_2-7_kun_18.11.2026.xlsx",
                    "Aloqadan_chiqib_ketgan_hisoblagichlar_7-30_kun_18.11.2026.xlsx",
                    "Aloqadan_chiqib_ketgan_hisoblagichlar_30-90_kun_18.11.2026.xlsx",
                    "Aloqadan_chiqib_ketgan_hisoblagichlar_90_kundan_ortiq_18.11.2026.xlsx"]
    assert not any(fake_tg.captions)                              # faqat fayl
    # faqat bitta rasm tanlansa — albom emas, oddiy rasm
    fake_tg.clear()
    r = client.post(f"/api/daily/{d['id']}/send", json={"files": ["img2"], "chat_ids": [cid]}, headers=ops)
    for _ in range(60):
        if client.get(f"/api/reports/send/{r.json()['id']}", headers=ops).json()["status"] != "running":
            break
        time.sleep(0.2)
    assert [s[1] for s in fake_tg if s[0] == "-100555"] == ["Aloqadan_chiqib_ketgan_hisoblagichlar_soni_18.11.2026.png"]
    client.delete(f"/api/daily/{d['id']}", headers=ops)


def test_other_sections_are_not_mixed():
    """Alohida bo'lim: o'z jadvali va o'z papkasi; boshqa bo'limlar jadvallariga tegmaydi."""
    from app.models import Base
    assert "daily_batches" in Base.metadata.tables
    assert D.folder(date(2026, 11, 23)).parts[-2:] == ("daily", "2026-11-23")
