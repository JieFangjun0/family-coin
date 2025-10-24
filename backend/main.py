# backend/main.py

import time
import json
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn

# 导入共享和账本模块
from shared.crypto_utils import (
    generate_key_pair, 
    verify_signature
)
from backend import ledger

# --- Pydantic 模型定义 (API的数据结构) ---
# ... (这部分模型定义完全不变，所以省略)
class UserRegisterRequest(BaseModel):
    username: str
    invitation_code: str

class UserRegisterResponse(BaseModel):
    username: str
    public_key: str
    private_key: str # 仅在注册时返回一次，服务器不保存

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
    is_active: bool # <<< 增加 is_active 字段，方便前端判断

class UserInfo(BaseModel):
    username: str
    public_key: str

class UserListResponse(BaseModel):
    users: List[UserInfo]

class ErrorResponse(BaseModel):
    detail: str
    
class SuccessResponse(BaseModel):
    detail: str

# --- Admin Pydantic 模型 ---
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

# 核心修改 1: (新增模型) 用于返回管理员查询的私钥
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
    
# --- Shop Pydantic 模型 ---
class SignedShopRequest(BaseModel):
    message_json: str
    signature: str

class ShopMessagePost(BaseModel):
    owner_key: str
    item_type: str 
    description: str
    price: float
    timestamp: float
    
class ShopMessageCancel(BaseModel):
    owner_key: str
    item_id: str
    timestamp: float

class ShopItemResponse(BaseModel):
    items: List[dict]

class ShopBuyRequest(BaseModel):
    item_id: str
    transaction_message_json: str
    transaction_signature: str

class ShopMessageFulfill(BaseModel):
    owner_key: str 
    item_id: str
    timestamp: float    

class GenesisRegisterRequest(BaseModel):
    username: str
    genesis_password: str

import os
# --- 管理员认证 ---
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "CHANGE_ME_IN_ENV")
GENESIS_PASSWORD = os.getenv("GENESIS_PASSWORD", "CHANGE_ME_IN_ENV")

def verify_admin(x_admin_secret: str = Header(None)):
    """FastAPI 依赖项，用于检查管理员秘密。"""
    if not x_admin_secret or x_admin_secret != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="未授权的管理员访问")
    return True

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="FamilyCoin API (V2.2 - Patched)",
    description="一个用于家庭和朋友的中心化玩具加密货币API (带邀请和商店)",
    version="0.2.2"
)

@app.on_event("startup")
def on_startup():
    """应用启动时，初始化数据库。"""
    print("正在启动 API (V2.2)... 初始化数据库...")
    ledger.init_db()

# --- 系统状态接口 ---
@app.get("/status", tags=["System"])
def api_get_system_status():
    """检查系统状态，主要用于前端判断是否需要进行首次设置。"""
    user_count = ledger.count_users()
    return {"needs_setup": user_count == 0}

