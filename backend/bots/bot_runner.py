# backend/bots/bot_runner.py

import time
import asyncio
import random
from backend.bots import BOT_LOGIC_MAP
from backend.bots.bot_client import BotClient
from backend import ledger

API_BASE_URL = "http://backend:8000"

# --- 内部状态 (重构) ---
# { "public_key_abc": {"client": BotClient, "logic": ShopEnthusiastBot_instance, "info": {...db_row...}} }
_active_bots = {} 

async def update_active_bots():
    """
    (重构) 根据数据库，动态创建和管理机器人实例。
    """
    global _active_bots
    
    try:
        # 1. 从数据库获取所有激活的机器人
        # (这是一个IO调用，但在
# 循环中是可接受的)
        active_db_bots_list = ledger.get_all_bots(include_inactive=False)
        active_db_bots = {bot['public_key']: bot for bot in active_db_bots_list}
        
    except Exception as e:
        print(f"❌ Bot Runner: 无法从数据库获取机器人列表: {e}")
        # 清空所有机器人以防万一
        _active_bots.clear()
        return

    current_bot_keys = set(_active_bots.keys())
    desired_bot_keys = set(active_db_bots.keys())

    # 2. 移除 (停用) 的机器人
    bots_to_remove = current_bot_keys - desired_bot_keys
    for key in bots_to_remove:
        print(f"🤖 机器人 '{_active_bots[key]['info']['username']}' 已被禁用或删除，正在停止...")
        del _active_bots[key]

    # 3. 供给并登录新机器人
    bots_to_add = desired_bot_keys - current_bot_keys
    for key in bots_to_add:
        bot_info = active_db_bots[key]
        username = bot_info['username']
        bot_type_name = bot_info['bot_type']
        
        if bot_type_name not in BOT_LOGIC_MAP:
            print(f"⚠️ 警告: 机器人 '{username}' 的类型 '{bot_type_name}' 在 BOT_LOGIC_MAP 中未注册，跳过。")
            continue
            
        bot_logic_class = BOT_LOGIC_MAP[bot_type_name]
        
        try:
            # (核心重构) 直接使用私钥初始化客户端，不再需要登录
            client = BotClient(
                base_url=API_BASE_URL,
                username=username,
                public_key=bot_info['public_key'],
                private_key_pem=bot_info['private_key_pem']
            )
            
            _active_bots[key] = {
                "client": client,
                "logic": bot_logic_class(client), # 实例化机器人逻辑
                "info": bot_info # 存储数据库信息 (包含概率)
            }
            print(f"✅ 机器人 '{username}' (类型: {bot_type_name}) 已激活。")
            
        except Exception as e:
            print(f"❌ 激活机器人 '{username}' 失败: {e}")


def run_bot_loop():
    """
    机器人运行器的主循环（在单独的线程中运行）。
    """
    print("--- 机器人调度器 (V2) 启动 ---")
    
    # 0. 稍微等待 Uvicorn 服务器启动
    print(f"--- 机器人调度器：等待 {API_BASE_URL} 启动... ---")
    time.sleep(15) 
    
    # 为这个新线程设置自己的 asyncio 事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    check_interval = 30 # 默认 30 秒
    
    while True:
        try:
            # +++ (新增) 1. 从数据库读取宏观设置 +++
            try:
                # (这是同步函数，但在此线程循环中是允许的)
                enabled_str = ledger.get_setting("bot_system_enabled")
                interval_str = ledger.get_setting("bot_check_interval_seconds")
                
                bot_system_enabled = enabled_str == 'True'
                check_interval = int(interval_str) if interval_str else 30
                
                if not bot_system_enabled:
                    print(f"--- 机器人系统：系统在设置中被禁用。将在 {check_interval} 秒后重试... ---")
                    if _active_bots:
                         _active_bots.clear() # 清空内存中的机器人
                    time.sleep(check_interval)
                    continue
                    
            except Exception as e:
                print(f"❌ Bot Runner: 无法从数据库读取全局配置: {e}。使用默认值。")
                check_interval = 30
            # +++ 新增结束 +++

            # 1. (新增) 在机器人回合开始前，先结算一次拍卖
            print(f"--- 机器人回合：正在结算已结束的拍卖... ---")
            try:
                resolved_count = ledger.resolve_finished_auctions()
                if resolved_count > 0:
                    print(f"--- 机器人回合：成功结算了 {resolved_count} 场拍卖。 ---")
            except Exception as e:
                print(f"❌ Bot Runner: 结算拍卖时出错: {e}")

            # 2. 动态调整机器人实例 (登录/注销)
            loop.run_until_complete(update_active_bots())
            
            if not _active_bots:
                print("--- 机器人系统：没有已激活的机器人实例。 ---")
                time.sleep(check_interval)
                continue

            # 3. 概率性触发机器人动作
            print(f"\n--- 机器人回合开始 (T={time.strftime('%H:%M:%S')}) ---")
            
            tasks = []
            for key, bot_instance in _active_bots.items():
                logic_instance = bot_instance["logic"]
                bot_info = bot_instance["info"]
                
                probability = bot_info.get("action_probability", 0.1)
                
                # 核心：概率性触发
                if random.random() < probability:
                    print(f"🎲 机器人 '{bot_info['username']}' 触发行动 (概率: {probability*100}%)")
                    tasks.append(logic_instance.execute_turn())
            
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            
            print(f"--- 机器人回合结束。下一周期检查在 {check_interval} 秒后 ---")
            time.sleep(check_interval)

        except Exception as e:
            print(f"❌ 机器人主循环出错: {e}")
            time.sleep(60) # 发生错误时，延长休眠时间