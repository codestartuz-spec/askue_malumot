"""Umumiy tezkor ombor: Redis (bo'lsa) yoki bitta jarayon ichidagi xotira (zaxira rejim).

Redis kerak bo'ladigan joylar: login cheklovi, navbat, yetakchi qulf (leader lock), kesh.
REDIS_URL bo'sh bo'lsa xotira rejimi ishlaydi — bitta jarayonli mahalliy ishga tushirish uchun yetarli."""
import threading
import time
from collections import deque

from .config import settings


class MemStore:
    """Redis'ning bizga kerak qismining xotiradagi nusxasi."""
    is_redis = False

    def __init__(self) -> None:
        self._d: dict[str, tuple[object, float | None]] = {}
        self._lists: dict[str, deque] = {}
        self._lock = threading.RLock()

    def _alive(self, k: str):
        v = self._d.get(k)
        if v and v[1] is not None and v[1] <= time.time():
            self._d.pop(k, None)
            return None
        return v

    def get(self, k):
        with self._lock:
            v = self._alive(k)
            return None if v is None else str(v[0])

    def set(self, k, v, ex=None, nx=False):
        with self._lock:
            if nx and self._alive(k) is not None:
                return False
            self._d[k] = (v, time.time() + ex if ex else None)
            return True

    def incr(self, k, by=1):
        with self._lock:
            v = self._alive(k)
            n = int(v[0]) + by if v else by
            self._d[k] = (n, v[1] if v else None)
            return n

    def expire(self, k, sec):
        with self._lock:
            v = self._alive(k)
            if v:
                self._d[k] = (v[0], time.time() + sec)
            return bool(v)

    def ttl(self, k):
        with self._lock:
            v = self._alive(k)
            if not v:
                return -2
            return -1 if v[1] is None else max(0, int(v[1] - time.time() + 0.999))

    def delete(self, *ks):
        with self._lock:
            n = 0
            for k in ks:
                n += 1 if self._d.pop(k, None) is not None else 0
            return n

    def rpush(self, k, v):
        with self._lock:
            self._lists.setdefault(k, deque()).append(v)
            return len(self._lists[k])

    def blmove(self, src, dst, timeout=0):
        end = time.time() + timeout
        while True:
            with self._lock:
                q = self._lists.get(src)
                if q:
                    v = q.popleft()
                    self._lists.setdefault(dst, deque()).append(v)
                    return v
            if time.time() >= end:
                return None
            time.sleep(0.2)

    def lrem(self, k, count, v):
        with self._lock:
            q = self._lists.get(k)
            if q and v in q:
                q.remove(v)
                return 1
            return 0

    def lrange(self, k, a, b):
        with self._lock:
            q = list(self._lists.get(k, []))
            return q[a:] if b == -1 else q[a:b + 1]

    def llen(self, k):
        with self._lock:
            return len(self._lists.get(k, []))

    def flushall(self):
        with self._lock:
            self._d.clear()
            self._lists.clear()


class RedisStore:
    is_redis = True

    def __init__(self, client) -> None:
        self.r = client

    def get(self, k):
        return self.r.get(k)

    def set(self, k, v, ex=None, nx=False):
        return bool(self.r.set(k, v, ex=ex, nx=nx))

    def incr(self, k, by=1):
        return int(self.r.incrby(k, by))

    def expire(self, k, sec):
        return bool(self.r.expire(k, sec))

    def ttl(self, k):
        return int(self.r.ttl(k))

    def delete(self, *ks):
        return int(self.r.delete(*ks)) if ks else 0

    def rpush(self, k, v):
        return int(self.r.rpush(k, v))

    def blmove(self, src, dst, timeout=0):
        return self.r.blmove(src, dst, timeout, "LEFT", "RIGHT")

    def lrem(self, k, count, v):
        return int(self.r.lrem(k, count, v))

    def lrange(self, k, a, b):
        return self.r.lrange(k, a, b)

    def llen(self, k):
        return int(self.r.llen(k))

    def flushall(self):
        self.r.flushdb()


import os
import uuid

OWNER = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"      # shu jarayon identifikatori (qulf egasi)
_store = None
_slock = threading.Lock()


def get_store():
    global _store
    if _store is None:
        with _slock:
            if _store is None:
                _store = _connect()
    return _store


def _connect():
    if settings.redis_url:
        try:
            import redis
            cli = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=10,
                                       socket_connect_timeout=5, health_check_interval=30)
            cli.ping()
            print("Redis ulandi:", settings.redis_url.split("@")[-1], flush=True)
            return RedisStore(cli)
        except Exception as e:  # noqa: BLE001
            if settings.env == "production":
                raise RuntimeError(f"Redis'ga ulanib bo'lmadi: {e}") from e
            print("OGOHLANTIRISH: Redis'ga ulanib bo'lmadi, xotira rejimiga o'tildi:", e, flush=True)
    return MemStore()


def use_store(s) -> None:
    """Testlar uchun almashtirish."""
    global _store
    _store = s


def acquire_lock(name: str, ttl: int, owner: str) -> bool:
    """Yetakchi qulf: kimda bo'lsa o'sha ishlaydi. Egasi har aylanishda yangilaydi."""
    s = get_store()
    key = f"askue:lock:{name}"
    if s.set(key, owner, ex=ttl, nx=True):
        return True
    if s.get(key) == owner:
        s.expire(key, ttl)
        return True
    return False
