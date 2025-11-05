# backend/db/queries_bots.py

import json
import uuid
import sqlite3
from typing import Optional, List, Dict
from shared.crypto_utils import generate_key_pair
from werkzeug.security import generate_password_hash

from backend.db.database import (
    LEDGER_LOCK, get_db_connection, _create_system_transaction,
    _generate_uid, _generate_secure_password, GENESIS_ACCOUNT
)

# +++ 核心修改: 移除了模块顶部的 BOT_LOGIC_MAP 和 get_random_chinese_name 导入 +++


def log_bot_action(bot_key: str, bot_username: str, action_type: str, message: str, data_snapshot: dict = None):
    # ... (此函数不变) ...
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            log_id = str(uuid.uuid4())
            data_json = json.dumps(data_snapshot, ensure_ascii=False) if data_snapshot else None
            
            cursor.execute(
                """
                INSERT INTO bot_logs (log_id, bot_key, bot_username, action_type, message, data_snapshot)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (log_id, bot_key, bot_username, action_type, message, data_json)
            )
            conn.commit()
        except Exception as e:
            print(f"!!!!!!!!!!!!!! 严重错误：无法将机器人日志写入数据库 !!!!!!!!!!!!!!")
            print(f"错误: {e}")
            conn.rollback()

def admin_get_bot_logs(bot_key: Optional[str] = None, limit: int = 100) -> List[dict]:
    # ... (此函数不变) ...
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                l.log_id, CAST(strftime('%s', l.timestamp) AS REAL) as timestamp, 
                l.bot_key, l.bot_username, l.action_type, l.message, l.data_snapshot,
                u.uid as bot_uid
            FROM bot_logs l
            LEFT JOIN users u ON l.bot_key = u.public_key
        """
        params = []
        
        if bot_key:
            query += " WHERE bot_key = ?"
            params.append(bot_key)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def admin_create_bot(username: Optional[str], bot_type: str, initial_funds: Optional[float], action_probability: Optional[float]) -> (bool, str, dict):
    """(修改) 管理员创建并供给一个机器人用户 (支持自动命名和默认配置)。"""
    
    # +++ 核心修改 1: 延迟导入以解决循环依赖 +++
    from backend.bots import BOT_LOGIC_MAP
    # (根据你的新机器人逻辑，决定从哪里导入)
    
    # --- 修改这里 ---
    # 导入两个命名函数
    from backend.bots.planet_bots import get_random_chinese_name as get_planet_name
    from backend.bots.bio_dna_bots import get_random_chinese_name as get_bio_dna_name
    # --- 修改结束 ---
    
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            # +++ 获取机器人配置默认值和中文名 +++
            BotClass = BOT_LOGIC_MAP.get(bot_type)
            if not BotClass:
                return False, "无效的机器人类型", None
                
            funds = initial_funds if initial_funds is not None else getattr(BotClass, 'DEFAULT_FUNDS', 1000.0)
            prob = action_probability if action_probability is not None else getattr(BotClass, 'DEFAULT_PROBABILITY', 0.1)
            if not username:
                if bot_type == "PlanetCapitalistBot":
                    username = get_planet_name(bot_type) 
                elif bot_type == "BIO_DNA_BOT":
                    username = get_bio_dna_name(bot_type) 
                else:
                    username = f"Bot_{bot_type}" 
                counter = 1
                base_username = username
                while True:
                    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                    if not cursor.fetchone():
                        break
                    username = f"{base_username}_{counter}"
                    counter += 1
            else:
                cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    return False, "用户名已存在", None
            # +++ 核心修改 2 结束 +++
            
            # ... (创建用户的剩余逻辑不变) ...
            private_key, public_key = generate_key_pair()
            bot_password = _generate_secure_password(20)
            password_hash = generate_password_hash(bot_password)
            
            while True:
                uid = f"BOT_{_generate_uid(4)}"
                cursor.execute("SELECT 1 FROM users WHERE uid = ?", (uid,))
                if not cursor.fetchone():
                    break
            
            cursor.execute(
                """
                INSERT INTO users 
                (public_key, uid, username, password_hash, invited_by, invitation_quota, private_key_pem, is_bot, bot_type, action_probability, is_active) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (public_key, uid, username, password_hash, "BOT_SYSTEM", 0, private_key, 1, bot_type, prob, 1)
            )
            cursor.execute("INSERT INTO user_profiles (public_key) VALUES (?)", (public_key,))
            cursor.execute("INSERT INTO balances (public_key, balance) VALUES (?, 0)", (public_key,))

            if funds > 0:
                success, detail = _create_system_transaction(
                    GENESIS_ACCOUNT, public_key, funds, f"机器人 ({bot_type}) 初始资金", conn
                )
                if not success:
                    conn.rollback()
                    return False, f"机器人 '{username}' 供给失败：无法发放初始资金。", None

            conn.commit()
            
            new_bot_info = {
                "public_key": public_key,
                "uid": uid,
                "username": username,
                "bot_type": bot_type,
                "is_active": True,
                "action_probability": prob,
                "balance": funds
            }
            return True, f"机器人 '{username}' 创建成功。", new_bot_info
            
        except sqlite3.IntegrityError:
            conn.rollback()
            return False, "用户名或UID已存在", None
        except Exception as e:
            conn.rollback()
            return False, f"机器人供给时发生严重错误: {e}", None

def get_all_bots(include_inactive=False) -> list:
    # ... (此函数不变) ...
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                u.public_key, u.uid, u.username, u.bot_type, u.is_active, 
                u.action_probability, u.private_key_pem,
                b.balance
            FROM users u
            LEFT JOIN balances b ON u.public_key = b.public_key
            WHERE u.is_bot = 1
        """
        if not include_inactive:
            query += " AND u.is_active = 1"
        
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def admin_set_bot_config(public_key: str, action_probability: float) -> (bool, str):
    # ... (此函数不变) ...
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET action_probability = ? WHERE public_key = ? AND is_bot = 1",
                (action_probability, public_key)
            )
            if cursor.rowcount == 0:
                return False, "未找到该机器人"
            conn.commit()
            return True, "机器人配置已更新"
        except Exception as e:
            conn.rollback()
            return False, f"更新机器人配置失败: {e}"

def get_bot_type_configs() -> Dict[str, dict]:
    """获取所有机器人类型的创建配置（资金、概率和中文名）。"""
    from backend.bots import BOT_LOGIC_MAP # +++ 核心修改 3: 延迟导入 +++
    configs = {}
    for bot_type, BotClass in BOT_LOGIC_MAP.items():
        configs[bot_type] = {
            "initial_funds": getattr(BotClass, 'DEFAULT_FUNDS', 1000.0),
            "action_probability": getattr(BotClass, 'DEFAULT_PROBABILITY', 0.1),
            "display_name": getattr(BotClass, 'CHINESE_DISPLAY_NAME', bot_type)
        }
    return configs