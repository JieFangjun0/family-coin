# backend/api/models.py

from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# --- Pydantic 模型定义 ---
class UserRegisterRequest(BaseModel):
    username: str
    password: str
    invitation_code: str

class UserRegisterResponse(BaseModel):
    uid: str
    username: str
    public_key: str

class UserLoginRequest(BaseModel):
    username_or_uid: str
    password: str

class UserLoginResponse(BaseModel):
    message: str
    public_key: str
    private_key: str
    username: str
    uid: str

class FriendActionMessage(BaseModel):
    owner_key: str
    target_key: str
    timestamp: float

class FriendRespondMessage(BaseModel):
    owner_key: str
    requester_key: str
    accept: bool
    timestamp: float

class FriendInfo(BaseModel):
    username: str
    public_key: str
    uid: str

class FriendListResponse(BaseModel):
    friends: List[FriendInfo]

class FriendRequestInfo(BaseModel):
    username: str
    public_key: str
    uid: str
    created_at: float # 保持 float, 匹配 DB 查询

class FriendRequestListResponse(BaseModel):
    requests: List[FriendRequestInfo]

class FriendshipStatusResponse(BaseModel):
    status: str
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
    uid: str
    created_at: float
    invitation_quota: int
    invited_by: Optional[str] = None
    inviter_username: Optional[str] = None
    inviter_uid: Optional[str] = None
    tx_count: int
    is_active: bool

class UserInfo(BaseModel):
    username: str
    public_key: str
    uid: str

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

class AdminResetPasswordRequest(BaseModel):
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
    password: str
    genesis_password: str

class GenesisRegisterResponse(BaseModel):
    uid: str
    username: str
    public_key: str
    private_key: str
    
class UserProfileResponse(BaseModel):
    uid: str
    username: str
    public_key: str
    created_at: float
    signature: Optional[str] = None
    displayed_nfts_details: List[dict] = []

class ProfileUpdateRequest(BaseModel):
    owner_key: str
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

class AdminCreateBotRequest(BaseModel):
    username: Optional[str] = None
    bot_type: str
    initial_funds: float
    action_probability: float

class AdminBotInfo(BaseModel):
    public_key: str
    uid: str
    username: str
    bot_type: str
    is_active: bool
    action_probability: float
    balance: float

class AdminBotListResponse(BaseModel):
    bots: List[AdminBotInfo]

class AdminSetBotConfigRequest(BaseModel):
    public_key: str
    action_probability: float

class BotLogEntry(BaseModel):
    log_id: str
    timestamp: float
    bot_key: str
    bot_username: str
    action_type: str
    message: str
    data_snapshot: Optional[str]

class AdminBotLogResponse(BaseModel):
    logs: List[BotLogEntry]

class AdminMarketTradeHistoryEntry(BaseModel):
    trade_id: str
    listing_id: str
    nft_id: str
    nft_type: str
    trade_type: str
    seller_key: str
    buyer_key: str
    price: float
    timestamp: float
    seller_username: Optional[str] = None
    buyer_username: Optional[str] = None
    listing_description: Optional[str] = None

class AdminMarketTradeHistoryResponse(BaseModel):
    history: List[AdminMarketTradeHistoryEntry]
    
# --- Notifications (新增) ---

class NotificationEntry(BaseModel):
    notif_id: str
    user_key: str
    message: str
    is_read: bool
    timestamp: float

class NotificationListResponse(BaseModel):
    notifications: List[NotificationEntry]
    unread_count: int
    
class PublicSettingsResponse(BaseModel):
    """
    用于返回公开的、非敏感的系统设置。
    """
    welcome_bonus_amount: float
    inviter_bonus_amount: float

# --- (新增) ---
class AccumulatedJphResponse(BaseModel):
    nft_id: str
    accumulated_jph: float
    is_ready: bool
    cooldown_left_seconds: int