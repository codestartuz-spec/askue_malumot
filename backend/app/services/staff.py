import re


def normalize_key(s: str | None) -> str | None:
    if not s:
        return None
    k = re.sub(r"\s+", " ", s.replace(" ", " ")).strip().upper()
    return k or None


_SPLIT_1 = re.compile(r"[,;/\n]+")
_SPLIT_2 = re.compile(r"\.\s+")
# "HAITOV.SH ASHUROVA.M QURBONOVA.D" ko'rinishi: familiya.bosh harf bo'sh joy bilan ajratilgan
_INITIAL_TOKEN = re.compile(r"^\S+\.[A-Za-z']{1,3}$")


def split_staff(s: str | None) -> list[str]:
    if not s:
        return []
    out: list[str] = []
    for part in _SPLIT_1.split(s):
        for sub in _SPLIT_2.split(part.strip()):
            sub = sub.strip(" .")
            if not sub:
                continue
            tokens = sub.split()
            cur: list[str] = []
            for t in tokens:
                cur.append(t)
                if _INITIAL_TOKEN.match(t):
                    out.append(" ".join(cur))
                    cur = []
            if cur:
                out.append(" ".join(cur))
    seen, res = set(), []
    for n in out:
        n = re.sub(r"\s+", " ", n).strip()
        if n and n.upper() not in seen:
            seen.add(n.upper())
            res.append(n)
    return res
