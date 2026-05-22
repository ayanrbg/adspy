import asyncio
import json
import re

import httpx

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.config.settings import GEMINI_API_KEY

_PROMPT = (
    "Classify this ad creative. "
    "Return ONLY valid JSON: {\"niche\": \"...\", \"confidence\": 0.0-1.0}. "
    "Possible niches: gambling, nutra, dating, finance, ecommerce, other. "
    "Look for: casino games, betting apps, rummy, teen patti, aviator, slots, "
    "cricket betting, colour prediction, earn money promises."
)

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Rate limit: 15 req/min for free tier
_SEMAPHORE = asyncio.Semaphore(5)
_DELAY = 4.0  # seconds between batches


class GeminiClassifyStep(Step):
    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        if not GEMINI_API_KEY:
            print("[GeminiClassifyStep] No GEMINI_API_KEY, skipping")
            return ads

        candidates = [
            ad for ad in ads
            if ad.niche_confidence < 0.5 and ad.screenshot_url
        ]
        if not candidates:
            return ads

        print(f"[GeminiClassifyStep] Classifying {len(candidates)} ads via Gemini")
        for ad in candidates:
            async with _SEMAPHORE:
                try:
                    niche, confidence = await self._classify(ad.screenshot_url)
                    if confidence > ad.niche_confidence:
                        ad.niche = niche
                        ad.niche_confidence = confidence
                except Exception as e:
                    print(f"[GeminiClassifyStep] Failed for {ad.id}: {e}")
                await asyncio.sleep(_DELAY)
        return ads

    async def _classify(self, image_url: str) -> tuple[str, float]:
        async with httpx.AsyncClient(timeout=60) as client:
            # Download image and encode as base64
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()

            import base64
            img_b64 = base64.b64encode(img_resp.content).decode()

            # Detect mime type
            content_type = img_resp.headers.get("content-type", "image/png")

            payload = {
                "contents": [{
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": content_type,
                                "data": img_b64,
                            }
                        },
                        {"text": _PROMPT},
                    ]
                }]
            }

            resp = await client.post(
                _GEMINI_URL,
                params={"key": GEMINI_API_KEY},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        # Extract JSON from response
        match = re.search(r"\{[^}]+\}", text)
        if match:
            result = json.loads(match.group())
            return result.get("niche", "other"), float(result.get("confidence", 0.0))
        return ("other", 0.0)
