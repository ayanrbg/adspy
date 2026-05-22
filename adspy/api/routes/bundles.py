from fastapi import APIRouter, Depends

from adspy.api.auth import get_current_user
from adspy.storage.postgres import PostgresStorage
from adspy.storage.elastic import ElasticStorage

router = APIRouter(prefix="/api/ads")
db = PostgresStorage()
es = ElasticStorage()


@router.get("/{ad_id}/bundle")
async def get_bundle(ad_id: str, user_id: str = Depends(get_current_user)):
    """Bundle: the ad + other ads from the same page + similar ads."""
    ad = await db.get_ad(ad_id)
    if not ad:
        return {"error": "Ad not found"}, 404

    days_active = ad.get("days_active") or 0
    strength = (
        "strong" if days_active >= 30 else
        "medium" if days_active >= 14 else
        "new"
    )

    page_other_ads = await db.get_page_ads(ad["page_id"], limit=20) if ad.get("page_id") else []
    similar_ads = await es.more_like_this(ad_id, limit=12)

    return {
        "ad": ad,
        "strength": strength,
        "days_active": days_active,
        "is_active": ad.get("is_active", False),
        "page_other_ads": page_other_ads,
        "similar_ads": similar_ads,
    }


@router.get("/pages/{page_id}/ads")
async def get_page_ads(page_id: str, limit: int = 50, user_id: str = Depends(get_current_user)):
    """All ad history for a specific advertiser."""
    ads = await db.get_page_ads(page_id, limit=limit)
    return {"data": ads}
