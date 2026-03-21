FROM python:3.12-slim

WORKDIR /app

ARG MAXMIND_LICENSE_KEY=""

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    wget \
    tar \
    && mkdir -p /usr/share/GeoIP \
    && if [ -n "$MAXMIND_LICENSE_KEY" ]; then \
      wget -qO /tmp/mm.tgz \
        "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
      && tar -xzf /tmp/mm.tgz -C /tmp \
      && MMDB="$(find /tmp -maxdepth 2 -name 'GeoLite2-City.mmdb' | head -1)" \
      && cp "$MMDB" /usr/share/GeoIP/GeoLite2-City.mmdb \
      && rm -rf /tmp/GeoLite2-City_* /tmp/mm.tgz; \
    fi \
    && apt-get purge -y wget tar \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini /app/
COPY app /app/app

RUN pip install --no-cache-dir .

EXPOSE 8000

ENV MAXMIND_CITY_DB_PATH=/usr/share/GeoIP/GeoLite2-City.mmdb

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
