# backend/api/routes_admin.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
from backend.db import queries_system, queries_bots, queries_market
from backend.api.models import (
    SuccessResponse, AdminMintNFTRequest, AdminIssueRequest, AdminMultiIssueRequest,
    AdminBurnRequest, AdminBalancesResponse, AdminSetQuotaRequest,
    AdminAdjustUserQuotaRequest, AdminSetUserActiveStatusRequest,
    AdminResetPasswordRequest, AdminPurgeUserRequest, AdminCreateBotRequest,
    AdminBotInfo, AdminBotListResponse, AdminSetBotConfigRequest,
    AdminBotLogResponse, AdminMarketTradeHistoryResponse
)
from backend.api.dependencies import verify_admin
from backend.nft_logic import get_handler, get_available_nft_types
from backend.nft_admin_utils import get_mint_info_for_type
from backend.bots import BOT_LOGIC_MAP
from backend.db import queries_user # 需要 get_user_details

router = APIRouter()

# --- Admin NFT ---
@router.get("/nft/types", response_model=List[str], tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_get_nft_types():
    return get_available_nft_types()

@router.get("/nft/mint_info/{nft_type}", tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_get_nft_mint_info(nft_type: str):
    info = get_mint_info_for_type(nft_type)
    if not info:
        raise HTTPException(status_code=404, detail=f"未找到类型为 {nft_type} 的铸造信息。")
    return info

@router.post("/nft/mint", response_model=SuccessResponse, tags=["Admin NFT"], dependencies=[Depends(verify_admin)])
def api_admin_mint_nft(request: AdminMintNFTRequest):
    handler = get_handler(request.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail=f"不存在的 NFT 类型: {request.nft_type}")
    
    user_details = queries_user.get_user_details(request.to_key)
    if not user_details:
        raise HTTPException(status_code=404, detail="接收用户不存在")
    
    username = user_details.get('username')
    success, detail, db_data = handler.mint(request.to_key, request.data, owner_username=username)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    
    from backend.db.queries_nft import mint_nft # 避免循环导入
    success, detail, nft_id = mint_nft(owner_key=request.to_key, nft_type=request.nft_type, data=db_data)
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    
    return SuccessResponse(detail=f"成功为用户 {request.to_key[:10]}... 铸造了 NFT (ID: {nft_id[:8]}...)！消息: {detail}")

# --- Admin General ---
@router.post("/issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_issue(request: AdminIssueRequest):
    success, detail = queries_system.admin_issue_coins(to_key=request.to_key, amount=request.amount, note=request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/multi_issue", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_multi_issue(request: AdminMultiIssueRequest):
    success, detail = queries_system.admin_multi_issue_coins(targets=request.targets, note=request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/burn", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_burn(request: AdminBurnRequest):
    success, detail = queries_system.admin_burn_coins(from_key=request.from_key, amount=request.amount, note=request.note)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.get("/balances", response_model=AdminBalancesResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_all_balances():
    balances = queries_system.get_all_balances(include_inactive=True)
    return AdminBalancesResponse(balances=balances)

@router.get("/setting/{key}", tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_setting(key: str):
    from backend.db.database import get_setting # 避免循环导入
    value = get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return {"key": key, "value": value}

@router.post("/set_setting", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_set_setting(request: AdminSetQuotaRequest):
    from backend.db.database import set_setting # 避免循环导入
    success = set_setting(request.key, request.value)
    if not success:
        raise HTTPException(status_code=500, detail="更新设置失败")
    return SuccessResponse(detail=f"设置 '{request.key}' 已更新为 '{request.value}'")

@router.post("/adjust_quota", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_adjust_user_quota(request: AdminAdjustUserQuotaRequest):
    success, detail = queries_system.admin_adjust_user_quota(request.public_key, request.new_quota)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/set_user_active_status", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_set_user_active_status(request: AdminSetUserActiveStatusRequest):
    success, detail = queries_system.admin_set_user_active_status(request.public_key, request.is_active)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/reset_password", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_reset_user_password(request: AdminResetPasswordRequest):
    if not request.new_password or len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要6个字符。")
    success, detail = queries_system.admin_reset_user_password(request.public_key, request.new_password)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/purge_user", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_purge_user(request: AdminPurgeUserRequest):
    success, detail = queries_system.admin_purge_user(request.public_key)
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/nuke_system", response_model=SuccessResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_nuke_system():
    success, detail = queries_system.nuke_database()
    if not success:
        raise HTTPException(status_code=500, detail=detail)
    return SuccessResponse(detail=detail)

@router.get("/market/history", response_model=AdminMarketTradeHistoryResponse, tags=["Admin"], dependencies=[Depends(verify_admin)])
def api_admin_get_market_trade_history(limit: int = 100):
    if limit > 500: limit = 500
    history = queries_market.admin_get_market_trade_history(limit=limit)
    return AdminMarketTradeHistoryResponse(history=history)

# --- Admin Bots ---
@router.get("/bots/types", response_model=Dict, tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
def api_admin_get_bot_types():
    return {"types": list(BOT_LOGIC_MAP.keys())}

@router.get("/bots/list", response_model=AdminBotListResponse, tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
def api_admin_get_bot_list():
    bots = queries_bots.get_all_bots(include_inactive=True)
    for bot in bots:
        if 'private_key_pem' in bot:
            del bot['private_key_pem']
    return AdminBotListResponse(bots=bots)

@router.post("/bots/create", response_model=AdminBotInfo, tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
def api_admin_create_bot(request: AdminCreateBotRequest):
    if request.bot_type not in BOT_LOGIC_MAP:
        raise HTTPException(status_code=400, detail="无效的机器人类型")
    if request.username and len(request.username) < 3:
        raise HTTPException(status_code=400, detail="机器人用户名至少需要3个字符")
    if request.initial_funds < 0:
        raise HTTPException(status_code=400, detail="初始资金不能为负")
    if not (0.0 <= request.action_probability <= 1.0):
        raise HTTPException(status_code=400, detail="行动概率必须在 0.0 和 1.0 之间")

    success, detail, new_bot_info = queries_bots.admin_create_bot(
        username=request.username,
        bot_type=request.bot_type,
        initial_funds=request.initial_funds,
        action_probability=request.action_probability
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    
    return AdminBotInfo(**new_bot_info)

@router.post("/bots/set_config", response_model=SuccessResponse, tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
def api_admin_set_bot_config(request: AdminSetBotConfigRequest):
    success, detail = queries_bots.admin_set_bot_config(
        public_key=request.public_key,
        action_probability=request.action_probability
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.get("/bots/logs", response_model=AdminBotLogResponse, tags=["Admin Bots"], dependencies=[Depends(verify_admin)])
def api_admin_get_bot_logs(public_key: str = None, limit: int = 100):
    if limit > 500: limit = 500
    logs = queries_bots.admin_get_bot_logs(bot_key=public_key, limit=limit)
    return AdminBotLogResponse(logs=logs)