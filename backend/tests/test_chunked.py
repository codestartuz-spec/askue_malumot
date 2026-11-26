"""Bo'laklab yuklash: bo'laklarni saqlash, SHA-256/qatorlar tekshiruvi, to'liqlik (bazasiz)."""
import gzip
import hashlib
import json

import pytest

from app.config import settings
from app.services import chunked


def gz(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"))


def manifest_for(blobs):
    return {"parts": [{"part": i, "rows": 2, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                      for i, b in enumerate(blobs, 1)]}


@pytest.fixture
def jid():
    n = 900001
    chunked.remove_session(n)
    yield n
    chunked.remove_session(n)


def test_parts_roundtrip_and_complete(jid):
    blobs = [gz("a,b\n1,2\n3,4\n"), gz("a,b\n5,6\n7,8\n")]
    chunked.save_manifest(jid, chunked.clean_manifest(manifest_for(blobs)))
    chunked.save_part(jid, 2, 2, blobs[1])
    with pytest.raises(chunked.ChunkError, match="yetishmayotgan raqamlar: 1"):
        chunked.verify_complete(jid, 2, False)
    chunked.save_part(jid, 1, 2, blobs[0])
    chunked.verify_complete(jid, 2, False)
    assert chunked.received(jid)["details"] == {1: len(blobs[0]), 2: len(blobs[1])}
    assert chunked.load_manifest(jid)["rows_total"] == 4


def test_corrupted_part_rejected(jid):
    good = gz("a\n1\n")
    chunked.save_manifest(jid, chunked.clean_manifest(manifest_for([good])))
    bad = bytearray(good)
    bad[-5] ^= 0xFF
    with pytest.raises(chunked.ChunkError, match="SHA-256"):
        chunked.save_part(jid, 1, 1, bytes(bad))
    chunked.save_part(jid, 1, 1, good)          # to'g'risi qabul qilinadi (qayta yuborish)


def test_rejects_non_gzip_empty_oversize_and_bad_number(jid):
    with pytest.raises(chunked.ChunkError, match="haqiqiy .gz"):
        chunked.save_part(jid, 1, 1, b"hello world")
    with pytest.raises(chunked.ChunkError, match="bo'sh"):
        chunked.save_part(jid, 1, 1, b"")
    with pytest.raises(chunked.ChunkError, match="raqami"):
        chunked.save_part(jid, 3, 2, gz("x"))
    old = settings.max_part_mb
    settings.max_part_mb = 0
    try:
        with pytest.raises(chunked.ChunkError, match="katta"):
            chunked.save_part(jid, 1, 1, gz("x"))
    finally:
        settings.max_part_mb = old


def test_manifest_part_count_must_match(jid):
    chunked.save_manifest(jid, chunked.clean_manifest(manifest_for([gz("a")])))
    with pytest.raises(chunked.ChunkError, match="ta bo'lak ko'rsatilgan"):
        chunked.save_part(jid, 1, 2, gz("a"))


def test_clean_manifest_rejects_garbage():
    with pytest.raises(chunked.ChunkError):
        chunked.clean_manifest({"parts": [{"part": "x"}]})
    with pytest.raises(chunked.ChunkError):
        chunked.clean_manifest(["no"])
    assert chunked.clean_manifest(None) is None


def test_ingest_reads_parts_dir_and_expected_rows(jid):
    from app.services.ingest import details_parts, _expected_rows
    chunked.save_part(jid, 2, 2, gz("h\n3\n4\n"))
    chunked.save_part(jid, 1, 2, gz("h\n1\n2\n"))
    chunked.save_manifest(jid, {"parts_total": 2, "rows_total": 4, "parts": []})
    d = str(chunked.details_dir(jid))
    parts = details_parts(d)
    assert [p.rsplit("/", 1)[-1] for p in parts] == ["001.csv.gz", "002.csv.gz"]      # tartib bo'yicha
    assert _expected_rows(d) == 4
    chunked.remove_path(d)
    assert not chunked.session_dir(jid).exists()
