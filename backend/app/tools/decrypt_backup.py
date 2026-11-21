"""Shifrlangan zaxirani ochadi:  python -m app.tools.decrypt_backup askue_zaxira_....sql.gz.enc [chiqish.sql.gz]"""
import sys
from pathlib import Path

from ..services.crypto import decrypt_bytes


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Foydalanish: python -m app.tools.decrypt_backup <fayl.enc> [chiqish.sql.gz]")
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix("")
    dst.write_bytes(decrypt_bytes(src.read_bytes()))
    print("Tayyor:", dst, "\nTiklash: gunzip -c", dst, "| mysql -u... askue")


if __name__ == "__main__":
    main()
