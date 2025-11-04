# backend/main.py

import time
import json
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Dict,Any
import uvicorn
import os
import threading
from backend.bots import bot_runner, BOT_LOGIC_MAP
from werkzeug.security import generate_password_hash

from shared.crypto_utils import (
    generate_key_pair, 
    verify_signature
)
from backend import ledger
from backend.nft_logic import get_handler, get_available_nft_types, NFT_HANDLERS
from backend.nft_admin_utils import get_mint_info_for_type
# --- Pydantic 模型定义 ---
class UserRegisterRequest(BaseModel):
    username: str
    password: str  # <--- 修改
    invitation_code: str

class UserRegisterResponse(BaseModel):
    uid: str # <--- 新增
    username: str
    public_key: str
    # private_key 字段被移除，不再在注册时返回

class UserLoginRequest(BaseModel): # <--- 新增
    username_or_uid: str
    password: str

class UserLoginResponse(BaseModel): # <--- 新增
    message: str
    public_key: str
    private_key: str # 只在登录成功时返回给用户
    username: str
    uid: str

class FriendActionMessage(BaseModel): # <--- 新增
    owner_key: str
    target_key: str
    timestamp: float

class FriendRespondMessage(BaseModel): # <--- 新增
    owner_key: str
    requester_key: str
    accept: bool
    timestamp: float

class FriendInfo(BaseModel): # <--- 新增
    username: str
    public_key: str
    uid: str

class FriendListResponse(BaseModel): # <--- 新增
    friends: List[FriendInfo]

class FriendRequestInfo(BaseModel): # <--- 新增
    username: str
    public_key: str
    uid: str
    created_at: str

class FriendRequestListResponse(BaseModel): # <--- 新增
    requests: List[FriendRequestInfo]

class FriendshipStatusResponse(BaseModel): # <--- 新增
    status: str # 'NONE', 'PENDING', 'ACCEPTED', 'SELF'
    action_user_key: Optional[str] = None
    
class TransactionMessage(BaseModel):
    from_key: str
    to_key: str
    amount: float
    timestamp: float
    note: Optional[str] = None

class TransactionRequest(BaseModel):
    message_json: str 
    signature: str

class BalanceResponse(BaseModel):
    public_key: str
    balance: float

class HistoryResponse(BaseModel):
    transactions: List[dict]
    
class UserDetailsResponse(BaseModel):
    public_key: str
    username: str
    created_at: float
    invitation_quota: int
    invited_by: Optional[str] = None
    inviter_username: Optional[str] = None
    tx_count: int
    is_active: bool

class UserInfo(BaseModel):
    username: str
    public_key: str
    uid: str  # <--- BUG 修正：添加 uid 字段

class UserListResponse(BaseModel):
    users: List[UserInfo]

class ErrorResponse(BaseModel):
    detail: str
    
class SuccessResponse(BaseModel):
    detail: str

class AdminMintNFTRequest(BaseModel):
    to_key: str
    nft_type: str
    data: dict

class NFTActionMessage(BaseModel):
    owner_key: str
    nft_id: str
    action: str
    action_data: Optional[dict] = None
    timestamp: float

class NFTActionRequest(BaseModel):
    message_json: str
    signature: str

class NFTResponse(BaseModel):
    nft_id: str
    owner_key: str
    nft_type: str
    data: dict
    created_at: float
    status: str

class NFTListResponse(BaseModel):
    nfts: List[NFTResponse]
    
class AdminIssueRequest(BaseModel):
    to_key: str 
    amount: float
    note: Optional[str] = None
    
class AdminMultiIssueRequest(BaseModel):
    targets: List[dict] 
    note: Optional[str] = None

class AdminBurnRequest(BaseModel):
    from_key: str 
    amount: float
    note: Optional[str] = None

class AdminDeleteUserRequest(BaseModel):
    public_key: str

class AdminPurgeUserRequest(BaseModel):
    public_key: str

class AdminSetQuotaRequest(BaseModel):
    key: str 
    value: str

class AdminAdjustUserQuotaRequest(BaseModel):
    public_key: str
    new_quota: int
    
class AdminSetUserActiveStatusRequest(BaseModel):
    public_key: str
    is_active: bool

