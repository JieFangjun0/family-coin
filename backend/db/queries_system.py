# backend/db/queries_system.py

import psycopg2.errors
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash
from backend.db.database import (
    get_db_connection, _create_system_transaction,
    GENESIS_ACCOUNT, BURN_ACCOUNT, init_db
)
# 导入市场查询是为了 admin_purge_user
from backend.db.queries_market import cancel_market_listing_in_tx

def count_users() -> int:
    """统计数据库中的用户总数。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            result = cursor.fetchone()
            return result[0] if result else 0

def create_genesis_user(username: str, password: str) -> (bool, str, dict):
    """创建第一个（创世）管理员用户。"""
    if count_users() > 0:
        return False, "系统已经初始化，无法创建创世用户。", {}

    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                
                # Note: crypto_utils is not in db layer, so we import it here
                from shared.crypto_utils import generate_key_pair
                private_key, public_key = generate_key_pair()
                password_hash = generate_password_hash(password)
                uid = "000"
                inv_quota = 999999

                cursor.execute(
                    "INSERT INTO users (public_key, uid, username, password_hash, invited_by, invitation_quota, private_key_pem) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (public_key, uid, username, password_hash, "GENESIS", inv_quota, private_key)
                )
                cursor.execute("INSERT INTO user_profiles (public_key) VALUES (%s)", (public_key,))
                cursor.execute("INSERT INTO balances (public_key, balance) VALUES (%s, 0)", (public_key,))

            conn.commit()
            return True, "创世管理员创建成功！", {"uid": uid, "username": username, "public_key": public_key, "private_key": private_key}
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return False, "创建创世用户失败：用户名或UID已存在", {}
        except Exception as e:
            conn.rollback()
            return False, f"创建创世用户失败: {e}", {}

def get_all_balances(include_inactive=False) -> list:
    """(管理员功能) 获取所有人类用户的余额和邀请信息。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT 
                    u.username, u.uid, b.public_key, b.balance, u.is_active,
                    u.invitation_quota, u.invited_by, inviter.username as inviter_username
                FROM users u
                JOIN balances b ON u.public_key = b.public_key
                LEFT JOIN users inviter ON u.invited_by = inviter.public_key
                WHERE u.is_bot = FALSE
            """
            if not include_inactive:
                query += " AND u.is_active = TRUE"
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
    with get_db_connection() as conn:
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
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("UPDATE users SET is_active = %s WHERE public_key = %s", (is_active, public_key))
                if cursor.rowcount == 0: return False, "未找到用户"
            conn.commit()
            status_text = "启用" if is_active else "禁用"
            return True, f"成功{status_text}用户 {public_key[:10]}..."
        except Exception as e:
            conn.rollback()
            return False, f"更新用户状态失败: {e}"

def admin_purge_user(public_key: str) -> (bool, str):
    """(管理员功能) 彻底清除一个用户的数据以释放用户名。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                
                cursor.execute("SELECT balance FROM balances WHERE public_key = %s", (public_key,))
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

                cursor.execute("SELECT listing_id FROM market_listings WHERE lister_key = %s and status = 'ACTIVE'", (public_key,))
                user_listings = cursor.fetchall()
                for listing in user_listings:
                    # 调用事务安全函数并传入当前连接
                    _success, _detail = cancel_market_listing_in_tx(conn, public_key, listing['listing_id'])
                    if not _success:
                        # 仍然只是打印警告，而不是中止整个清除过程
                        print(f"Warning: Purging user, failed to cancel listing {listing['listing_id']}: {_detail}")

                cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE listing_id IN (SELECT listing_id FROM market_listings WHERE lister_key = %s) AND status = 'PENDING'", (public_key,))
                cursor.execute("DELETE FROM market_offers WHERE offerer_key = %s", (public_key,))
                cursor.execute("UPDATE nfts SET status = 'BURNED' WHERE owner_key = %s", (public_key,))
                cursor.execute("DELETE FROM invitation_codes WHERE generated_by = %s OR used_by = %s", (public_key, public_key))
                cursor.execute("DELETE FROM friendships WHERE user1_key = %s OR user2_key = %s", (public_key, public_key))
                cursor.execute("DELETE FROM user_profiles WHERE public_key = %s", (public_key,))
                cursor.execute("DELETE FROM balances WHERE public_key = %s", (public_key,))
                cursor.execute("DELETE FROM users WHERE public_key = %s", (public_key,))

            conn.commit()
            return True, f"用户 {public_key[:10]}... 已被彻底清除，用户名已释放。"
        except Exception as e:
            conn.rollback()
            return False, f"清除用户失败: {e}"

def admin_adjust_user_quota(public_key: str, new_quota: int) -> (bool, str):
    """(管理员功能) 调整特定用户的邀请额度。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("UPDATE users SET invitation_quota = %s WHERE public_key = %s", (new_quota, public_key))
                if cursor.rowcount == 0: return False, "未找到用户"
            conn.commit()
            return True, f"成功设置用户 {public_key[:10]}... 的邀请额度为 {new_quota}"
        except Exception as e:
            conn.rollback()
            return False, f"更新额度失败: {e}"

def admin_reset_user_password(public_key: str, new_password: str) -> (bool, str):
    """(管理员功能) 重置用户的密码。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                new_password_hash = generate_password_hash(new_password)
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE public_key = %s",
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
    """(管理员功能) 彻底清空所有表并重建。"""
    print("!!!!!!!!!!!!!! 警告：正在执行数据库清空 (NUKE) 操作 !!!!!!!!!!!!!!")
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # 必须按依赖顺序的反向顺序删除，或者使用 CASCADE
                tables = [
                    'bot_logs', 'market_trade_history', 'auction_bids', 
                    'market_offers', 'market_listings', 'nfts', 
                    'transactions', 'balances', 'friendships', 
                    'notifications', 'user_profiles', 'invitation_codes', 
                    'settings', 'users' 
                ]
                for table in tables:
                    print(f"Dropping table {table}...")
                    # 使用 CASCADE 自动处理外键依赖
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            
            conn.commit()
            
            # 提交删除后，重新初始化
            print("Re-initializing database schema...")
            init_db() # init_db 会处理自己的连接和提交
            
            return True, "数据库已清空并重建。"
        except Exception as e:
            conn.rollback()
            return False, f"重置数据库失败: {e}"