"""Login urinishlarini cheklash (Redis yoki xotira). Bosqichma-bosqich oshib boruvchi bloklash.

Uch kalit: login+IP juftligi (asosiy), bitta IP (turli loginlarni sinash), bitta login (turli IPlardan —
taqsimlangan hujum). Faqat login bo'yicha bloklash begona odamga haqiqiy xodimni bloklash imkonini berar edi,
shuning uchun juftlik chegarasi qattiq, login chegarasi esa yuqori."""
from .config import settings
from .store import get_store

LEVELS = [60, 300, 900, 3600]       # ketma-ket bloklash davomiyligi (soniya)


def _keys(user: str, ip: str, scope: str) -> list[tuple[str, int]]:
    u = (user or "").strip().lower()[:64]
    return [(f"thr:{scope}:pair:{u}|{ip}", settings.login_limit_pair),
            (f"thr:{scope}:ip:{ip}", settings.login_limit_ip),
            (f"thr:{scope}:user:{u}", settings.login_limit_user)]


def retry_after(user: str, ip: str, scope: str = "login") -> int:
    """Bloklangan bo'lsa — necha soniyadan keyin urinish mumkinligini qaytaradi, aks holda 0."""
    s = get_store()
    return max([max(0, s.ttl(f"{k}:lock")) for k, _ in _keys(user, ip, scope)] + [0])


def register_fail(user: str, ip: str, scope: str = "login") -> int:
    """Xato urinishni qayd etadi. Chegaradan oshsa bloklaydi va blok davomiyligini qaytaradi (yoki 0)."""
    s = get_store()
    lock = 0
    for k, limit in _keys(user, ip, scope):
        n = s.incr(k)
        if n == 1:
            s.expire(k, settings.login_window_sec)
        if n >= limit:
            lvl = s.incr(f"{k}:lvl")
            s.expire(f"{k}:lvl", 86400)
            dur = LEVELS[min(lvl - 1, len(LEVELS) - 1)]
            s.set(f"{k}:lock", "1", ex=dur)
            s.delete(k)
            lock = max(lock, dur)
    return lock


def clear(user: str, ip: str, scope: str = "login") -> None:
    """Muvaffaqiyatli kirishdan keyin juftlik hisobini tozalaydi."""
    k = _keys(user, ip, scope)[0][0]
    get_store().delete(k, f"{k}:lvl")


def fmt_wait(sec: int) -> str:
    return f"{sec} soniya" if sec < 90 else f"{(sec + 59) // 60} daqiqa"
