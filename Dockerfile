# syntax=docker/dockerfile:1
# ---- 1) Frontend (React/Vite) ----
FROM node:26-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2) Backend (FastAPI) + tayyor frontend ----
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 TZ=Asia/Tashkent
RUN apt-get update && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/app ./app
COPY backend/assets ./assets
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -m -u 1000 askue && mkdir -p data/uploads && chown -R askue:askue /app
USER askue
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1
# --proxy-headers O'CHIRILGAN: mijoz IP sini ilovaning o'zi TRUSTED_PROXIES bo'yicha ishonchli proksidan oladi.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-proxy-headers"]
