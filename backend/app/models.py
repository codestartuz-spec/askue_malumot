from datetime import date, datetime

from sqlalchemy import (JSON, BigInteger, Boolean, Column, Date, DateTime, Float, ForeignKey,
                        Index, Integer, MetaData, SmallInteger, String, Table, Text,
                        UniqueConstraint)
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .metrics import ALL_METRICS


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(150), default="")
    password_hash: Mapped[str] = mapped_column(String(120))
    is_super: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    perms: Mapped[list] = mapped_column(JSON, default=list)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Esp(Base):
    __tablename__ = "esps"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    code: Mapped[str] = mapped_column(String(20), default="")
    label: Mapped[str] = mapped_column(String(80), default="")
    sort: Mapped[int] = mapped_column(Integer, default=999)


class Brigade(Base):
    __tablename__ = "brigades"
    id: Mapped[int] = mapped_column(primary_key=True)
    esp_id: Mapped[int] = mapped_column(ForeignKey("esps.id"), index=True)
    manager_key: Mapped[str] = mapped_column(String(300))
    number: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(120))
    source_name: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now,
                                                 server_default=func.now())
    __table_args__ = (UniqueConstraint("esp_id", "manager_key", name="uq_brigade_key"),)


class BrigadeMember(Base):
    __tablename__ = "brigade_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    brigade_id: Mapped[int] = mapped_column(ForeignKey("brigades.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Tr(Base):
    """Area faylidagi bitta qator: TP (transformator) va unga biriktirilgan konsentrator."""
    __tablename__ = "trs"
    id: Mapped[int] = mapped_column(primary_key=True)
    esp_id: Mapped[int] = mapped_column(ForeignKey("esps.id"))
    tr_code: Mapped[str] = mapped_column(String(24))
    tp_no: Mapped[str] = mapped_column(String(80))
    substation: Mapped[str] = mapped_column(String(150), default="")
    feeder: Mapped[str] = mapped_column(String(150), default="")
    dcu: Mapped[str | None] = mapped_column(String(32), nullable=True)
    file_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    brigade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    has_dcu: Mapped[bool] = mapped_column(Boolean, default=False)
    attached: Mapped[bool] = mapped_column(Boolean, default=False)
    offline: Mapped[bool] = mapped_column(Boolean, default=False)
    offline3: Mapped[bool] = mapped_column(Boolean, default=False)
    lv: Mapped[int] = mapped_column(SmallInteger, default=0)
    obx_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[int] = mapped_column(SmallInteger, default=0)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    batch: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("esp_id", "tr_code", name="uq_tr"),
        Index("ix_tr_tp", "esp_id", "tp_no"),
        Index("ix_tr_scope", "esp_id", "brigade_id"),
    )


class Meter(Base):
    __tablename__ = "meters"
    meter_no: Mapped[str] = mapped_column(String(24), primary_key=True)
    esp_id: Mapped[int] = mapped_column(Integer)
    tp_no: Mapped[str] = mapped_column(String(80), default="")
    tr_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brigade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account: Mapped[str] = mapped_column(String(24), default="")
    mtype: Mapped[str] = mapped_column(String(24), default="")
    link: Mapped[str] = mapped_column(String(8), default="")
    ctype: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    name: Mapped[str] = mapped_column(String(200), default="")
    address: Mapped[str] = mapped_column(String(250), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_poll: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bucket: Mapped[int] = mapped_column(SmallInteger, default=0)
    direct: Mapped[bool] = mapped_column(Boolean, default=False)
    batch: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        Index("ix_m_scope", "esp_id", "brigade_id", "ctype", "bucket"),
        Index("ix_m_tr", "tr_id"),
        Index("ix_m_geo2", "lat", "lon", "ctype", "bucket", "esp_id", "brigade_id"),
        Index("ix_m_direct", "direct", "lat"),
    )


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    stage: Mapped[str] = mapped_column(String(200), default="Navbatda")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    snap_date: Mapped[datetime] = mapped_column(Date)
    area_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    area_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Device(Base):
    """Ilovadan foydalangan har bir qurilma (brauzer)."""
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[str] = mapped_column(String(20), default="desktop")
    ua: Mapped[str] = mapped_column(String(400), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    ua_hash: Mapped[str] = mapped_column(String(32), default="", server_default="", index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_user: Mapped[str] = mapped_column(String(64), default="")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    blocked_by: Mapped[str] = mapped_column(String(64), default="")


class UserSession(Base):
    """Kirish sessiyasi: bitta loginda faqat bitta faol sessiya bo'ladi."""
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    sid: Mapped[str] = mapped_column(String(40), unique=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    device_id: Mapped[int] = mapped_column(Integer, index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(200), default="")


class Kv(Base):
    __tablename__ = "kv"
    k: Mapped[str] = mapped_column(String(60), primary_key=True)
    v: Mapped[str] = mapped_column(String(300), default="")


class TgChat(Base):
    """Bot admin sifatida qo'shilgan kanal / guruhlar."""
    __tablename__ = "tg_chats"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(20), default="")        # channel / group / supergroup
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="auto")  # auto / manual
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    members: Mapped[int | None] = mapped_column(Integer, nullable=True)
    members_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TgUser(Base):
    """Botga /start bosgan shaxsiy chatlar (chat ID'ni topish uchun)."""
    __tablename__ = "tg_users"
    chat_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)