class AdminBalancesResponse(BaseModel):
    balances: List[dict]

class AdminResetPasswordRequest(BaseModel): # 新增
    public_key: str
    new_password: str
    
class InvitationCodeResponse(BaseModel):
    code: str

class InvitationCodeListResponse(BaseModel):
    codes: List[dict]

class MessageGenerateCode(BaseModel):
    owner_key: str
    timestamp: float

class GenesisRegisterRequest(BaseModel):
    username: str
    password: str # <--- 修改
    genesis_password: str

class GenesisRegisterResponse(BaseModel): # <--- 新增
    uid: str
    username: str
    public_key: str
    private_key: str
    
class UserProfileResponse(BaseModel): # <--- 新增
    uid: str
    username: str
    public_key: str
    created_at: float
    signature: Optional[str] = None
    displayed_nfts_details: List[dict] = []

class ProfileUpdateRequest(BaseModel): # <--- 新增
    owner_key: str # 用于验证
    timestamp: float
    signature: Optional[str] = None
    displayed_nfts: Optional[List[str]] = None

class MarketSignedRequest(BaseModel):
    message_json: str
    signature: str

class MarketListingRequest(BaseModel):
    owner_key: str
    timestamp: float
    listing_type: str
    nft_id: Optional[str] = None
    nft_type: str
    description: str
    price: float
    auction_hours: Optional[float] = None

class MarketActionMessage(BaseModel):
    owner_key: str
    listing_id: str
    timestamp: float

class MarketBidRequest(BaseModel):
    owner_key: str
    timestamp: float
    listing_id: str
    amount: float
class BidHistoryResponse(BaseModel):
    bid_amount: float
    created_at: float
    bidder_username: str
    bidder_uid: str
class MarketOfferRequest(BaseModel):
    owner_key: str
    timestamp: float
    listing_id: str
    offered_nft_id: str

class MarketOfferResponseRequest(BaseModel):
    owner_key: str
    timestamp: float
    offer_id: str
    accept: bool

class ShopCreateNftRequest(BaseModel):
    owner_key: str
    timestamp: float
    nft_type: str
    cost: float
    data: dict

class ShopActionRequest(BaseModel):
    owner_key: str
    timestamp: float
    nft_type: str
    cost: float
    data: dict
class BotGlobalSettings(BaseModel):
    bot_system_enabled: bool
    bot_check_interval_seconds: int

class BotTypeConfig(BaseModel):
    count: int
    action_probability: float

class FullBotConfigRequest(BaseModel):
    global_settings: BotGlobalSettings
    bot_types: Dict[str, BotTypeConfig]
# --- 管理员认证 ---
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "CHANGE_ME_IN_ENV")
GENESIS_PASSWORD = os.getenv("GENESIS_PASSWORD", "CHANGE_ME_IN_ENV")

def verify_admin(x_admin_secret: str = Header(None)):
    if not x_admin_secret or x_admin_secret != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="未授权的管理员访问")
    return True

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="FamilyCoin API (V0.3.0 - Market System)",
    description="一个用于家庭和朋友的中心化玩具加密货币API (带邀请、市场和NFT框架)",
    version="0.3.0"
)

@app.on_event("startup")
def on_startup():
    print("正在启动 API ... 初始化数据库...")
    ledger.init_db()
    
    print("--- API 启动：正在启动后台机器人调度器线程... ---")
    bot_thread = threading.Thread(
        target=bot_runner.run_bot_loop, 
        daemon=True 
    )
    bot_thread.start()
    print("--- API 启动：机器人线程已启动。 ---")

# --- 系统状态接口 ---
@app.get("/status", tags=["System"])
def api_get_system_status():
    user_count = ledger.count_users()
    return {"needs_setup": user_count == 0}

@app.post("/genesis_register", response_model=GenesisRegisterResponse, tags=["System"])
def api_genesis_register(request: GenesisRegisterRequest):
    if ledger.count_users() > 0:
        raise HTTPException(status_code=403, detail="系统已经初始化，无法注册创世用户。")

    if request.genesis_password != GENESIS_PASSWORD:
        raise HTTPException(status_code=403, detail="创世密钥错误。")
        
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="用户密码至少需要6个字符")

    success, detail, user_data = ledger.create_genesis_user(
        username=request.username, 
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=500, detail=detail)

    return GenesisRegisterResponse(**user_data)
