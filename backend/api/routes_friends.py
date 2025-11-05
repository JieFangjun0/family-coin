# backend/api/routes_friends.py

from fastapi import APIRouter, HTTPException
from backend.db import queries_user
from backend.api.models import (
    FriendshipStatusResponse, MarketSignedRequest, SuccessResponse,
    FriendActionMessage, FriendRespondMessage, FriendListResponse,
    FriendRequestListResponse
)
from backend.api.dependencies import get_verified_message

router = APIRouter()

@router.get("/friends/status/{target_key}", response_model=FriendshipStatusResponse, tags=["Friends"])
def api_get_friendship_status(target_key: str, current_user_key: str):
    if not current_user_key or not target_key:
        raise HTTPException(status_code=400, detail="必须同时提供当前用户和目标用户的公钥")
    status_info = queries_user.get_friendship_status(current_user_key, target_key)
    return FriendshipStatusResponse(**status_info)


@router.post("/friends/request", response_model=SuccessResponse, tags=["Friends"])
def api_send_friend_request(request: MarketSignedRequest):
    message = get_verified_message(request, FriendActionMessage)
    success, detail = queries_user.send_friend_request(
        requester_key=message.owner_key,
        target_key=message.target_key
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)


@router.post("/friends/respond", response_model=SuccessResponse, tags=["Friends"])
def api_respond_to_friend_request(request: MarketSignedRequest):
    message = get_verified_message(request, FriendRespondMessage)
    success, detail = queries_user.respond_to_friend_request(
        responder_key=message.owner_key,
        requester_key=message.requester_key,
        accept=message.accept
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)


@router.post("/friends/delete", response_model=SuccessResponse, tags=["Friends"])
def api_delete_friend(request: MarketSignedRequest):
    message = get_verified_message(request, FriendActionMessage)
    success, detail = queries_user.delete_friend(
        deleter_key=message.owner_key,
        friend_to_delete_key=message.target_key
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)


@router.get("/friends/list", response_model=FriendListResponse, tags=["Friends"])
def api_get_friend_list(public_key: str):
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")
    friends = queries_user.get_friends(public_key)
    return FriendListResponse(friends=friends)


@router.get("/friends/requests", response_model=FriendRequestListResponse, tags=["Friends"])
def api_get_friend_requests(public_key: str):
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")
    requests = queries_user.get_friend_requests(public_key)
    return FriendRequestListResponse(requests=requests)