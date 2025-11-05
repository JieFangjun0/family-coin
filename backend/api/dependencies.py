# backend/api/dependencies.py

import os
import json
import time
from fastapi import HTTPException, Header
from pydantic import BaseModel
from typing import Type

from shared.crypto_utils import verify_signature

# --- 导入模型 ---
from backend.api.models import (
    MarketSignedRequest, NFTActionRequest, NFTActionMessage,
    ProfileUpdateRequest, TransactionMessage, MessageGenerateCode,
    FriendActionMessage, FriendRespondMessage, MarketListingRequest,
    MarketActionMessage, MarketBidRequest, MarketOfferRequest,
    MarketOfferResponseRequest, ShopCreateNftRequest, ShopActionRequest
)

# --- Admin Auth ---
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "CHANGE_ME_IN_ENV")
GENESIS_PASSWORD = os.getenv("GENESIS_PASSWORD", "CHANGE_ME_IN_ENV")

def verify_admin(x_admin_secret: str = Header(None)):
    if not x_admin_secret or x_admin_secret != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="未授权的管理员访问")
    return True

# --- Signature Verification ---

def get_verified_message(request: MarketSignedRequest, model: Type[BaseModel]):
    """
    通用签名验证辅助函数。
    它解析JSON，验证模型，检查签名和时间戳。
    """
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

def get_verified_nft_action_message(request: NFTActionRequest, model: Type[BaseModel]):
    """
    NFTActionRequest 的特定验证器 (结构不同)
    """
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