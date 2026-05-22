import anthropic

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.config.settings import ANTHROPIC_API_KEY


class ClassifyStep(Step):
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        for ad in ads:
            if ad.body.strip() and ad.niche_confidence > 0.5:
                continue
            if not ad.screenshot_url or not self._client:
                continue
            try:
                niche, confidence = await self._classify_image(ad.screenshot_url)
                ad.niche = niche
                ad.niche_confidence = confidence
            except Exception as e:
                print(f"[ClassifyStep] Failed for {ad.id}: {e}")
        return ads

    async def _classify_image(self, image_url: str) -> tuple[str, float]:
        # TODO: implement Vision API call with Claude
        # message = self._client.messages.create(
        #     model="claude-sonnet-4-20250514",
        #     max_tokens=256,
        #     messages=[{
        #         "role": "user",
        #         "content": [
        #             {"type": "image", "source": {"type": "url", "url": image_url}},
        #             {"type": "text", "text": "Classify this ad creative. Return JSON: {\"niche\": \"...\", \"confidence\": 0.0-1.0}. Possible niches: gambling, nutra, dating, finance, ecommerce, other."},
        #         ],
        #     }],
        # )
        # parse response...
        return ("gambling", 0.0)
