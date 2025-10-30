# backend/main.py

import time
import json
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
import os

from shared.crypto_utils import (
    generate_key_pair, 
    verify_signature
)
from backend import ledger
from backend.nft_logic import get_handler, get_available_nft_types, NFT_HANDLERS

# --- Pydantic 模型定义 ---
class UserRegisterRequest(BaseModel):
    username: str
    invitation_code: str

class UserRegisterResponse(BaseModel):
    username: str
    public_key: str
    private_key: str

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

class AdminPrivateKeyResponse(BaseModel):
    public_key: str
    private_key: str
    
class InvitationCodeResponse(BaseModel):
    code: str

class InvitationCodeListResponse(BaseModel):
    codes: List[dict]

class MessageGenerateCode(BaseModel):
    owner_key: str
    timestamp: float

class GenesisRegisterRequest(BaseModel):
    username: str
    genesis_password: str

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
    print("正在启动 API (V3.0 Market)... 初始化数据库...")
    ledger.init_db()

# --- 系统状态接口 ---
@app.get("/status", tags=["System"])
def api_get_system_status():
    user_count = ledger.count_users()
    return {"needs_setup": user_count == 0}

@app.post("/genesis_register", response_model=UserRegisterResponse, tags=["System"])
def api_genesis_register(request: GenesisRegisterRequest):
    if ledger.count_users() > 0:
        raise HTTPException(status_code=403, detail="系统已经初始化，无法注册创世用户。")

    if request.genesis_password != GENESIS_PASSWORD:
        raise HTTPException(status_code=403, detail="创世密码错误。")
        
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    private_key, public_key = generate_key_pair()
    
    success, detail = ledger.create_genesis_user(
        username=request.username, 
        public_key=public_key,
        private_key=private_key
    )

    if not success:
        raise HTTPException(status_code=500, detail=detail)

    return UserRegisterResponse(
        username=request.username,
        public_key=public_key,
        private_key=private_key
    )

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
@app.post("/register", response_model=UserRegisterResponse, tags=["User"])
def api_register_user(request: UserRegisterRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
        
    if not request.invitation_code:
        raise HTTPException(status_code=400, detail="必须提供邀请码")
        
    private_key, public_key = generate_key_pair()
    
    success, detail = ledger.register_user(
        username=request.username, 
        public_key=public_key,
        private_key=private_key,
        invitation_code=request.invitation_code.upper()
    )
    
    if not success:
        raise HTTPException(status_code=409, detail=detail)
        
    return UserRegisterResponse(
        username=request.username,
        public_key=public_key,
        private_key=private_key
    )

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

@app.get("/balance/", response_model=BalanceResponse, tags=["User"])
def api_get_balance(public_key: str):
    balance = ledger.get_balance(public_key)
    return BalanceResponse(public_key=public_key, balance=balance)

@app.get("/history/", response_model=HistoryResponse, tags=["User"])
def api_get_history(public_key: str):
    history = ledger.get_transaction_history(public_key)
    return HistoryResponse(transactions=history)

@app.get("/user/details/", response_model=UserDetailsResponse, tags=["User"])
def api_get_user_details(public_key: str):
    details = ledger.get_user_details(public_key)
    if not details:
        raise HTTPException(status_code=404, detail="未找到用户或用户已被禁用")
    return UserDetailsResponse(**details)

@app.get("/users/list", response_model=UserListResponse, tags=["User"])
def api_get_all_users():
    users = ledger.get_all_active_users()
    return UserListResponse(users=users)

@app.post("/user/generate_invitation", response_model=InvitationCodeResponse, tags=["User"])
def api_generate_invitation(request: MarketSignedRequest):
    message = get_verified_message(request, MessageGenerateCode)
    
    success, code_or_error = ledger.generate_invitation_code(message.owner_key)
    
    if not success:
        raise HTTPException(status_code=400, detail=code_or_error)
        
    return InvitationCodeResponse(code=code_or_error)

@app.get("/user/my_invitations/", response_model=InvitationCodeListResponse, tags=["User"])
def api_get_my_invitations(public_key: str):
    if not public_key or "PUBLIC KEY" not in public_key:
         raise HTTPException(status_code=400, detail="无效的公钥格式")
         
    codes = ledger.get_my_invitation_codes(public_key)
    return InvitationCodeListResponse(codes=codes)

# --- NFT 接口 ---
@app.get("/nfts/my/", response_model=NFTListResponse, tags=["NFT"])
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

    with ledger.LEDGER_LOCK, ledger.get_db_connection() as conn:
        success, detail = ledger._create_system_transaction(message.owner_key, ledger.BURN_ACCOUNT, message.cost, f"商店铸造NFT: {message.nft_type}", conn)
        if not success:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"支付失败: {detail}")
        
        user_details = ledger.get_user_details(message.owner_key, conn) # 在事务中查询
        if not user_details:
             # 理论上不会发生，因为能支付成功说明用户存在
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
            raise HTTPException(status_code=400, detail=f"支付失败: {detail}")

        # 2. 执行插件定义的动作
        user_details = ledger.get_user_details(message.owner_key, conn)
        username = user_details.get('username') if user_details else "未知用户"

        success, detail, new_nft_id = handler.execute_shop_action(message.owner_key, username, message.data, conn)

        if not success:
            conn.rollback() # 很重要，如果动作失败（比如没抽中），也要回滚支付
            raise HTTPException(status_code=400, detail=detail)

        conn.commit()
        return SuccessResponse(detail=detail)

