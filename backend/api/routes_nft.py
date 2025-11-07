# backend/api/routes_nft.py

from fastapi import APIRouter, HTTPException
import json
from typing import List
from backend.db import queries_nft
from backend.db import queries_user
from backend.api.models import (
    NFTListResponse, NFTResponse, NFTActionRequest,
    NFTActionMessage, SuccessResponse,
    AccumulatedJphResponse
)
from backend.api.dependencies import get_verified_nft_action_message
from backend.nft_logic import NFT_HANDLERS, get_handler
# (V3 新增导入)
from backend.db.database import LEDGER_LOCK, get_db_connection, _create_system_transaction, BURN_ACCOUNT, GENESIS_ACCOUNT
from backend.nft_logic.planet import PLANET_ECONOMICS # 导入经济配置以获取扫描成本
from backend.nft_logic.bio_dna import PET_ECONOMICS # <<< (1) 导入灵宠经济配置

router = APIRouter()

@router.get("/display_names", tags=["NFT"])
def api_get_nft_display_names():
    names = {}
    for nft_type, handler_class in NFT_HANDLERS.items():
        names[nft_type] = handler_class.get_display_name()
    return names

@router.get("/my", response_model=NFTListResponse, tags=["NFT"])
def api_get_my_nfts(public_key: str):
    if not public_key:
        raise HTTPException(status_code=400, detail="必须提供公钥")
    nfts = queries_nft.get_nfts_by_owner(public_key)
    return NFTListResponse(nfts=nfts)

@router.get("/{nft_id}", response_model=NFTResponse, tags=["NFT"])
def api_get_nft_details(nft_id: str):
    nft = queries_nft.get_nft_by_id(nft_id)
    if not nft:
        raise HTTPException(status_code=404, detail="未找到该 NFT")
    return NFTResponse(**nft)

@router.get("/economics/all", tags=["NFT"])
def api_get_all_nft_economics():
    """
    (V2) 获取所有公开的、非敏感的NFT经济配置 (用于解耦前端)。
    """
    configs = {}
    for nft_type, handler_class in NFT_HANDLERS.items():
        if hasattr(handler_class, 'get_economic_config_and_valuation'):
            try:
                config_data = handler_class.get_economic_config_and_valuation()
                configs[nft_type] = config_data.get("config")
            except Exception:
                pass # 忽略没有配置的
    return configs

@router.get("/{nft_id}/jph_status", response_model=AccumulatedJphResponse, tags=["NFT"])
def api_get_nft_jph_status(nft_id: str):
    """
    (V2) 获取单个NFT的实时JPH积累和冷却状态。
    """
    nft = queries_nft.get_nft_by_id(nft_id)
    if not nft:
        raise HTTPException(status_code=404, detail="未找到该 NFT")

    handler = get_handler(nft['nft_type'])

    # 检查处理器是否实现了所需的方法
    if not handler or not hasattr(handler, 'get_accumulated_jph') or not hasattr(handler, 'get_harvest_cooldown_info'):
        return AccumulatedJphResponse(
            nft_id=nft_id, 
            accumulated_jph=0.0, 
            is_ready=False, 
            cooldown_left_seconds=-1
        )

    jph = handler.get_accumulated_jph(nft['data'])
    is_ready, cd_left = handler.get_harvest_cooldown_info(nft['data'])

    return AccumulatedJphResponse(
        nft_id=nft_id,
        accumulated_jph=jph,
        is_ready=is_ready,
        cooldown_left_seconds=cd_left
    )
