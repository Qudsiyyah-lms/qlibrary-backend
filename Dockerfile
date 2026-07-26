FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# migrate & collectstatic butuh env vars (SECRET_KEY, dsb) yang baru tersedia
# saat container jalan (docker-compose --env-file), makanya dijalankan di
# entrypoint, bukan saat build image.
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--workers", "2", "--bind", "0.0.0.0:8000"]