# --- 辅助函数：验证签名 ---
def get_verified_message(request: MarketSignedRequest, model: BaseModel):
    try:
        message_dict = json.loads(request.message_json)
        message = model(**message_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的消息体: {e}")
        
    if not hasattr(message, 'owner_key'):
        raise HTTPException(status_code=400, detail="消息体中缺少'owner_key'字段")
        
    if not verify_signature(message.owner_key, message_dict, request.signature):
        raise HTTPException(status_code=403, detail="签名无效")
        
    if (time.time() - message.timestamp) > 300:
        raise HTTPException(status_code=400, detail="请求已过期")
        
    return message

def get_verified_nft_action_message(request: NFTActionRequest, model: BaseModel):
    try:
        message_dict = json.loads(request.message_json)
        message = model(**message_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的消息体: {e}")
        
    if not hasattr(message, 'owner_key'):
        raise HTTPException(status_code=400, detail="消息体中缺少'owner_key'字段")
        
    if not verify_signature(message.owner_key, message_dict, request.signature):
        raise HTTPException(status_code=403, detail="签名无效")
        
    if (time.time() - message.timestamp) > 300:
        raise HTTPException(status_code=400, detail="请求已过期")
        
    return message

# --- 公共接口 ---
@app.post("/login", response_model=UserLoginResponse, tags=["User"])
def api_login(request: UserLoginRequest):
    """(新增) 用户通过用户名/UID和密码登录。"""
    if not request.username_or_uid or not request.password:
        raise HTTPException(status_code=400, detail="用户名/UID和密码不能为空")

    success, detail, user_data = ledger.authenticate_user(
        request.username_or_uid, request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=detail)

    return UserLoginResponse(message=detail, **user_data)


@app.post("/register", response_model=UserRegisterResponse, tags=["User"])
def api_register_user(request: UserRegisterRequest): # <--- 这里是关键修改点
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要6个字符")
        
    if not request.invitation_code:
        raise HTTPException(status_code=400, detail="必须提供邀请码")
        
    success, detail, new_user_info = ledger.register_user(
        username=request.username, 
        password=request.password,
        invitation_code=request.invitation_code.upper()
    )
    
    if not success:
        raise HTTPException(status_code=409, detail=detail)
        
    return UserRegisterResponse(**new_user_info)

@app.get("/profile/{uid_or_username}", response_model=UserProfileResponse, tags=["User"])
def api_get_user_profile(uid_or_username: str):
    """(新增) 获取用户的公开个人主页。"""
    profile_data = ledger.get_user_profile(uid_or_username)
    if not profile_data:
        raise HTTPException(status_code=404, detail="未找到该用户")
    return UserProfileResponse(**profile_data)

@app.post("/profile/update", response_model=SuccessResponse, tags=["User"])
def api_update_user_profile(request: MarketSignedRequest):
    """(新增) 用户更新自己的个人主页。"""
    message = get_verified_message(request, ProfileUpdateRequest)
    
    success, detail = ledger.update_user_profile(
        public_key=message.owner_key,
        signature=message.signature,
        displayed_nfts=message.displayed_nfts
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    
    return SuccessResponse(detail=detail)
@app.post("/transaction", response_model=SuccessResponse, tags=["User"])
def api_create_transaction(request: TransactionRequest):
    try:
        message = json.loads(request.message_json)
        msg_model = TransactionMessage(**message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的交易消息体: {e}")

    success, detail = ledger.process_transaction(
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

@app.get("/balance", response_model=BalanceResponse, tags=["User"])
def api_get_balance(public_key: str):
    balance = ledger.get_balance(public_key)
    return BalanceResponse(public_key=public_key, balance=balance)

@app.get("/history", response_model=HistoryResponse, tags=["User"])
def api_get_history(public_key: str):
    history = ledger.get_transaction_history(public_key)
    return HistoryResponse(transactions=history)

@app.get("/user/details", response_model=UserDetailsResponse, tags=["User"])
def api_get_user_details(public_key: str):
    details = ledger.get_user_details(public_key)
    if not details:
        raise HTTPException(status_code=404, detail="未找到用户或用户已被禁用")
    return UserDetailsResponse(**details)

@app.get("/users/list", response_model=UserListResponse, tags=["User"])
def api_get_all_users(public_key: str):
    """
    获取用户列表。
    - 如果请求者是管理员(创世用户)，返回所有活跃用户。
    - 如果是普通用户，返回其好友列表。
    """
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")

    # 检查用户是否为管理员
    user_details = ledger.get_user_details(public_key)
    if not user_details:
        raise HTTPException(status_code=404, detail="请求用户不存在")

    if user_details.get('invited_by') == 'GENESIS':
        # 管理员获取所有用户
        users = ledger.get_all_active_users()
    else:
        # 普通用户获取好友
        users = ledger.get_friends(public_key)
        
    return UserListResponse(users=users)

@app.post("/user/generate_invitation", response_model=InvitationCodeResponse, tags=["User"])
def api_generate_invitation(request: MarketSignedRequest):
    message = get_verified_message(request, MessageGenerateCode)
    
    success, code_or_error = ledger.generate_invitation_code(message.owner_key)
    
    if not success:
        raise HTTPException(status_code=400, detail=code_or_error)
        
    return InvitationCodeResponse(code=code_or_error)

@app.get("/user/my_invitations", response_model=InvitationCodeListResponse, tags=["User"])
def api_get_my_invitations(public_key: str):
    # --- 将这部分修改为如下 ---
    if not public_key:
         raise HTTPException(status_code=400, detail="必须提供有效的公钥")
    # --- 修改结束 ---
         
    codes = ledger.get_my_invitation_codes(public_key)
    return InvitationCodeListResponse(codes=codes)

# ==============================================================================
# --- 新增: 好友系统接口 ---
# ==============================================================================
@app.get("/friends/status/{target_key}", response_model=FriendshipStatusResponse, tags=["Friends"])
def api_get_friendship_status(target_key: str, current_user_key: str):
    """检查当前用户与目标用户之间的好友关系状态。"""
    if not current_user_key or not target_key:
        raise HTTPException(status_code=400, detail="必须同时提供当前用户和目标用户的公钥")
    status_info = ledger.get_friendship_status(current_user_key, target_key)
    return FriendshipStatusResponse(**status_info)


@app.post("/friends/request", response_model=SuccessResponse, tags=["Friends"])
def api_send_friend_request(request: MarketSignedRequest):
    """发送好友请求。"""
    message = get_verified_message(request, FriendActionMessage)
    success, detail = ledger.send_friend_request(
        requester_key=message.owner_key,
        target_key=message.target_key
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)


@app.post("/friends/respond", response_model=SuccessResponse, tags=["Friends"])
def api_respond_to_friend_request(request: MarketSignedRequest):
    """回应好友请求 (接受/拒绝)。"""
    message = get_verified_message(request, FriendRespondMessage)
    success, detail = ledger.respond_to_friend_request(
        responder_key=message.owner_key,
        requester_key=message.requester_key,
        accept=message.accept
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)


@app.post("/friends/delete", response_model=SuccessResponse, tags=["Friends"])
def api_delete_friend(request: MarketSignedRequest):
    """删除好友。"""
    message = get_verified_message(request, FriendActionMessage)
    success, detail = ledger.delete_friend(
        deleter_key=message.owner_key,
        friend_to_delete_key=message.target_key
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)


@app.get("/friends/list", response_model=FriendListResponse, tags=["Friends"])
def api_get_friend_list(public_key: str):
    """获取我的好友列表。"""
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")
    friends = ledger.get_friends(public_key)
    return FriendListResponse(friends=friends)


@app.get("/friends/requests", response_model=FriendRequestListResponse, tags=["Friends"])
def api_get_friend_requests(public_key: str):
    """获取我收到的待处理好友请求。"""
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供 public_key")
    requests = ledger.get_friend_requests(public_key)
    return FriendRequestListResponse(requests=requests)
# --- NFT 接口 ---
@app.get("/nfts/display_names", tags=["NFT"])
def api_get_nft_display_names():
    """获取所有 NFT 类型的 KEY -> 中文显示名称 映射。"""
    names = {}
    for nft_type, handler_class in NFT_HANDLERS.items():
        names[nft_type] = handler_class.get_display_name()
    return names
@app.get("/nfts/my", response_model=NFTListResponse, tags=["NFT"])
def api_get_my_nfts(public_key: str):
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供公钥")
    nfts = ledger.get_nfts_by_owner(public_key)
    return NFTListResponse(nfts=nfts)

@app.get("/nfts/{nft_id}", response_model=NFTResponse, tags=["NFT"])
def api_get_nft_details(nft_id: str):
    nft = ledger.get_nft_by_id(nft_id)
    if not nft:
        raise HTTPException(status_code=404, detail="未找到该 NFT")
    return NFTResponse(**nft)

# <<< --- 关键修正点：确保这个路由装饰器是 @app.post --- >>>
@app.post("/nfts/action", response_model=SuccessResponse, tags=["NFT"])
def api_perform_nft_action(request: NFTActionRequest):
    message = get_verified_nft_action_message(request, NFTActionMessage)
    
    nft = ledger.get_nft_by_id(message.nft_id)
    if not nft or nft['owner_key'] != message.owner_key:
        raise HTTPException(status_code=404, detail="未找到 NFT 或你不是所有者")

    if nft.get('status') != 'ACTIVE':
        raise HTTPException(status_code=400, detail="该 NFT 当前不是活跃状态，无法执行操作")

    handler = get_handler(nft['nft_type'])
    if not handler:
        raise HTTPException(status_code=501, detail=f"不支持的 NFT 类型: {nft['nft_type']}")

    is_valid, reason = handler.validate_action(nft, message.action, message.action_data, message.owner_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    success, detail, updated_data = handler.perform_action(nft, message.action, message.action_data, message.owner_key)
    if not success:
        raise HTTPException(status_code=500, detail=detail)

    new_status = updated_data.pop('__new_status__', None)

    update_success, update_detail = ledger.update_nft(message.nft_id, updated_data, new_status)
    if not update_success:
        raise HTTPException(status_code=500, detail=f"执行成功但数据更新失败: {update_detail}")

    return SuccessResponse(detail=detail)

# --- 市场接口 ---
@app.get("/market/listings", tags=["Market"])
def api_get_market_listings(listing_type: str, exclude_owner: Optional[str] = None):
    items = ledger.get_market_listings(listing_type=listing_type, exclude_owner=exclude_owner)
    
    # <<< 核心修改：为每个挂单添加动态描述 >>>
    for item in items:
        # 只有挂售和拍卖的才有具体的 nft_data
        if item.get('nft_data'):
            nft_type = item.get('nft_type')
            handler = get_handler(nft_type)
            if handler:
                # 构造一个临时的 nft 对象以调用方法
                temp_nft_for_desc = {
                    "data": item['nft_data'],
                    "nft_type": nft_type
                }
                item['trade_description'] = handler.get_trade_description(temp_nft_for_desc)
            else:
                item['trade_description'] = item['description'] # Fallback
        else:
            item['trade_description'] = item['description'] # 求购单直接使用自身描述

    return {"listings": items}

@app.get("/market/my_activity", tags=["Market"])
def api_get_my_activity(public_key: str):
    activity = ledger.get_my_market_activity(public_key)
    return activity

@app.get("/market/offers", tags=["Market"])
def api_get_offers(listing_id: str):
    offers = ledger.get_offers_for_listing(listing_id)
    for offer in offers:
        if offer.get('nft_data'):
            nft_type = offer.get('nft_type')
            handler = get_handler(nft_type)
            if handler:
                # 构造一个临时的 nft 对象以调用方法
                temp_nft_for_desc = {
                    "data": offer['nft_data'],
                    "nft_type": nft_type
                }
                offer['trade_description'] = handler.get_trade_description(temp_nft_for_desc)
            else:
                # Fallback to the name in data or the ID
                offer['trade_description'] = offer['nft_data'].get('name', offer['offered_nft_id'][:8])
        else:
            offer['trade_description'] = "未知NFT"
            
    return {"offers": offers}

# <<< --- 新增 API 终端 --- >>>
@app.get("/market/listings/{listing_id}/bids", response_model=List[BidHistoryResponse], tags=["Market"])
def api_get_bid_history(listing_id: str):
    """(新增) 获取一个拍卖单的出价历史。"""
    bids = ledger.get_bids_for_listing(listing_id)
    return bids
# <<< --- 新增代码结束 --- >>>
@app.post("/market/create_listing", response_model=SuccessResponse, tags=["Market"])
def api_create_listing(request: MarketSignedRequest):
    message = get_verified_message(request, MarketListingRequest)
    success, detail = ledger.create_market_listing(
        lister_key=message.owner_key,
        listing_type=message.listing_type,
        nft_id=message.nft_id,
        nft_type=message.nft_type,
        description=message.description,
        price=message.price,
        auction_hours=message.auction_hours
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/market/cancel_listing", response_model=SuccessResponse, tags=["Market"])
def api_cancel_listing(request: MarketSignedRequest):
    message = get_verified_message(request, MarketActionMessage)
    success, detail = ledger.cancel_market_listing(
        lister_key=message.owner_key,
        listing_id=message.listing_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/market/buy", response_model=SuccessResponse, tags=["Market"])
def api_buy_nft(request: MarketSignedRequest):
    message = get_verified_message(request, MarketActionMessage)
    success, detail = ledger.execute_sale(
        buyer_key=message.owner_key,
        listing_id=message.listing_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/market/place_bid", response_model=SuccessResponse, tags=["Market"])
def api_place_bid(request: MarketSignedRequest):
    message = get_verified_message(request, MarketBidRequest)
    success, detail = ledger.place_auction_bid(
        bidder_key=message.owner_key,
        listing_id=message.listing_id,
        bid_amount=message.amount
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/market/make_offer", response_model=SuccessResponse, tags=["Market"])
def api_make_offer(request: MarketSignedRequest):
    message = get_verified_message(request, MarketOfferRequest)
    success, detail = ledger.make_seek_offer(
        offerer_key=message.owner_key,
        listing_id=message.listing_id,
        offered_nft_id=message.offered_nft_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/market/respond_offer", response_model=SuccessResponse, tags=["Market"])
def api_respond_offer(request: MarketSignedRequest):
    message = get_verified_message(request, MarketOfferResponseRequest)
    success, detail = ledger.respond_to_seek_offer(
        seeker_key=message.owner_key,
        offer_id=message.offer_id,
        accept=message.accept
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.get("/market/creatable_nfts", tags=["Market"])
def api_get_creatable_nfts():
    configs = {}
    for nft_type, handler_class in NFT_HANDLERS.items():
        config = handler_class.get_shop_config()
        if config.get("creatable"):
            configs[nft_type] = config
    return configs

@app.post("/market/create_nft", response_model=SuccessResponse, tags=["Market"])
def api_create_nft_from_shop(request: MarketSignedRequest):
    message = get_verified_message(request, ShopCreateNftRequest)
    
    handler = get_handler(message.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail="无效的NFT类型")
    
    config = handler.get_shop_config()
    if not config.get("creatable") or config.get("cost") != message.cost:
        raise HTTPException(status_code=400, detail="NFT创建配置不匹配或该NFT不可创建")

    # <<< --- BUG修复 #3：预先检查余额 --- >>>
    if ledger.get_balance(message.owner_key) < message.cost:
        raise HTTPException(status_code=400, detail="你的余额不足以支付铸造成本")
    # <<< --- 修复结束 --- >>>

    with ledger.LEDGER_LOCK, ledger.get_db_connection() as conn:
        # 扣款现在应该总是成功的
        success, detail = ledger._create_system_transaction(message.owner_key, ledger.BURN_ACCOUNT, message.cost, f"商店铸造NFT: {message.nft_type}", conn)
        if not success:
            conn.rollback()
            # 这种情况理论上不应发生，但作为保险
            raise HTTPException(status_code=500, detail=f"支付失败: {detail}")
        
        user_details = ledger.get_user_details(message.owner_key, conn)
        if not user_details:
            conn.rollback()
            raise HTTPException(status_code=404, detail="无法找到铸造者信息")

        success, detail, db_data = handler.mint(message.owner_key, message.data, owner_username=user_details.get('username'))
        if not success:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"铸造逻辑失败: {detail}")

        success, detail, nft_id = ledger.mint_nft(message.owner_key, message.nft_type, db_data, conn)
        if not success:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"数据库写入失败: {detail}")

        conn.commit()

    return SuccessResponse(detail=f"铸造成功！你获得了新的 {config.get('name', 'NFT')}!")
    
@app.post("/market/shop_action", response_model=SuccessResponse, tags=["Market"])
def api_perform_shop_action(request: MarketSignedRequest):
    message = get_verified_message(request, ShopActionRequest)

    handler = get_handler(message.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail="无效的NFT类型")

    config = handler.get_shop_config()
    if not config.get("creatable") or config.get("cost") != message.cost:
        raise HTTPException(status_code=400, detail="商店配置不匹配或该物品不可用")

    # <<< --- BUG修复 #3：预先检查余额 --- >>>
    if ledger.get_balance(message.owner_key) < message.cost:
        raise HTTPException(status_code=400, detail="你的余额不足以支付此操作的费用")
    # <<< --- 修复结束 --- >>>

    with ledger.LEDGER_LOCK, ledger.get_db_connection() as conn:
        # 1. 扣款
        success, detail = ledger._create_system_transaction(
            message.owner_key,
            ledger.BURN_ACCOUNT,
            message.cost,
            f"执行商店动作: {config.get('name', message.nft_type)}",
            conn
        )
        if not success:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"支付失败: {detail}")

        # 2. 执行插件定义的动作
        user_details = ledger.get_user_details(message.owner_key, conn)
        username = user_details.get('username') if user_details else "未知用户"

        success, detail, new_nft_id = handler.execute_shop_action(message.owner_key, username, message.data, conn)

        if not success:
            conn.rollback()
            raise HTTPException(status_code=400, detail=detail)

        conn.commit()
        return SuccessResponse(detail=detail)

# ==============================================================================
# --- (新增) 机器人管理 API ---
# ==============================================================================
@app.get("/admin/bots/config", tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
async def api_admin_get_bot_config():
    """
    (重构) 获取当前机器人系统的配置 (动态发现)。
    """
    config = ledger.get_bot_config()
    
    # 1. 分离全局配置
    global_config = {
        "bot_system_enabled": config.get("bot_system_enabled", False),
        "bot_check_interval_seconds": config.get("bot_check_interval_seconds", 30)
    }
    
    # 2. 动态构建机器人类型配置
    bot_type_configs = {}
    
    # 3. 迭代所有在后端注册的机器人
    for bot_name, bot_class in BOT_LOGIC_MAP.items():
        # 从数据库加载配置，或使用默认值
        db_config = config.get(bot_name, {"count": 0, "action_probability": 0.1})
        
        # 自动提取描述
        description = "该机器人没有提供描述。"
        if bot_class.__doc__:
            description = bot_class.__doc__.strip().split('\n')[0] # 取文档字符串的第一行
            
        bot_type_configs[bot_name] = {
            "count": db_config.get("count", 0),
            "action_probability": db_config.get("action_probability", 0.1),
            "description": description # <--- 动态将描述发送给前端
        }
    # 4. 返回解耦的结构
    return {
        "global_settings": global_config,
        "bot_types": bot_type_configs
    }
@app.post("/admin/bots/config", response_model=SuccessResponse, tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
async def api_admin_set_bot_config(request: FullBotConfigRequest): # <--- 5. 使用新的 Pydantic 模型
    """
    (重构) 更新机器人系统的配置。
    """
    try:
        with ledger.LEDGER_LOCK, ledger.get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. 保存全局设置
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("bot_system_enabled", str(request.global_settings.bot_system_enabled).lower())
            )
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("bot_check_interval_seconds", str(request.global_settings.bot_check_interval_seconds))
            )
            # 2. 保存所有已知的机器人特定设置
            for bot_name, config in request.bot_types.items():
                if bot_name in BOT_LOGIC_MAP: # 确保只保存后端认识的机器人
                    db_key = f"bot_config_{bot_name}"
                    # 只保存 count 和 probability
                    config_to_save = {
                        "count": config.count,
                        "action_probability": config.action_probability
                    }
                    db_value = json.dumps(config_to_save, ensure_ascii=False)
                    cursor.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (db_key, db_value)
                    )
            conn.commit()
            
        return SuccessResponse(detail="机器人配置已成功更新。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {e}")
# --- 管理员接口 ---
@app.get("/admin/nft/types", response_model=List[str], tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_get_nft_types():
    return get_available_nft_types()

@app.get("/admin/nft/mint_info/{nft_type}", tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_get_nft_mint_info(nft_type: str):
    """获取特定NFT类型的管理员铸造帮助信息和默认JSON。"""
    info = get_mint_info_for_type(nft_type)
    if not info:
        raise HTTPException(status_code=404, detail=f"未找到类型为 {nft_type} 的铸造信息。")
    return info

@app.post("/admin/nft/mint", response_model=SuccessResponse, tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_mint_nft(request: AdminMintNFTRequest):
    handler = get_handler(request.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail=f"不存在的 NFT 类型: {request.nft_type}")
    user_details = ledger.get_user_details(request.to_key)
    if not user_details:
        raise HTTPException(status_code=404, detail="接收用户不存在")
    username = user_details.get('username')
    success, detail, db_data = handler.mint(request.to_key, request.data, owner_username=username)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    success, detail, nft_id = ledger.mint_nft(owner_key=request.to_key, nft_type=request.nft_type, data=db_data)
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=f"成功为用户 {request.to_key[:10]}... 铸造了 NFT (ID: {nft_id[:8]}...)！消息: {detail}")

@app.post("/admin/issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_issue(request: AdminIssueRequest):
    success, detail = ledger.admin_issue_coins(to_key=request.to_key, amount=request.amount, note=request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/multi_issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_multi_issue(request: AdminMultiIssueRequest):
    success, detail = ledger.admin_multi_issue_coins(targets=request.targets, note=request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/burn", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_burn(request: AdminBurnRequest):
    success, detail = ledger.admin_burn_coins(from_key=request.from_key, amount=request.amount, note=request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.get("/admin/balances", response_model=AdminBalancesResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_all_balances():
    balances = ledger.get_all_balances(include_inactive=True)
    return AdminBalancesResponse(balances=balances)

@app.get("/admin/setting/{key}", tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_setting(key: str):
    value = ledger.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return {"key": key, "value": value}

@app.post("/admin/set_setting", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_set_setting(request: AdminSetQuotaRequest):
    success = ledger.set_setting(request.key, request.value)
    if not success:
        raise HTTPException(status_code=500, detail="更新设置失败")
    return SuccessResponse(detail=f"设置 '{request.key}' 已更新为 '{request.value}'")

@app.post("/admin/adjust_quota", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_adjust_user_quota(request: AdminAdjustUserQuotaRequest):
    success, detail = ledger.admin_adjust_user_quota(request.public_key, request.new_quota)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

# +++ 核心修正 #1：添加缺失的接口 +++
@app.post("/admin/set_user_active_status", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_set_user_active_status(request: AdminSetUserActiveStatusRequest):
    """(管理员功能) 启用或禁用一个用户。"""
    success, detail = ledger.admin_set_user_active_status(request.public_key, request.is_active)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/reset_password", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_reset_user_password(request: AdminResetPasswordRequest):
    if not request.new_password or len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要6个字符。")
    success, detail = ledger.admin_reset_user_password(request.public_key, request.new_password)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/purge_user", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_purge_user(request: AdminPurgeUserRequest):
    """(管理员功能) 彻底清除用户数据"""
    success, detail = ledger.admin_purge_user(request.public_key)
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=detail)


@app.post("/admin/nuke_system", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_nuke_system():
    success, detail = ledger.nuke_database()
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=detail)
# --- 启动 (用于本地调试) ---
if __name__ == "__main__":
    print("--- 警告：正在以调试模式启动 (非 Docker) ---")
    on_startup() 
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)