from datetime import date

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd


class SignalsStep(Step):
    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        for ad in ads:
            if ad.start_date:
                start = date.fromisoformat(ad.start_date[:10])
                end = date.fromisoformat(ad.stop_date[:10]) if ad.stop_date else date.today()
                ad.days_active = (end - start).days
                ad.is_active = ad.stop_date is None
        return ads
