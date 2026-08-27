# Vue SPA
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# API + static
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/frontend/dist ./frontend/dist

ENV DJANGO_DEBUG=false
RUN python manage.py collectstatic --noinput

EXPOSE 8080
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_groups && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2"]
