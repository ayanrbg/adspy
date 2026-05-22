import streamlit as st
import aiohttp
import asyncio
import sqlite3
import json
import csv
import io
import os
import tempfile
from datetime import date
from pathlib import Path

# On Streamlit Cloud the filesystem is ephemeral but writable in /tmp
if os.environ.get("STREAMLIT_SHARING_MODE") or os.environ.get("IS_STREAMLIT_CLOUD"):
    DB_PATH = Path(tempfile.gettempdir()) / "adspy_local.db"
else:
    DB_PATH = Path(__file__).parent / "adspy_local.db"

# ======================== KEYWORDS ========================

GAMBLING_IN_KEYWORDS = [
    # Top brands
    "1xbet", "betway India", "parimatch", "pin-up casino", "mostbet",
    "melbet", "1win", "linebet", "betwinner", "dafabet India",
    "bet365 India", "10cric", "fun88", "pure win", "casumo India",
    "leovegas India", "betmaster", "rajabets", "megapari", "4rabet",
    "crickex", "fairplay club", "lotus365", "world777", "diamondexch",
    "skyexchange", "laser247", "tigerexch", "lordsexch", "gold365", "silverexch",
    # Generic
    "online casino India", "casino bonus India", "live casino India",
    "slots real money", "win real money", "jackpot India",
    "casino app download", "best casino app", "real money casino",
    "casino deposit bonus", "free spins India", "welcome bonus casino",
    # Card games
    "teen patti real cash", "teen patti gold", "teen patti master",
    "andar bahar online", "andar bahar real money", "poker online India",
    "dragon tiger game", "jhandi munda online",
    # Rummy
    "rummy online", "rummy real cash", "rummy circle", "rummy culture",
    "a23 rummy", "junglee rummy", "rummy bo", "holy rummy",
    "rummy gold", "rummy nabob", "rummy modern", "rummy ola",
    # Crash / instant
    "aviator game", "aviator predictor", "aviator app",
    "JetX game", "spaceman game", "mines game casino",
    "plinko game", "crash game real money",
    # Sports betting
    "cricket betting app", "cricket betting tips", "IPL betting",
    "IPL prediction", "cricket satta", "sports betting app",
    "live betting app", "best betting app India", "online satta", "satta matka",
    # Fantasy
    "fantasy cricket", "dream11 alternative", "fantasy sports real money",
    # Hindi
    "ऑनलाइन कैसीनो", "जीतो असली पैसा", "क्रिकेट सट्टा",
    "तीन पत्ती", "रमी गेम", "पैसे कमाओ", "सट्टा मटका", "एविएटर गेम",
    # Lure phrases
    "earn money online game", "daily income app", "UPI withdrawal",
    "instant withdrawal casino", "paytm casino", "colour prediction",
    "color prediction game", "colour trading", "wingo game",
]

# ======================== DATABASE ========================

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id TEXT PRIMARY KEY,
            source TEXT,
            page_id TEXT,
            page_name TEXT,
            body TEXT,
            title TEXT,
            snapshot_url TEXT,
            country TEXT,
            niche TEXT,
            start_date TEXT,
            stop_date TEXT,
            is_active INTEGER DEFAULT 1,
            days_active INTEGER,
            raw TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_country_niche ON ads (country, niche)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_days_active ON ads (days_active DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_page_id ON ads (page_id)")
    conn.commit()
    return conn


def save_ads_to_db(ads: list[dict]) -> int:
    conn = get_db()
    saved = 0
    for ad in ads:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO ads
                (id, source, page_id, page_name, body, title, snapshot_url,
                 country, niche, start_date, stop_date, is_active, days_active, raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ad["id"], ad["source"], ad.get("page_id"), ad.get("page_name"),
                ad.get("body", ""), ad.get("title", ""), ad.get("snapshot_url"),
                ad["country"], ad["niche"],
                ad.get("start_date"), ad.get("stop_date"),
                1 if ad.get("is_active") else 0,
                ad.get("days_active"),
                json.dumps(ad.get("raw", {}), ensure_ascii=False),
            ))
            saved += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return saved



