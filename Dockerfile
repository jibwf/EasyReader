FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update \
	&& apt-get install -y --no-install-recommends gcc libc6-dev \
	&& rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
	&& apt-get purge -y --auto-remove gcc libc6-dev \
	&& rm -rf /var/lib/apt/lists/* /root/.cache
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./static/
COPY data/fonts/ ./builtin-fonts/
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
ARG GIT_SHA=unknown
ARG APP_VERSION=
RUN if [ -n "$APP_VERSION" ]; then echo "$APP_VERSION" > /app/VERSION; else echo "$GIT_SHA" > /app/VERSION; fi
VOLUME ["/app/data"]
EXPOSE 8080
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
