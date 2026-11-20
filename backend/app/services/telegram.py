"""Telegram bot: yuborish va /start, /parol buyruqlari hamda kanal/guruhlarni avtomatik aniqlash (long polling)."""
import html
import json
import re
import secrets
import threading
import time
import traceback
from datetime import datetime

import requests
from sqlalchemy import text

from ..config import settings
from ..db import engine
from ..security import hash_password


class TgError(Exception):
    pass


_sess = requests.Session()


def _proxies() -> dict | None:
    p = settings.telegram_proxy.strip()
    return {"http": p, "https": p} if p else None


def get_token() -> str:
    with engine.connect() as c:
        return c.execute(text("SELECT v FROM kv WHERE k='tg_token'")).scalar() or ""


def call(method: str, params: dict | None = None, files: dict | None = None,
         timeout: int | tuple = 30, token: str | None = None, retries: int = 3) -> dict:
    token = token if token is not None else get_token()
    if not token:
        raise TgError("Telegram bot tokeni kiritilmagan")
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = _sess.post(f"{settings.telegram_api}/bot{token}/{method}", data=params or {}, files=files,
                           timeout=timeout, proxies=_proxies())
            break
        except requests.RequestException as e:
            last = e
            if attempt < retries:
                time.sleep(1.5 * attempt)     # vaqtinchalik uzilish: qayta urinib ko'ramiz
    else:
        name = type(last).__name__
        hint = " (internet yoki proxy sozlamasini tekshiring: TELEGRAM_PROXY)" if "Connection" in name or "Proxy" in name else ""
        raise TgError(f"Telegram'ga ulanib bo'lmadi: {name}{hint}") from last
    try:
        j = r.json()
    except ValueError as e:
        raise TgError(f"Telegram javobi noto'g'ri ({r.status_code})") from e
    if not j.get("ok"):
        retry_after = (j.get("parameters") or {}).get("retry_after")
        if retry_after and retries > 1 and int(retry_after) <= 120:
            time.sleep(int(retry_after) + 1)
            return call(method, params, files, timeout, token, retries - 1)
        raise TgError(j.get("description") or f"Telegram xatosi ({r.status_code})")
    return j["result"]


_ALLOWED = re.compile(r'<(/?)(b|i|u|s|code|pre|a)(?: href="(https?://[^"\s<>]+)")?>')


def clean_html(text_: str) -> str:
    """Faqat xavfsiz teglarga (b, i, u, s, code, pre, a[https]) ruxsat beradi; juft bo'lmagan teglarni to'g'rilaydi."""
    out, pos, stack = [], 0, []
    for m in _ALLOWED.finditer(text_):
        closing, tag, href = m.group(1) == "/", m.group(2), m.group(3)
        out.append(html.escape(text_[pos:m.start()], quote=False))
        pos = m.end()
        if closing:
            if href is None and stack and stack[-1] == tag:
                stack.pop()
                out.append(f"</{tag}>")
            else:
                out.append(html.escape(m.group(0), quote=False))
        elif tag == "a" and not href or tag != "a" and href:
            out.append(html.escape(m.group(0), quote=False))
        else:
            stack.append(tag)
            out.append(m.group(0))
    out.append(html.escape(text_[pos:], quote=False))
    out += [f"</{t}>" for t in reversed(stack)]
    return "".join(out)


def send_text(chat_id: str, msg: str, html_mode: bool = False, **kw) -> dict:
    if html_mode:
        return call("sendMessage", {"chat_id": chat_id, "text": clean_html(msg)[:4096], "parse_mode": "HTML", **kw})
    return call("sendMessage", {"chat_id": chat_id, "text": msg[:4096], **kw})


def send_file(chat_id: str, filename: str, data: bytes, caption: str = "", markup: str | None = None) -> dict:
    params = {"chat_id": chat_id, "caption": caption[:1000]}
    if markup:
        params["reply_markup"] = markup
    return call("sendDocument", params, files={"document": (filename, data)}, timeout=(15, 180))


def _kind(mime: str) -> str:
    return "photo" if mime.startswith("image/") and mime != "image/gif" else "video" if mime.startswith("video/") else "document"


