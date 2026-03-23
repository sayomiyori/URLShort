# URLShort

[![CI](https://github.com/sayomiyori/URLShort/actions/workflows/ci.yml/badge.svg)](https://github.com/sayomiyori/URLShort/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](#)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](#)
[![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](#)

Высоконагруженный сокращатель ссылок на **FastAPI + PostgreSQL + Redis** с GeoIP-аналитикой, Nginx-кешированием, метриками Prometheus и дашбордом Grafana.

## Стек

| Компонент | Технология |
|-----------|-----------|
| API | FastAPI (asyncio) |
| База данных | PostgreSQL 16, SQLAlchemy 2 (asyncpg) |
| Кеш / Rate-limit / Счётчики | Redis 7 (ZSET sliding window, INCR+Lua flush) |
| GeoIP | MaxMind GeoLite2-City (опционально) |
| Парсинг User-Agent | `user-agents` |
| Reverse proxy | Nginx 1.27 (micro-caching редиректов 301, 10m) |
| Метрики | Prometheus + Grafana |
| Нагрузочные тесты | Locust |

## Быстрый старт

```bash
# Только API + зависимости
docker compose up -d postgres redis app

# Полный стек (+ Nginx :8080, Prometheus :9090, Grafana :3000)
docker compose up -d
```

> **GeoLite2** — при сборке образа передайте `MAXMIND_LICENSE_KEY`:
> ```bash
> MAXMIND_LICENSE_KEY=your_key docker compose build app
> docker compose up -d
> ```
> Без ключа приложение работает без геолокации (поля `country`/`city` = null).

**Grafana**: `http://localhost:3000` — логин `admin` / пароль `admin`. Дашборд **URLShort** подключается автоматически через provisioning.

## API

### `POST /api/v1/shorten`

Создать короткую ссылку.

```json
// Запрос
{
  "url": "https://example.com/very/long/path",
  "custom_alias": "my-link",   // опционально, 3–20 символов [a-zA-Z0-9_-]
  "ttl_hours": 24              // опционально, TTL в часах
}

// Ответ 200
{
  "short_url": "http://localhost:8012/my-link",
  "code": "my-link",
  "expires_at": "2025-03-22T12:00:00+00:00"
}
```

| Статус | Причина |
|--------|---------|
| 200 | Успешно создано |
| 409 | `custom_alias` уже занят |
| 422 | Невалидный alias или URL |

---

### `GET /{code}`

Редирект на оригинальный URL (301). Клик записывается фоново.

| Статус | Причина |
|--------|---------|
| 301 | Редирект |
| 404 | Код не найден или истёк |
| 429 | Превышен rate limit (заголовок `Retry-After`) |

---

### `GET /api/v1/stats/{code}`

Статистика по короткой ссылке за последние 30 дней.

```json
{
  "total_clicks": 1500,
  "original_url": "https://example.com/very/long/path",
  "created_at": "2025-03-01T10:00:00+00:00",
  "clicks_by_day": [
    {"date": "2025-03-01", "count": 42}, ...
  ],
  "top_referers": [
    {"referer": "https://google.com", "count": 800}, ...
  ],
  "top_countries": [
    {"country": "US", "count": 600}, ...
  ],
  "device_breakdown": {
    "desktop": 900,
    "mobile": 500,
    "tablet": 80,
    "bot": 20
  }
}
```

---

### `GET /metrics`

Prometheus-метрики (стандарт text/plain).

## Метрики Prometheus

| Метрика | Тип | Описание |
|--------|-----|----------|
| `redirects_total` | Counter | Редиректы; метки: `status_code`, `cached` |
| `short_url_created_total` | Counter | Успешные создания коротких ссылок |
| `redirect_duration_seconds` | Histogram | Время обработки `GET /{code}` (бакеты до 250 ms) |
| `cache_operations_total` | Counter | Redis URL-кеш; метка: `result` = `hit`/`miss` |
| `cache_hit_ratio` | Gauge | Отношение hit/(hit+miss), обновляется каждые 10 с |
| `rate_limit_rejected_total` | Counter | Ответы 429 от rate-limiter |
| `active_urls_total` | Gauge | Число активных URL в БД, обновляется каждые 10 с |

## Архитектура Redis

| Ключ | Тип | Назначение |
|------|-----|------------|
| `url:{code}` | String (JSON) | Кеш URL-записи, TTL 1 ч |
| `clicks:{code}` | String (int) | Атомарный счётчик кликов; сбрасывается в PG каждые 60 с и при завершении |
| `rl:redirect:{ip}` | ZSET | Sliding-window rate limit редиректов (100 req/min) |
| `rl:shorten:{key/ip}` | ZSET | Sliding-window rate limit создания ссылок (30 req/min) |

## Запуск тестов

```bash
# Поднять PostgreSQL и Redis
docker compose up -d postgres redis

# Установить dev-зависимости
pip install -e ".[dev]"

# Прогнать тесты
pytest -v
```

## Нагрузочное тестирование (Locust)

```bash
# Поднять полный стек
docker compose up -d postgres redis app prometheus grafana

# Запустить Locust
locust -f locustfile.py --host=http://localhost:8012 --users=500 --spawn-rate=50
```

Веб-интерфейс Locust: `http://localhost:8089`

### Сценарии

| Задача | Запрос | Вес |
|--------|--------|-----|
| CreateURL | `POST /api/v1/shorten` | 1 |
| RedirectHot | `GET /{code}` — «горячие» коды (до 10 на пользователя) | 8 |
| RedirectCold | `GET /{code}` — случайный или несуществующий код | 2 |
| GetStats | `GET /api/v1/stats/{code}` | 1 |

## Performance

Заполните после прогона Locust:

| Метрика | Значение |
|---------|----------|
| RPS (redirect) | — |
| Latency p50 | — ms |
| Latency p95 | — ms |
| Latency p99 | — ms |
| Cache hit ratio | — % |

Скриншоты Grafana положите в [`docs/images/`](docs/images/) и раскомментируйте:

<!--
![Redirect RPS](docs/images/grafana-rps.png)
![Latency p50/p95/p99](docs/images/grafana-latency.png)
![Cache hit ratio](docs/images/grafana-cache-ratio.png)
![Rate limit / min](docs/images/grafana-rate-limit.png)
![Active URLs](docs/images/grafana-active-urls.png)
-->

## Лицензия GeoLite2

База **GeoLite2-City.mmdb** распространяется MaxMind по [отдельной лицензии](https://www.maxmind.com/en/geolite2/eula). Передайте `MAXMIND_LICENSE_KEY` при сборке Docker-образа или смонтируйте готовый файл через `MAXMIND_CITY_DB_PATH`.
