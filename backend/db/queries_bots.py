# backend/db/queries_bots.py

import json
import uuid
import sqlite3
from typing import Optional, List
from shared.crypto_utils import generate_key_pair
from werkzeug.security import generate_password_hash

from backend.db.database import (
    LEDGER_LOCK, get_db_connection, _create_system_transaction,
    _generate_uid, _generate_secure_password, GENESIS_ACCOUNT
)

def log_bot_action(bot_key: str, bot_username: str, action_type: str, message: str, data_snapshot: dict = None):
    """
    (线程安全) 将机器人的操作记录到数据库。
    """
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
            print(f"日志内容: [{bot_username}/{action_type}] {message}")
            conn.rollback()

def admin_get_bot_logs(bot_key: Optional[str] = None, limit: int = 100) -> List[dict]:
    """(管理员功能) 从数据库获取最新的机器人日志。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT log_id, CAST(strftime('%s', timestamp) AS REAL) as timestamp, 
                   bot_key, bot_username, action_type, message, data_snapshot
            FROM bot_logs
        """
        params = []
        
        if bot_key:
            query += " WHERE bot_key = ?"
            params.append(bot_key)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def admin_create_bot(username: Optional[str], bot_type: str, initial_funds: float, action_probability: float) -> (bool, str, dict):
    """(修改) 管理员创建并供给一个机器人用户 (支持自动命名)。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            if not username:
                base_name_prefix = bot_type.replace('Bot', '').upper()
                while True:
                    username = f"BOT_{base_name_prefix}_{_generate_uid(3)}"
                    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                    if not cursor.fetchone():
                        break
            else:
                cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    return False, "用户名已存在", None
            
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
                (public_key, uid, username, password_hash, "BOT_SYSTEM", 0, private_key, 1, bot_type, action_probability, 1)
            )
            cursor.execute("INSERT INTO user_profiles (public_key) VALUES (?)", (public_key,))
            cursor.execute("INSERT INTO balances (public_key, balance) VALUES (?, 0)", (public_key,))

            if initial_funds > 0:
                success, detail = _create_system_transaction(
                    GENESIS_ACCOUNT, public_key, initial_funds, f"机器人 ({bot_type}) 初始资金", conn
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
                "action_probability": action_probability,
                "balance": initial_funds
            }
            return True, f"机器人 '{username}' 创建成功。", new_bot_info
            
        except sqlite3.IntegrityError:
            conn.rollback()
            return False, "用户名或UID已存在", None
        except Exception as e:
            conn.rollback()
            return False, f"机器人供给时发生严重错误: {e}", None

def get_all_bots(include_inactive=False) -> list:
    """获取所有被标记为机器人的用户。"""
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
    """更新一个机器人的配置。"""
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