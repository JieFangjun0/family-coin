# backend/api/routes_user.py

from fastapi import APIRouter, HTTPException
from backend.db import queries_user
from backend.api.models import (
    UserLoginRequest, UserLoginResponse, UserRegisterRequest, UserRegisterResponse,
    UserProfileResponse, MarketSignedRequest, ProfileUpdateRequest, SuccessResponse,
    TransactionRequest, TransactionMessage, BalanceResponse, HistoryResponse,
    UserDetailsResponse, UserListResponse, InvitationCodeResponse,
    MessageGenerateCode, InvitationCodeListResponse
)
from backend.api.dependencies import get_verified_message
from backend.db.queries_user import get_user_details as db_get_user_details # 避免命名冲突
from backend.db.queries_user import get_friends as db_get_friends
from backend.db.queries_user import get_all_active_users as db_get_all_active_users
import json

router = APIRouter()

@router.post("/login", response_model=UserLoginResponse, tags=["User"])
def api_login(request: UserLoginRequest):
    if not request.username_or_uid or not request.password:
        raise HTTPException(status_code=400, detail="用户名/UID和密码不能为空")

    success, detail, user_data = queries_user.authenticate_user(
        request.username_or_uid, request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=detail)

    return UserLoginResponse(message=detail, **user_data)


@router.post("/register", response_model=UserRegisterResponse, tags=["User"])
def api_register_user(request: UserRegisterRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要6个字符")
        
    if not request.invitation_code:
        raise HTTPException(status_code=400, detail="必须提供邀请码")
        
    success, detail, new_user_info = queries_user.register_user(
        username=request.username, 
        password=request.password,
        invitation_code=request.invitation_code.upper()
    )
    
    if not success:
        raise HTTPException(status_code=409, detail=detail)
        
    return UserRegisterResponse(**new_user_info)

@router.get("/profile/{uid_or_username}", response_model=UserProfileResponse, tags=["User"])
def api_get_user_profile(uid_or_username: str):
    profile_data = queries_user.get_user_profile(uid_or_username)
    if not profile_data:
        raise HTTPException(status_code=404, detail="未找到该用户")
    return UserProfileResponse(**profile_data)

@router.post("/profile/update", response_model=SuccessResponse, tags=["User"])
def api_update_user_profile(request: MarketSignedRequest):
    message = get_verified_message(request, ProfileUpdateRequest)
    
    success, detail = queries_user.update_user_profile(
        public_key=message.owner_key,
        signature=message.signature,
        displayed_nfts=message.displayed_nfts
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    
    return SuccessResponse(detail=detail)

@router.post("/transaction", response_model=SuccessResponse, tags=["User"])
def api_create_transaction(request: TransactionRequest):
    try:
        message = json.loads(request.message_json)
        msg_model = TransactionMessage(**message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的交易消息体: {e}")

    success, detail = queries_user.process_transaction(
        from_key=msg_model.from_key,
        to_key=msg_model.to_key,
        amount=msg_model.amount,
        message_json=request.message_json,
        signature=request.signature,
        note=msg_model.note
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
        
    return SuccessResponse(detail=detail)

@router.get("/balance", response_model=BalanceResponse, tags=["User"])
def api_get_balance(public_key: str):
    balance = queries_user.get_balance(public_key)
    return BalanceResponse(public_key=public_key, balance=balance)

@router.get("/history", response_model=HistoryResponse, tags=["User"])
def api_get_history(public_key: str):
    history = queries_user.get_transaction_history(public_key)
    return HistoryResponse(transactions=history)

@router.get("/user/details", response_model=UserDetailsResponse, tags=["User"])
def api_get_user_details(public_key: str):
    details = db_get_user_details(public_key)
    if not details:
        raise HTTPException(status_code=404, detail="未找到用户或用户已被禁用")
    return UserDetailsResponse(**details)

@router.get("/users/list", response_model=UserListResponse, tags=["User"])
def api_get_all_users(public_key: str):
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")

    user_details = db_get_user_details(public_key)
    if not user_details:
        raise HTTPException(status_code=404, detail="请求用户不存在")

    if user_details.get('invited_by') == 'GENESIS':
        users = db_get_all_active_users()
    else:
        users = db_get_friends(public_key)
        
    return UserListResponse(users=users)

@router.post("/user/generate_invitation", response_model=InvitationCodeResponse, tags=["User"])
def api_generate_invitation(request: MarketSignedRequest):
    message = get_verified_message(request, MessageGenerateCode)
    
    success, code_or_error = queries_user.generate_invitation_code(message.owner_key)
    
    if not success:
        raise HTTPException(status_code=400, detail=code_or_error)
        
    return InvitationCodeResponse(code=code_or_error)

@router.get("/user/my_invitations", response_model=InvitationCodeListResponse, tags=["User"])
def api_get_my_invitations(public_key: str):
    if not public_key:
         raise HTTPException(status_code=400, detail="必须提供有效的公钥")
         
    codes = queries_user.get_my_invitation_codes(public_key)
    return InvitationCodeListResponse(codes=codes)