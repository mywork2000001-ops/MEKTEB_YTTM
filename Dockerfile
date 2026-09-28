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
RUN pip install -r requirements.txt && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
EXPOSE 8000
# Miqrasiyalar və ilk quraşdırma tətbiq açılanda (bootstrap) avtomatik icra olunur
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
