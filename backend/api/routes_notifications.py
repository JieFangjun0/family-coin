# backend/api/routes_notifications.py

from fastapi import APIRouter, HTTPException
from backend.db import queries_notifications
from backend.api.models import (
    NotificationListResponse, SuccessResponse,
    MarketSignedRequest, MarketActionMessage 
)
from backend.api.dependencies import get_verified_message

router = APIRouter()

@router.get("/notifications/my", response_model=NotificationListResponse, tags=["Notifications"])
def api_get_my_notifications(public_key: str):
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")
    
    data = queries_notifications.get_notifications_by_user(public_key)
    return NotificationListResponse(**data)

@router.post("/notifications/mark_read", response_model=SuccessResponse, tags=["Notifications"])
def api_mark_notification_as_read(request: MarketSignedRequest):
    # 重用 MarketActionMessage, 将 listing_id 视为 notif_id
    message = get_verified_message(request, MarketActionMessage) 
    notif_id = message.listing_id 
    user_key = message.owner_key

    success, detail = queries_notifications.mark_notification_as_read(notif_id, user_key)

    if not success and detail != "通知不存在或已读":
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail="通知状态已更新")