"""Bo'laklab (≈5 MB) yuklash: sekin/uzilib turadigan internetda ham Details faylini serverga yetkazish.

Generator Details CSV'ni mustaqil .csv.gz bo'laklarga bo'ladi (…part001-of-008.csv.gz …) va manifest (.json) yozadi.
Brauzer har bo'lakni alohida yuboradi (uzilsa faqat shu bo'lak qayta yuboriladi), server hammasi kelganini
va yaxlitligini (SHA-256, qatorlar soni) tekshirgach, ishni navbatga qo'yadi.
Bu modul bazaga bog'liq emas (fayllar bilan ishlaydi) — alohida sinash oson.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

from ..config import settings

MAX_PARTS = 500
PART_NAME_RE = re.compile(r"part(\d{3})-of-(\d{3})", re.I)


class ChunkError(Exception):
    pass


def session_dir(jid: int) -> Path:
    return settings.data_dir / "uploads" / f"job{jid}"


def details_dir(jid: int) -> Path:
    return session_dir(jid) / "details"


def area_file(jid: int) -> Path:
    return session_dir(jid) / "area.csv.gz"


def part_file(jid: int, n: int) -> Path:
    return details_dir(jid) / f"{n:03d}.csv.gz"


def clean_manifest(m) -> dict | None:
    """Brauzer yuborgan manifestdan faqat kerakli maydonlarni olib qoladi (hajm va turini tekshiradi)."""
    if not m:
        return None
    if not isinstance(m, dict) or not isinstance(m.get("parts"), list):
        raise ChunkError("Manifest fayli noto'g'ri")
    parts = []
    for p in m["parts"][:MAX_PARTS]:
        try:
            parts.append({"part": int(p["part"]), "rows": int(p["rows"]), "bytes": int(p["bytes"]),
                          "sha256": str(p["sha256"]).lower()})
        except (KeyError, TypeError, ValueError):
            raise ChunkError("Manifest fayli noto'g'ri (bo'laklar ro'yxati)")
    return {"parts_total": len(parts), "rows_total": sum(p["rows"] for p in parts), "parts": parts}


def save_manifest(jid: int, manifest: dict) -> None:
    d = session_dir(jid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def load_manifest(jid: int) -> dict | None:
    f = session_dir(jid) / "manifest.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _validate_blob(data: bytes, what: str) -> None:
    if not data:
        raise ChunkError(f"{what}: bo'sh bo'lak")
    if len(data) > settings.max_part_mb * 1048576:
        raise ChunkError(f"{what}: bo'lak {settings.max_part_mb} MB dan katta")
    if data[:2] != b"\x1f\x8b":
        raise ChunkError(f"{what}: bu haqiqiy .gz fayl emas")


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def save_part(jid: int, n: int, total: int, data: bytes) -> dict:
    """Bitta Details bo'lagini saqlaydi (qayta yuborilsa ustiga yozadi). Manifest bo'lsa SHA-256 tekshiriladi."""
    if not (1 <= n <= total <= MAX_PARTS):
        raise ChunkError("Bo'lak raqami noto'g'ri")
    name = f"Details {n}/{total}"
    _validate_blob(data, name)
    m = load_manifest(jid)
    if m:
        if m["parts_total"] != total:
            raise ChunkError(f"{name}: manifestda {m['parts_total']} ta bo'lak ko'rsatilgan")
        want = next((p for p in m["parts"] if p["part"] == n), None)
        if want is None:
            raise ChunkError(f"{name}: manifestda bu bo'lak yo'q")
        if len(data) != want["bytes"] or hashlib.sha256(data).hexdigest() != want["sha256"]:
            raise ChunkError(f"{name}: bo'lak buzilgan (SHA-256 mos kelmadi) — qayta yuboring")
    _write_atomic(part_file(jid, n), data)
    return {"part": n, "bytes": len(data)}


def save_area(jid: int, data: bytes) -> dict:
    _validate_blob(data, "Area")
    _write_atomic(area_file(jid), data)
    return {"bytes": len(data)}


def received(jid: int) -> dict:
    parts = {}
    d = details_dir(jid)
    if d.is_dir():
        for p in d.glob("*.csv.gz"):
            if p.stem.endswith(".csv") or p.name.endswith(".csv.gz"):
                try:
                    parts[int(p.name.split(".")[0])] = p.stat().st_size
                except ValueError:
                    pass
    a = area_file(jid)
    return {"area": a.stat().st_size if a.exists() else None, "details": parts}


def verify_complete(jid: int, total: int, has_area: bool) -> None:
    """Hamma bo'lak kelganini tekshiradi; kamchilik bo'lsa aniq xabar bilan ChunkError."""
    got = received(jid)
    if has_area and got["area"] is None:
        raise ChunkError("Area fayli hali yetib kelmagan")
    if total:
        missing = [n for n in range(1, total + 1) if n not in got["details"]]
        if missing:
            shown = ", ".join(str(n) for n in missing[:10]) + (" …" if len(missing) > 10 else "")
            raise ChunkError(f"Details bo'laklari to'liq emas: yetishmayotgan raqamlar: {shown}")
        extra = [n for n in got["details"] if n > total]
        if extra:
            raise ChunkError("Serverda ortiqcha Details bo'laklari bor — yangidan yuklang")


def remove_session(jid: int) -> None:
    shutil.rmtree(session_dir(jid), ignore_errors=True)


def remove_path(p: str | None) -> None:
    """Fayl yoki papkani (bo'laklar) o'chiradi."""
    if not p:
        return
    path = Path(p)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        # papka job<ID>/details bo'lsa, ota papka (job<ID>) ham bo'sh qoladi - uni ham olib tashlaymiz
        parent = path.parent
        if parent.name.startswith("job") and parent.parent == settings.data_dir / "uploads":
            shutil.rmtree(parent, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass
        parent = path.parent
        if parent.name.startswith("job") and parent.parent == settings.data_dir / "uploads":
            try:
                parent.rmdir()
            except OSError:
                pass