class PwReset(Base):
    __tablename__ = "pw_resets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime)
    tries: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SendJob(Base):
    """Telegram kanallarga hisobot yuborish jarayoni."""
    __tablename__ = "send_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(12), default="running")
    progress: Mapped[float] = mapped_column(Float, default=0)
    log: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TgPost(Base):
    """Telegramga yuborilgan har bir xabar / hisobot jurnali."""
    __tablename__ = "tg_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), default="xabar")        # xabar | hisobot | respublika
    title: Mapped[str] = mapped_column(String(250), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    files: Mapped[list] = mapped_column(JSON, default=list)
    ack: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class TgPostItem(Base):
    """Xabarning bitta kanal/guruhdagi nusxasi."""
    __tablename__ = "tg_post_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, index=True)
    chat_id: Mapped[str] = mapped_column(String(30))
    chat_title: Mapped[str] = mapped_column(String(200), default="")
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(8), default="wait")        # wait | ok | err
    error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TgAck(Base):
    """«Tanishdim» tugmasini bosganlar. Bir foydalanuvchi bir xabarga faqat bir marta."""
    __tablename__ = "tg_acks"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(200), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acked_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("item_id", "tg_user_id", name="uq_ack"),)


# Kunlik snapshot: har kuni (sana, tuman, brigada) kesimidagi jami sonlar.
# brigade_id = 0  ->  biriktirilmagan TP'lar.
snapshots = Table(
    "snapshots", Base.metadata,
    Column("snap_date", Date, primary_key=True),
    Column("esp_id", Integer, primary_key=True),
    Column("brigade_id", Integer, primary_key=True, default=0),
    *[Column(m, Integer, nullable=False, default=0, server_default="0") for m in ALL_METRICS],
)


class RepublicReport(Base):
    """Respublika dinamikasi: har bir yuklangan PDF (oy boshidan shu sanagacha) — viloyat jami qatorlari."""
    __tablename__ = "republic_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    end_date: Mapped[date] = mapped_column(Date, unique=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AgReport(Base):
    """AG dinamikasi: har bir yuklangan PDF (boshlang'ich sanadan shu sanagacha) — hududlar kesimidagi jadval."""
    __tablename__ = "ag_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    end_date: Mapped[date] = mapped_column(Date, unique=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class DailyBatch(Base):
    """Kunlik topshiriq: bir kunda yuklangan 5 ta Excel fayl va ulardan tayyorlangan jadvallar (alohida bo'lim)."""
    __tablename__ = "daily_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_date: Mapped[date] = mapped_column(Date, unique=True)
    status: Mapped[str] = mapped_column(String(10), default="queued")    # queued | running | ask | done | error
    progress: Mapped[float] = mapped_column(Float, default=0)
    message: Mapped[str] = mapped_column(String(500), default="")
    files: Mapped[dict] = mapped_column(JSON, default=dict)             # {tur: {name, size}}
    ask: Mapped[list] = mapped_column(JSON, default=list)               # tushunarsiz iste'molchi turlari
    data: Mapped[dict] = mapped_column(JSON, default=dict)              # hisoblangan jadvallar
    counts: Mapped[dict] = mapped_column(JSON, default=dict)            # topshiriq faylidagi qatorlar soni
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DailySetting(Base):
    """Kunlik topshiriq bo'limining sozlamalari (JSON) — kv (300 belgi) ga sig'maydi, shuning uchun alohida jadval."""
    __tablename__ = "daily_settings"
    k: Mapped[str] = mapped_column(String(60), primary_key=True)
    v: Mapped[str] = mapped_column(Text, default="")


class Backup(Base):
    """Zaxira nusxalar tarixi."""
    __tablename__ = "backups"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    kind: Mapped[str] = mapped_column(String(10), default="auto")        # auto | manual
    filename: Mapped[str] = mapped_column(String(160), default="")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(10), default="ok")        # ok | error
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(400), default="")
