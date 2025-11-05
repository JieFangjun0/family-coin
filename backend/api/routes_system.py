# backend/api/routes_system.py

from fastapi import APIRouter, HTTPException
from backend.db import queries_system
from backend.api.models import GenesisRegisterRequest, GenesisRegisterResponse,PublicSettingsResponse
from backend.api.dependencies import GENESIS_PASSWORD
from backend.db.database import get_setting
router = APIRouter()

@router.get("/status", tags=["System"])
def api_get_system_status():
    user_count = queries_system.count_users()
    return {"needs_setup": user_count == 0}

@router.post("/genesis_register", response_model=GenesisRegisterResponse, tags=["System"])
def api_genesis_register(request: GenesisRegisterRequest):
    if queries_system.count_users() > 0:
        raise HTTPException(status_code=403, detail="系统已经初始化，无法注册创世用户。")

    if request.genesis_password != GENESIS_PASSWORD:
        raise HTTPException(status_code=403, detail="创世密钥错误。")
        
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="用户密码至少需要6个字符")

    success, detail, user_data = queries_system.create_genesis_user(
        username=request.username, 
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=500, detail=detail)

    return GenesisRegisterResponse(**user_data)

router.get("/settings/public", response_model=PublicSettingsResponse, tags=["System"])
def api_get_public_settings():
    """
    获取公开的、非敏感的系统设置，例如邀请奖励。
    """
    try:
        # 从数据库的 settings 表中读取值
        welcome_str = get_setting('welcome_bonus_amount')
        inviter_str = get_setting('inviter_bonus_amount')
        
        # 转换为浮点数，如果不存在则默认为 0.0
        welcome_bonus = float(welcome_str) if welcome_str else 0.0
        inviter_bonus = float(inviter_str) if inviter_str else 0.0
        
        return PublicSettingsResponse(
            welcome_bonus_amount=welcome_bonus,
            inviter_bonus_amount=inviter_bonus
        )
    except Exception as e:
        # 如果数据库出错，返回 500 错误
        raise HTTPException(status_code=500, detail=f"无法加载系统设置: {e}")