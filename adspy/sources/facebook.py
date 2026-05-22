import aiohttp

from adspy.sources.base import AdSource
from adspy.models.ad import NormalizedAd
from adspy.config.keywords import load_keywords


class FacebookSource(AdSource):
    name = "fb_api"
    BASE = "https://graph.facebook.com/v19.0/ads_archive"

    def __init__(self, token_pool: list[str] | None = None):
        self.tokens = token_pool or []
        self._i = 0

    def _next_token(self) -> str:
        if not self.tokens:
            raise RuntimeError("No Facebook tokens configured")
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

    async def fetch_by_page_id(self, page_id: str, country: str = "IN") -> list[NormalizedAd]:
        """Fetch all ads from a specific page (used by snowball)."""
        out: list[NormalizedAd] = []
        cfg = {"country": country, "niche": "gambling"}
        async with aiohttp.ClientSession() as session:
            params = {
                "access_token": self._next_token(),
                "search_page_ids": page_id,
                "ad_reached_countries": country,
                "ad_type": "ALL",
                "limit": 100,
                "fields": ",".join([
                    "id", "page_id", "page_name",
                    "ad_creative_bodies", "ad_creative_link_titles",
                    "ad_snapshot_url", "ad_delivery_start_time",
                    "ad_delivery_stop_time", "impressions",
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
            niche=cfg["niche"],
            start_date=raw.get("ad_delivery_start_time"),
            stop_date=raw.get("ad_delivery_stop_time"),
            raw=raw,
        )