# --- 管理员接口 ---
@app.get("/admin/nft/types", response_model=List[str], tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_get_nft_types():
    return get_available_nft_types()

@app.post("/admin/nft/mint", response_model=SuccessResponse, tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_mint_nft(request: AdminMintNFTRequest):
    handler = get_handler(request.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail=f"不存在的 NFT 类型: {request.nft_type}")

    # 获取用户名以传递给 mint 函数
    user_details = ledger.get_user_details(request.to_key)
    if not user_details:
        raise HTTPException(status_code=404, detail="接收用户不存在")
    username = user_details.get('username')

    success, detail, db_data = handler.mint(request.to_key, request.data, owner_username=username)
    if not success:
        raise HTTPException(status_code=400, detail=detail)

    success, detail, nft_id = ledger.mint_nft(
        owner_key=request.to_key,
        nft_type=request.nft_type,
        data=db_data
    )
    if not success:
        raise HTTPException(status_code=500, detail=detail)
        
    return SuccessResponse(detail=f"成功为用户 {request.to_key[:10]}... 铸造了 NFT (ID: {nft_id[:8]}...)！消息: {detail}")

@app.post("/admin/issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_issue(request: AdminIssueRequest):
    """(管理员) 增发货币。"""
    success, detail = ledger.admin_issue_coins(
        to_key=request.to_key,
        amount=request.amount,
        note=request.note
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/multi_issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_multi_issue(request: AdminMultiIssueRequest):
    """(管理员) 批量增发货币。"""
    success, detail = ledger.admin_multi_issue_coins(
        targets=request.targets,
        note=request.note
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/burn", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_burn(request: AdminBurnRequest):
    """(管理员) 销毁货币。"""
    success, detail = ledger.admin_burn_coins(
        from_key=request.from_key,
        amount=request.amount,
        note=request.note
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)
@app.get("/admin/balances", response_model=AdminBalancesResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_all_balances():
    """(管理员) 监控所有用户的余额。"""
    balances = ledger.get_all_balances(include_inactive=True)
    return AdminBalancesResponse(balances=balances)

@app.get("/admin/setting/{key}", tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_setting(key: str):
    """(管理员) 获取单个系统设置。"""
    value = ledger.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return {"key": key, "value": value}

@app.post("/admin/set_setting", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_set_setting(request: AdminSetQuotaRequest):
    """(管理员) 更新全局设置。"""
    success = ledger.set_setting(request.key, request.value)
    if not success:
        raise HTTPException(status_code=500, detail="更新设置失败")
    return SuccessResponse(detail=f"设置 '{request.key}' 已更新为 '{request.value}'")

@app.post("/admin/adjust_quota", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_adjust_user_quota(request: AdminAdjustUserQuotaRequest):
    """(管理员) 调整特定用户的邀请额度。"""
    success, detail = ledger.admin_adjust_user_quota(request.public_key, request.new_quota)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.get("/admin/private_key/", response_model=AdminPrivateKeyResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_private_key(public_key: str):
    """(管理员) 获取指定用户的私钥。"""
    private_key = ledger.admin_get_user_private_key(public_key)
    if not private_key:
        raise HTTPException(status_code=404, detail="未找到用户或该用户没有存储私钥。")
    return AdminPrivateKeyResponse(public_key=public_key, private_key=private_key)

@app.post("/admin/nuke_system", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_nuke_system():
    """(管理员) 彻底删除数据库并重建，返回到创世状态。"""
    success, detail = ledger.nuke_database()
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=detail)

# --- 启动 (用于本地调试) ---
if __name__ == "__main__":
    print("--- 警告：正在以调试模式启动 (非 Docker) ---")
    on_startup() 
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)