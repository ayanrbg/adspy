from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.storage.postgres import PostgresStorage
from adspy.storage.elastic import ElasticStorage


class SaveStep(Step):
    def __init__(self):
        self._pg = PostgresStorage()
        self._es = ElasticStorage()

    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        for ad in ads:
            await self._pg.upsert_ad(ad)
            await self._es.index_ad(ad)
        return ads
