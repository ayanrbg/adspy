import asyncpg

from adspy.config.settings import DATABASE_URL
from adspy.models.ad import NormalizedAd


class PostgresStorage:
    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(DATABASE_URL)
        return self._pool

    async def upsert_ad(self, ad: NormalizedAd) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ads (
                    id, source, page_id, page_name, body, title,
                    screenshot_url, image_urls, video_urls, has_video,
                    country, niche, niche_confidence,
                    start_date, stop_date, is_active, days_active,
                    impressions_min, impressions_max
                ) VALUES (
                    $1, $2, $3, $4, $5, $6,
                    $7, $8::jsonb, $9::jsonb, $10,
                    $11, $12, $13,
                    $14, $15, $16, $17,
                    $18, $19
                )
                ON CONFLICT (id) DO UPDATE SET
                    stop_date = EXCLUDED.stop_date,
                    is_active = EXCLUDED.is_active,
                    days_active = EXCLUDED.days_active,
                    impressions_min = EXCLUDED.impressions_min,
                    impressions_max = EXCLUDED.impressions_max,
                    screenshot_url = COALESCE(EXCLUDED.screenshot_url, ads.screenshot_url),
                    niche = CASE WHEN EXCLUDED.niche_confidence > ads.niche_confidence
                                 THEN EXCLUDED.niche ELSE ads.niche END,
                    niche_confidence = GREATEST(EXCLUDED.niche_confidence, ads.niche_confidence),
                    updated_at = NOW()
                """,
                ad.id, ad.source, ad.page_id, ad.page_name, ad.body, ad.title,
                ad.screenshot_url,
                str(ad.image_urls) if ad.image_urls else "[]",
                str(ad.video_urls) if ad.video_urls else "[]",
                ad.has_video,
                ad.country, ad.niche, ad.niche_confidence,
                ad.start_date, ad.stop_date, ad.is_active, ad.days_active,
                ad.impressions_min, ad.impressions_max,
            )

    async def get_ad(self, ad_id: str) -> dict | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM ads WHERE id = $1", ad_id)
            return dict(row) if row else None

    async def get_page_ads(self, page_id: str, limit: int = 20) -> list[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM ads WHERE page_id = $1 ORDER BY start_date DESC LIMIT $2",
                page_id, limit,
            )
            return [dict(r) for r in rows]

    async def search_ads(
        self,
        country: str = "IN",
        niche: str = "gambling",
        min_days_active: int = 0,
        only_active: bool = True,
        has_video: bool | None = None,
        sort_by: str = "days_active",
        page: int = 1,
        limit: int = 20,
    ) -> list[dict]:
        pool = await self._get_pool()
        conditions = ["country = $1", "niche = $2", "COALESCE(days_active, 0) >= $3"]
        params: list = [country, niche, min_days_active]
        idx = 4

        if only_active:
            conditions.append("is_active = TRUE")

        if has_video is not None:
            conditions.append(f"has_video = ${idx}")
            params.append(has_video)
            idx += 1

        allowed_sort = {"days_active", "start_date", "impressions_max", "created_at"}
        sort_col = sort_by if sort_by in allowed_sort else "days_active"

        offset = (page - 1) * limit
        params.extend([limit, offset])

        query = f"""
            SELECT * FROM ads
            WHERE {' AND '.join(conditions)}
            ORDER BY {sort_col} DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]
