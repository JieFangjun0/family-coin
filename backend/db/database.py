# backend/db/database.py

import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
import time
import uuid
import json
import random
import string
import secrets
from contextlib import contextmanager

# 从环境变量中获取数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 环境变量未设置！")

# --- PostgreSQL 连接池 ---
# 在应用启动时创建一次
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=DATABASE_URL
    )
except psycopg2.OperationalError as e:
    print(f"!!!!!!!!!!!!!! 数据库连接失败 !!!!!!!!!!!!!!")
    print(f"错误: {e}")
    print(f"请检查 DATABASE_URL 和 PostgreSQL 服务是否正在运行。")
    db_pool = None

# --- 系统保留账户 ---
GENESIS_ACCOUNT = "JFJ_GENESIS"
BURN_ACCOUNT = "JFJ_BURN"
ESCROW_ACCOUNT = "JFJ_ESCROW" 
DEFAULT_INVITATION_QUOTA = 3

def _generate_secure_password(length=12):
    """生成一个安全的随机密码。"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))

def _generate_uid(length=8):
    """生成一个指定长度的纯数字UID。"""
    return ''.join(random.choices(string.digits, k=length))

# --- 数据库连接上下文 ---
@contextmanager
def get_db_connection():
    """获取 PostgreSQL 数据库连接的上下文管理器。"""
    if db_pool is None:
        raise ConnectionError("数据库连接池未初始化。")
    
    conn = None
    try:
        conn = db_pool.getconn()
        # 我们将在创建 cursor 时使用 DictCursor
        yield conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        raise e
    finally:
        if conn:
            db_pool.putconn(conn) # 释放连接回连接池

# --- 数据库初始化 ---
def init_db():
    """初始化数据库和表结构 (PostgreSQL 语法)。"""
    
    with get_db_connection() as conn:
        # 使用 cursor_factory=psycopg2.extras.DictCursor
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            
            # --- 用户表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                public_key TEXT PRIMARY KEY,
                uid TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                invited_by TEXT,
                invitation_quota INTEGER DEFAULT 0,
                private_key_pem TEXT,
                profile_signature TEXT,
                
                is_bot BOOLEAN DEFAULT FALSE,
                bot_type TEXT,
                action_probability FLOAT DEFAULT 0.1
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_uid ON users (uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_bot ON users (is_bot)")
            
            # --- 用户个人主页表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                public_key TEXT PRIMARY KEY,
                signature TEXT,
                displayed_nfts TEXT,
                updated_at TIMESTAMPTZ,
                FOREIGN KEY (public_key) REFERENCES users (public_key) ON DELETE CASCADE
            )
            ''')
            
            # --- 通知表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                notif_id TEXT PRIMARY KEY,
                user_key TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                timestamp FLOAT NOT NULL,
                FOREIGN KEY (user_key) REFERENCES users (public_key) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_key ON notifications (user_key, is_read)")

            # --- 好友关系表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS friendships (
                user1_key TEXT NOT NULL,
                user2_key TEXT NOT NULL,
                status TEXT NOT NULL, 
                action_user_key TEXT NOT NULL, 
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user1_key, user2_key),
                FOREIGN KEY (user1_key) REFERENCES users (public_key) ON DELETE CASCADE,
                FOREIGN KEY (user2_key) REFERENCES users (public_key) ON DELETE CASCADE,
                FOREIGN KEY (action_user_key) REFERENCES users (public_key) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships (status)")

            # --- 余额表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS balances (
                public_key TEXT PRIMARY KEY,
                balance FLOAT NOT NULL DEFAULT 0
            )
            ''')
            
            # --- 交易记录表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                from_key TEXT NOT NULL,
                to_key TEXT NOT NULL,
                amount FLOAT NOT NULL,
                timestamp FLOAT NOT NULL,
                message_json TEXT NOT NULL,
                signature TEXT NOT NULL,
                note TEXT
            )
            ''')
            
            # --- nfts 表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS nfts (
                nft_id TEXT PRIMARY KEY,
                owner_key TEXT NOT NULL,
                nft_type TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'ACTIVE',
                FOREIGN KEY (owner_key) REFERENCES users (public_key) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_owner_key ON nfts (owner_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_nft_type ON nfts (nft_type)")
            
            # --- 市场挂单表 (market_listings) ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_listings (
                listing_id TEXT PRIMARY KEY,
                lister_key TEXT NOT NULL,
                listing_type TEXT NOT NULL,
                nft_id TEXT,
                nft_type TEXT NOT NULL,
                description TEXT NOT NULL,
                price FLOAT NOT NULL,
                end_time TIMESTAMPTZ,
                status TEXT NOT NULL,
                highest_bidder TEXT,
                highest_bid FLOAT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lister_key) REFERENCES users(public_key) ON DELETE CASCADE,
                FOREIGN KEY (nft_id) REFERENCES nfts(nft_id) ON DELETE SET NULL
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_type_status ON market_listings (listing_type, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_lister ON market_listings (lister_key)")

            # --- 市场报价表 (market_offers) ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_offers (
                offer_id TEXT PRIMARY KEY,
                listing_id TEXT NOT NULL,
                offerer_key TEXT NOT NULL,
                offered_nft_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id) ON DELETE CASCADE,
                FOREIGN KEY (offerer_key) REFERENCES users(public_key) ON DELETE CASCADE,
                FOREIGN KEY (offered_nft_id) REFERENCES nfts(nft_id) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_offers_listing_id ON market_offers (listing_id)")
            
            # --- 拍卖出价记录表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS auction_bids (
                bid_id TEXT PRIMARY KEY,
                listing_id TEXT NOT NULL,
                bidder_key TEXT NOT NULL,
                bid_amount FLOAT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id) ON DELETE CASCADE,
                FOREIGN KEY (bidder_key) REFERENCES users(public_key) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bids_listing_id ON auction_bids (listing_id)")

            # --- 市场成交历史表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_trade_history (
                trade_id TEXT PRIMARY KEY,
                listing_id TEXT NOT NULL,
                nft_id TEXT NOT NULL,
                nft_type TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                seller_key TEXT NOT NULL,
                buyer_key TEXT NOT NULL,
                price FLOAT NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_history_timestamp ON market_trade_history (timestamp)")

            # --- 机器人日志表 ---
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_logs (
                log_id TEXT PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                bot_key TEXT NOT NULL,
                bot_username TEXT,
                action_type TEXT NOT NULL,
                message TEXT NOT NULL,
                data_snapshot TEXT,
                FOREIGN KEY (bot_key) REFERENCES users (public_key) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_logs_bot_key ON bot_logs (bot_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_logs_timestamp ON bot_logs (timestamp)")

            # --- 设置表等 ---
            cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS invitation_codes (
                code TEXT PRIMARY KEY, 
                generated_by TEXT NOT NULL, 
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, 
                is_used BOOLEAN DEFAULT FALSE, 
                used_by TEXT, 
                FOREIGN KEY (generated_by) REFERENCES users (public_key) ON DELETE CASCADE
            )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_codes_generated_by ON invitation_codes (generated_by)")
            
            # 使用 ON CONFLICT DO NOTHING 确保插入幂等性
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", ('default_invitation_quota', str(DEFAULT_INVITATION_QUOTA)))
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", ('welcome_bonus_amount', '300'))
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", ('inviter_bonus_amount', '200'))
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", ('bot_system_enabled', 'False'))
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", ('bot_check_interval_seconds', '30'))
            
        conn.commit()
        print("数据库初始化完成 (PostgreSQL)。")

# --- 核心设置函数 ---
def get_setting(key: str) -> str:
    """从设置表获取一个值。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT value FROM settings WHERE key = %s", (key,))
            result = cursor.fetchone()
            return result['value'] if result else None

