# backend/db/queries_user.py

import time
import json
import sqlite3
from typing import Optional, List
from werkzeug.security import generate_password_hash, check_password_hash
from shared.crypto_utils import verify_signature, generate_key_pair

from backend.db.database import (
    LEDGER_LOCK, get_db_connection, _create_system_transaction,
    _generate_uid, _generate_secure_password, get_setting,
    GENESIS_ACCOUNT, BURN_ACCOUNT, ESCROW_ACCOUNT, DEFAULT_INVITATION_QUOTA
)

# --- 余额 ---

def get_balance(public_key: str) -> float:
    """查询指定公钥的余额。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (public_key,))
        result = cursor.fetchone()
        return result['balance'] if result else 0.0

# --- 用户注册与认证 ---

def register_user(username: str, password: str, invitation_code: str) -> (bool, str, dict):
    """注册一个新用户，需要一次性邀请码。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT generated_by, CAST(strftime('%s', created_at) AS REAL) as created_at_unix
                FROM invitation_codes 
                WHERE code = ? AND is_used = 0
                """,
                (invitation_code,)
            )
            code_data = cursor.fetchone()
            
            if not code_data:
                return False, "无效的邀请码或邀请码已被使用", {}
            
            if (time.time() - code_data['created_at_unix']) > 86400 * 7: # 7 days validity
                return False, "邀请码已过期", {}
                
            inviter_key = code_data['generated_by']
            
            private_key, public_key = generate_key_pair()
            password_hash = generate_password_hash(password)
            
            while True:
                uid = _generate_uid()
                cursor.execute("SELECT 1 FROM users WHERE uid = ?", (uid,))
                if not cursor.fetchone():
                    break
            
            default_quota_str = get_setting('default_invitation_quota')
            default_quota = int(default_quota_str) if default_quota_str and default_quota_str.isdigit() else DEFAULT_INVITATION_QUOTA
            
            cursor.execute(
                "INSERT INTO users (public_key, uid, username, password_hash, invited_by, invitation_quota, private_key_pem) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (public_key, uid, username, password_hash, inviter_key, default_quota, private_key)
            )
            
            cursor.execute("INSERT INTO user_profiles (public_key) VALUES (?)", (public_key,))
            cursor.execute("INSERT INTO balances (public_key, balance) VALUES (?, 0)", (public_key,))
            
            # 发放新用户奖励
            welcome_bonus_str = get_setting('welcome_bonus_amount')
            if welcome_bonus_str:
                try:
                    bonus_amount = float(welcome_bonus_str)
                    if bonus_amount > 0:
                        _create_system_transaction(
                            from_key=GENESIS_ACCOUNT, to_key=public_key,
                            amount=bonus_amount, note="新用户注册奖励", conn=conn
                        )
                except (ValueError, TypeError): pass 
            
            # 发放邀请人奖励
            inviter_bonus_str = get_setting('inviter_bonus_amount')
            if inviter_bonus_str:
                try:
                    inviter_bonus_amount = float(inviter_bonus_str)
                    if inviter_bonus_amount > 0 and inviter_key != GENESIS_ACCOUNT:
                        _create_system_transaction(
                            from_key=GENESIS_ACCOUNT, to_key=inviter_key,
                            amount=inviter_bonus_amount, note=f"成功邀请新用户: {username}", conn=conn
                        )
                except (ValueError, TypeError): pass
            
            cursor.execute(
                "UPDATE invitation_codes SET is_used = 1, used_by = ? WHERE code = ?",
                (public_key, invitation_code)
            )

            # 自动添加好友
            if inviter_key != GENESIS_ACCOUNT:
                user1, user2 = sorted([public_key, inviter_key])
                cursor.execute(
                    "INSERT INTO friendships (user1_key, user2_key, status, action_user_key) VALUES (?, ?, 'ACCEPTED', ?)",
                    (user1, user2, inviter_key)
                )
            
            conn.commit()
            return True, "注册成功！", {"uid": uid, "username": username, "public_key": public_key}
            
        except sqlite3.IntegrityError:
            conn.rollback()
            return False, "用户名或UID已存在", {}
        except Exception as e:
            conn.rollback()
            return False, f"注册时发生未知错误: {e}", {}

def authenticate_user(username_or_uid: str, password: str) -> (bool, str, dict):
    """使用用户名/UID和密码进行身份验证。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT public_key, username, uid, password_hash, private_key_pem, is_active FROM users WHERE (username = ? OR uid = ?) AND is_bot = 0",
            (username_or_uid, username_or_uid)
        )
        user = cursor.fetchone()

        if not user:
            return False, "用户不存在", {}
        
        user_dict = dict(user)

        if not user_dict['is_active']:
            return False, "该账户已被禁用", {}

        if not check_password_hash(user_dict['password_hash'], password):
            return False, "密码错误", {}
            
        return True, "登录成功", {
            "public_key": user_dict['public_key'],
            "private_key": user_dict['private_key_pem'],
            "username": user_dict['username'],
            "uid": user_dict['uid']
        }

