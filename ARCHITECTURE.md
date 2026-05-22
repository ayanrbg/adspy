# AdSpy — Архитектура проекта

> Сервис для поиска рекламных связок (creatives + bundles) из Facebook Ads и других источников.
> Первый запуск: **India · Gambling**. Архитектура спроектирована так, чтобы новые ниши и регионы добавлялись через конфиг, без изменения кода.

---

## 1. Главный принцип — конфиг, а не хардкод

«Индия + гемблинг» — это просто первая запись в списке поисков. Любая новая ниша или регион добавляется одной записью в `config/searches.py`. Вся система (воркеры, расписание, источники, pipeline) подхватывает новый конфиг автоматически.

```python
# config/searches.py
SEARCHES = [
    {
        "id": "in_gambling",              # ← ПЕРВЫЙ ЗАПУСК
        "country": "IN",
        "niche": "gambling",
        "keywords_ref": "gambling_in",     # ссылка на файл с ключами
        "sources": ["fb_api", "tiktok", "direct_scrape"],
        "proxy_geo": "IN",
        "schedule": "*/6 hours",
        "priority": "high",
        "enabled": True,
    },
    # Будущие поиски — просто дописываем словари:
    # {"id": "br_nutra",  "country": "BR", "niche": "nutra",  ...},
    # {"id": "de_dating", "country": "DE", "niche": "dating", ...},
]
```

| Что хочешь добавить         | Что делаешь практически                |
| --------------------------- | -------------------------------------- |
| Новая ниша / регион         | Дописать словарь в `searches.py`       |
| Новый источник (X Ads)      | Новый класс-адаптер, один файл         |
| Новый шаг обработки         | Добавить step в pipeline               |
| API для агентств            | Роут уже в `api/routes/`               |
| Telegram-бот                | Отдельный клиент, дёргает тот же API   |
| White-label перепродажа     | API уже отделён от фронта              |

Ядро (**сбор → нормализация → pipeline → хранение → API**) не меняется. Рост идёт только за счёт конфигов и адаптеров.

---

## 2. Слои системы

```
┌──────────────────────────────────────────────────────────┐
│  1 · ИСТОЧНИКИ (адаптеры)                                  │
│  FB Ad Library API · TikTok · Google Ads · Direct scraper │
└──────────────────────────────────────────────────────────┘
                          │  сырые объявления
                          ▼
┌──────────────────────────────────────────────────────────┐
│  2 · НОРМАЛИЗАЦИЯ → единый формат NormalizedAd            │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  3 · PIPELINE ОБРАБОТКИ                                    │
│  dedup → download → classify → signals → save             │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  4 · ХРАНЕНИЕ                                              │
│  PostgreSQL · Elasticsearch · Redis · S3/R2               │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  5 · API (FastAPI)                                         │
│  search · bundles · alerts · billing · auth               │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  6 · КЛИЕНТЫ                                               │
│  Web (Next.js) · Telegram bot · публичный API             │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Структура папок

```
adspy/
├── config/
│   ├── searches.py            # ← India/gambling тут, первый конфиг
│   ├── keywords/
│   │   ├── gambling_in.py      # ключевые слова по нише+гео
│   │   └── nutra_br.py
│   └── settings.py             # env, токены, прокси, лимиты
│
├── sources/                   # адаптеры источников (паттерн Adapter)
│   ├── base.py                 # абстрактный AdSource
│   ├── facebook.py
│   ├── tiktok.py
│   ├── google.py
│   ├── direct_scraper.py
│   └── registry.py             # SOURCE_REGISTRY
│
├── pipeline/                  # обработка (паттерн Chain)
│   ├── processor.py
│   └── steps/
│       ├── base.py
│       ├── deduplicate.py
│       ├── download.py
│       ├── classify.py         # Vision AI для пустого текста
│       └── signals.py          # дни активности, связки
│
├── models/
│   └── ad.py                   # NormalizedAd — единый формат
│
├── storage/
│   ├── postgres.py
│   ├── elastic.py
│   ├── redis_client.py
│   └── s3.py
│
├── workers/
│   ├── celery_app.py
│   └── tasks.py                # запуск из config по расписанию
│
├── api/                       # FastAPI
│   ├── main.py
│   ├── routes/
│   │   ├── search.py
│   │   ├── bundles.py          # связки
│   │   ├── alerts.py
│   │   └── billing.py
│   └── auth.py
│
├── web/                       # Next.js фронт (отдельный репозиторий)
│
├── docker-compose.yml
└── requirements.txt
```

---

## 4. Слой источников (адаптеры)

Каждый источник реализует один интерфейс. Новый источник = новый класс, остальное не трогается.

```python
# sources/base.py
from abc import ABC, abstractmethod
from models.ad import NormalizedAd

