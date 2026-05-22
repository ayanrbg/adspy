import asyncio

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.sources.facebook import FacebookSource
from adspy.config.settings import FB_TOKENS


class SnowballStep(Step):
    """Expand coverage: for every gambling page, fetch ALL its ads via API."""

    def __init__(self):
        self._fb = FacebookSource() if FB_TOKENS else None

    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        if not self._fb:
            print("[SnowballStep] No FB tokens, skipping")
            return ads

        # Collect page IDs where at least 1 ad is gambling with high confidence
        gambling_pages = {
            ad.page_id
            for ad in ads
            if ad.page_id and ad.niche == "gambling" and ad.niche_confidence >= 0.6
        }

        if not gambling_pages:
            return ads

        existing_ids = {ad.id for ad in ads}
        new_ads = []

        print(f"[SnowballStep] Expanding {len(gambling_pages)} gambling pages")
        for page_id in gambling_pages:
            try:
                page_ads = await self._fb.fetch_by_page_id(page_id)
                for ad in page_ads:
                    if ad.id not in existing_ids:
                        ad.niche = "gambling"
                        ad.niche_confidence = 0.7  # inherited from page
                        new_ads.append(ad)
                        existing_ids.add(ad.id)
            except Exception as e:
                print(f"[SnowballStep] Failed for page {page_id}: {e}")

        if new_ads:
            print(f"[SnowballStep] Found {len(new_ads)} new ads from gambling pages")
            ads.extend(new_ads)
        return ads
