# backend/db/queries_system.py

import os
from werkzeug.security import generate_password_hash
from backend.db.database import (
    LEDGER_LOCK, get_db_connection, _create_system_transaction,
    DATABASE_PATH, GENESIS_ACCOUNT, BURN_ACCOUNT, init_db
)
# 导入市场查询是为了 admin_purge_user
from backend.db.queries_market import cancel_market_listing_in_tx

def count_users() -> int:
    """统计数据库中的用户总数。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        return result[0] if result else 0

def create_genesis_user(username: str, password: str) -> (bool, str, dict):
    """创建第一个（创世）管理员用户。"""
    if count_users() > 0:
        return False, "系统已经初始化，无法创建创世用户。", {}

    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            # Note: crypto_utils is not in db layer, so we import it here
            from shared.crypto_utils import generate_key_pair
            private_key, public_key = generate_key_pair()
            password_hash = generate_password_hash(password)
            uid = "000"
            inv_quota = 999999

            cursor.execute(
                "INSERT INTO users (public_key, uid, username, password_hash, invited_by, invitation_quota, private_key_pem) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (public_key, uid, username, password_hash, "GENESIS", inv_quota, private_key)
            )
            cursor.execute("INSERT INTO user_profiles (public_key) VALUES (?)", (public_key,))
            cursor.execute("INSERT INTO balances (public_key, balance) VALUES (?, 0)", (public_key,))

            conn.commit()
            return True, "创世管理员创建成功！", {"uid": uid, "username": username, "public_key": public_key, "private_key": private_key}
        except Exception as e:
            conn.rollback()
            return False, f"创建创世用户失败: {e}", {}

def get_all_balances(include_inactive=False) -> list:
    """(管理员功能) 获取所有人类用户的余额和邀请信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                u.username, u.uid, b.public_key, b.balance, u.is_active,
                u.invitation_quota, u.invited_by, inviter.username as inviter_username
            FROM users u
            JOIN balances b ON u.public_key = b.public_key
            LEFT JOIN users inviter ON u.invited_by = inviter.public_key
            WHERE u.is_bot = 0
        """
        if not include_inactive:
            query += " AND u.is_active = 1"
        query += " ORDER BY u.created_at"
        
        cursor.execute(query)
        
        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            if row_dict['invited_by'] == 'GENESIS':
                row_dict['inviter_username'] = '--- 创世用户 ---'
            elif row_dict['inviter_username'] is None and row_dict['invited_by']:
                row_dict['inviter_username'] = f"未知 ({row_dict['invited_by'][:10]}...)"
            results.append(row_dict)
            
        return results

def admin_issue_coins(to_key: str, amount: float, note: str = None) -> (bool, str):
    """(管理员功能) 增发货币。"""
    if amount <= 0: return False, "发行金额必须大于0"
    return _create_system_transaction(GENESIS_ACCOUNT, to_key, amount, note or "管理员增发")

def admin_multi_issue_coins(targets: list, note: str = None) -> (bool, str):
    """(管理员功能) 批量增发货币。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            valid_targets = [t for t in targets if t.get('key') and isinstance(t.get('amount'), (int, float)) and t.get('amount') > 0]
            if not valid_targets:
                return False, "提供的目标用户列表无效或为空"

            for target in valid_targets:
                to_key = target.get('key')
                amount = target.get('amount')
                
                # We need the internal logic function here
                from backend.db.database import _execute_system_tx_logic
                success, detail = _execute_system_tx_logic(
                    from_key=GENESIS_ACCOUNT, 
                    to_key=to_key, 
                    amount=amount, 
                    note=note or "管理员批量增发", 
                    conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"为用户 {to_key[:10]}... 发行失败: {detail}"
            conn.commit()
            return True, f"成功为 {len(valid_targets)} 个用户批量发行货币。"
        except Exception as e:
            conn.rollback()
            return False, f"批量发行时发生数据库错误: {e}"

def admin_burn_coins(from_key: str, amount: float, note: str = None) -> (bool, str):
    """(管理员功能) 销毁货币。"""
    if amount <= 0: return False, "销毁金额必须大于0"
    return _create_system_transaction(from_key, BURN_ACCOUNT, amount, note or "管理员减持")

def admin_set_user_active_status(public_key: str, is_active: bool) -> (bool, str):
    """(管理员功能) 启用或禁用一个用户。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = ? WHERE public_key = ?", (int(is_active), public_key))
            if cursor.rowcount == 0: return False, "未找到用户"
            conn.commit()
            status_text = "启用" if is_active else "禁用"
            return True, f"成功{status_text}用户 {public_key[:10]}..."
        except Exception as e:
            conn.rollback()
            return False, f"更新用户状态失败: {e}"

def admin_purge_user(public_key: str) -> (bool, str):
    """(管理员功能) 彻底清除一个用户的数据以释放用户名。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (public_key,))
            balance_row = cursor.fetchone()
            if not balance_row: 
                return False, "用户不存在"
            
            current_balance = balance_row['balance']

            if current_balance > 0:
                from backend.db.database import _execute_system_tx_logic
                success, detail = _execute_system_tx_logic(
                    from_key=public_key, to_key=BURN_ACCOUNT, amount=current_balance,
                    note=f"彻底清除用户 {public_key[:10]}... 并清零资产", conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"清除用户时清零资产失败: {detail}"

            cursor.execute("SELECT listing_id FROM market_listings WHERE lister_key = ? and status = 'ACTIVE'", (public_key,))
            user_listings = cursor.fetchall()
            for listing in user_listings:
                # 调用事务安全函数并传入当前连接
                _success, _detail = cancel_market_listing_in_tx(conn, public_key, listing['listing_id'])
                if not _success:
                    # 仍然只是打印警告，而不是中止整个清除过程
                    print(f"Warning: Purging user, failed to cancel listing {listing['listing_id']}: {_detail}")

            cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE listing_id IN (SELECT listing_id FROM market_listings WHERE lister_key = ?) AND status = 'PENDING'", (public_key,))
            cursor.execute("DELETE FROM market_offers WHERE offerer_key = ?", (public_key,))
            cursor.execute("UPDATE nfts SET status = 'BURNED' WHERE owner_key = ?", (public_key,))
            cursor.execute("DELETE FROM invitation_codes WHERE generated_by = ? OR used_by = ?", (public_key, public_key))
            cursor.execute("DELETE FROM friendships WHERE user1_key = ? OR user2_key = ?", (public_key, public_key))
            cursor.execute("DELETE FROM user_profiles WHERE public_key = ?", (public_key,))
            cursor.execute("DELETE FROM balances WHERE public_key = ?", (public_key,))
            cursor.execute("DELETE FROM users WHERE public_key = ?", (public_key,))

            conn.commit()
            return True, f"用户 {public_key[:10]}... 已被彻底清除，用户名已释放。"
        except Exception as e:
            conn.rollback()
            return False, f"清除用户失败: {e}"

def admin_adjust_user_quota(public_key: str, new_quota: int) -> (bool, str):
    """(管理员功能) 调整特定用户的邀请额度。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET invitation_quota = ? WHERE public_key = ?", (new_quota, public_key))
            if cursor.rowcount == 0: return False, "未找到用户"
            conn.commit()
            return True, f"成功设置用户 {public_key[:10]}... 的邀请额度为 {new_quota}"
        except Exception as e:
            conn.rollback()
            return False, f"更新额度失败: {e}"

def admin_reset_user_password(public_key: str, new_password: str) -> (bool, str):
    """(管理员功能) 重置用户的密码。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            new_password_hash = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE public_key = ?",
                (new_password_hash, public_key)
            )
            if cursor.rowcount == 0:
                return False, "未找到用户"
            conn.commit()
            return True, f"成功重置用户 {public_key[:10]}... 的密码"
        except Exception as e:
            conn.rollback()
            return False, f"重置密码失败: {e}"

def nuke_database() -> (bool, str):
    """(管理员功能) 彻底删除数据库文件并重建。"""
    with LEDGER_LOCK:
        try:
            if os.path.exists(DATABASE_PATH):
                os.remove(DATABASE_PATH)
            
            init_db() # Re-initialize
            
            return True, "数据库已重置并重建。"
        except Exception as e:
            return False, f"重置数据库失败: {e}"