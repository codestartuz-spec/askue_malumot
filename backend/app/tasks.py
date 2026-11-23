"""Fon vazifalari. Oddiy threading.Thread o'rniga.

 • Redis bor:    vazifa ro'yxatga (askue:tasks) yoziladi, worker jarayoni uni ishonchli tarzda oladi
                 (BLMOVE → "ishlanmoqda" ro'yxati). Worker yiqilsa, qayta ishga tushganda yarim qolganlar
                 navbatga qaytariladi. API qayta ishga tushsa ham vazifa yo'qolmaydi.
 • Redis yo'q:   cheklangan ThreadPoolExecutor (API jarayonining o'zida) — mahalliy kompyuter uchun.

Vazifa argumentlari JSON bo'lishi shart (pickle ishlatilmaydi — Redis'ga yozish imkoni bor odam kod bajartira olmasin)."""
import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from .store import get_store

QUEUE = "askue:tasks"
PROC = "askue:tasks:processing"
REGISTRY: dict[str, callable] = {}
_pool: ThreadPoolExecutor | None = None
_pl = threading.Lock()


def task(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        fn.task_name = name
        return fn
    return deco


def load_all() -> None:
    """Vazifa funksiyalari ro'yxatdan o'tishi uchun ularni saqlovchi modullarni import qiladi."""
    from .routers import ag, daily, reports, republic, telegram  # noqa: F401
    from .services import telegram as _t  # noqa: F401


def _execute(raw: str) -> None:
    msg = json.loads(raw)
    fn = REGISTRY.get(msg["name"])
    if fn is None:
        load_all()
        fn = REGISTRY.get(msg["name"])
    if fn is None:
        print("Noma'lum vazifa:", msg["name"], flush=True)
        return
    try:
        fn(*msg.get("args", []), **msg.get("kwargs", {}))
    except Exception:  # noqa: BLE001
        print(f"Vazifa xatosi: {msg['name']}", flush=True)
        traceback.print_exc()


def submit(name: str, *args, **kwargs) -> str:
    """Vazifani navbatga qo'yadi. Argumentlar JSON ko'rinishida bo'lishi kerak."""
    raw = json.dumps({"id": uuid.uuid4().hex, "name": name, "args": args, "kwargs": kwargs}, ensure_ascii=False)
    s = get_store()
    if s.is_redis:
        s.rpush(QUEUE, raw)
    else:
        global _pool
        with _pl:
            if _pool is None:
                _pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="task")
        _pool.submit(_execute, raw)
    return raw


def recover() -> int:
    """Worker qayta ishga tushganda oldingi yarim qolgan vazifalarni navbatga qaytaradi."""
    s = get_store()
    if not s.is_redis:
        return 0
    n = 0
    for raw in s.lrange(PROC, 0, -1):
        s.rpush(QUEUE, raw)
        s.lrem(PROC, 1, raw)
        n += 1
    return n


def consume_forever(stop: threading.Event | None = None, poll: int = 5) -> None:
    """Worker uchun: Redis navbatidan vazifalarni ishonchli oladi va bajaradi."""
    s = get_store()
    load_all()
    while not (stop and stop.is_set()):
        try:
            raw = s.blmove(QUEUE, PROC, poll)
            if raw is None:
                continue
            _execute(raw)
            s.lrem(PROC, 1, raw)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            time.sleep(2)
