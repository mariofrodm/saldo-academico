FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm test && npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home saldo
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_harmony')"
COPY backend/ backend/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY pytest.ini ./
COPY tests/ tests/
COPY scripts/ scripts/
COPY --from=web /web/dist frontend/dist
USER saldo
ARG BUILD_SHA=local
ENV BUILD_SHA=${BUILD_SHA}
EXPOSE 8000
CMD ["sh","-c","python -m alembic upgrade head && python -m backend.recover && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
