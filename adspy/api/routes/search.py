from fastapi import APIRouter, Depends

from adspy.api.auth import get_current_user
from adspy.storage.postgres import PostgresStorage
from adspy.storage.elastic import ElasticStorage

router = APIRouter(prefix="/api/ads")
db = PostgresStorage()
es = ElasticStorage()


@router.get("/search")
async def search_ads(
    country: str = "IN",
    niche: str = "gambling",
    min_days_active: int = 0,
    only_active: bool = True,
    has_video: bool | None = None,
    sort_by: str = "days_active",
    page: int = 1,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
):
    """Main search endpoint for affiliates."""
    results = await db.search_ads(
        country=country,
        niche=niche,
        min_days_active=min_days_active,
        only_active=only_active,
        has_video=has_video,
        sort_by=sort_by,
        page=page,
        limit=limit,
    )
    return {"data": results, "page": page, "limit": limit}


@router.get("/fulltext")
async def fulltext_search(
    q: str = "",
    country: str | None = None,
    niche: str | None = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
):
    """Full-text search via Elasticsearch."""
    results = await es.search(query=q, country=country, niche=niche, limit=limit)
    return {"data": results}


@router.get("/{ad_id}")
async def get_ad(ad_id: str, user_id: str = Depends(get_current_user)):
    ad = await db.get_ad(ad_id)
    if not ad:
        return {"error": "Ad not found"}, 404
    return ad
