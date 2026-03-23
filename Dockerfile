FROM python:3.12-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

ARG MAXMIND_LICENSE_KEY=""

# Avoid apt purge wget/tar — it often returns 100 on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        wget \
        tar \
    && mkdir -p /usr/share/GeoIP \
    && rm -rf /var/lib/apt/lists/*

RUN if [ -n "$MAXMIND_LICENSE_KEY" ]; then \
        if wget -qO /tmp/mm.tgz \
            "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
            && tar -xzf /tmp/mm.tgz -C /tmp; then \
            MMDB="$(find /tmp -type f -name 'GeoLite2-City.mmdb' 2>/dev/null | head -1)"; \
            if [ -n "$MMDB" ] && [ -f "$MMDB" ]; then \
                cp "$MMDB" /usr/share/GeoIP/GeoLite2-City.mmdb; \
            else \
                echo "GeoLite2: .mmdb not found inside archive (check tarball layout)"; \
            fi; \
        else \
            echo "GeoLite2: wget/tar failed (invalid license key or network); continuing without DB"; \
        fi; \
        rm -f /tmp/mm.tgz; \
        rm -rf /tmp/GeoLite2-City_* 2>/dev/null || true; \
    fi

COPY pyproject.toml alembic.ini /app/
COPY app /app/app

RUN pip install --no-cache-dir .

EXPOSE 8012

ENV MAXMIND_CITY_DB_PATH=/usr/share/GeoIP/GeoLite2-City.mmdb

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8012"]