def search_db(
    country: str, niche: str, min_days: int, only_active: bool,
    sort_by: str, limit: int, text_filter: str = "",
) -> list[dict]:
    conn = get_db()
    conditions = ["country = ?", "niche = ?", "COALESCE(days_active, 0) >= ?"]
    params: list = [country, niche, min_days]

    if only_active:
        conditions.append("is_active = 1")

    if text_filter.strip():
        conditions.append("(body LIKE ? OR title LIKE ? OR page_name LIKE ?)")
        like = f"%{text_filter.strip()}%"
        params.extend([like, like, like])

    allowed_sort = {"days_active", "start_date", "created_at"}
    sort_col = sort_by if sort_by in allowed_sort else "days_active"

    query = f"""
        SELECT * FROM ads
        WHERE {' AND '.join(conditions)}
        ORDER BY {sort_col} DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_page_ads(page_id: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ads WHERE page_id = ? ORDER BY start_date DESC LIMIT 100",
        (page_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_db_stats() -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM ads WHERE is_active = 1").fetchone()[0]
    pages = conn.execute("SELECT COUNT(DISTINCT page_id) FROM ads WHERE page_id IS NOT NULL").fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "pages": pages}


def get_top_pages(country: str, niche: str, limit: int = 30) -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT page_id, page_name, COUNT(*) as ad_count,
               SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count,
               MAX(days_active) as max_days
        FROM ads
        WHERE country = ? AND niche = ? AND page_id IS NOT NULL
        GROUP BY page_id
        ORDER BY ad_count DESC
        LIMIT ?
    """, (country, niche, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_csv(ads: list[dict]) -> str:
    output = io.StringIO()
    if not ads:
        return ""
    fields = ["id", "page_name", "page_id", "body", "title", "country", "niche",
              "days_active", "is_active", "start_date", "stop_date", "snapshot_url"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(ads)
    return output.getvalue()


# ======================== DEEP SCAN HELPERS ========================

def _match_gambling_text(text: str) -> float:
    """Return confidence based on gambling keyword matches in text."""
    if not text.strip():
        return 0.0
    import re as _re
    lower = text.lower()
    hits = sum(1 for kw in GAMBLING_IN_KEYWORDS if kw.lower() in lower)
    if hits >= 3:
        return 0.95
    if hits == 2:
        return 0.8
    if hits == 1:
        return 0.6
    return 0.0


def ocr_extract(image_bytes: bytes) -> str:
    """Run OCR on image bytes, return extracted text."""
    try:
        import pytesseract
    except ImportError:
        raise RuntimeError("pytesseract not installed")
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    try:
        return pytesseract.image_to_string(img, lang="eng+hin")
    except Exception:
        # Fallback to English only if Hindi not available
        return pytesseract.image_to_string(img, lang="eng")


async def download_image(url: str) -> bytes | None:
    """Download image from URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.read()
    return None


async def gemini_classify_image(image_bytes: bytes, api_key: str) -> tuple[str, float]:
    """Send image to Gemini Flash for classification."""
    import base64
    img_b64 = base64.b64encode(image_bytes).decode()
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                {"text": (
                    "Classify this ad creative. Return ONLY JSON: "
                    "{\"niche\": \"...\", \"confidence\": 0.0-1.0}. "
                    "Niches: gambling, nutra, dating, finance, ecommerce, other."
                )},
            ]
        }]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params={"key": api_key}, json=payload) as resp:
            data = await resp.json()
    import re as _re
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    match = _re.search(r"\{[^}]+\}", text)
    if match:
        result = json.loads(match.group())
        return result.get("niche", "other"), float(result.get("confidence", 0.0))
    return ("other", 0.0)


async def fetch_page_ads_api(token: str, page_id: str, country: str) -> list[dict]:
    """Fetch all ads from a page via Facebook API (snowball)."""
    params = {
        "access_token": token,
        "search_page_ids": page_id,
        "ad_reached_countries": country,
        "ad_type": "ALL",
        "limit": 250,
        "fields": FB_FIELDS,
    }
    ads = []
    url = FB_API_URL
    async with aiohttp.ClientSession() as session:
        for _ in range(10):  # max 10 pages
            if not url:
                break
            if _ == 0:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
            else:
                async with session.get(url) as resp:
                    data = await resp.json()
            if "error" in data:
                break
            batch = data.get("data", [])
            if not batch:
                break
            for raw in batch:
                ads.append(normalize_fb_ad(raw, country, "gambling"))
            url = data.get("paging", {}).get("next")
    return ads


def update_ad_in_db(ad_id: str, body: str, niche: str, niche_confidence: float):
    """Update an ad's body and niche in DB."""
    conn = get_db()
    conn.execute(
        "UPDATE ads SET body = ?, niche = ? WHERE id = ?",
        (body, niche, ad_id),
    )
    conn.commit()
    conn.close()


def get_ads_for_deep_scan(country: str, limit: int = 500) -> list[dict]:
    """Get ads with empty/short body or low-confidence niche for deep scanning."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM ads
        WHERE country = ? AND snapshot_url IS NOT NULL
        AND (LENGTH(COALESCE(body, '')) < 10 OR niche = '' OR niche = 'other')
        ORDER BY created_at DESC
        LIMIT ?
    """, (country, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_gambling_page_ids(country: str) -> list[str]:
    """Get page IDs that have at least 1 gambling ad."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT page_id FROM ads
        WHERE country = ? AND niche = 'gambling' AND page_id IS NOT NULL
    """, (country,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ======================== FACEBOOK API ========================

FB_API_URL = "https://graph.facebook.com/v19.0/ads_archive"
FB_FIELDS = ",".join([
    "id", "page_id", "page_name",
    "ad_creative_bodies", "ad_creative_link_titles",
    "ad_snapshot_url", "ad_delivery_start_time",
    "ad_delivery_stop_time",
])


def normalize_fb_ad(raw: dict, country: str, niche: str) -> dict:
    start = raw.get("ad_delivery_start_time")
    stop = raw.get("ad_delivery_stop_time")
    days = None
    is_active = stop is None
    if start:
        try:
            start_d = date.fromisoformat(start[:10])
            end_d = date.fromisoformat(stop[:10]) if stop else date.today()
            days = (end_d - start_d).days
        except ValueError:
            pass
    return {
        "id": f"fb_{raw['id']}",
        "source": "fb_api",
        "page_id": raw.get("page_id"),
        "page_name": raw.get("page_name"),
        "body": (raw.get("ad_creative_bodies") or [""])[0],
        "title": (raw.get("ad_creative_link_titles") or [""])[0],
        "snapshot_url": raw.get("ad_snapshot_url"),
        "country": country,
        "niche": niche,
        "start_date": start,
        "stop_date": stop,
        "is_active": is_active,
        "days_active": days,
        "raw": raw,
    }


async def fetch_facebook_ads_paginated(
    token: str, keyword: str, country: str, niche: str,
    max_pages: int = 20,
) -> list[dict]:
    """Fetch ads with full pagination."""
    params = {
        "access_token": token,
        "search_terms": keyword,
        "ad_reached_countries": country,
        "ad_type": "ALL",
        "limit": 250,
        "fields": FB_FIELDS,
    }
    ads = []
    pages_fetched = 0
    url = FB_API_URL

    async with aiohttp.ClientSession() as session:
        while url and pages_fetched < max_pages:
            if pages_fetched == 0:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
            else:
                async with session.get(url) as resp:
                    data = await resp.json()

            if "error" in data:
                raise Exception(data["error"].get("message", str(data["error"])))

            batch = data.get("data", [])
            if not batch:
                break

            for raw in batch:
                ads.append(normalize_fb_ad(raw, country, niche))

            pages_fetched += 1
            url = data.get("paging", {}).get("next")

    return ads


# ======================== STREAMLIT UI ========================

st.set_page_config(page_title="AdSpy", page_icon="🔍", layout="wide")
st.title("🔍 AdSpy — India Gambling Spy Service")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    fb_token = st.text_input("Facebook Access Token", type="password",
                             help="developers.facebook.com/tools/explorer")

    st.divider()
    country = st.selectbox("Country", ["IN", "BR", "DE", "US", "ID", "PH", "NG", "KE", "BD", "PK"])
    niche = st.selectbox("Niche", ["gambling", "nutra", "dating", "finance", "ecommerce", "crypto"])

    st.divider()
    stats = get_db_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Ads", stats["total"])
    c2.metric("Active", stats["active"])
    c3.metric("Pages", stats["pages"])



_HAS_PLAYWRIGHT = False
try:
    import playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    pass

if _HAS_PLAYWRIGHT:
    tab_collect, tab_scrape, tab_deep, tab_search, tab_pages, tab_bundles, tab_export = st.tabs([
        "🚀 Collect", "🌐 Full Scrape", "🕷️ Deep Scan", "🔎 Search", "📊 Top Pages", "🔗 Bundles", "📥 Export"
    ])
else:
    tab_collect, tab_deep, tab_search, tab_pages, tab_bundles, tab_export = st.tabs([
        "🚀 Collect", "🕷️ Deep Scan", "🔎 Search", "📊 Top Pages", "🔗 Bundles", "📥 Export"
    ])
    tab_scrape = None

# ======================== COLLECT TAB ========================
with tab_collect:
    st.subheader("Mass collect from Facebook Ad Library")

    if not fb_token:
        st.error("⬅️ Enter Facebook token in sidebar first!")
        st.markdown("""
        ### How to get a Facebook Ad Library token:

        1. Go to **[developers.facebook.com/apps](https://developers.facebook.com/apps/)** → Create App (type: Business)
        2. Open **[Graph API Explorer](https://developers.facebook.com/tools/explorer/)**
        3. Select your app → Click **Generate Access Token**
        4. Grant `ads_read` permission
        5. Copy token → paste in sidebar

        > ⏰ Token expires in ~2 hours. For 60-day token: App Settings → Basic → get App Secret, then exchange via API.
        """)
    else:
        mode = st.radio("Mode", ["🔥 Full blast (all keywords)", "🎯 Custom keywords"], horizontal=True)

        if mode == "🔥 Full blast (all keywords)":
            st.info(f"Will search **{len(GAMBLING_IN_KEYWORDS)} keywords** with pagination.")
            keywords = GAMBLING_IN_KEYWORDS
        else:
            keywords_input = st.text_area(
                "Keywords (one per line)",
                value="\n".join(GAMBLING_IN_KEYWORDS[:10]),
                height=200,
            )
            keywords = [k.strip() for k in keywords_input.strip().split("\n") if k.strip()]

        max_pages = st.slider(
            "Pages per keyword (each = 250 ads max)",
            min_value=1, max_value=50, value=5,
        )
        st.caption(f"Keywords: **{len(keywords)}** | Max capacity: **{len(keywords) * max_pages * 250:,}** ads")

        if st.button("🚀 START COLLECTION", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_container = st.container()

            all_ads = []
            seen_ids: set[str] = set()
            errors = 0
            stopped = False

            for i, kw in enumerate(keywords):
                status_text.text(f"[{i+1}/{len(keywords)}] Searching: {kw}")
                progress_bar.progress((i + 1) / len(keywords))

                try:
                    ads = asyncio.run(fetch_facebook_ads_paginated(
                        fb_token, kw, country, niche, max_pages,
                    ))
                    new = 0
                    for ad in ads:
                        if ad["id"] not in seen_ids:
                            seen_ids.add(ad["id"])
                            all_ads.append(ad)
                            new += 1
                    log_container.caption(f"✅ '{kw}' — {len(ads)} found, {new} new")
                except Exception as e:
                    errors += 1
                    log_container.caption(f"❌ '{kw}' — {e}")
                    err_lower = str(e).lower()
                    if "too many calls" in err_lower or "rate limit" in err_lower:
                        log_container.warning("⚠️ Rate limited. Stopping to save what we have.")
                        stopped = True
                        break

            if all_ads:
                saved = save_ads_to_db(all_ads)
                st.success(f"✅ Collected **{len(all_ads)}** unique ads → **{saved}** saved to DB")
                if stopped:
                    st.warning("Collection was stopped due to rate limit. Run again later for more.")
                st.balloons()
            else:
                st.warning("No ads found. Check token or keywords.")

# ======================== FULL SCRAPE TAB ========================
if tab_scrape is not None:
    with tab_scrape:
        st.subheader("Full Scrape — No API Token Needed")
        st.caption("Searches Ad Library via browser, intercepts data from responses")

        scrape_mode = st.radio("Keywords", [
            "All gambling keywords (159)",
            "Custom keywords",
        ], horizontal=True, key="scrape_mode")

        if scrape_mode == "Custom keywords":
            scrape_kw_input = st.text_area(
                "Keywords (one per line)", value="casino\nbetting\nrummy\naviator\nteen patti",
                height=150, key="scrape_kw",
            )
            scrape_keywords = [k.strip() for k in scrape_kw_input.strip().split("\n") if k.strip()]
        else:
            scrape_keywords = GAMBLING_IN_KEYWORDS

        sc1, sc2 = st.columns(2)
        scrape_max = sc1.slider("Max ads total", 50, 5000, 1000, step=50, key="scrape_max")
        scrape_pause = sc2.slider("Pause between scrolls (sec)", 3, 15, 5, key="scrape_pause")

        st.caption(f"Keywords: **{len(scrape_keywords)}** | No Facebook token needed")

        if st.button("🌐 START SCRAPE", type="primary", use_container_width=True):
            try:
                from adspy.sources.fb_scraper import scrape_ad_library, ScrapedAd
            except Exception as import_err:
                st.error(f"Failed to load scraper: {import_err}")
                st.stop()

            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            def on_progress(count, text):
                progress_placeholder.metric("Ads collected", count)
                status_placeholder.text(text)

            status_placeholder.text("Launching browser...")
            scraped = asyncio.run(scrape_ad_library(
                country=country,
                keywords=scrape_keywords,
                max_ads=scrape_max,
                scroll_pause_min=max(2.0, scrape_pause - 2),
                scroll_pause_max=scrape_pause + 2,
                on_progress=on_progress,
            ))

            if scraped:
                ads_to_save = []
                for s in scraped:
                    ads_to_save.append({
                        "id": f"fb_scrape_{s.ad_id}" if s.ad_id else f"fb_scrape_{hash(s.page_name + s.body[:50])}",
                        "source": "fb_scraper",
                        "page_id": s.page_id,
                        "page_name": s.page_name,
                        "body": s.body,
                        "title": "",
                        "snapshot_url": s.snapshot_url,
                        "country": country,
                        "niche": "",
                        "start_date": None,
                        "stop_date": None,
                        "is_active": True,
                        "days_active": None,
                        "raw": {},
                    })
                saved = save_ads_to_db(ads_to_save)
                st.success(f"Scraped **{len(scraped)}** ads, saved **{saved}** to DB")
                st.caption("Now run **Deep Scan** to classify them (OCR + Gemini)")
            else:
                st.warning("No ads scraped. Facebook may have blocked or page structure changed.")

# ======================== DEEP SCAN TAB ========================
with tab_deep:
    st.subheader("Deep Scan — OCR + AI + Snowball")
    st.caption("Find ads that keyword search missed: image-only ads, cloaked text, new pages")

    gemini_key = st.text_input("Gemini API Key (free)", type="password",
                               help="Get free key at aistudio.google.com")

    col1, col2, col3 = st.columns(3)
    run_ocr = col1.checkbox("OCR (extract text from images)", value=True)
    run_gemini = col2.checkbox("Gemini AI classify", value=bool(gemini_key))
    run_snowball = col3.checkbox("Snowball (expand pages)", value=bool(fb_token))

    scan_limit = st.slider("Ads to scan", 10, 500, 100, key="scan_limit")

    if st.button("🕷️ START DEEP SCAN", type="primary", use_container_width=True):
        ocr_count = 0
        gemini_count = 0
        snowball_count = 0

        # Phase 1: OCR
        if run_ocr:
            candidates = get_ads_for_deep_scan(country, scan_limit)
            if candidates:
                st.write(f"**Phase 1: OCR** — scanning {len(candidates)} ads...")
                progress = st.progress(0)
                for i, ad in enumerate(candidates):
                    progress.progress((i + 1) / len(candidates))
                    if not ad.get("snapshot_url"):
                        continue
                    try:
                        img_bytes = asyncio.run(download_image(ad["snapshot_url"]))
                        if not img_bytes:
                            continue
                        text = ocr_extract(img_bytes)
                        if text.strip():
                            conf = _match_gambling_text(text)
                            if conf > 0.5:
                                update_ad_in_db(ad["id"], text[:2000], "gambling", conf)
                                ocr_count += 1
                    except Exception as e:
                        st.caption(f"OCR error: {ad['id']} — {e}")
                st.success(f"OCR found **{ocr_count}** gambling ads from images")
            else:
                st.info("No candidates for OCR scan")

        # Phase 2: Gemini
        if run_gemini and gemini_key:
            remaining = get_ads_for_deep_scan(country, scan_limit)
            if remaining:
                st.write(f"**Phase 2: Gemini** — classifying {len(remaining)} ads...")
                progress2 = st.progress(0)
                for i, ad in enumerate(remaining):
                    progress2.progress((i + 1) / len(remaining))
                    if not ad.get("snapshot_url"):
                        continue
                    try:
                        img_bytes = asyncio.run(download_image(ad["snapshot_url"]))
                        if not img_bytes:
                            continue
                        niche_result, conf = asyncio.run(
                            gemini_classify_image(img_bytes, gemini_key)
                        )
                        if niche_result == "gambling" and conf > 0.5:
                            body = ad.get("body") or ""
                            update_ad_in_db(ad["id"], body, "gambling", conf)
                            gemini_count += 1
                    except Exception as e:
                        st.caption(f"Gemini error: {ad['id']} — {e}")
                        if "quota" in str(e).lower() or "429" in str(e):
                            st.warning("Gemini rate limit hit, stopping AI phase")
                            break
                st.success(f"Gemini classified **{gemini_count}** gambling ads")
            else:
                st.info("No candidates for Gemini")

        # Phase 3: Snowball
        if run_snowball and fb_token:
            gambling_pages = get_gambling_page_ids(country)
            if gambling_pages:
                st.write(f"**Phase 3: Snowball** — expanding {len(gambling_pages)} pages...")
                progress3 = st.progress(0)
                existing_ids = set()
                conn = get_db()
                for row in conn.execute("SELECT id FROM ads").fetchall():
                    existing_ids.add(row[0])
                conn.close()

                new_ads = []
                for i, pid in enumerate(gambling_pages):
                    progress3.progress((i + 1) / len(gambling_pages))
                    try:
                        page_ads = asyncio.run(fetch_page_ads_api(fb_token, pid, country))
                        for ad in page_ads:
                            if ad["id"] not in existing_ids:
                                existing_ids.add(ad["id"])
                                ad["niche"] = "gambling"
                                new_ads.append(ad)
                    except Exception as e:
                        st.caption(f"Snowball error: {pid} — {e}")

                if new_ads:
                    snowball_count = save_ads_to_db(new_ads)
                st.success(f"Snowball found **{snowball_count}** new ads from gambling pages")
            else:
                st.info("No gambling pages to expand")

        # Summary
        st.divider()
        total_found = ocr_count + gemini_count + snowball_count
        if total_found > 0:
            st.success(f"🎯 Deep Scan complete: **{total_found}** new gambling ads discovered")
            c1, c2, c3 = st.columns(3)
            c1.metric("OCR", ocr_count)
            c2.metric("Gemini AI", gemini_count)
            c3.metric("Snowball", snowball_count)
        else:
            st.info("Deep Scan complete — no new gambling ads found this time")

# ======================== SEARCH TAB ========================
with tab_search:
    st.subheader("Search collected ads")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        text_filter = st.text_input("Text search", placeholder="casino, aviator...")
    with c2:
        min_days = st.number_input("Min days active", 0, 365, 0)
    with c3:
        only_active = st.checkbox("Only active", value=False)
    with c4:
        sort_by = st.selectbox("Sort by", ["days_active", "start_date", "created_at"])
    with c5:
        result_limit = st.slider("Limit", 10, 500, 100)

    results = search_db(country, niche, min_days, only_active, sort_by, result_limit, text_filter)

    if not results:
        st.info("No ads. Collect first in 🚀 Collect tab.")
    else:
        st.write(f"**{len(results)} ads**")
        for ad in results:
            days = ad.get("days_active") or 0
            badge = "🔥" if days >= 30 else ("⚡" if days >= 14 else "🆕")
            active_icon = "🟢" if ad.get("is_active") else "🔴"

            with st.expander(f"{badge} {active_icon} {ad.get('page_name', '?')} — {days}d"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    if ad.get("title"):
                        st.markdown(f"**{ad['title']}**")
                    if ad.get("body"):
                        st.text(ad["body"][:500])
                with c2:
                    st.markdown(f"**ID:** `{ad['id']}`")
                    st.markdown(f"**Page:** `{ad.get('page_id', '?')}`")
                    st.markdown(f"**Days:** {days} | **Active:** {'Yes' if ad.get('is_active') else 'No'}")
                    st.markdown(f"**Start:** {ad.get('start_date', '?')} | **Stop:** {ad.get('stop_date', 'running')}")
                    if ad.get("snapshot_url"):
                        st.link_button("🖼️ View Creative", ad["snapshot_url"])

# ======================== TOP PAGES TAB ========================
with tab_pages:
    st.subheader("Top advertisers")
    top = get_top_pages(country, niche, limit=50)
    if not top:
        st.info("No data yet.")
    else:
        for p in top:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.markdown(f"**{p.get('page_name') or p['page_id']}** (`{p['page_id']}`)")
            c2.metric("Ads", p["ad_count"])
            c3.metric("Active", p["active_count"])
            c4.metric("Max days", p["max_days"] or 0)

# ======================== BUNDLES TAB ========================
with tab_bundles:
    st.subheader("All ads from one advertiser")
    page_id = st.text_input("Page ID", value=st.session_state.get("selected_page", ""))

    if page_id:
        page_ads = get_page_ads(page_id)
        if page_ads:
            name = page_ads[0].get("page_name", page_id)
            st.markdown(f"### {name}")

            active_count = sum(1 for a in page_ads if a.get("is_active"))
            max_days = max((a.get("days_active") or 0) for a in page_ads)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total", len(page_ads))
            c2.metric("Active", active_count)
            c3.metric("Max days", f"{max_days}d")

            if max_days >= 30:
                st.success(f"🔥 STRONG — {max_days}+ days running")

            for ad in page_ads:
                days = ad.get("days_active") or 0
                icon = "🟢" if ad.get("is_active") else "🔴"
                line = ad.get("title") or ad.get("body", "")[:100]
                st.markdown(f"{icon} **{days}d** — {line}")
                if ad.get("snapshot_url"):
                    st.caption(f"[View creative]({ad['snapshot_url']})")
        else:
            st.info("No ads for this page.")

# ======================== EXPORT TAB ========================
with tab_export:
    st.subheader("Export data")
    all_data = search_db(country, niche, 0, False, "days_active", 50000)
    if all_data:
        st.write(f"**{len(all_data)}** ads")
        st.download_button(
            "📥 Download CSV",
            export_csv(all_data),
            file_name=f"adspy_{country}_{niche}_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("No data to export.")
