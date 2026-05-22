from adspy.sources.base import AdSource
from adspy.models.ad import NormalizedAd
from adspy.config.keywords import load_keywords


class TikTokSource(AdSource):
    name = "tiktok"

    async def fetch(self, cfg: dict) -> list[NormalizedAd]:
        # TODO: implement TikTok Creative Center API integration
        keywords = load_keywords(cfg["keywords_ref"])
        out: list[NormalizedAd] = []
        return out
