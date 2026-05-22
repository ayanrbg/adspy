from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from adspy.api.auth import get_current_user

router = APIRouter(prefix="/api/billing")


class SubscribeRequest(BaseModel):
    plan: str  # "basic" / "pro" / "enterprise"
    payment_method: str = "stripe"  # "stripe" / "crypto"


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, user_id: str = Depends(get_current_user)):
    """Create or update subscription."""
    # TODO: integrate Stripe / crypto payment
    return {"status": "subscribed", "plan": req.plan, "user_id": user_id}


@router.get("/status")
async def billing_status(user_id: str = Depends(get_current_user)):
    """Get current billing status."""
    # TODO: fetch from DB
    return {"user_id": user_id, "plan": "free", "active": True}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    # TODO: verify signature and process event
    return {"status": "ok"}
