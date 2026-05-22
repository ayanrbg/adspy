"""
Scrape Facebook Ad Library website to get ALL ads for a country.
No keyword dependency — scrolls through the full list.
"""
import asyncio
import random
import re
from dataclasses import dataclass

from playwright.async_api import async_playwright, Page, Browser

from adspy.config.settings import PROXY_URL

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
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


async def scrape_ad_library(
    country: str = "IN",
    max_ads: int = 500,
    scroll_pause_min: float = 3.0,
    scroll_pause_max: float = 7.0,
    on_progress=None,
) -> list[ScrapedAd]:
    """
    Open Ad Library, set country filter, scroll and collect all ad cards.

    Args:
        country: 2-letter country code
        max_ads: stop after collecting this many
        scroll_pause_min/max: random pause range between scrolls (anti-ban)
        on_progress: callback(collected_count, status_text)

    Returns:
        List of ScrapedAd
    """
    launch_kwargs = {"headless": True}
    if PROXY_URL:
        launch_kwargs["proxy"] = {"server": PROXY_URL}

    ads: list[ScrapedAd] = []
    seen_texts: set[str] = set()  # dedup by page_name + body prefix

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = await context.new_page()

        try:
            # Navigate to Ad Library with country filter
            url = (
                f"{AD_LIBRARY_URL}?active_status=active"
                f"&ad_type=all"
                f"&country={country}"
                f"&media_type=all"
            )
            if on_progress:
                on_progress(0, "Opening Ad Library...")

            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)

            # Accept cookies if dialog appears
            try:
                cookie_btn = page.locator('[data-cookiebanner="accept_button"]')
                if await cookie_btn.is_visible(timeout=3000):
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Scroll and collect
            no_new_count = 0
            while len(ads) < max_ads:
                new_ads = await _extract_cards(page, seen_texts)

                if new_ads:
                    ads.extend(new_ads)
                    no_new_count = 0
                    if on_progress:
                        on_progress(len(ads), f"Collected {len(ads)} ads...")
                else:
                    no_new_count += 1
                    if no_new_count >= 5:
                        if on_progress:
                            on_progress(len(ads), "No more ads found, stopping")
                        break

                # Scroll down
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                pause = random.uniform(scroll_pause_min, scroll_pause_max)
                await asyncio.sleep(pause)

                # Check for "see more" button
                try:
                    see_more = page.locator('div[role="button"]:has-text("See more")')
                    if await see_more.first.is_visible(timeout=1000):
                        await see_more.first.click()
                        await asyncio.sleep(2)
                except Exception:
                    pass

        except Exception as e:
            if on_progress:
                on_progress(len(ads), f"Error: {e}")
        finally:
            await browser.close()

    return ads[:max_ads]


async def _extract_cards(page: Page, seen: set[str]) -> list[ScrapedAd]:
    """Extract ad cards from current page state."""
    new_ads = []

    # Ad Library renders ads in divs with specific structure
    # Each ad card typically has: page name, ad text, "See ad details" link
    cards = await page.locator('[class*="xrvj5dj"]').all()

    if not cards:
        # Fallback: try broader selectors
        cards = await page.locator('div[class*="x1yztbdb"]').all()

    for card in cards:
        try:
            text_content = await card.inner_text(timeout=2000)
            if not text_content.strip():
                continue

            lines = [l.strip() for l in text_content.split("\n") if l.strip()]
            if len(lines) < 2:
                continue

            page_name = lines[0]
            body = "\n".join(lines[1:5])  # first few lines as body

            dedup_key = f"{page_name}|{body[:100]}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Try to extract page ID and ad ID from links
            page_id = None
            snapshot_url = None
            library_url = None

            links = await card.locator("a[href]").all()
            for link in links:
                href = await link.get_attribute("href")
                if not href:
                    continue
                if "/ads/library/" in href and "id=" in href:
                    library_url = href
                    id_match = re.search(r"id=(\d+)", href)
                    if id_match:
                        snapshot_url = f"https://www.facebook.com/ads/archive/render_ad/?id={id_match.group(1)}"
                if "facebook.com/" in href and "/ads/library/" not in href:
                    pid_match = re.search(r"facebook\.com/(\d+)", href)
                    if pid_match:
                        page_id = pid_match.group(1)

            ad_id = None
            if library_url:
                id_match = re.search(r"id=(\d+)", library_url)
                if id_match:
                    ad_id = id_match.group(1)

            new_ads.append(ScrapedAd(
                ad_id=ad_id,
                page_name=page_name,
                page_id=page_id,
                body=body,
                snapshot_url=snapshot_url,
                library_url=library_url,
            ))
        except Exception:
            continue

    return new_ads
