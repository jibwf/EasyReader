FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
# Keep optional deps so platform-specific Rollup binaries are installed in Alpine.
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim AS python-wheels
WORKDIR /tmp
RUN apt-get update \
	&& apt-get install -y --no-install-recommends gcc libc6-dev \
	&& rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime-base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1
COPY backend/requirements.txt ./requirements.txt
COPY --from=python-wheels /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
	&& rm -rf /wheels /root/.cache
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./static/
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
ARG GIT_SHA=unknown
ARG APP_VERSION=
RUN if [ -n "$APP_VERSION" ]; then echo "$APP_VERSION" > /app/VERSION; else echo "$GIT_SHA" > /app/VERSION; fi
VOLUME ["/app/data"]
EXPOSE 8080
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Smaller image target without bundled fonts.
FROM runtime-base AS runtime-slim
RUN mkdir -p /app/builtin-fonts

# Default target keeps existing behavior (bundle builtin fonts).
FROM runtime-base AS runtime
COPY data/fonts/ ./builtin-fonts/
