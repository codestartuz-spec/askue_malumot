"""Test muhiti: alohida MySQL/MariaDB bazasi (askue_test), MySQL 8 sql_mode, soxta Telegram."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_URL = os.environ.get("TEST_DATABASE_URL", "mysql+pymysql://root:root@127.0.0.1:3306/askue_test?charset=utf8mb4")
os.environ.update({
    "ENV": "test", "DATABASE_URL": TEST_URL, "SECRET_KEY": "test-secret-key-test-secret-key-0123456789",
    "SADMIN_USERNAME": "sadmin", "SADMIN_PASSWORD": "Sadmin@Test1", "REDIS_URL": os.environ.get("TEST_REDIS_URL", ""),
    "DATA_DIR": str(ROOT / "tests" / ".data"), "SEND_DELAY_SEC": "0", "LOGIN_LIMIT_PAIR": "4",
})
(ROOT / "tests" / ".data").mkdir(exist_ok=True)

import shutil  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

url = make_url(TEST_URL)
_eng = create_engine(url._replace(database=None), isolation_level="AUTOCOMMIT")
with _eng.connect() as c:
    c.execute(text(f"DROP DATABASE IF EXISTS `{url.database}`"))
_eng.dispose()
shutil.rmtree(ROOT / "tests" / ".data", ignore_errors=True)
(ROOT / "tests" / ".data").mkdir(exist_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app import store  # noqa: E402
from app.main import app  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def client():
    with TestClient(app, base_url="http://localhost") as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_store():
    store.use_store(store.MemStore())
    yield


def login(client, username="sadmin", password="Sadmin@Test1", device=None):
    r = client.post("/api/auth/login", json={"username": username, "password": password, "device_id": device})
    return r


@pytest.fixture(scope="session")
def admin(client):
    r = login(client)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


_n = [0]


@pytest.fixture
def make_user(client, admin):
    """make_user(perms) -> (username, headers). Har chaqiruvda yangi xodim yaratadi va unga kiradi."""
    def mk(perms):
        _n[0] += 1
        name = f"u{_n[0]}_{os.getpid()}"
        r = client.post("/api/users", json={"username": name, "password": "Passw0rd!", "full_name": name, "perms": perms,
                                            "is_active": True}, headers=admin)
        assert r.status_code == 200, r.text
        lr = login(client, name, "Passw0rd!", device=f"dev{name}".ljust(20, "x"))
        assert lr.status_code == 200, lr.text
        return name, {"Authorization": f"Bearer {lr.json()['token']}"}
    return mk


@pytest.fixture
def fake_tg(monkeypatch):
    """Telegramga haqiqiy so'rov yubormaydi: yuborilganlar ro'yxatini yig'adi."""
    from app.services import telegram as tg
    sent = []
    monkeypatch.setattr(tg, "send_file", lambda chat, name, blob, cap="", markup=None: (sent.append((chat, name, len(blob))) or {"message_id": 1}))
    monkeypatch.setattr(tg, "send_post", lambda chat, msg, files, markup=None: (sent.append((chat, "msg", len(files))) or 1))
    monkeypatch.setattr(tg, "send_text", lambda chat, text_, *a, **k: sent.append((chat, "text", text_)))
    monkeypatch.setattr(tg, "get_token", lambda: "123:fake")
    return sent
