"""Login cheklovi, ishonchli IP, qurilma cookie'si va bloklangan qurilmani aylanib o'tish urinishi."""
from types import SimpleNamespace

import pytest

from app import store, throttle
from app.services import devices as D
from tests.conftest import login


def _req(peer, headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers={k.lower(): v for k, v in (headers or {}).items()})


# ---------------------------------------------------------------- IP
def test_untrusted_peer_cannot_spoof_headers():
    r = _req("203.0.113.9", {"CF-Connecting-IP": "1.2.3.4", "X-Forwarded-For": "5.6.7.8"})
    assert D.client_ip(r) == "203.0.113.9"


def test_trusted_proxy_uses_cloudflare_header():
    assert D.client_ip(_req("172.18.0.5", {"CF-Connecting-IP": "198.51.100.7"})) == "198.51.100.7"
    assert D.client_ip(_req("127.0.0.1", {"CF-Connecting-IP": "198.51.100.7"})) == "198.51.100.7"


def test_xff_takes_rightmost_untrusted():
    r = _req("172.18.0.5", {"X-Forwarded-For": "6.6.6.6, 198.51.100.7, 172.18.0.2"})
    assert D.client_ip(r) == "198.51.100.7"          # chapdagi 6.6.6.6 — mijoz yozgan soxta qiymat


def test_garbage_header_ignored():
    assert D.client_ip(_req("127.0.0.1", {"CF-Connecting-IP": "not-an-ip"})) == "127.0.0.1"


# ---------------------------------------------------------------- throttle
def test_throttle_locks_pair_and_escalates():
    for _ in range(3):
        assert throttle.register_fail("bob", "1.1.1.1") == 0
    assert throttle.register_fail("bob", "1.1.1.1") == throttle.LEVELS[0]      # 4-urinish (limit 4) bloklaydi
    assert throttle.retry_after("bob", "1.1.1.1") > 0
    assert throttle.retry_after("bob", "2.2.2.2") == 0                       # boshqa IP bloklanmaydi
    assert throttle.retry_after("alice", "1.1.1.1") == 0                     # boshqa login ham


def test_throttle_clear_on_success():
    throttle.register_fail("carol", "3.3.3.3")
    throttle.clear("carol", "3.3.3.3")
    for _ in range(3):
        assert throttle.register_fail("carol", "3.3.3.3") == 0


def test_login_endpoint_rate_limited(client):
    for _ in range(4):
        assert login(client, "sadmin", "wrong-pass", device="d" * 20).status_code == 401
    r = login(client, "sadmin", "Sadmin@Test1", device="d" * 20)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_throttle_state_lives_in_store_not_process():
    """Cheklov holati umumiy omborda (Redis) — jarayon almashsa ham yo'qolmaydi."""
    for _ in range(4):
        throttle.register_fail("dave", "4.4.4.4")
    s = store.get_store()
    other = store.MemStore()
    other._d, other._lock = s._d, s._lock       # xuddi shu ombor, "boshqa jarayon" ko'rinishida
    store.use_store(other)
    assert throttle.retry_after("dave", "4.4.4.4") > 0


# ---------------------------------------------------------------- qurilma
def test_device_cookie_issued_and_reused(client):
    r = client.post("/api/auth/ping", json={"device_id": None}, headers={"User-Agent": "UA-cookie-test"})
    assert D.COOKIE in r.headers.get("set-cookie", "")
    assert "httponly" in r.headers["set-cookie"].lower()


def test_forged_cookie_is_ignored(client):
    r = client.post("/api/auth/ping", json={}, headers={"User-Agent": "UA-forge", "Cookie": f"{D.COOKIE}=deadbeef" * 1 + ".bad"})
    assert r.status_code == 200 and not r.json()["blocked"]


def test_blocked_device_stays_blocked_after_clearing_storage(client, admin, make_user):
    ua = {"User-Agent": "Mozilla/5.0 BlockedUA-Test"}
    name, _h = make_user([])
    cl = type(client)(client.app, base_url="http://localhost")       # alohida cookie jar
    with cl:
        lr = cl.post("/api/auth/login", json={"username": name, "password": "Passw0rd!", "device_id": "z" * 24}, headers=ua)
        assert lr.status_code == 200
        devs = client.get("/api/devices", headers=admin).json()["items"]
        mine = next(d for d in devs if d["ua"] == ua["User-Agent"])
        b = client.post(f"/api/devices/{mine['id']}/block", json={"blocked": True}, headers=admin)
        assert b.status_code == 200, b.text
        assert cl.post("/api/auth/ping", json={"device_id": "z" * 24}, headers=ua).json()["blocked"] is True
    # cookie ham, localStorage ham tozalangan "yangi" brauzer — bir xil IP+UA
    fresh = type(client)(client.app, base_url="http://localhost")
    with fresh:
        r = fresh.post("/api/auth/ping", json={"device_id": "q" * 24}, headers=ua)
        assert r.json()["blocked"] is True
        r = fresh.post("/api/auth/login", json={"username": name, "password": "Passw0rd!", "device_id": "q" * 24}, headers=ua)
        assert r.status_code == 403


def test_single_active_session_per_login(client, make_user):
    name, h1 = make_user([])
    r2 = login(client, name, "Passw0rd!", device="second-device-".ljust(20, "y"))
    assert r2.status_code == 200
    assert client.get("/api/auth/me", headers=h1).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r2.json()['token']}"}).status_code == 200
