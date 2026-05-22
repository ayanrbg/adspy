import redis

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.config.settings import REDIS_URL

DEDUP_TTL = 30 * 24 * 3600  # 30 days


class DeduplicateStep(Step):
    def __init__(self):
        self._redis = redis.from_url(REDIS_URL)

    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        unique = []
        for ad in ads:
            key = f"dedup:{ad.id}"
            if self._redis.set(key, 1, nx=True, ex=DEDUP_TTL):
                unique.append(ad)
        return unique
