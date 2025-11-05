# backend/api/routes_nft.py

from fastapi import APIRouter, HTTPException
import json
from typing import List
from backend.db import queries_nft
from backend.db import queries_user
from backend.api.models import (
    NFTListResponse, NFTResponse, NFTActionRequest,
    NFTActionMessage, SuccessResponse
)
from backend.api.dependencies import get_verified_nft_action_message
from backend.nft_logic import NFT_HANDLERS, get_handler

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

    # (新增) 处理需要消耗 FC 的动作，例如 'scan'
    if message.action == 'scan': # 这是一个示例，你可以将其做得更通用
        scan_cost = 5.0 # 应该从配置中读取
        current_balance = queries_user.get_balance(message.owner_key)
        if current_balance < scan_cost:
            raise HTTPException(status_code=400, detail=f"余额不足以支付 {scan_cost} FC 的扫描费用")
        
        # 在数据库事务中执行
        from backend.db.database import LEDGER_LOCK, get_db_connection, _create_system_transaction, BURN_ACCOUNT
        with LEDGER_LOCK, get_db_connection() as conn:
            # 1. 扣款
            success_pay, detail_pay = _create_system_transaction(
                message.owner_key, BURN_ACCOUNT, scan_cost, f"NFT 扫描: {nft['nft_id'][:8]}", conn
            )
            if not success_pay:
                conn.rollback()
                raise HTTPException(status_code=500, detail=f"支付失败: {detail_pay}")

            # 2. 执行动作
            success, detail, updated_data = handler.perform_action(nft, message.action, message.action_data, message.owner_key)
            if not success:
                conn.rollback()
                raise HTTPException(status_code=500, detail=detail)

            # 3. 更新 NFT 数据
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
        success, detail, updated_data = handler.perform_action(nft, message.action, message.action_data, message.owner_key)
        if not success:
            raise HTTPException(status_code=500, detail=detail)

        new_status = updated_data.pop('__new_status__', None)

        update_success, update_detail = queries_nft.update_nft(message.nft_id, updated_data, new_status)
        if not update_success:
            # 注意：这里的操作没有回滚，因为动作已执行。这是一个需要权衡的地方。
            raise HTTPException(status_code=500, detail=f"执行成功但数据更新失败: {update_detail}")

        return SuccessResponse(detail=detail)