# backend/bots/bot_runner.py

import time
import asyncio
import random
from backend.bots import BOT_LOGIC_MAP
from backend.bots.bot_client import BotClient
from backend import ledger
import string
import secrets
API_BASE_URL = "http://backend:8000"

# --- 内部状态 ---
# { "bot_shop_0": {"client": BotClient, "logic": ShopEnthusiastBot_instance} }
_active_bots = {} 
# { "bot_shop_0": "generated_password" }
_bot_passwords = {}


def _generate_password(length=16):
    """生成一个临时的、安全的密码。"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))

async def provision_and_login_bots(config: dict):
    """
    (核心) 根据数据库配置，动态创建、登录和管理机器人实例。
    """
    global _active_bots, _bot_passwords
    
    desired_bots = {} # { "bot_username": "BotLogicClassName" }
    
    # 1. 根据配置构建期望的机器人列表
    for bot_type_name, bot_config in config.items():
        if bot_type_name in BOT_LOGIC_MAP:
            count = bot_config.get("count", 0)
            for i in range(count):
                username = f"bot_{bot_type_name.replace('Bot', '').lower()}_{i}"
                desired_bots[username] = bot_type_name

    # 2. 移除不再需要的机器人
    current_bot_names = set(_active_bots.keys())
    desired_bot_names = set(desired_bots.keys())
    
    bots_to_remove = current_bot_names - desired_bot_names
    for username in bots_to_remove:
        print(f"🤖 机器人 '{username}' 已被管理员禁用，正在移除...")
        del _active_bots[username]
        if username in _bot_passwords:
            del _bot_passwords[username]

    # 3. 供给并登录新机器人
    bots_to_add = desired_bot_names - current_bot_names
    for username in bots_to_add:
        bot_type_name = desired_bots[username]
        bot_logic_class = BOT_LOGIC_MAP[bot_type_name]
        
        # 生成或获取密码
        if username not in _bot_passwords:
            _bot_passwords[username] = _generate_password()
        
        password = _bot_passwords[username]
        
        # 自动在数据库中创建账户 (如果不存在)
        if not ledger.provision_bot_user(username, password, bot_type_name):
            print(f"❌ 无法为 '{username}' 供给账户，跳过该机器人。")
            continue
            
        # 创建客户端并登录
        client = BotClient(API_BASE_URL, username, password)
        if await client.login():
            _active_bots[username] = {
                "client": client,
                "logic": bot_logic_class(client) # 实例化机器人逻辑
            }
        else:
            print(f"❌ 机器人 '{username}' 登录失败，将在下一周期重试。")
            # 清除密码，以便下次尝试时重新供给 (以防密码被篡改)
            if username in _bot_passwords:
                del _bot_passwords[username]

def run_bot_loop():
    """
    机器人运行器的主循环（在单独的线程中运行）。
    """
    print("--- 机器人调度器启动 ---")
    
    # 0. 稍微等待 Uvicorn 服务器启动
    print(f"--- 机器人调度器：等待 {API_BASE_URL} 启动... ---")
    time.sleep(15) 
    
    # 为这个新线程设置自己的 asyncio 事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            # 1. 每次循环都从数据库读取最新配置
            config = ledger.get_bot_config()
            
            if not config.get("bot_system_enabled", False):
                if _active_bots:
                    print("--- 机器人系统已被管理员禁用，清空所有机器人... ---")
                    _active_bots.clear()
                    _bot_passwords.clear()
                
                print("--- 机器人系统已禁用，调度器休眠 60 秒... ---")
                time.sleep(60)
                continue

            # 2. 动态调整机器人实例 (登录/注销)
            loop.run_until_complete(provision_and_login_bots(config))
            
            if not _active_bots:
                print("--- 机器人系统已启用，但没有配置机器人实例。 ---")
                time.sleep(30)
                continue

            # 3. 概率性触发机器人动作
            check_interval = config.get("bot_check_interval_seconds", 30)
            print(f"\n--- 机器人回合开始 (T={time.strftime('%H:%M:%S')}) ---")
            
            tasks = []
            for username, bot_instance in _active_bots.items():
                logic_instance = bot_instance["logic"]
                bot_type_name = logic_instance.__class__.__name__
                
                bot_type_config = config.get(bot_type_name, {})
                probability = bot_type_config.get("action_probability", 0.1)
                
                # 核心：概率性触发
                if random.random() < probability:
                    print(f"🎲 机器人 '{username}' ({bot_type_name}) 触发行动 (概率: {probability*100}%)")
                    tasks.append(logic_instance.execute_turn())
            
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            
            print(f"--- 机器人回合结束。下一周期检查在 {check_interval} 秒后 ---")
            time.sleep(check_interval)

        except Exception as e:
            print(f"❌ 机器人主循环出错: {e}")
            time.sleep(60) # 发生错误时，延长休眠时间