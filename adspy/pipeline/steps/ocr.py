import io
import re

import httpx
from PIL import Image

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.config.keywords.gambling_in import KEYWORDS

# Pre-compile patterns for fast matching
_PATTERNS = [re.compile(re.escape(kw), re.IGNORECASE) for kw in KEYWORDS]


def _match_gambling(text: str) -> float:
    """Return confidence 0.0-1.0 based on how many gambling keywords match."""
    if not text.strip():
        return 0.0
    hits = sum(1 for p in _PATTERNS if p.search(text))
    if hits >= 3:
        return 0.95
    if hits == 2:
        return 0.8
    if hits == 1:
        return 0.6
    return 0.0


class OCRStep(Step):
    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        try:
            import pytesseract
        except ImportError:
            print("[OCRStep] pytesseract not installed, skipping")
            return ads

        for ad in ads:
            if ad.body.strip() and ad.niche_confidence > 0.5:
                continue
            if not ad.screenshot_url:
                continue
            try:
                text = await self._extract_text(ad.screenshot_url, pytesseract)
                if text.strip():
                    if not ad.body.strip():
                        ad.body = text
                    confidence = _match_gambling(text)
                    if confidence > ad.niche_confidence:
                        ad.niche = "gambling"
                        ad.niche_confidence = confidence
            except Exception as e:
                print(f"[OCRStep] Failed for {ad.id}: {e}")
        return ads

    async def _extract_text(self, url: str, pytesseract) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        text = pytesseract.image_to_string(img, lang="eng+hin")
        return text
