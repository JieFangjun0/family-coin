# backend/main.py

from fastapi import FastAPI
import asyncio
import uvicorn
from backend.db.database import init_db
# 导入所有 API 路由模块 (让它们先被加载和注册)
from backend.api import routes_system
from backend.api import routes_user
from backend.api import routes_friends
from backend.api import routes_nft
from backend.api import routes_market
from backend.api import routes_admin
from backend.api import routes_notifications

from backend.bots import bot_runner



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
    print("正在启动 API ... 初始化数据库...")
    init_db()
    
    print("--- API 启动：正在启动后台机器人调度器任务... ---")
    asyncio.create_task(bot_runner.run_bot_loop())
    print("--- API 启动：机器人任务已启动。 ---")

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