class AdSource(ABC):
    name: str

    @abstractmethod
    async def fetch(self, search_config: dict) -> list[NormalizedAd]:
        """Собирает объявления и возвращает в едином формате."""
        ...
```

```python
# sources/registry.py
from sources.facebook import FacebookSource
from sources.tiktok import TikTokSource
from sources.google import GoogleSource
from sources.direct_scraper import DirectScraper

SOURCE_REGISTRY = {
    "fb_api":        FacebookSource(),
    "tiktok":        TikTokSource(),
    "google":        GoogleSource(),
    "direct_scrape": DirectScraper(),
}
```

```python
# sources/facebook.py
import aiohttp
from sources.base import AdSource
from models.ad import NormalizedAd
from config.keywords import load_keywords

class FacebookSource(AdSource):
    name = "fb_api"
    BASE = "https://graph.facebook.com/v19.0/ads_archive"

    def __init__(self, token_pool: list[str]):
        self.tokens = token_pool
        self._i = 0

    def _next_token(self) -> str:
        t = self.tokens[self._i]
        self._i = (self._i + 1) % len(self.tokens)
        return t

    async def fetch(self, cfg: dict) -> list[NormalizedAd]:
        keywords = load_keywords(cfg["keywords_ref"])
        out: list[NormalizedAd] = []
        async with aiohttp.ClientSession() as session:
            for kw in keywords:
                params = {
                    "access_token": self._next_token(),
                    "search_terms": kw,
                    "ad_reached_countries": cfg["country"],
                    "ad_type": "ALL",
                    "limit": 100,
                    "fields": ",".join([
                        "id", "page_id", "page_name",
                        "ad_creative_bodies", "ad_creative_link_titles",
                        "ad_snapshot_url", "ad_delivery_start_time",
                        "ad_delivery_stop_time", "impressions",
                        "spend", "demographic_distribution",
                    ]),
                }
                async with session.get(self.BASE, params=params) as r:
                    data = await r.json()
                    for raw in data.get("data", []):
                        out.append(self._normalize(raw, cfg))
        return out

    def _normalize(self, raw: dict, cfg: dict) -> NormalizedAd:
        return NormalizedAd(
            id=f"fb_{raw['id']}",
            source=self.name,
            page_id=raw.get("page_id"),
            page_name=raw.get("page_name"),
            body=(raw.get("ad_creative_bodies") or [""])[0],
            title=(raw.get("ad_creative_link_titles") or [""])[0],
            snapshot_url=raw.get("ad_snapshot_url"),
            country=cfg["country"],
            niche=cfg["niche"],          # предварительно из конфига
            start_date=raw.get("ad_delivery_start_time"),
            stop_date=raw.get("ad_delivery_stop_time"),
            raw=raw,
        )
```

---

## 5. Единый формат — NormalizedAd

Любой источник приводится к одной модели. Дальше всей системе всё равно, откуда пришли данные.

```python
# models/ad.py
from dataclasses import dataclass, field
from datetime import date

@dataclass
class NormalizedAd:
    id: str                       # "fb_123" / "tt_456" — с префиксом источника
    source: str                   # "fb_api" / "tiktok" / ...
    page_id: str | None = None
    page_name: str | None = None
    body: str = ""
    title: str = ""
    snapshot_url: str | None = None

    # заполняется в pipeline
    screenshot_url: str | None = None
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    has_video: bool = False

    country: str = ""
    niche: str = ""               # уточняется ClassifyStep
    niche_confidence: float = 0.0

    start_date: str | None = None
    stop_date: str | None = None
    days_active: int | None = None
    is_active: bool = True

    impressions_min: int = 0
    impressions_max: int = 0

    raw: dict = field(default_factory=dict)   # оригинал на всякий случай
