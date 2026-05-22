from adspy.models.ad import NormalizedAd


class Pipeline:
    def __init__(self, steps: list):
        self.steps = steps

    async def run(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        for step in self.steps:
            ads = await step.process(ads)
            print(f"[{step.__class__.__name__}] -> {len(ads)} ads")
        return ads
