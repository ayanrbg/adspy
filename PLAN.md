# План: полный охват + классификация

## Проблема
1. API отдаёт только объявления, совпадающие по ключевым словам
2. Объявления без текста (только картинка/видео) не находятся
3. Замаскированный текст и клоакинг пропускаются

## Решение — 4 модуля

---

### Модуль 1: Скрейпер сайта Facebook Ad Library
**Файл:** `adspy/sources/fb_scraper.py`

Что делает:
- Playwright открывает `facebook.com/ads/library`
- Фильтр: country=IN, status=active, ad_type=all
- Скроллит страницу, собирает ВСЕ карточки объявлений
- Из каждой карточки вытаскивает: page_name, page_id, тексты, ссылку на snapshot, даты
- Не зависит от ключевых слов — берёт всё подряд
- Опционально фильтрует по категориям если доступно

Зависимости: `playwright` (бесплатно)

Ограничения: Facebook может банить при агрессивном скрейпинге → нужны паузы между скроллами и прокси

---

### Модуль 2: OCR — извлечение текста из картинок
**Файл:** `adspy/pipeline/steps/ocr.py`

Что делает:
- Берёт скриншот объявления (из snapshot_url)
- Прогоняет через Tesseract OCR
- Извлечённый текст добавляет в поле `body` (если body был пустой)
- Проверяет извлечённый текст на gambling-ключевые слова
- Ставит `niche_confidence` если нашёл совпадения

Зависимости: `pytesseract`, `Pillow`, системный Tesseract (бесплатно)

---

### Модуль 3: Gemini Flash — классификация картинок
**Файл:** `adspy/pipeline/steps/gemini_classify.py`

Что делает:
- Берёт объявления где OCR не дал результата (body пустой, niche_confidence низкая)
- Отправляет скриншот в Gemini 2.0 Flash
- Промпт: "Classify this ad. Is it gambling? Return niche and confidence."
- Обновляет niche и niche_confidence

Зависимости: `google-genai` (бесплатно, 1500 запросов/день, 15/мин)

Лимит: 1500/день — хватит для сложных случаев, основную массу покроет OCR

---

### Модуль 4: Snowball — расширение через страницы
**Файл:** `adspy/pipeline/steps/snowball.py`

Что делает:
- Берёт все page_id где хотя бы 1 объявление = gambling
- Для каждого page_id запрашивает ВСЕ объявления через API (`search_page_ids=`)
- Новые объявления проходят через OCR + Gemini
- Находит страницы, которые ключевые слова бы пропустили

Зависимости: существующий FB API токен

---

## Порядок реализации

```
Шаг 1: OCR модуль (ocr.py)
        - самый простой, сразу даёт результат
        - добавить в pipeline между download и classify

Шаг 2: Gemini classify (gemini_classify.py)
        - заменяет текущий classify.py (Anthropic → Gemini Free)
        - работает для картинок где OCR не помог

Шаг 3: Snowball (snowball.py)
        - расширяет охват через найденные страницы
        - добавить в pipeline после save

Шаг 4: Скрейпер сайта (fb_scraper.py)
        - самый сложный, требует Playwright + обход защиты
        - делается последним, но даёт максимальный охват

Шаг 5: Интеграция в Streamlit
        - новая вкладка "🕷️ Deep Scan"
        - кнопка запуска snowball
        - статистика: сколько объявлений нашёл OCR, сколько Gemini
```

## Обновлённый pipeline

```
БЫЛО:   dedup → download → classify → signals → save
БУДЕТ:  dedup → download → ocr → gemini_classify → signals → snowball → save
```

## Зависимости (все бесплатные)

```
pytesseract    — OCR обёртка
Pillow         — работа с изображениями
google-genai   — Gemini API (бесплатный tier)
playwright     — скрейпинг сайта (шаг 4)
```
