# backend/api/routes_system.py

from fastapi import APIRouter, HTTPException
from backend.db import queries_system
from backend.api.models import GenesisRegisterRequest, GenesisRegisterResponse
from backend.api.dependencies import GENESIS_PASSWORD

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