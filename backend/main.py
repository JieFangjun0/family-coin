# backend/main.py

from fastapi import FastAPI
import asyncio
import uvicorn
from backend.db import database
# 导入所有 API 路由模块 (让它们先被加载和注册)
from backend.api import routes_system
from backend.api import routes_user
from backend.api import routes_friends
from backend.api import routes_nft
from backend.api import routes_market
from backend.api import routes_admin
from backend.api import routes_notifications

from backend.bots import bot_runner
import threading


app = FastAPI(
    title="JCoin API (V0.4.0 - Refactored)",
    description="一个用于家庭和朋友的中心化玩具加密货币API (已解耦)",
    version="0.4.0"
)

@app.on_event("startup")
async def on_startup():
    """
    应用启动时执行初始化。
    """
    
    # (!!! 核心修改 2 !!!)
    try:
        # 1. 首先，初始化数据库连接池
        # (这是一个同步的、阻塞的操作，在 startup 事件中是允许的)
        # 这将在 'sleep 5' 之后运行，给了 postgres 充足的时间
        database.initialize_connection_pool()
        
        # 2. 然后，使用该连接池初始化表
        print("正在启动 API ... 初始化数据库表...")
        database.init_db() # (原为 init_db())
    
    except Exception as e:
        print(f"!!!!!!!!!!!!!! 严重错误：数据库启动失败 !!!!!!!!!!!!!!")
        print(f"错误: {e}")
        # 重新引发错误，以防止 Uvicorn 错误地报告 "Application startup complete"
        raise

# --- 包含所有解耦的路由 ---

# 1. 系统路由 (/, /status, /genesis_register)
app.include_router(routes_system.router, tags=["System"])

# 2. 用户路由 (/login, /register, /balance, /history, etc.)
app.include_router(routes_user.router, tags=["User"])

# 3. 好友路由 (/friends/...)
app.include_router(routes_friends.router, tags=["Friends"])

# 4. NFT 路由 (/nfts/...)
app.include_router(routes_nft.router, prefix="/nfts", tags=["NFT"])

# 5. 市场路由 (/market/...)
app.include_router(routes_market.router, prefix="/market", tags=["Market"])

# 6. 管理员路由 (/admin/...)
app.include_router(routes_admin.router, prefix="/admin", tags=["Admin"])

# 7. 通知路由 (/notifications/...)
app.include_router(routes_notifications.router, tags=["Notifications"])

# --- 启动 (用于本地调试) ---
if __name__ == "__main__":
    print("--- 警告：正在以调试模式启动 (非 Docker) ---")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)