def send_post(chat_id: str, msg: str, files: list[tuple[str, bytes, str]], markup: str | None = None) -> int | None:
    """Matn + rasm/video: bitta fayl bo'lsa sarlavha (caption) bilan, bir nechta bo'lsa albom qilib yuboradi.
    markup (inline tugma) berilsa — u xabarning oxirgi qismiga qo'yiladi. Qaytaradi: tugmali xabar ID'si."""
    msg = clean_html(msg.strip()) if msg.strip() else ""
    mk = {"reply_markup": markup} if markup else {}
    if not files:
        r = call("sendMessage", {"chat_id": chat_id, "text": msg[:4096], "parse_mode": "HTML", **mk}, timeout=(15, 60))
        return r.get("message_id")
    cap_ok = len(msg) <= 1024
    caption = msg if cap_ok else ""
    media = [f for f in files if _kind(f[2]) in ("photo", "video")]
    docs = [f for f in files if _kind(f[2]) == "document"]
    only_one = len(media) == 1 and not docs and cap_ok     # tugma shu yagona xabarga qo'yiladi
    first = True
    mid = None
    if len(media) == 1:
        name, data, mime = media[0]
        k = _kind(mime)
        params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        if only_one:
            params.update(mk)
        if k == "video":
            params["supports_streaming"] = "true"
        r = call("sendPhoto" if k == "photo" else "sendVideo", params, files={k: (name, data, mime)}, timeout=(15, 300))
        mid = r.get("message_id")
        first = False
    elif len(media) > 1:
        for i in range(0, len(media), 10):
            chunk = media[i:i + 10]
            if len(chunk) == 1:
                name, data, mime = chunk[0]
                k = _kind(mime)
                call("sendPhoto" if k == "photo" else "sendVideo", {"chat_id": chat_id}, files={k: (name, data, mime)},
                     timeout=(15, 300))
                continue
            arr, fl = [], {}
            for j, (name, data, mime) in enumerate(chunk):
                item = {"type": _kind(mime), "media": f"attach://f{j}"}
                if first and j == 0 and caption:
                    item.update(caption=caption, parse_mode="HTML")
                arr.append(item)
                fl[f"f{j}"] = (name, data, mime)
            res = call("sendMediaGroup", {"chat_id": chat_id, "media": json.dumps(arr)}, files=fl, timeout=(15, 300))
            if mid is None and isinstance(res, list) and res:
                mid = res[0].get("message_id")
            first = False
    for k, (name, data, mime) in enumerate(docs):
        params = {"chat_id": chat_id}
        if first and k == 0 and caption:
            params.update(caption=caption, parse_mode="HTML")
            first = False
        r = call("sendDocument", params, files={"document": (name, data, mime)}, timeout=(15, 300))
        mid = mid or r.get("message_id")
    if msg and not cap_ok:
        r = call("sendMessage", {"chat_id": chat_id, "text": msg[:4096], "parse_mode": "HTML", **mk}, timeout=(15, 60))
        return r.get("message_id")
    if markup and not only_one:
        # albom yoki hujjatlar: tugma alohida qisqa xabarga qo'yiladi
        r = call("sendMessage", {"chat_id": chat_id, "text": "👆 Yuqoridagi xabar bilan tanishib chiqing.", **mk},
                 timeout=(15, 60))
        return r.get("message_id")
    return mid


def chat_kind(t: str) -> str:
    return {"channel": "kanal", "group": "guruh", "supergroup": "guruh"}.get(t, t)


def upsert_chat(chat: dict, source: str = "auto", active: bool = True) -> None:
    if chat.get("type") not in ("channel", "group", "supergroup"):
        return
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO tg_chats (chat_id,title,kind,username,source,is_active,created_at) "
            "VALUES (:i,:t,:k,:u,:s,:a,:n) ON DUPLICATE KEY UPDATE title=VALUES(title), kind=VALUES(kind), "
            "username=VALUES(username), is_active=VALUES(is_active)"),
            {"i": str(chat["id"]), "t": (chat.get("title") or "")[:200], "k": chat_kind(chat["type"]),
             "u": chat.get("username"), "s": source, "a": active, "n": datetime.now()})


# ---------------------------------------------------------------- bot buyruqlari
def _handle_message(m: dict) -> None:
    chat = m.get("chat", {})
    cid = str(chat.get("id"))
    txt = (m.get("text") or "").strip()
    if chat.get("type") != "private":
        if chat.get("type") in ("group", "supergroup"):
            upsert_chat(chat)
        return
    frm = m.get("from", {})
    name = " ".join(x for x in (frm.get("first_name"), frm.get("last_name")) if x)
    with engine.begin() as c:
        c.execute(text("INSERT INTO tg_users (chat_id,name,username,last_seen) VALUES (:i,:n,:u,:t) "
                       "ON DUPLICATE KEY UPDATE name=VALUES(name), username=VALUES(username), "
                       "last_seen=VALUES(last_seen)"),
                  {"i": cid, "n": name[:200], "u": frm.get("username"), "t": datetime.now()})
        user = c.execute(text("SELECT id, username, full_name FROM users WHERE chat_id=:i AND is_active=1"),
                         {"i": cid}).mappings().first()
    cmd = txt.split()[0].split("@")[0].lower() if txt.startswith("/") else ""
    if cmd in ("/start", "/id"):
        msg = (f"Assalomu alaykum{', ' + name if name else ''}!\n\n"
               f"Sizning Telegram chat ID raqamingiz:\n{cid}\n\n"
               "Shu raqamni ASKUE ma'lumot tizimida xodim profiliga kiriting — shunda parolni "
               "shu bot orqali tiklay olasiz.")
        if user:
            msg += f"\n\n✅ Siz tizimda «{user['username']}» ({user['full_name'] or '—'}) sifatida bog'langansiz."
        send_text(cid, msg)
    elif cmd in ("/parol", "/password"):
        if not user:
            send_text(cid, "Bu chat ID hech bir xodimga bog'lanmagan. Avval chat ID'ni tizimda profilingizga "
                           f"kiriting.\n\nChat ID: {cid}")
            return
        pw = secrets.token_urlsafe(8)
        with engine.begin() as c:
            c.execute(text("UPDATE users SET password_hash=:h WHERE id=:i"),
                      {"h": hash_password(pw), "i": user["id"]})
            c.execute(text("INSERT INTO audit (username,action,detail,created_at) VALUES (:u,'parol_tiklash',"
                           "'Telegram bot orqali yangi parol berildi',:t)"), {"u": user["username"], "t": datetime.now()})
        send_text(cid, f"🔑 Yangi parol: {pw}\nLogin: {user['username']}\n\nKirgach, parolni almashtirib qo'ying.")
    else:
        send_text(cid, "Buyruqlar:\n/start — chat ID'ni bilish\n/parol — yangi parol olish (xodim bo'lsangiz)")