def set_setting(key: str, value: str) -> bool:
    """更新或插入一个设置值。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cursor:
                # 使用 ON CONFLICT DO UPDATE 实现插入或更新
                cursor.execute(
                    """
                    INSERT INTO settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """,
                    (key, value)
                )
            conn.commit()
            return True
        except Exception as e:
            print(f"更新设置失败: {e}")
            conn.rollback()
            return False

# --- 核心事务逻辑 ---
def _execute_system_tx_logic(from_key, to_key, amount, note, conn):
    """(内部函数) 执行系统交易的核心逻辑。"""
    # 使用 DictCursor 以便按列名访问
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        try:
            if from_key != GENESIS_ACCOUNT:
                # 使用 %s 占位符
                # 添加 FOR UPDATE 以锁定行，防止并发冲突
                cursor.execute("SELECT balance FROM balances WHERE public_key = %s FOR UPDATE", (from_key,))
                from_balance_row = cursor.fetchone()
                current_from_balance = from_balance_row['balance'] if from_balance_row else 0.0
                if current_from_balance < amount:
                    return False, f"系统账户 {from_key} 余额不足"
                new_from_balance = current_from_balance - amount
                cursor.execute("UPDATE balances SET balance = %s WHERE public_key = %s", (new_from_balance, from_key))

            if to_key != BURN_ACCOUNT:
                # 添加 FOR UPDATE
                cursor.execute("SELECT balance FROM balances WHERE public_key = %s FOR UPDATE", (to_key,))
                to_balance_row = cursor.fetchone()
                current_to_balance = to_balance_row['balance'] if to_balance_row else 0.0
                new_to_balance = current_to_balance + amount
                # 使用 ON CONFLICT DO UPDATE 实现插入或更新
                cursor.execute(
                    """
                    INSERT INTO balances (public_key, balance) VALUES (%s, %s)
                    ON CONFLICT (public_key) DO UPDATE SET balance = EXCLUDED.balance
                    """,
                    (to_key, new_to_balance)
                )

            tx_id = str(uuid.uuid4())
            timestamp = time.time()
            message = {"from": from_key, "to": to_key, "amount": amount, "timestamp": timestamp, "note": note}
            message_json = json.dumps(message, sort_keys=True, ensure_ascii=False)
            
            cursor.execute(
                "INSERT INTO transactions (tx_id, from_key, to_key, amount, timestamp, message_json, signature, note) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (tx_id, from_key, to_key, amount, timestamp, message_json, "ADMIN_SYSTEM", note)
            )
            return True, "系统操作成功"
        except Exception as e:
            return False, f"系统操作数据库失败: {e}"

# --- 通知函数 ---
def create_notification(user_key: str, message: str, conn):
    """ (内部函数) 在事务连接中为指定用户创建一条通知。 """
    try:
        cursor = conn.cursor()
        notif_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO notifications (notif_id, user_key, message, is_read, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (notif_id, user_key, message, False, time.time())
        )
        return True, "通知创建成功"
    except Exception as e:
        print(f"!!!!!!!!!!!!!! 严重错误：无法创建通知 for {user_key[:10]}... !!!!!!!!!!!!!!")
        print(f"错误: {e}")
        return False, f"通知创建失败: {e}"

# --- 系统事务 ---
def _create_system_transaction(from_key: str, to_key: str, amount: float, note: str = None, conn=None) -> (bool, str):
    """创建一笔系统交易 (铸币/销毁/托管)。"""
    def run_logic(connection):
        return _execute_system_tx_logic(from_key, to_key, amount, note, connection)

    if conn:
        # 如果已在事务中，直接运行
        return run_logic(conn)
    else:
        # 否则，创建新事务
        with get_db_connection() as new_conn:
            success, detail = run_logic(new_conn)
            if success:
                new_conn.commit()
            else:
                new_conn.rollback()
            return success, detail