# --- 用户信息与资料 ---

def get_user_details(public_key: str, conn=None) -> dict:
    """获取用户的详细信息。"""
    def run_logic(connection):
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                u.public_key, u.uid, u.username,
                CAST(strftime('%s', u.created_at) AS REAL) as created_at,
                u.invitation_quota, u.invited_by, u.is_active,
                (SELECT inviter.username FROM users inviter WHERE inviter.public_key = u.invited_by) as inviter_username,
                (SELECT inviter.uid FROM users inviter WHERE inviter.public_key = u.invited_by) as inviter_uid
            FROM users u
            WHERE u.public_key = ?
            """,
            (public_key,)
        )
        user_details = cursor.fetchone()
        if not user_details: return None

        user_dict = dict(user_details)
        user_dict['is_active'] = bool(user_dict['is_active'])
        
        if user_dict['invited_by'] == 'GENESIS':
            user_dict['inviter_username'] = '--- 系统 ---'
            user_dict['inviter_uid'] = None
        if user_dict['invited_by'] == 'BOT_SYSTEM':
            user_dict['inviter_username'] = '--- 机器人 ---'
            user_dict['inviter_uid'] = None

        cursor.execute(
            "SELECT COUNT(*) as tx_count FROM transactions WHERE from_key = ? OR to_key = ?",
            (public_key, public_key)
        )
        user_dict['tx_count'] = cursor.fetchone()['tx_count']
        return user_dict

    if conn:
        return run_logic(conn)
    else:
        with get_db_connection() as new_conn:
            return run_logic(new_conn)

def get_all_active_users() -> list:
    """获取所有活跃的人类用户列表。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, public_key, uid FROM users WHERE is_active = 1 AND is_bot = 0 ORDER BY username")
        return [dict(row) for row in cursor.fetchall()]

def get_user_profile(uid_or_username: str) -> dict:
    """获取用户的公开个人主页信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT u.uid, u.username, u.public_key, CAST(strftime('%s', u.created_at) AS REAL) as created_at,
                   p.signature, p.displayed_nfts
            FROM users u
            LEFT JOIN user_profiles p ON u.public_key = p.public_key
            WHERE u.uid = ? OR u.username = ?
            """,
            (uid_or_username, uid_or_username)
        )
        user_profile = cursor.fetchone()
        if not user_profile: return None
            
        profile_dict = dict(user_profile)
        
        displayed_nfts_ids = json.loads(profile_dict.get('displayed_nfts') or '[]')
        nfts_details = []
        if displayed_nfts_ids:
            placeholders = ','.join('?' for _ in displayed_nfts_ids)
            query = f"""
                SELECT nft_id, owner_key, nft_type, data, status
                FROM nfts WHERE nft_id IN ({placeholders}) AND owner_key = ? AND status = 'ACTIVE'
            """
            cursor.execute(query, displayed_nfts_ids + [profile_dict['public_key']])
            for row in cursor.fetchall():
                nft_dict = dict(row)
                nft_dict['data'] = json.loads(nft_dict['data'])
                nfts_details.append(nft_dict)
        
        profile_dict['displayed_nfts_details'] = nfts_details
        return profile_dict

