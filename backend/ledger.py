import sqlite3
import time
import uuid
import threading
import json
import os
from contextlib import contextmanager
from shared.crypto_utils import verify_signature

DATABASE_PATH = '/app/data/ledger.db'
LEDGER_LOCK = threading.Lock()

# --- 系统保留账户 ---
GENESIS_ACCOUNT = "JFJ_GENESIS"
BURN_ACCOUNT = "JFJ_BURN"
ESCROW_ACCOUNT = "JFJ_ESCROW"

DEFAULT_INVITATION_QUOTA = 3

@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器。"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
    finally:
        if conn:
            conn.close()

def init_db():
    """初始化数据库和表结构。"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # --- 用户表 ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            public_key TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            invited_by TEXT,
            invitation_quota INTEGER DEFAULT 0,
            private_key_pem TEXT
        )
        ''')
        
        # --- 余额表 ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS balances (
            public_key TEXT PRIMARY KEY,
            balance REAL NOT NULL DEFAULT 0
        )
        ''')
        
        # --- 交易记录表 ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id TEXT PRIMARY KEY,
            from_key TEXT NOT NULL,
            to_key TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            message_json TEXT NOT NULL,
            signature TEXT NOT NULL,
            note TEXT
        )
        ''')
        
        # --- 商店物品表 (FT) ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            item_id TEXT PRIMARY KEY,
            owner_key TEXT NOT NULL,
            item_type TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ACTIVE',
            FOREIGN KEY (owner_key) REFERENCES users (public_key)
        )
        ''')

        # <<< NFT 架构升级: 新建 nfts 表 >>>
        # 这是所有非同质化资产的“户籍中心”。
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS nfts (
            nft_id TEXT PRIMARY KEY,
            owner_key TEXT NOT NULL,
            nft_type TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ACTIVE',
            FOREIGN KEY (owner_key) REFERENCES users (public_key)
        )
        ''')
        # 为常用查询建立索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_owner_key ON nfts (owner_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_nft_type ON nfts (nft_type)")
        
        # --- 设置表 ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        ''')
        
        # --- 一次性邀请码表 ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS invitation_codes (
            code TEXT PRIMARY KEY,
            generated_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_used BOOLEAN DEFAULT 0,
            used_by TEXT,
            FOREIGN KEY (generated_by) REFERENCES users (public_key)
        )
        ''')
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_codes_generated_by ON invitation_codes (generated_by)"
        )
        
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ('default_invitation_quota', str(DEFAULT_INVITATION_QUOTA))
        )
        
        conn.commit()
    print("数据库初始化完成。")

# <<< NFT 架构升级: 新增 NFT 数据库核心函数 >>>

def mint_nft(owner_key: str, nft_type: str, data: dict) -> (bool, str, str):
    """(底层) 将一个新的 NFT 记录到数据库中。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            nft_id = str(uuid.uuid4())
            data_json = json.dumps(data, ensure_ascii=False)

            cursor.execute("SELECT 1 FROM users WHERE public_key = ?", (owner_key,))
            if not cursor.fetchone():
                return False, "NFT所有者不存在", None

            cursor.execute(
                "INSERT INTO nfts (nft_id, owner_key, nft_type, data, status) VALUES (?, ?, ?, ?, 'ACTIVE')",
                (nft_id, owner_key, nft_type, data_json)
            )
            conn.commit()
            return True, "NFT 铸造成功", nft_id
        except Exception as e:
            conn.rollback()
            return False, f"NFT 铸造时数据库出错: {e}", None

def get_nft_by_id(nft_id: str) -> dict:
    """根据 ID 获取单个 NFT 的详细信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                nft_id, owner_key, nft_type, data, 
                CAST(strftime('%s', created_at) AS REAL) as created_at,
                status
            FROM nfts 
            WHERE nft_id = ?
            """,
            (nft_id,)
        )
        nft = cursor.fetchone()
        if not nft:
            return None
        nft_dict = dict(nft)
        nft_dict['data'] = json.loads(nft_dict['data']) # 将 JSON 字符串反序列化为字典
        return nft_dict

