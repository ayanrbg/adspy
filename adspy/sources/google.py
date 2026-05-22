from adspy.sources.base import AdSource
from adspy.models.ad import NormalizedAd
from adspy.config.keywords import load_keywords


class GoogleSource(AdSource):
    name = "google"

    async def fetch(self, cfg: dict) -> list[NormalizedAd]:
        # TODO: implement Google Ads Transparency Center integration
        keywords = load_keywords(cfg["keywords_ref"])
        out: list[NormalizedAd] = []
        return out