@app.post("/genesis_register", response_model=UserRegisterResponse, tags=["System"])
def api_genesis_register(request: GenesisRegisterRequest):
    """(仅在首次运行时可用) 创建第一个管理员用户。"""
    if ledger.count_users() > 0:
        raise HTTPException(status_code=403, detail="系统已经初始化，无法注册创世用户。")

    if request.genesis_password != GENESIS_PASSWORD:
        raise HTTPException(status_code=403, detail="创世密码错误。")
        
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    private_key, public_key = generate_key_pair()
    
    # 核心修改 2: 调用 ledger 函数时传入 private_key
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
def get_verified_message(request: SignedShopRequest, model: BaseModel):
    """验证签名并返回反序列化的消息体。"""
    try:
        message_dict = json.loads(request.message_json)
        message = model(**message_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的消息体: {e}")
        
    if not hasattr(message, 'owner_key'):
        raise HTTPException(status_code=400, detail="消息体中缺少'owner_key'字段")
        
    if not verify_signature(message.owner_key, message_dict, request.signature):
        raise HTTPException(status_code=403, detail="签名无效")
        
    if (time.time() - message.timestamp) > 300: # 5分钟有效期
        raise HTTPException(status_code=400, detail="请求已过期")
        
    return message

# --- 公共接口 (Public API) ---

@app.post("/register", response_model=UserRegisterResponse, tags=["User"])
def api_register_user(request: UserRegisterRequest):
    """(V2) 注册一个新用户 (需要邀请码)。"""
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
        
    if not request.invitation_code:
        raise HTTPException(status_code=400, detail="必须提供邀请码")
        
    private_key, public_key = generate_key_pair()
    
    # 核心修改 3: 调用 ledger 函数时传入 private_key
    success, detail = ledger.register_user(
        username=request.username, 
        public_key=public_key,
        private_key=private_key,
        invitation_code=request.invitation_code.upper() # 邀请码不区分大小写
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
    """提交一笔已签名的交易。"""
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

# <<< 核心修改 1: 将 {public_key} 从路径参数改为查询参数
@app.get("/balance/", response_model=BalanceResponse, tags=["User"])
def api_get_balance(public_key: str):
    """获取指定公钥的当前余额。"""
    balance = ledger.get_balance(public_key)
    return BalanceResponse(public_key=public_key, balance=balance)

# <<< 核心修改 2: 将 {public_key} 从路径参数改为查询参数
@app.get("/history/", response_model=HistoryResponse, tags=["User"])
def api_get_history(public_key: str):
    """获取指定公钥的交易历史。"""
    history = ledger.get_transaction_history(public_key)
    return HistoryResponse(transactions=history)

# <<< 核心修改 3: 将 {public_key} 从路径参数改为查询参数
@app.get("/user/details/", response_model=UserDetailsResponse, tags=["User"])
def api_get_user_details(public_key: str):
    """(V2) 获取用户的详细信息。"""
    details = ledger.get_user_details(public_key)
    if not details:
        raise HTTPException(status_code=404, detail="未找到用户或用户已被禁用")
    return UserDetailsResponse(**details)

@app.get("/users/list", response_model=UserListResponse, tags=["User"])
def api_get_all_users():
    """(V2) 获取所有活跃用户的列表 (用于下拉菜单)。"""
    users = ledger.get_all_active_users()
    return UserListResponse(users=users)

@app.post("/user/generate_invitation", response_model=InvitationCodeResponse, tags=["User"])
def api_generate_invitation(request: SignedShopRequest):
    """生成一个新的、一次性的邀请码。"""
    message = get_verified_message(request, MessageGenerateCode)
    
    success, code_or_error = ledger.generate_invitation_code(message.owner_key)
    
    if not success:
        raise HTTPException(status_code=400, detail=code_or_error)
        
    return InvitationCodeResponse(code=code_or_error)

# <<< 核心修改 4: 将 {public_key} 从路径参数改为查询参数
@app.get("/user/my_invitations/", response_model=InvitationCodeListResponse, tags=["User"])
def api_get_my_invitations(public_key: str):
    """获取一个用户所有未使用的邀请码。"""
    if not public_key or "PUBLIC KEY" not in public_key:
         raise HTTPException(status_code=400, detail="无效的公钥格式")
         
    codes = ledger.get_my_invitation_codes(public_key)
    return InvitationCodeListResponse(codes=codes)

# --- 商店接口 (Shop API) ---

@app.get("/shop/list", response_model=ShopItemResponse, tags=["Shop"])
def api_get_shop_items(item_type: Optional[str] = None, exclude_owner: Optional[str] = None):
    """(V2) 获取商店商品列表。"""
    items = ledger.get_shop_items(item_type=item_type, exclude_owner=exclude_owner)
    return ShopItemResponse(items=items)

# <<< 核心修改 5: 将 {public_key} 从路径参数改为查询参数
@app.get("/shop/my_items/", response_model=ShopItemResponse, tags=["Shop"])
def api_get_my_shop_items(public_key: str):
    """(V2) 获取我发布的所有商品。"""
    items = ledger.get_my_shop_items(public_key)
    return ShopItemResponse(items=items)

@app.post("/shop/post", response_model=SuccessResponse, tags=["Shop"])
def api_post_shop_item(request: SignedShopRequest):
    """(V2) 发布一个新商品 (需签名)。"""
    message = get_verified_message(request, ShopMessagePost)
    
    success, detail = ledger.add_shop_item(
        owner_key=message.owner_key,
        item_type=message.item_type,
        description=message.description,
        price=message.price
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/shop/cancel", response_model=SuccessResponse, tags=["Shop"])
def api_cancel_shop_item(request: SignedShopRequest):
    """(V2) 取消一个商品 (需签名)。"""
    message = get_verified_message(request, ShopMessageCancel)
    
    success, detail = ledger.cancel_shop_item(
        item_id=message.item_id,
        owner_key=message.owner_key
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/shop/buy", response_model=SuccessResponse, tags=["Shop"])
def api_buy_shop_item(request: ShopBuyRequest):
    """(V2) 购买一个商品 (需附带签名交易)。"""
    try:
        tx_message_dict = json.loads(request.transaction_message_json)
        buyer_key = tx_message_dict.get('from_key')
        if not buyer_key:
            raise ValueError("交易消息中缺少 from_key")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的交易消息: {e}")

    success, detail = ledger.execute_purchase(
        item_id=request.item_id,
        buyer_key=buyer_key,
        transaction_message_json=request.transaction_message_json,
        transaction_signature=request.transaction_signature
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/shop/fulfill_wanted", response_model=SuccessResponse, tags=["Shop"])
def api_fulfill_wanted_item(request: SignedShopRequest):
    """(新增) 响应一个求购(WANTED)请求。"""
    message = get_verified_message(request, ShopMessageFulfill)
    
    success, detail = ledger.fulfill_wanted_item(
        item_id=message.item_id,
        seller_key=message.owner_key
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
        
    return SuccessResponse(detail=detail)
    
# --- 管理员接口 (Admin API) ---

@app.post("/admin/issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_issue(request: AdminIssueRequest):
    """(管理员) 增发货币到指定账户。"""
    success, detail = ledger.admin_issue_coins(request.to_key, request.amount, request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/multi_issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_multi_issue(request: AdminMultiIssueRequest):
    """(V2 管理员) 批量增发货币。"""
    success_count = 0
    fail_count = 0
    details = []
    
    for target in request.targets:
        key = target.get('key')
        amount = target.get('amount')
        if not key or not amount or amount <= 0:
            fail_count += 1
            details.append(f"无效条目: {target}")
            continue
            
        success, detail = ledger.admin_issue_coins(key, amount, request.note or "管理员批量增发")
        if success:
            success_count += 1
        else:
            fail_count += 1
            details.append(f"失败 ({key[:10]}...): {detail}")
            
    return SuccessResponse(detail=f"批量发行完成：{success_count} 成功, {fail_count} 失败。{'; '.join(details)}")

@app.post("/admin/burn", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_burn(request: AdminBurnRequest):
    """(V2 管理员) 销毁(减持)指定账户的货币。"""
    success, detail = ledger.admin_burn_coins(request.from_key, request.amount, request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

# (注意: delete_user 现在只是禁用，而 purge_user 是彻底删除)
@app.post("/admin/set_user_active_status", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_set_user_active_status(request: AdminSetUserActiveStatusRequest):
    """(管理员) 设置用户的活跃状态（禁用/启用）。"""
    success, detail = ledger.admin_set_user_active_status(request.public_key, request.is_active)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@app.post("/admin/purge_user", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_purge_user(request: AdminPurgeUserRequest):
    """(V2 管理员) 彻底清除一个用户的数据，释放用户名。"""
    success, detail = ledger.admin_purge_user(request.public_key)
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
    """(V2 管理员) 更新全局设置。"""
    success = ledger.set_setting(request.key, request.value)
    if not success:
        raise HTTPException(status_code=500, detail="更新设置失败")
    return SuccessResponse(detail=f"设置 '{request.key}' 已更新为 '{request.value}'")

@app.post("/admin/adjust_quota", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_adjust_user_quota(request: AdminAdjustUserQuotaRequest):
    """(V2 管理员) 调整特定用户的邀请额度。"""
    success, detail = ledger.admin_adjust_user_quota(request.public_key, request.new_quota)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

# 核心修改 4: (新增API) 增加管理员查询用户私钥的端点
@app.get("/admin/private_key/", response_model=AdminPrivateKeyResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_private_key(public_key: str):
    """(管理员) 获取指定用户的私钥。"""
    private_key = ledger.admin_get_user_private_key(public_key)
    if not private_key:
        raise HTTPException(status_code=404, detail="未找到用户或该用户没有存储私钥。")
    return AdminPrivateKeyResponse(public_key=public_key, private_key=private_key)

@app.post("/admin/nuke_system", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_nuke_system():
    """(V2 管理员) 彻底删除数据库并重建，返回到创世状态。"""
    success, detail = ledger.nuke_database()
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=detail)

# --- 启动 (用于本地调试) ---
if __name__ == "__main__":
    print("--- 警告：正在以调试模式启动 (非 Docker) ---")
    on_startup() # 手动初始化数据库
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)