def get_nfts_by_owner(owner_key: str) -> list:
    """获取指定所有者的所有 NFT。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                nft_id, owner_key, nft_type, data, 
                CAST(strftime('%s', created_at) AS REAL) as created_at,
                status
            FROM nfts 
            WHERE owner_key = ? 
            ORDER BY created_at DESC
            """,
            (owner_key,)
        )
        nfts = []
        for row in cursor.fetchall():
            nft_dict = dict(row)
            nft_dict['data'] = json.loads(nft_dict['data'])
            nfts.append(nft_dict)
        return nfts

def update_nft(nft_id: str, new_data: dict, new_status: str = None) -> (bool, str):
    """更新 NFT 的 data 或 status 字段。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            data_json = json.dumps(new_data, ensure_ascii=False)
            
            if new_status:
                cursor.execute(
                    "UPDATE nfts SET data = ?, status = ? WHERE nft_id = ?",
                    (data_json, new_status, nft_id)
                )
            else:
                cursor.execute("UPDATE nfts SET data = ? WHERE nft_id = ?", (data_json, nft_id))

            if cursor.rowcount == 0:
                return False, "未找到要更新的 NFT"
            
            conn.commit()
            return True, "NFT 更新成功"
        except Exception as e:
            conn.rollback()
            return False, f"更新 NFT 时数据库出错: {e}"

def get_setting(key: str) -> str:
    """从设置表获取一个值。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result['value'] if result else None

def set_setting(key: str, value: str) -> bool:
    """更新或插入一个设置值。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"更新设置失败: {e}")
            return False

# 核心修改 2: 增加 private_key 参数，用于存储
def register_user(username: str, public_key: str, private_key: str, invitation_code: str) -> (bool, str):
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
                return False, "无效的邀请码或邀请码已被使用"
            
            if (time.time() - code_data['created_at_unix']) > 86400 * 7: # 7天有效期
                return False, "邀请码已过期"
                
            inviter_key = code_data['generated_by']
            
            default_quota_str = get_setting('default_invitation_quota')
            default_quota = int(default_quota_str) if default_quota_str and default_quota_str.isdigit() else DEFAULT_INVITATION_QUOTA
            
            # 核心修改 3: 在 INSERT 语句中增加私钥字段
            cursor.execute(
                "INSERT INTO users (public_key, username, invited_by, invitation_quota, private_key_pem) VALUES (?, ?, ?, ?, ?)",
                (public_key, username, inviter_key, default_quota, private_key)
            )
            
            cursor.execute("INSERT INTO balances (public_key, balance) VALUES (?, 0)", (public_key,))
            
            cursor.execute(
                "UPDATE invitation_codes SET is_used = 1, used_by = ? WHERE code = ?",
                (public_key, invitation_code)
            )
            
            conn.commit()
            return True, f"注册成功！"
            
        except sqlite3.IntegrityError:
            conn.rollback()
            return False, "用户名或公钥已存在"
        except Exception as e:
            conn.rollback()
            return False, f"注册时发生未知错误: {e}"

# --- 用户查询 ---

def get_balance(public_key: str) -> float:
    """查询指定公钥的余额。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (public_key,))
        result = cursor.fetchone()
        return result['balance'] if result else 0.0

def get_user_details(public_key: str) -> dict:
    """获取用户的详细信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                u.public_key, 
                u.username, 
                CAST(strftime('%s', u.created_at) AS REAL) as created_at, 
                u.invitation_quota, 
                u.invited_by,
                u.is_active,
                CASE 
                    WHEN u.invited_by = 'GENESIS' THEN '--- 系统 ---'
                    ELSE (SELECT inviter.username FROM users inviter WHERE inviter.public_key = u.invited_by)
                END as inviter_username
            FROM users u
            WHERE u.public_key = ?
            """,
            (public_key,)
        )
        user_details = cursor.fetchone()
        if not user_details:
            return None
        
        user_dict = dict(user_details)
        user_dict['is_active'] = bool(user_dict['is_active'])
        
        cursor.execute(
            "SELECT COUNT(*) as tx_count FROM transactions WHERE from_key = ? OR to_key = ?",
            (public_key, public_key)
        )
        user_dict['tx_count'] = cursor.fetchone()['tx_count']
        return user_dict

