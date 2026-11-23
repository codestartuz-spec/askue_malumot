"""Shifrlash, Redis/xotira ombori, fon vazifalari navbati, ilova sozlamalari."""
import json
import os
import shutil
import subprocess
import time

import pytest

from app import store, tasks
from app.config import settings
from app.services import crypto

REDIS_BIN = shutil.which("redis-server")


@pytest.fixture(scope="module")
def redis_store():
    url = os.environ.get("TEST_REDIS_URL")
    proc = None
    if not url:
        if not REDIS_BIN:
            pytest.skip("redis-server topilmadi")
        proc = subprocess.Popen([REDIS_BIN, "--port", "6391", "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL)
        url = "redis://127.0.0.1:6391/0"
        time.sleep(0.6)
    import redis
    cli = redis.Redis.from_url(url, decode_responses=True)
    cli.flushdb()
    yield store.RedisStore(cli)
    cli.flushdb()
    if proc:
        proc.terminate()


# ------------------------------------------------------------------ shifrlash
def test_backup_encryption_roundtrip_and_tamper():
    blob = b"-- SQL dump --" * 1000
    enc = crypto.encrypt_bytes(blob)
    assert enc.startswith(crypto.MAGIC) and blob[:20] not in enc
    assert crypto.decrypt_bytes(enc) == blob
    with pytest.raises(ValueError):
        crypto.decrypt_bytes(enc[:-5] + b"AAAAA")


def test_backup_wrong_key_fails(monkeypatch):
    enc = crypto.encrypt_bytes(b"secret")
    monkeypatch.setattr(settings, "backup_key", "boshqa-kalit")
    with pytest.raises(ValueError):
        crypto.decrypt_bytes(enc)


def test_legacy_plain_backup_passes_through():
    assert crypto.decrypt_bytes(b"\x1f\x8bplain-gzip") == b"\x1f\x8bplain-gzip"


def test_text_secret_encrypt_decrypt():
    e = crypto.encrypt_text("123456:ABC-token")
    assert e.startswith("enc1:") and "ABC" not in e
    assert crypto.decrypt_text(e) == "123456:ABC-token"
    assert crypto.decrypt_text("eski-ochiq-token") == "eski-ochiq-token"
    assert crypto.encrypt_text(e) == e


def test_telegram_token_is_stored_encrypted(client, admin, monkeypatch):
    from sqlalchemy import text
    from app.db import engine
    from app.services import telegram as tg
    monkeypatch.setattr(tg, "call", lambda *a, **k: {"username": "test_bot", "first_name": "T"})
    r = client.put("/api/telegram/token", json={"token": "999:SECRET-VALUE"}, headers=admin)
    assert r.status_code == 200, r.text
    with engine.connect() as c:
        raw = c.execute(text("SELECT v FROM kv WHERE k='tg_token'")).scalar()
    assert raw.startswith("enc1:") and "SECRET" not in raw
    monkeypatch.undo()
    assert tg.get_token() == "999:SECRET-VALUE"


def test_backup_file_is_encrypted_and_restorable(client, admin):
    from app.services import backup
    r = client.post("/api/system/backups/run", headers=admin)
    assert r.status_code == 200, r.text
    name = r.json()["filename"]
    assert name.endswith(".enc")
    raw = (backup._bdir() / name).read_bytes()
    assert raw.startswith(crypto.MAGIC)
    import gzip
    sql = gzip.decompress(crypto.decrypt_bytes(raw)).decode()
    assert "CREATE TABLE" in sql or "INSERT INTO" in sql
    assert "enc1:" in sql or "tg_token" not in sql          # token ochiq holda zaxiraga tushmaydi


# ------------------------------------------------------------------ ombor
@pytest.mark.parametrize("kind", ["mem", "redis"])
def test_store_contract(kind, request):
    s = store.MemStore() if kind == "mem" else request.getfixturevalue("redis_store")
    s.flushall()
    assert s.get("a") is None
    assert s.set("a", "1", ex=5) and s.get("a") == "1"
    assert not s.set("a", "2", nx=True)
    assert s.incr("n") == 1 and s.incr("n") == 2
    assert 0 < s.ttl("a") <= 5 and s.ttl("nokey") == -2
    s.expire("n", 1)
    assert s.delete("a") == 1
    s.rpush("q", "x"); s.rpush("q", "y")
    assert s.blmove("q", "p", 1) == "x" and s.lrange("p", 0, -1) == ["x"] and s.llen("q") == 1
    assert s.lrem("p", 1, "x") == 1 and s.lrange("p", 0, -1) == []
    assert s.blmove("empty", "p", 1) is None


def test_memstore_expiry():
    s = store.MemStore()
    s.set("k", "v", ex=1)
    time.sleep(1.1)
    assert s.get("k") is None


@pytest.mark.parametrize("kind", ["mem", "redis"])
def test_leader_lock_single_owner(kind, request):
    s = store.MemStore() if kind == "mem" else request.getfixturevalue("redis_store")
    s.flushall()
    store.use_store(s)
    assert store.acquire_lock("job", 30, "A")
    assert not store.acquire_lock("job", 30, "B")
    assert store.acquire_lock("job", 30, "A")        # egasi yangilaydi
    s.delete("askue:lock:job")
    assert store.acquire_lock("job", 30, "B")


# ------------------------------------------------------------------ vazifalar
RESULTS = []


@tasks.task("test.echo")
def _echo(x, y=0):
    RESULTS.append(x + y)


def test_task_runs_in_pool_without_redis():
    RESULTS.clear()
    store.use_store(store.MemStore())
    tasks.submit("test.echo", 2, y=3)
    for _ in range(50):
        if RESULTS:
            break
        time.sleep(0.05)
    assert RESULTS == [5]


def test_task_args_must_be_json():
    with pytest.raises(TypeError):
        tasks.submit("test.echo", object())


def test_redis_queue_worker_and_crash_recovery(redis_store):
    import threading
    RESULTS.clear()
    redis_store.flushall()
    store.use_store(redis_store)
    tasks.submit("test.echo", 1, y=1)
    assert redis_store.llen(tasks.QUEUE) == 1 and not RESULTS        # API navbatga yozdi, o'zi bajarmadi
    # worker yiqilgan: vazifa "ishlanmoqda" ro'yxatida qolgan
    raw = redis_store.blmove(tasks.QUEUE, tasks.PROC, 1)
    assert redis_store.llen(tasks.PROC) == 1
    assert tasks.recover() == 1 and redis_store.llen(tasks.QUEUE) == 1
    stop = threading.Event()
    th = threading.Thread(target=tasks.consume_forever, args=(stop, 1), daemon=True)
    th.start()
    for _ in range(50):
        if RESULTS:
            break
        time.sleep(0.1)
    stop.set()
    th.join(3)
    assert RESULTS == [2] and redis_store.llen(tasks.PROC) == 0 and json.loads(raw)["name"] == "test.echo"


def test_login_throttle_shared_through_redis(redis_store, client):
    """Ikki API jarayoni bitta Redis'ni ko'radi: biridagi xato urinishlar ikkinchisida ham hisoblanadi."""
    from app import throttle
    redis_store.flushall()
    store.use_store(redis_store)
    for _ in range(4):
        throttle.register_fail("eve", "9.9.9.9")
    second = store.RedisStore(redis_store.r)          # "boshqa jarayon"
    store.use_store(second)
    assert throttle.retry_after("eve", "9.9.9.9") > 0


# ------------------------------------------------------------------ sozlamalar
def test_app_settings_roundtrip_and_cache(client, admin, make_user):
    r = client.get("/api/appsettings", headers=admin).json()
    assert {x["key"] for x in r} >= {"region_name", "ag_region", "ag_title", "ag_start_date"}
    bad = client.put("/api/appsettings", json={"values": {"ag_start_date": "20.02.2023"}}, headers=admin)
    assert bad.status_code == 400
    assert client.put("/api/appsettings", json={"values": {"nope": "x"}}, headers=admin).status_code == 400
    ok = client.put("/api/appsettings", json={"values": {"region_name": "Test filiali"}}, headers=admin)
    assert ok.status_code == 200
    assert client.get("/api/meta/bootstrap", headers=admin).json()["region_name"] == "Test filiali"
    _, h = make_user([])
    assert client.put("/api/appsettings", json={"values": {"region_name": "x"}}, headers=h).status_code == 403
    client.put("/api/appsettings", json={"values": {"region_name": "Qashqadaryo hududiy filiali"}}, headers=admin)


def test_security_headers_and_api_no_store(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["cache-control"] == "no-store"


def test_telegram_message_with_files_goes_through_outbox(client, make_user, fake_tg):
    from sqlalchemy import text
    from app.db import engine, upsert_kv
    from app.services import telegram as tgs
    _, h = make_user(["telegram.message"])
    with engine.begin() as c:
        upsert_kv(c, "tg_token", "x")
    tgs.upsert_chat({"id": -100888, "title": "Xabar kanali", "type": "channel"}, source="manual")
    with engine.connect() as c:
        cid = c.execute(text("SELECT id FROM tg_chats WHERE chat_id='-100888'")).scalar()
    r = client.post("/api/telegram/send", data={"chat_ids": str(cid), "message": "Salom", "ack": "false"},
                    files=[("files", ("a.png", b"\x89PNG" + b"0" * 50, "image/png"))], headers=h)
    assert r.status_code == 200, r.text
    for _ in range(60):
        st = client.get(f"/api/reports/send/{r.json()['id']}", headers=make_user(["telegram.send"])[1]).json()
        if st["status"] != "running":
            break
        time.sleep(0.2)
    assert st["status"] == "done", st
    assert ("-100888", "msg", 1) in fake_tg
    assert not (settings.data_dir / "outbox" / str(r.json()["id"])).exists()       # vaqtinchalik fayllar tozalandi


def test_referrer_policy_allows_map_tiles(client):
    """same-origin bo'lsa OSM plitkalari Referer'siz so'raladi va 403 beradi — origin yuborilishi shart."""
    r = client.get("/api/appsettings/public")
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-content-type-options"] == "nosniff"
