from fastapi import APIRouter, Depends
from pydantic import BaseModel

from adspy.api.auth import get_current_user

router = APIRouter(prefix="/api/alerts")


class AlertCreate(BaseModel):
    country: str
    niche: str
    keywords: list[str] = []
    telegram_chat_id: str | None = None


@router.post("")
async def create_alert(alert: AlertCreate, user_id: str = Depends(get_current_user)):
    """Subscribe to alerts for new ads in a niche/geo."""
    # TODO: store alert in DB and set up notification worker
    return {"status": "created", "alert": alert.model_dump(), "user_id": user_id}


@router.get("")
async def list_alerts(user_id: str = Depends(get_current_user)):
    """List user's active alerts."""
    # TODO: fetch from DB
    return {"data": []}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, user_id: str = Depends(get_current_user)):
    """Delete an alert."""
    # TODO: delete from DB
    return {"status": "deleted", "alert_id": alert_id}