def get_all_active_users() -> list:
    """获取所有活跃用户列表。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, public_key FROM users WHERE is_active = 1 ORDER BY username")
        return [dict(row) for row in cursor.fetchall()]

def get_transaction_history(public_key: str) -> list:
    """获取与某个公钥相关的所有交易记录。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                tx_id, from_key, to_key, amount, timestamp, 'out' as type, note,
                (SELECT username FROM users WHERE public_key = T.from_key) as from_username,
                (SELECT username FROM users WHERE public_key = T.to_key) as to_username
            FROM transactions T WHERE from_key = ?
            UNION ALL
            SELECT 
                tx_id, from_key, to_key, amount, timestamp, 'in' as type, note,
                (SELECT username FROM users WHERE public_key = T.from_key) as from_username,
                (SELECT username FROM users WHERE public_key = T.to_key) as to_username
            FROM transactions T WHERE to_key = ?
            ORDER BY timestamp DESC
            """,
            (public_key, public_key)
        )
        
        def format_username(key, username):
            if key == GENESIS_ACCOUNT: return "⭐ 系统铸币"
            if key == BURN_ACCOUNT: return "🔥 系统销毁"
            if key == ESCROW_ACCOUNT: return "🔒 系统托管"
            # (问题2 修复) 如果用户已被删除(username=null)，显示公钥
            return username or f"{key[:10]}... (已清除)"

        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            row_dict['from_display'] = format_username(row_dict['from_key'], row_dict['from_username'])
            row_dict['to_display'] = format_username(row_dict['to_key'], row_dict['to_username'])
            results.append(row_dict)
            
        return results

# --- 核心交易逻辑 ---

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

# --- 管理员与系统功能 ---

def get_all_balances(include_inactive=False) -> list:
    """(管理员功能) 获取所有用户的余额和邀请信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                u.username, b.public_key, b.balance, u.is_active,
                u.invitation_quota, u.invited_by, inviter.username as inviter_username
            FROM users u
            JOIN balances b ON u.public_key = b.public_key
            LEFT JOIN users inviter ON u.invited_by = inviter.public_key
        """
        if not include_inactive:
            query += " WHERE u.is_active = 1"
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

def _execute_system_tx_logic(from_key, to_key, amount, note, conn):
    """(内部函数) 执行系统交易的核心逻辑，被 _create_system_transaction 调用。"""
    cursor = conn.cursor()
    try:
        # 更新付款方 (如果不是铸币)
        if from_key != GENESIS_ACCOUNT:
            cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (from_key,))
            from_balance_row = cursor.fetchone()
            current_from_balance = from_balance_row['balance'] if from_balance_row else 0.0
            if current_from_balance < amount:
                return False, f"系统账户 {from_key} 余额不足"
            new_from_balance = current_from_balance - amount
            cursor.execute("UPDATE balances SET balance = ? WHERE public_key = ?", (new_from_balance, from_key))

        # 更新收款方 (如果不是销毁)
        if to_key != BURN_ACCOUNT:
            cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (to_key,))
            to_balance_row = cursor.fetchone()
            current_to_balance = to_balance_row['balance'] if to_balance_row else 0.0
            new_to_balance = current_to_balance + amount
            cursor.execute("INSERT OR REPLACE INTO balances (public_key, balance) VALUES (?, ?)", (to_key, new_to_balance))

        # 记录交易
        tx_id = str(uuid.uuid4())
        timestamp = time.time()
        message = {"from": from_key, "to": to_key, "amount": amount, "timestamp": timestamp, "note": note}
        message_json = json.dumps(message, sort_keys=True, ensure_ascii=False)
        
        cursor.execute(
            "INSERT INTO transactions (tx_id, from_key, to_key, amount, timestamp, message_json, signature, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tx_id, from_key, to_key, amount, timestamp, message_json, "ADMIN_SYSTEM", note)
        )
        return True, "系统操作成功"
    except Exception as e:
        return False, f"系统操作数据库失败: {e}"

def _create_system_transaction(from_key: str, to_key: str, amount: float, note: str = None, conn=None) -> (bool, str):
    """(重构) 创建一笔系统交易 (铸币/销毁/托管)。"""
    def run_logic(connection):
        return _execute_system_tx_logic(from_key, to_key, amount, note, connection)

    if conn:
        return run_logic(conn)
    else:
        with LEDGER_LOCK, get_db_connection() as new_conn:
            success, detail = run_logic(new_conn)
            if success:
                new_conn.commit()
            else:
                new_conn.rollback()
            return success, detail

def admin_issue_coins(to_key: str, amount: float, note: str = None) -> (bool, str):
    """(管理员功能) 增发货币。"""
    if amount <= 0: return False, "发行金额必须大于0"
    return _create_system_transaction(GENESIS_ACCOUNT, to_key, amount, note or "管理员增发")

def admin_burn_coins(from_key: str, amount: float, note: str = None) -> (bool, str):
    """(管理员功能) 销毁货币。"""
    if amount <= 0: return False, "销毁金额必须大于0"
    return _create_system_transaction(from_key, BURN_ACCOUNT, amount, note or "管理员减持")

def admin_delete_user(public_key: str) -> (bool, str):
    """(管理员功能) 禁用一个用户并清零其资产。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (public_key,))
            balance_row = cursor.fetchone()
            if not balance_row: return False, "用户不存在"
            
            current_balance = balance_row['balance']
            
            cursor.execute("UPDATE users SET is_active = 0, invitation_quota = 0 WHERE public_key = ?", (public_key,))
            
            if current_balance > 0:
                success, detail = _create_system_transaction(
                    from_key=public_key, to_key=BURN_ACCOUNT, amount=current_balance,
                    note=f"禁用用户 {public_key[:10]}... 并清零资产", conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"禁用用户时清零资产失败: {detail}"

            conn.commit()
            return True, f"用户 {public_key[:10]}... 已被禁用"
        except Exception as e:
            conn.rollback()
            return False, f"禁用用户失败: {e}"

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
                success, detail = _create_system_transaction(
                    from_key=public_key, to_key=BURN_ACCOUNT, amount=current_balance,
                    note=f"彻底清除用户 {public_key[:10]}... 并清零资产", conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"清除用户时清零资产失败: {detail}"

            # <<< NFT 架构升级: 增加 NFT 相关清理 >>>
            # 1. 烧毁该用户的所有 NFT (或者转移给系统, 这里选择更新状态为BURNED)
            cursor.execute("UPDATE nfts SET status = 'BURNED' WHERE owner_key = ?", (public_key,))

            # 2. 从所有相关表中删除 (注意顺序)
            cursor.execute("DELETE FROM shop_items WHERE owner_key = ?", (public_key,))
            cursor.execute("DELETE FROM invitation_codes WHERE generated_by = ? OR used_by = ?", (public_key, public_key))
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

# (问题 3 修复) 新增系统重置功能
def nuke_database() -> (bool, str):
    """(管理员功能) 彻底删除数据库文件并重建。"""
    with LEDGER_LOCK: # 确保在操作文件时没有其他线程在访问
        try:
            # 尝试关闭所有连接（虽然很难完美做到，但删除文件是主要目的）
            # 在 Python 中，最好的方法是确保所有 get_db_connection() 都已退出
            # 锁定后，我们可以安全地删除文件
            
            if os.path.exists(DATABASE_PATH):
                os.remove(DATABASE_PATH)
            
            # 立即重建
            init_db()
            
            return True, "数据库已重置并重建。"
        except Exception as e:
            return False, f"重置数据库失败: {e}"

# --- 邀请码功能 ---

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

# --- 商店功能 (已修改) ---

def add_shop_item(owner_key: str, item_type: str, description: str, price: float) -> (bool, str):
    """(修改后) 添加一个商品到商店。如果类型为WANTED，则执行托管。"""
    if price <= 0: return False, "价格必须大于0"
    if item_type not in ['FOR_SALE', 'WANTED']: return False, "无效的商品类型"
        
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            if item_type == 'WANTED':
                cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (owner_key,))
                balance_row = cursor.fetchone()
                if not balance_row or balance_row['balance'] < price:
                    return False, "你的余额不足以发布此求购"
                
                # 托管资金
                success, detail = _create_system_transaction(
                    from_key=owner_key, to_key=ESCROW_ACCOUNT, amount=price,
                    note=f"托管求购资金: {description[:20]}...", conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"托管资金失败: {detail}"

            item_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO shop_items (item_id, owner_key, item_type, description, price, status) VALUES (?, ?, ?, ?, ?, 'ACTIVE')",
                (item_id, owner_key, item_type, description, price)
            )
            conn.commit()
            return True, "商品已发布"
        except Exception as e:
            conn.rollback()
            return False, f"发布商品失败: {e}"

def get_shop_items(item_type: str = None, exclude_owner: str = None) -> list:
    """获取所有活跃的商品。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT i.item_id, i.owner_key, i.item_type, i.description, i.price, i.created_at, u.username
            FROM shop_items i JOIN users u ON u.public_key = i.owner_key
            WHERE i.status = 'ACTIVE' AND u.is_active = 1
        """
        params = []
        if item_type:
            query += " AND i.item_type = ?"
            params.append(item_type)
        if exclude_owner:
            query += " AND i.owner_key != ?"
            params.append(exclude_owner)
        query += " ORDER BY i.created_at DESC"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_my_shop_items(owner_key: str) -> list:
    """获取我发布的所有商品。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT item_id, item_type, description, price, created_at, status FROM shop_items WHERE owner_key = ? ORDER BY created_at DESC",
            (owner_key,)
        )
        return [dict(row) for row in cursor.fetchall()]

def cancel_shop_item(item_id: str, owner_key: str) -> (bool, str):
    """(修改后) 取消一个商品。如果类型为WANTED，则退回托管资金。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT item_type, price, status FROM shop_items WHERE item_id = ? AND owner_key = ?", (item_id, owner_key))
            item = cursor.fetchone()

            if not item: return False, "未找到商品或你不是所有者"
            if item['status'] != 'ACTIVE': return False, "商品已非活跃状态"
                
            if item['item_type'] == 'WANTED':
                # 退还托管资金
                success, detail = _create_system_transaction(
                    from_key=ESCROW_ACCOUNT, to_key=owner_key, amount=item['price'],
                    note=f"取消求购，退回托管资金。Item ID: {item_id[:8]}", conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"退回托管资金失败: {detail}"

            cursor.execute("UPDATE shop_items SET status = 'CANCELLED' WHERE item_id = ?", (item_id,))
            conn.commit()
            return True, "商品已取消"
        except Exception as e:
            conn.rollback()
            return False, f"取消失败: {e}"

def execute_purchase(item_id: str, buyer_key: str, transaction_message_json: str, transaction_signature: str) -> (bool, str):
    """执行一笔购买 (FOR_SALE)。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT owner_key, price, status, item_type, description FROM shop_items WHERE item_id = ?", (item_id,))
        item = cursor.fetchone()
        
        if not item: return False, "未找到商品"
        if item['status'] != 'ACTIVE': return False, "商品已下架"
        if item['item_type'] != 'FOR_SALE': return False, "该商品非出售状态"
            
        seller_key = item['owner_key']
        price = item['price']
        
        if seller_key == buyer_key: return False, "不能购买自己的商品"

        # 复用通用的交易处理函数，但在同一个数据库连接和事务中
        success, detail = process_transaction_within_conn(
            conn, buyer_key, seller_key, price, 
            transaction_message_json, transaction_signature, 
            f"购买商品: {item['description'][:20]}..."
        )
        
        if not success:
            conn.rollback()
            return False, detail
        
        try:
            # 交易成功后，更新商品状态
            cursor.execute("UPDATE shop_items SET status = 'SOLD' WHERE item_id = ?", (item_id,))
            conn.commit()
            return True, "购买成功！"
        except Exception as e:
            conn.rollback()
            return False, f"更新商品状态失败: {e}"

def process_transaction_within_conn(conn, from_key, to_key, amount, message_json, signature, note):
    """(内部辅助) 在已有的数据库连接中处理交易，不自动提交或回滚。"""
    try:
        # 验证签名和时间戳 (在调用 ledger.process_transaction 时已完成，这里简化)
        message = json.loads(message_json)
        if not verify_signature(from_key, message, signature):
             return False, "签名无效 (内部)"
        if (time.time() - message.get('timestamp', 0)) > 300: 
             return False, "交易已过期 (内部)"

        cursor = conn.cursor()
        from_balance_row = cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (from_key,)).fetchone()
        if not from_balance_row or from_balance_row['balance'] < amount:
            return False, "余额不足"

        cursor.execute("UPDATE balances SET balance = balance - ? WHERE public_key = ?", (amount, from_key))
        cursor.execute("UPDATE balances SET balance = balance + ? WHERE public_key = ?", (amount, to_key))
        
        tx_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO transactions (tx_id, from_key, to_key, amount, timestamp, message_json, signature, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tx_id, from_key, to_key, amount, message['timestamp'], message_json, signature, note)
        )
        return True, "交易部分成功"
    except Exception as e:
        return False, f"交易处理失败: {e}"

def fulfill_wanted_item(item_id: str, seller_key: str) -> (bool, str):
    """(新增) 响应一个WANTED求购。将托管资金转给卖家。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT owner_key, price, status, item_type FROM shop_items WHERE item_id = ?", (item_id,))
            item = cursor.fetchone()
            
            if not item: return False, "未找到求购信息"
            if item['status'] != 'ACTIVE': return False, "该求购已结束"
            if item['item_type'] != 'WANTED': return False, "该信息不是求购类型"
            
            buyer_key = item['owner_key']
            price = item['price']
            
            if buyer_key == seller_key: return False, "不能向自己出售"
                
            # 从托管账户向卖家付款
            success, detail = _create_system_transaction(
                from_key=ESCROW_ACCOUNT, to_key=seller_key, amount=price,
                note=f"完成求购交易。Item ID: {item_id[:8]}", conn=conn
            )
            if not success:
                conn.rollback()
                return False, f"支付卖家失败: {detail}"

            # 更新商品状态为“已完成” (FULFILLED)
            cursor.execute("UPDATE shop_items SET status = 'FULFILLED' WHERE item_id = ?", (item_id,))
            
            conn.commit()
            return True, f"出售成功！你已收到 {price:,.2f} FC"

        except Exception as e:
            conn.rollback()
            return False, f"完成交易时发生错误: {e}"

def count_users() -> int:
    """统计数据库中的用户总数。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        return result[0] if result else 0

# 核心修改 4: 增加 private_key 参数
def create_genesis_user(username: str, public_key: str, private_key: str) -> (bool, str):
    """创建第一个（创世）管理员用户。"""
    if count_users() > 0:
        return False, "系统已经初始化，无法创建创世用户。"

    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            inv_quota = 999999 # 无限邀请

            # 核心修改 5: 在 INSERT 语句中增加私钥字段
            cursor.execute(
                "INSERT INTO users (public_key, username, invited_by, invitation_quota, private_key_pem) VALUES (?, ?, ?, ?, ?)",
                (public_key, username, "GENESIS", inv_quota, private_key)
            )

            cursor.execute("INSERT INTO balances (public_key, balance) VALUES (?, 0)", (public_key,))

            conn.commit()
            return True, "创世管理员创建成功！"
        except Exception as e:
            conn.rollback()
            return False, f"创建创世用户失败: {e}"

# 核心修改 6: (新增函数) 增加管理员查询用户私钥的功能
def admin_get_user_private_key(public_key: str) -> str:
    """(管理员功能) 获取用户的私钥。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT private_key_pem FROM users WHERE public_key = ?", (public_key,))
        result = cursor.fetchone()
        return result['private_key_pem'] if result and result['private_key_pem'] else None