def update_user_profile(public_key: str, signature: str, displayed_nfts: list) -> (bool, str):
    """更新用户的个人主页信息。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            if displayed_nfts:
                placeholders = ','.join('?' for _ in displayed_nfts)
                query = f"SELECT COUNT(*) FROM nfts WHERE nft_id IN ({placeholders}) AND owner_key = ?"
                cursor.execute(query, displayed_nfts + [public_key])
                count = cursor.fetchone()[0]
                if count != len(displayed_nfts):
                    return False, "一个或多个所选的NFT不属于你或不存在"

            displayed_nfts_json = json.dumps(displayed_nfts)
            
            cursor.execute(
                "INSERT OR REPLACE INTO user_profiles (public_key, signature, displayed_nfts, updated_at) VALUES (?, ?, ?, ?)",
                (public_key, signature, displayed_nfts_json, time.time())
            )
            
            conn.commit()
            return True, "个人主页更新成功"
        except Exception as e:
            conn.rollback()
            return False, f"更新个人主页失败: {e}"

# --- 交易 ---

def get_transaction_history(public_key: str) -> list:
    """获取与某个公钥相关的所有交易记录。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                tx_id, from_key, to_key, amount, timestamp, 'out' as type, note,
                (SELECT username FROM users WHERE public_key = T.from_key) as from_username,
                (SELECT uid FROM users WHERE public_key = T.from_key) as from_uid,
                (SELECT username FROM users WHERE public_key = T.to_key) as to_username,
                (SELECT uid FROM users WHERE public_key = T.to_key) as to_uid
            FROM transactions T WHERE from_key = ?
            UNION ALL
            SELECT 
                tx_id, from_key, to_key, amount, timestamp, 'in' as type, note,
                (SELECT username FROM users WHERE public_key = T.from_key) as from_username,
                (SELECT uid FROM users WHERE public_key = T.from_key) as from_uid,
                (SELECT username FROM users WHERE public_key = T.to_key) as to_username,
                (SELECT uid FROM users WHERE public_key = T.to_key) as to_uid
            FROM transactions T WHERE to_key = ?
            ORDER BY timestamp DESC
            """,
            (public_key, public_key)
        )
        
        def format_username(key, username):
            if key == GENESIS_ACCOUNT: return "⭐ 系统铸币"
            if key == BURN_ACCOUNT: return "🔥 系统销毁"
            if key == ESCROW_ACCOUNT: return "🔒 系统托管"
            return username or f"{key[:10]}... (已清除)"

        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            row_dict['from_display'] = format_username(row_dict['from_key'], row_dict['from_username'])
            row_dict['to_display'] = format_username(row_dict['to_key'], row_dict['to_username'])
            results.append(row_dict)
            
        return results

def process_transaction(
    from_key: str, to_key: str, amount: float, 
    message_json: str, signature: str, note: str = None
) -> (bool, str):
    """处理一笔用户间的交易。"""
    if amount <= 0: return False, "转账金额必须大于0"
    if from_key == to_key: return False, "不能给自己转账"
    
    try:
        message = json.loads(message_json)
    except json.JSONDecodeError:
        return False, "无效的消息格式"

    if not verify_signature(from_key, message, signature): return False, "签名无效"
    if (time.time() - message.get('timestamp', 0)) > 300: return False, "交易已过期"

    with LEDGER_LOCK, get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM users WHERE public_key = ? AND is_active = 1", (to_key,))
        if not cursor.fetchone(): return False, "收款方用户不存在或已被禁用"
            
        cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (from_key,))
        from_balance = cursor.fetchone()
        if not from_balance or from_balance['balance'] < amount: return False, "余额不足"
        
        try:
            new_from_balance = from_balance['balance'] - amount
            cursor.execute("UPDATE balances SET balance = ? WHERE public_key = ?", (new_from_balance, from_key))
            
            cursor.execute("UPDATE balances SET balance = balance + ? WHERE public_key = ?", (amount, to_key))
            
            tx_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO transactions (tx_id, from_key, to_key, amount, timestamp, message_json, signature, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tx_id, from_key, to_key, amount, message['timestamp'], message_json, signature, note)
            )
            
            conn.commit()
            return True, "交易成功"
        except Exception as e:
            conn.rollback()
            return False, f"交易失败: {e}"

# --- 邀请 ---

def generate_invitation_code(generator_key: str) -> (bool, str):
    """消耗1个邀请额度，生成一个新的一次性邀请码。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT invitation_quota FROM users WHERE public_key = ? AND is_active = 1", (generator_key,))
            user = cursor.fetchone()
            
            if not user: return False, "未找到用户"
            if user['invitation_quota'] <= 0: return False, "邀请额度不足"

            cursor.execute("UPDATE users SET invitation_quota = invitation_quota - 1 WHERE public_key = ?", (generator_key,))
            
            while True:
                new_code = uuid.uuid4().hex[:8].upper()
                try:
                    cursor.execute("INSERT INTO invitation_codes (code, generated_by) VALUES (?, ?)", (new_code, generator_key))
                    break
                except sqlite3.IntegrityError:
                    continue
            
            conn.commit()
            return True, new_code
        except Exception as e:
            conn.rollback()
            return False, f"生成邀请码失败: {e}"