```

---

## 6. Pipeline обработки

Цепочка независимых шагов. Хочешь добавить новый этап — вставляешь step в список.

```python
# pipeline/processor.py
class Pipeline:
    def __init__(self, steps: list):
        self.steps = steps

    async def run(self, ads: list) -> list:
        for step in self.steps:
            ads = await step.process(ads)
            print(f"[{step.__class__.__name__}] → {len(ads)} объявлений")
        return ads
```

```python
# pipeline/steps/base.py
from abc import ABC, abstractmethod

class Step(ABC):
    @abstractmethod
    async def process(self, ads: list) -> list: ...
```

Шаги по порядку:

1. **DeduplicateStep** — отбрасывает уже виденные объявления (Redis `SETNX`, TTL 30 дней).
2. **DownloadCreativeStep** — открывает `snapshot_url` через Playwright (мобильный UA + прокси гео из конфига), снимает скриншот, тянет картинки/видео, грузит в S3.
3. **ClassifyStep** — если текст пустой/неясный, прогоняет креатив через Vision AI и уточняет нишу (важно для гемблинга в Индии, где смысл в картинке).
4. **SignalsStep** — считает `days_active`, флаг `is_active`, силу связки (strong / medium / new).
5. **SaveStep** — пишет метаданные в PostgreSQL и индексирует в Elasticsearch.

```python
# pipeline/steps/signals.py
from datetime import date
from pipeline.steps.base import Step

class SignalsStep(Step):
    async def process(self, ads):
        for ad in ads:
            if ad.start_date:
                start = date.fromisoformat(ad.start_date[:10])
                end = date.fromisoformat(ad.stop_date[:10]) if ad.stop_date else date.today()
                ad.days_active = (end - start).days
                ad.is_active = ad.stop_date is None
        return ads
