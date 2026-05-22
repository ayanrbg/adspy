"""
Scrape Facebook Ad Library website to get ALL ads for a country.
Intercepts GraphQL API responses instead of parsing DOM (more reliable).
"""
import asyncio
import json
import random
import re
import os
from dataclasses import dataclass

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
    """Extract ad data from a GraphQL response node."""
    try:
        ad_id = node.get("adArchiveID") or node.get("ad_archive_id") or node.get("id")
        page_name = ""
        page_id = None

        # Try different response structures
        page_info = node.get("publisherPlatformPageInfo") or node.get("page_info") or {}
        if isinstance(page_info, list) and page_info:
            page_info = page_info[0]
        page_name = page_info.get("page_name") or page_info.get("name") or ""
        page_id = page_info.get("page_id") or page_info.get("id")

        if not page_name:
            page_name = node.get("page_name", "") or node.get("pageName", "")
        if not page_id:
            page_id = node.get("page_id") or node.get("pageID")

        # Get ad body text
        body = ""
        body_field = node.get("body") or node.get("ad_creative_bodies")
        if isinstance(body_field, dict):
            body = body_field.get("text", "")
        elif isinstance(body_field, list):
            body = body_field[0] if body_field else ""
        elif isinstance(body_field, str):
            body = body_field

        snapshot_url = None
        if ad_id:
            snapshot_url = f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}"

        library_url = None
        if ad_id:
            library_url = f"https://www.facebook.com/ads/library/?id={ad_id}"

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
    """Try to extract ads from any API/GraphQL response text."""
    ads = []

    # Try to find JSON objects containing ad data
    # Facebook often returns multiple JSON objects or uses "for (;;);" prefix
    cleaned = text
    if cleaned.startswith("for (;;);"):
        cleaned = cleaned[len("for (;;);"):]

    # Try parsing as JSON
    try:
        data = json.loads(cleaned)
        ads.extend(_walk_json_for_ads(data))
    except json.JSONDecodeError:
        # Try to find JSON fragments
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
    """Recursively walk JSON to find ad nodes."""
    if depth > 15:
        return []
    ads = []

    if isinstance(data, dict):
        # Check if this node looks like an ad
        if any(k in data for k in ("adArchiveID", "ad_archive_id", "adcard")):
            ad = _parse_ad_from_graphql(data)
            if ad:
                ads.append(ad)

        # Check for edges/nodes pattern (GraphQL)
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

        # Recurse into all values
        if not ads:
            for v in data.values():
                ads.extend(_walk_json_for_ads(v, depth + 1))

    elif isinstance(data, list):
        for item in data:
            ads.extend(_walk_json_for_ads(item, depth + 1))

    return ads


async def scrape_ad_library(
    country: str = "IN",
    max_ads: int = 500,
    scroll_pause_min: float = 3.0,
    scroll_pause_max: float = 7.0,
    on_progress=None,
) -> list[ScrapedAd]:
    from playwright.async_api import async_playwright

    launch_kwargs = {"headless": True}
    if PROXY_URL:
        launch_kwargs["proxy"] = {"server": PROXY_URL}

    ads: list[ScrapedAd] = []
    seen_ids: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = await context.new_page()

        # Intercept API responses
        async def handle_response(response):
            try:
                url = response.url
                if not any(x in url for x in ("graphql", "api/graphql", "ads_archive", "AdLibrarySearch")):
                    return
                if response.status != 200:
                    return
                text = await response.text()
                found = _extract_ads_from_response(text)
                for ad in found:
                    key = ad.ad_id or f"{ad.page_name}|{ad.body[:50]}"
                    if key not in seen_ids:
                        seen_ids.add(key)
                        ads.append(ad)
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            url = (
                f"{AD_LIBRARY_URL}?active_status=active"
                f"&ad_type=all"
                f"&country={country}"
                f"&media_type=all"
            )
            if on_progress:
                on_progress(0, "Opening Ad Library...")

            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)

            # Accept cookies
            try:
                cookie_btn = page.locator('[data-cookiebanner="accept_button"]')
                if await cookie_btn.is_visible(timeout=3000):
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            if on_progress:
                on_progress(len(ads), f"Page loaded, collected {len(ads)} ads so far...")

            # Scroll loop
            prev_count = 0
            no_new_rounds = 0

            while len(ads) < max_ads:
                # Scroll down
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                pause = random.uniform(scroll_pause_min, scroll_pause_max)
                await asyncio.sleep(pause)

                # Click "See more results" type buttons
                for btn_text in ["See more", "Show more", "Load more"]:
                    try:
                        btn = page.locator(f'div[role="button"]:has-text("{btn_text}")')
                        if await btn.first.is_visible(timeout=500):
                            await btn.first.click()
                            await asyncio.sleep(3)
                    except Exception:
                        pass

                if on_progress:
                    on_progress(len(ads), f"Scrolling... {len(ads)} ads collected")

                if len(ads) == prev_count:
                    no_new_rounds += 1
                    if no_new_rounds >= 8:
                        if on_progress:
                            on_progress(len(ads), "No more new ads, stopping")
                        break
                else:
                    no_new_rounds = 0
                    prev_count = len(ads)

        except Exception as e:
            if on_progress:
                on_progress(len(ads), f"Error: {e}")
        finally:
            await browser.close()

    return ads[:max_ads]