@router.post("/action", response_model=SuccessResponse, tags=["NFT"])
def api_perform_nft_action(request: NFTActionRequest):
    message = get_verified_nft_action_message(request, NFTActionMessage)
    
    nft = queries_nft.get_nft_by_id(message.nft_id)
    if not nft or nft['owner_key'] != message.owner_key:
        raise HTTPException(status_code=404, detail="未找到 NFT 或你不是所有者")

    if nft.get('status') != 'ACTIVE':
        raise HTTPException(status_code=400, detail="该 NFT 当前不是活跃状态，无法执行操作")

    handler = get_handler(nft['nft_type'])
    if not handler:
        raise HTTPException(status_code=501, detail=f"不支持的 NFT 类型: {nft['nft_type']}")

    # 验证操作
    is_valid, reason = handler.validate_action(nft, message.action, message.action_data, message.owner_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    # (V3 核心修改：将 'scan', 'harvest', 'train', 'breed' 纳入事务处理)
    if message.action in ['scan', 'harvest', 'train', 'breed']: # <<< (2) 新增 'train', 'breed'
        
        with LEDGER_LOCK, get_db_connection() as conn:
            
            # --- 1. 处理成本 (如果是 'scan' 或 'train') ---
            cost = 0.0
            note = ""
            
            if message.action == 'scan':
                cost = PLANET_ECONOMICS.get('SCAN_COST', 10.0) 
                note = f"NFT 扫描: {nft['nft_id'][:8]}"
            
            elif message.action == 'train': # <<< (3) 新增 'train' 成本逻辑
                level = nft['data'].get('level', 1)
                cost = PET_ECONOMICS.get('TRAIN_COST_PER_LEVEL', 5.0) * level
                note = f"灵宠训练: {nft['nft_id'][:8]}"
            
            if cost > 0:
                current_balance = queries_user.get_balance(message.owner_key) 
                if current_balance < cost:
                    raise HTTPException(status_code=400, detail=f"余额不足以支付 {cost} FC 的{message.action}费用")
                
                success_pay, detail_pay = _create_system_transaction(
                    message.owner_key, BURN_ACCOUNT, cost, note, conn
                )
                if not success_pay:
                    conn.rollback()
                    raise HTTPException(status_code=500, detail=f"支付失败: {detail_pay}")

            # --- 2. 执行动作 (scan, harvest, train, breed) ---
            # <<< (4) 传递 conn 到 perform_action >>>
            success, detail, updated_data = handler.perform_action(nft, message.action, message.action_data, message.owner_key, conn=conn)
            if not success:
                conn.rollback()
                raise HTTPException(status_code=500, detail=detail)

            # --- 3. (V3 新增) 处理产出 (如果是 'harvest') ---
            if message.action == 'harvest':
                jcoin_produced = updated_data.pop('__jcoin_produced__', 0.0)
                if jcoin_produced > 0:
                    success_grant, detail_grant = _create_system_transaction(
                        GENESIS_ACCOUNT, message.owner_key, jcoin_produced, f"NFT 丰收: {nft['nft_id'][:8]}", conn
                    )
                    if not success_grant:
                        conn.rollback()
                        raise HTTPException(status_code=500, detail=f"丰收成功但JCoin发放失败: {detail_grant}")

            # --- 4. 更新 NFT 数据 ---
            new_status = updated_data.pop('__new_status__', None)
            from backend.db.queries_nft import update_nft # 避免循环导入
            
            # 在同一个事务连接中更新 NFT
            data_json = json.dumps(updated_data, ensure_ascii=False)
            try:
                cursor = conn.cursor()
                if new_status:
                    cursor.execute("UPDATE nfts SET data = ?, status = ? WHERE nft_id = ?", (data_json, new_status, message.nft_id))
                else:
                    cursor.execute("UPDATE nfts SET data = ? WHERE nft_id = ?", (data_json, message.nft_id))
                if cursor.rowcount == 0:
                    conn.rollback()
                    raise HTTPException(status_code=500, detail="执行成功但数据更新失败: 未找到 NFT")
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=500, detail=f"执行成功但数据更新失败: {e}")

            conn.commit()
            return SuccessResponse(detail=detail)

    else:
        # --- 处理不需要支付的动作 (例如 'rename', 'destroy') ---
        success, detail, updated_data = handler.perform_action(nft, message.action, message.action_data, message.owner_key, conn=None) # <<< (5) 传递 conn=None
        if not success:
            raise HTTPException(status_code=500, detail=detail)

        new_status = updated_data.pop('__new_status__', None)

        update_success, update_detail = queries_nft.update_nft(message.nft_id, updated_data, new_status)
        if not update_success:
            raise HTTPException(status_code=500, detail=f"执行成功但数据更新失败: {update_detail}")

        return SuccessResponse(detail=detail)