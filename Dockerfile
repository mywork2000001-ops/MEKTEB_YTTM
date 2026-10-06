# Müəllim köməkçisi – tək xidmət: FastAPI + hazır interfeys (frontend/dist) + Chromium (viktorina test bazası üçün)
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright TZ=Asia/Baku
WORKDIR /app/backend
COPY backend/requirements.txt ./
# Çap/PDF: Times New Roman ölçülü açıq şriftlər (Liberation Serif, Tinos ekvivalenti) – «Əə Ğğ Iı İi Şş» glifləri ilə
RUN pip install -r requirements.txt && python -m playwright install --with-deps chromium \
    && apt-get update && apt-get install -y --no-install-recommends fonts-liberation fonts-dejavu-core \
    && (fc-cache -f || true) && rm -rf /var/lib/apt/lists/*
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
EXPOSE 8000
# Miqrasiyalar və ilk quraşdırma tətbiq açılanda (bootstrap) avtomatik icra olunur
# MK_WORKERS – uvicorn prosesləri (pulsuz plan: 1; Standard 1 CPU / 2 GB: 2–3). Fon işləri yalnız birində (app/scheduler.py)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${MK_WORKERS:-1} --proxy-headers --forwarded-allow-ips='*'"]