```

---

## 7. Хранение

| Хранилище        | Назначение                                        |
| ---------------- | ------------------------------------------------- |
| **PostgreSQL**   | Метаданные объявлений, страницы, пользователи, подписки |
| **Elasticsearch**| Полнотекстовый поиск, `more_like_this` для похожих |
| **Redis**        | Дедупликация, кэш, rate-limit, очереди Celery     |
| **S3 / R2**      | Скриншоты, картинки, видео                        |

```sql
-- основная таблица
CREATE TABLE ads (
    id              VARCHAR PRIMARY KEY,   -- "fb_123"
    source          VARCHAR,               -- fb_api / tiktok / ...
    page_id         VARCHAR,
    page_name       VARCHAR,
    body            TEXT,
    title           VARCHAR,
    screenshot_url  TEXT,
    image_urls      JSONB,
    video_urls      JSONB,
    has_video       BOOLEAN DEFAULT FALSE,
    country         VARCHAR,
    niche           VARCHAR,
    niche_confidence REAL,
    start_date      DATE,
    stop_date       DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    days_active     INT,
    impressions_min INT,
    impressions_max INT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ads_country_niche ON ads (country, niche);
CREATE INDEX idx_ads_days_active   ON ads (days_active DESC);
CREATE INDEX idx_ads_active        ON ads (is_active);
CREATE INDEX idx_ads_page          ON ads (page_id);
CREATE INDEX idx_ads_has_video     ON ads (has_video);
```

---

## 8. Воркеры и расписание

Celery beat сам читает `config/searches.py` и ставит задачи. Включил конфиг — он сразу в расписании.

```python
# workers/tasks.py
import asyncio
from workers.celery_app import app
from config.searches import SEARCHES
from sources.registry import SOURCE_REGISTRY
from pipeline.processor import Pipeline
from pipeline.steps import (
    DeduplicateStep, DownloadCreativeStep,
    ClassifyStep, SignalsStep, SaveStep,
)

pipeline = Pipeline([
    DeduplicateStep(),
    DownloadCreativeStep(),
    ClassifyStep(),
    SignalsStep(),
    SaveStep(),
])

@app.task
def run_search(search_id: str):
    cfg = next(s for s in SEARCHES if s["id"] == search_id)

    # 1. собираем со всех источников из конфига
    all_ads = []
    for source_name in cfg["sources"]:
        source = SOURCE_REGISTRY[source_name]
        ads = asyncio.run(source.fetch(cfg))
        all_ads.extend(ads)

    # 2. прогоняем через pipeline
    asyncio.run(pipeline.run(all_ads))
    print(f"[{search_id}] готово: {len(all_ads)} собрано")

# расписание строится автоматически из конфига
app.conf.beat_schedule = {
    s["id"]: {
        "task": "workers.tasks.run_search",
        "schedule": parse_schedule(s["schedule"]),
        "args": [s["id"]],
    }
    for s in SEARCHES if s["enabled"]
}
```

---

## 9. API (FastAPI)

Отделён от фронта — это и есть точка будущего роста (Telegram-бот, агентский API, white-label).

```python
# api/routes/search.py
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/ads")

@router.get("/search")
async def search_ads(
    country: str = "IN",
    niche: str = "gambling",
    min_days_active: int = 0,
    only_active: bool = True,
    has_video: bool | None = None,
    sort_by: str = "days_active",
    page: int = 1,
    limit: int = 20,
):
    """Главный поиск связок для арбитражника."""
    ...

@router.get("/{ad_id}/bundle")
async def get_bundle(ad_id: str):
    """Связка: само объявление + другие объявления страницы + похожие."""
    ...
```

Ключевые эндпоинты:

- `GET /api/ads/search` — поиск с фильтрами (страна, ниша, дни активности, видео, охват).
- `GET /api/ads/{id}/bundle` — связка: объявление + все объявления аккаунта + похожие (Elasticsearch `more_like_this`).
- `GET /api/pages/{page_id}/ads` — вся история рекламы конкретного рекламодателя.
- `POST /api/alerts` — подписка на алерты (новое объявление в нише/гео → Telegram).
- `POST /api/billing/subscribe` — тарифы (Stripe / крипта).

---

## 10. Связка — главная ценность

Арбитражнику важно не отдельное объявление, а доказательство, что связка работает.

```python
# api/routes/bundles.py
async def build_bundle(ad_id: str) -> dict:
    ad = await db.get_ad(ad_id)

    strength = (
        "strong" if (ad.days_active or 0) >= 30 else
        "medium" if (ad.days_active or 0) >= 14 else
        "new"
    )

    return {
        "ad": ad,
        "strength": strength,            # 🔥 / ⚡ / 🆕
        "days_active": ad.days_active,
        "is_active": ad.is_active,
        "page_other_ads": await db.get_page_ads(ad.page_id, limit=20),
        "similar_ads": await es.more_like_this(ad_id, limit=12),
    }
```

Что видит пользователь: скриншот креатива, «активно 47 дней», гео, охват, другие объявления того же аккаунта, похожие связки, динамика активности.

---

## 11. Дорожная карта расширения

| Фаза | Что добавляем                                      | Изменения в коде            |
| ---- | -------------------------------------------------- | --------------------------- |
| 0    | India · Gambling (FB API)                          | первый конфиг + FacebookSource |
| 1    | + TikTok, Google, прямой скрейпинг для Индии       | три адаптера                |
| 2    | + Vision-классификация (картинки без текста)       | ClassifyStep                |
| 3    | + новые гео и ниши (BR/nutra, DE/dating)           | только конфиги              |
| 4    | + Telegram-бот с алертами                          | новый клиент над API        |
| 5    | + публичный API для агентств, white-label          | роуты + ключи               |
| 6    | + аналитика трендов, отслеживание воронок целиком  | новые steps + таблицы       |

---

## 12. Стек

- **Язык:** Python 3.11 (сбор, pipeline, API)
- **API:** FastAPI + Uvicorn
- **Очереди:** Celery + Redis
- **Скрейпинг:** Playwright (Chromium), резидентные/мобильные прокси
- **БД:** PostgreSQL 16
- **Поиск:** Elasticsearch 8
- **Файлы:** S3 / Cloudflare R2
- **Vision:** Anthropic Claude (классификация креативов)
- **Фронт:** Next.js + React (отдельный репозиторий)
- **Оплата:** Stripe / крипто-платёжки
- **Деплой:** Docker Compose → позже Kubernetes
