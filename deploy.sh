#!/usr/bin/env bash
# ASKUE ma'lumot — bitta buyruq bilan o'rnatish / yangilash (Ubuntu/Debian serverlar uchun).
#   bash deploy.sh            o'rnatish yoki yangilash (git pull + build + ishga tushirish)
#   bash deploy.sh status     konteynerlar holati
#   bash deploy.sh logs [xizmat]   jurnallarni ko'rish (api | worker | mysql | cloudflared)
#   bash deploy.sh backup     bazani ./backups/ ga saqlash (mysqldump)
#   bash deploy.sh restart | stop
set -euo pipefail
cd "$(dirname "$0")"

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
say() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then return; fi
  say "Docker o'rnatilmoqda…"
  curl -fsSL https://get.docker.com | $SUDO sh
  $SUDO systemctl enable --now docker
  [ -n "${SUDO}" ] && $SUDO usermod -aG docker "$USER" || true
}
DC() { if docker info >/dev/null 2>&1; then docker compose "$@"; else $SUDO docker compose "$@"; fi; }

rand() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"; }
setenv() { # KEY VALUE — faqat bo'sh bo'lsa to'ldiradi
  local k="$1" v="$2"
  if grep -qE "^${k}=.+" .env; then return; fi
  if grep -qE "^${k}=" .env; then sed -i "s|^${k}=.*|${k}=${v}|" .env; else echo "${k}=${v}" >> .env; fi
}

prepare_env() {
  if [ ! -f .env ]; then cp .env.example .env; chmod 600 .env; say ".env yaratildi"; fi
  setenv MYSQL_ROOT_PASSWORD "$(rand 28)"
  setenv MYSQL_PASSWORD "$(rand 28)"
  setenv SECRET_KEY "$(rand 64)"
  setenv BACKUP_KEY "$(rand 48)"
  setenv REDIS_PASSWORD "$(rand 28)"
  if ! grep -qE '^SADMIN_PASSWORD=.+' .env; then
    NEWPASS="$(rand 14)Aa1"; setenv SADMIN_PASSWORD "$NEWPASS"; SHOWPASS="$NEWPASS"
  fi
  set -a; . ./.env; set +a
  if [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then export COMPOSE_PROFILES=tunnel; fi
}

cmd="${1:-up}"
case "$cmd" in
  up|"")
    install_docker
    [ -d .git ] && { say "Yangi kod olinmoqda (git pull)…"; git pull --ff-only || true; }
    prepare_env
    say "Tizim yig'ilmoqda va ishga tushirilmoqda…"
    DC up -d --build --remove-orphans
    say "Tayyor bo'lishi kutilmoqda…"
    for i in $(seq 1 60); do
      if curl -fsS "http://127.0.0.1:${API_PORT:-8000}/api/health" >/dev/null 2>&1; then OK=1; break; fi; sleep 3
    done
    DC ps
    echo
    if [ "${OK:-0}" = 1 ]; then
      say "ISHLAYAPTI: http://127.0.0.1:${API_PORT:-8000}"
      [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ] && say "Cloudflare tunnel yoqilgan — domen Cloudflare panelida ko'rsatilgan (Public hostname → http://api:8000)."
      [ -n "${SHOWPASS:-}" ] && { echo; echo "  Birinchi kirish:  ${SADMIN_USERNAME:-sadmin} / ${SHOWPASS}   (kirgach parolni almashtiring; .env da ham saqlangan)"; }
    else
      echo "Server hali javob bermadi. Jurnal:  bash deploy.sh logs api"; exit 1
    fi ;;
  status) prepare_env; DC ps ;;
  logs)   prepare_env; DC logs -f --tail=100 "${2:-}" ;;
  restart) prepare_env; DC restart ;;
  stop)   prepare_env; DC stop ;;
  backup)
    prepare_env; mkdir -p backups; f="backups/askue_$(date +%F_%H%M).sql.gz"
    DC exec -T mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines askue' | gzip > "$f"
    say "Saqlandi: $f ($(du -h "$f" | cut -f1))" ;;
  *) echo "Noma'lum buyruq: $cmd"; sed -n 2,9p "$0"; exit 1 ;;
esac
