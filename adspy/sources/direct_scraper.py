from adspy.sources.base import AdSource
from adspy.models.ad import NormalizedAd
from adspy.config.keywords import load_keywords


class DirectScraper(AdSource):
    name = "direct_scrape"

    async def fetch(self, cfg: dict) -> list[NormalizedAd]:
        # TODO: implement Playwright-based direct scraping
        keywords = load_keywords(cfg["keywords_ref"])
        out: list[NormalizedAd] = []
        return out