def _handle_callback(cq: dict) -> None:
    """«Tanishdim» tugmasi: har bir foydalanuvchi bir xabarga bir marta; kim va qachon — jurnalga yoziladi."""
    from .posts import markup
    qid, data = cq.get("id"), cq.get("data") or ""
    if not data.startswith("ack:") or not data[4:].isdigit():
        call("answerCallbackQuery", {"callback_query_id": qid}, retries=1)
        return
    item_id = int(data[4:])
    frm = cq.get("from", {})
    name = " ".join(x for x in (frm.get("first_name"), frm.get("last_name")) if x)
    with engine.begin() as c:
        ok = c.execute(text("SELECT 1 FROM tg_post_items WHERE id=:i"), {"i": item_id}).first()
        if not ok:
            call("answerCallbackQuery", {"callback_query_id": qid, "text": "Xabar jurnalda topilmadi"}, retries=1)
            return
        res = c.execute(text("INSERT IGNORE INTO tg_acks (item_id,tg_user_id,name,username,acked_at) "
                             "VALUES (:i,:u,:n,:un,:t)"),
                        {"i": item_id, "u": frm.get("id"), "n": name[:200], "un": frm.get("username"),
                         "t": datetime.now()})
        new = res.rowcount == 1
        cnt = c.execute(text("SELECT COUNT(*) FROM tg_acks WHERE item_id=:i"), {"i": item_id}).scalar() or 0
    call("answerCallbackQuery", {"callback_query_id": qid,
                                 "text": "✅ Tanishganingiz qayd etildi. Rahmat!" if new
                                 else "Siz allaqachon tanishgansiz ✅"}, retries=1)
    msg = cq.get("message") or {}
    if new and msg.get("message_id") and (msg.get("chat") or {}).get("id") is not None:
        try:
            call("editMessageReplyMarkup", {"chat_id": msg["chat"]["id"], "message_id": msg["message_id"],
                                            "reply_markup": markup(item_id, cnt)}, retries=1)
        except TgError:
            pass


def _handle_update(u: dict) -> None:
    if "callback_query" in u:
        _handle_callback(u["callback_query"])
    elif "message" in u:
        _handle_message(u["message"])
    elif "channel_post" in u:
        upsert_chat(u["channel_post"]["chat"])
    elif "my_chat_member" in u:
        e = u["my_chat_member"]
        status = e.get("new_chat_member", {}).get("status")
        if e["chat"].get("type") in ("channel", "group", "supergroup"):
            upsert_chat(e["chat"], active=status in ("administrator", "member"))


def poll_forever() -> None:
    offset = 0
    last_token = None
    while True:
        try:
            token = get_token()
            if not token:
                time.sleep(5)
                continue
            if token != last_token:
                last_token = token
                try:
                    call("deleteWebhook", token=token, timeout=15)
                except TgError:
                    pass
            updates = call("getUpdates", {"offset": offset, "timeout": 20,
                                          "allowed_updates": '["message","my_chat_member","channel_post","callback_query"]'},
                           timeout=35, token=token, retries=1)
            with engine.begin() as c:
                c.execute(text("INSERT INTO kv (k,v) VALUES ('tg_poll_hb',:v) ON DUPLICATE KEY UPDATE v=VALUES(v)"),
                          {"v": str(int(time.time()))})
            for u in updates:
                offset = u["update_id"] + 1
                try:
                    _handle_update(u)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
        except TgError as e:
            print(f"Telegram: {e}", flush=True)
            time.sleep(8)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            time.sleep(8)


def start_polling() -> None:
    threading.Thread(target=poll_forever, daemon=True, name="tg-poll").start()