def get_my_invitation_codes(public_key: str) -> list:
    """获取用户所有未使用的邀请码。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT code, CAST(strftime('%s', created_at) AS REAL) as created_at
            FROM invitation_codes WHERE generated_by = ? AND is_used = 0
            ORDER BY created_at DESC
            """,
            (public_key,)
        )
        return [dict(row) for row in cursor.fetchall()]

# --- 好友系统 ---

def get_friendship_status(user_a_key: str, user_b_key: str) -> dict:
    """检查两个用户之间的好友关系状态。"""
    if user_a_key == user_b_key:
        return {"status": "SELF"}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        user1, user2 = sorted([user_a_key, user_b_key])
        cursor.execute(
            "SELECT status, action_user_key FROM friendships WHERE user1_key = ? AND user2_key = ?",
            (user1, user2)
        )
        result = cursor.fetchone()
        if not result:
            return {"status": "NONE"}
        
        return {
            "status": result['status'],
            "action_user_key": result['action_user_key']
        }

def send_friend_request(requester_key: str, target_key: str) -> (bool, str):
    """发送一个好友请求。"""
    if requester_key == target_key:
        return False, "不能添加自己为好友"

    status_info = get_friendship_status(requester_key, target_key)
    if status_info['status'] != 'NONE':
        return False, f"无法发送请求，当前状态: {status_info['status']}"

    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            user1, user2 = sorted([requester_key, target_key])
            cursor.execute(
                "INSERT INTO friendships (user1_key, user2_key, status, action_user_key) VALUES (?, ?, 'PENDING', ?)",
                (user1, user2, requester_key)
            )
            conn.commit()
            return True, "好友请求已发送"
        except Exception as e:
            conn.rollback()
            return False, f"发送请求失败: {e}"

def respond_to_friend_request(responder_key: str, requester_key: str, accept: bool) -> (bool, str):
    """回应一个好友请求。"""
    status_info = get_friendship_status(responder_key, requester_key)
    if status_info.get('status') != 'PENDING' or status_info.get('action_user_key') != requester_key:
        return False, "不存在来自该用户的有效好友请求"
        
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            user1, user2 = sorted([responder_key, requester_key])
            if accept:
                cursor.execute(
                    "UPDATE friendships SET status = 'ACCEPTED' WHERE user1_key = ? AND user2_key = ?",
                    (user1, user2)
                )
                message = "已接受好友请求"
            else:
                cursor.execute(
                    "DELETE FROM friendships WHERE user1_key = ? AND user2_key = ?",
                    (user1, user2)
                )
                message = "已拒绝好友请求"
            conn.commit()
            return True, message
        except Exception as e:
            conn.rollback()
            return False, f"处理请求失败: {e}"

def delete_friend(deleter_key: str, friend_to_delete_key: str) -> (bool, str):
    """单方面删除好友。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            user1, user2 = sorted([deleter_key, friend_to_delete_key])
            cursor.execute(
                "DELETE FROM friendships WHERE user1_key = ? AND user2_key = ? AND status = 'ACCEPTED'",
                (user1, user2)
            )
            if cursor.rowcount == 0:
                return False, "你们不是好友关系"
            conn.commit()
            return True, "好友已删除"
        except Exception as e:
            conn.rollback()
            return False, f"删除好友失败: {e}"

def get_friends(public_key: str) -> list:
    """获取一个用户的所有好友列表。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT u.public_key, u.username, u.uid
            FROM users u
            JOIN (
                SELECT CASE
                           WHEN user1_key = :pk THEN user2_key
                           ELSE user1_key
                       END AS friend_key
                FROM friendships
                WHERE (user1_key = :pk OR user2_key = :pk) AND status = 'ACCEPTED'
            ) f ON u.public_key = f.friend_key
            WHERE u.is_active = 1
            ORDER BY u.username;
        """
        cursor.execute(query, {"pk": public_key})
        return [dict(row) for row in cursor.fetchall()]

def get_friend_requests(public_key: str) -> list:
    """获取收到的好友请求列表。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT u.public_key, u.username, u.uid, f.created_at
            FROM users u
            JOIN friendships f ON u.public_key = f.action_user_key
            WHERE ((f.user1_key = :pk OR f.user2_key = :pk) AND f.status = 'PENDING' AND f.action_user_key != :pk)
            ORDER BY f.created_at DESC;
        """
        cursor.execute(query, {"pk": public_key})
        return [dict(row) for row in cursor.fetchall()]