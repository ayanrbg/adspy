"""
Scrape Facebook Ad Library via browser — no API token needed.
Searches by keywords, intercepts GraphQL responses for reliable data extraction.
"""
import asyncio
import json
import random
import re
import os
from dataclasses import dataclass
from urllib.parse import quote

PROXY_URL = os.getenv("PROXY_URL", "")

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"


@dataclass
class ScrapedAd:
    ad_id: str | None
    page_name: str
    page_id: str | None
    body: str
    snapshot_url: str | None
    library_url: str | None


def _parse_ad_from_graphql(node: dict) -> ScrapedAd | None:
    try:
        ad_id = node.get("adArchiveID") or node.get("ad_archive_id") or node.get("id")

        page_name = ""
        page_id = None
        page_info = node.get("publisherPlatformPageInfo") or node.get("page_info") or {}
        if isinstance(page_info, list) and page_info:
            page_info = page_info[0]
        if isinstance(page_info, dict):
            page_name = page_info.get("page_name") or page_info.get("name") or ""
            page_id = page_info.get("page_id") or page_info.get("id")

        if not page_name:
            page_name = node.get("page_name", "") or node.get("pageName", "")
        if not page_id:
            page_id = node.get("page_id") or node.get("pageID")

        body = ""
        body_field = node.get("body") or node.get("ad_creative_bodies")
        if isinstance(body_field, dict):
            body = body_field.get("text", "")
        elif isinstance(body_field, list):
            body = body_field[0] if body_field else ""
        elif isinstance(body_field, str):
            body = body_field

        snapshot_url = f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}" if ad_id else None
        library_url = f"https://www.facebook.com/ads/library/?id={ad_id}" if ad_id else None

        if not ad_id and not page_name:
            return None

        return ScrapedAd(
            ad_id=str(ad_id) if ad_id else None,
            page_name=page_name,
            page_id=str(page_id) if page_id else None,
            body=body,
            snapshot_url=snapshot_url,
            library_url=library_url,
        )
    except Exception:
        return None


def _extract_ads_from_response(text: str) -> list[ScrapedAd]:
    ads = []
    cleaned = text
    if cleaned.startswith("for (;;);"):
        cleaned = cleaned[len("for (;;);"):]

    try:
        data = json.loads(cleaned)
        ads.extend(_walk_json_for_ads(data))
    except json.JSONDecodeError:
        for match in re.finditer(r'\{[^{}]*"adArchiveID"[^{}]*\}', text):
            try:
                node = json.loads(match.group())
                ad = _parse_ad_from_graphql(node)
                if ad:
                    ads.append(ad)
            except Exception:
                continue
    return ads


def _walk_json_for_ads(data, depth=0) -> list[ScrapedAd]:
    if depth > 15:
        return []
    ads = []

    if isinstance(data, dict):
        if any(k in data for k in ("adArchiveID", "ad_archive_id", "adcard")):
            ad = _parse_ad_from_graphql(data)
            if ad:
                ads.append(ad)

        for key in ("edges", "results", "ads", "ad_cards", "search_results"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        node = item.get("node", item)
                        ad = _parse_ad_from_graphql(node)
                        if ad:
                            ads.append(ad)
                        else:
                            ads.extend(_walk_json_for_ads(node, depth + 1))

        if not ads:
            for v in data.values():
                ads.extend(_walk_json_for_ads(v, depth + 1))

    elif isinstance(data, list):
        for item in data:
            ads.extend(_walk_json_for_ads(item, depth + 1))

    return ads


async def scrape_ad_library(
    country: str = "IN",
    keywords: list[str] | None = None,
    max_ads: int = 500,
    scroll_pause_min: float = 3.0,
    scroll_pause_max: float = 7.0,
    on_progress=None,
) -> list[ScrapedAd]:
    """
    Scrape Facebook Ad Library by searching keywords in the browser.
    No API token needed.
    """
    from playwright.async_api import async_playwright

    if not keywords:
        keywords = ["casino", "betting", "slots", "rummy"]

    launch_kwargs = {"headless": True}
    if PROXY_URL:
        launch_kwargs["proxy"] = {"server": PROXY_URL}

    all_ads: list[ScrapedAd] = []
    seen_ids: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)

        try:
            for kw_idx, keyword in enumerate(keywords):
                if len(all_ads) >= max_ads:
                    break

                if on_progress:
                    on_progress(len(all_ads), f"[{kw_idx+1}/{len(keywords)}] Searching: {keyword}")

                context = await browser.new_context(
                    user_agent=random.choice(_USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                page = await context.new_page()

                # Collect ads from network responses
                batch_ads: list[ScrapedAd] = []

                async def handle_response(response):
                    try:
                        url = response.url
                        if not any(x in url for x in ("graphql", "ads_archive", "AdLibrary")):
                            return
                        if response.status != 200:
                            return
                        text = await response.text()
                        found = _extract_ads_from_response(text)
                        for ad in found:
                            key = ad.ad_id or f"{ad.page_name}|{ad.body[:50]}"
                            if key not in seen_ids:
                                seen_ids.add(key)
                                batch_ads.append(ad)
                    except Exception:
                        pass

                page.on("response", handle_response)

                try:
                    url = (
                        f"{AD_LIBRARY_URL}?active_status=active"
                        f"&ad_type=all"
                        f"&country={country}"
                        f"&q={quote(keyword)}"
                        f"&media_type=all"
                    )

                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    await asyncio.sleep(4)

                    # Accept cookies on first keyword
                    if kw_idx == 0:
                        try:
                            cookie_btn = page.locator('[data-cookiebanner="accept_button"]')
                            if await cookie_btn.is_visible(timeout=3000):
                                await cookie_btn.click()
                                await asyncio.sleep(1)
                        except Exception:
                            pass

                    # Scroll to load more results
                    prev_batch = 0
                    no_new = 0
                    for _ in range(20):  # max 20 scrolls per keyword
                        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                        pause = random.uniform(scroll_pause_min, scroll_pause_max)
                        await asyncio.sleep(pause)

                        if len(batch_ads) == prev_batch:
                            no_new += 1
                            if no_new >= 3:
                                break
                        else:
                            no_new = 0
                            prev_batch = len(batch_ads)

                    all_ads.extend(batch_ads)
                    if on_progress:
                        on_progress(len(all_ads), f"'{keyword}' -> {len(batch_ads)} ads (total: {len(all_ads)})")

                except Exception as e:
                    if on_progress:
                        on_progress(len(all_ads), f"Error on '{keyword}': {e}")
                finally:
                    await context.close()

                # Pause between keywords to avoid rate limiting
                if kw_idx < len(keywords) - 1:
                    await asyncio.sleep(random.uniform(2, 5))

        finally:
            await browser.close()

    return all_ads[:max_ads]
