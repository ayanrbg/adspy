import hashlib
import io

import boto3

from adspy.pipeline.steps.base import Step
from adspy.models.ad import NormalizedAd
from adspy.config.settings import (
    S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_PUBLIC_URL, PROXY_URL,
)


class DownloadCreativeStep(Step):
    def __init__(self):
        s3_kwargs = {}
        if S3_ENDPOINT:
            s3_kwargs["endpoint_url"] = S3_ENDPOINT
        if S3_ACCESS_KEY:
            s3_kwargs["aws_access_key_id"] = S3_ACCESS_KEY
            s3_kwargs["aws_secret_access_key"] = S3_SECRET_KEY
        self._s3 = boto3.client("s3", **s3_kwargs) if S3_ACCESS_KEY else None

    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        for ad in ads:
            if not ad.snapshot_url:
                continue
            try:
                screenshot_bytes = await self._take_screenshot(ad.snapshot_url, ad.country)
                if screenshot_bytes and self._s3:
                    key = f"screenshots/{ad.id}.png"
                    self._s3.upload_fileobj(
                        io.BytesIO(screenshot_bytes),
                        S3_BUCKET,
                        key,
                        ExtraArgs={"ContentType": "image/png"},
                    )
                    ad.screenshot_url = f"{S3_PUBLIC_URL}/{key}"
            except Exception as e:
                print(f"[DownloadCreativeStep] Failed for {ad.id}: {e}")
        return ads

    async def _take_screenshot(self, url: str, country: str) -> bytes | None:
        # TODO: implement Playwright screenshot with geo-proxy
        # from playwright.async_api import async_playwright
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(proxy={"server": PROXY_URL})
        #     page = await browser.new_page(user_agent="mobile UA")
        #     await page.goto(url)
        #     screenshot = await page.screenshot(full_page=True)
        #     await browser.close()
        #     return screenshot
        return None
