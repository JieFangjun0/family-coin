# backend/db/database.py

import sqlite3
import time
import uuid
import threading
import json
import os
import random
import string
import secrets
from contextlib import contextmanager

DATABASE_PATH = '/app/data/ledger.db'
LEDGER_LOCK = threading.Lock()

# --- 系统保留账户 ---
GENESIS_ACCOUNT = "JFJ_GENESIS"
BURN_ACCOUNT = "JFJ_BURN"
ESCROW_ACCOUNT = "JFJ_ESCROW" 

DEFAULT_INVITATION_QUOTA = 3

def _generate_secure_password(length=12):
    """(新增) 生成一个安全的随机密码。"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))

def _generate_uid(length=8):
    """生成一个指定长度的纯数字UID。"""
    return ''.join(random.choices(string.digits, k=length))

@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器。"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
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
        
        # --- 用户表 (核心修改) ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            public_key TEXT PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            invited_by TEXT,
            invitation_quota INTEGER DEFAULT 0,
            private_key_pem TEXT,
            profile_signature TEXT,
            
            -- +++ 新增机器人字段 +++
            is_bot BOOLEAN DEFAULT 0,
            bot_type TEXT,
            action_probability REAL DEFAULT 0.1
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_uid ON users (uid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_bot ON users (is_bot)") # 新增索引
        
        # --- 新增：用户个人主页表 ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            public_key TEXT PRIMARY KEY,
            signature TEXT,
            displayed_nfts TEXT,
            updated_at TIMESTAMP,
            FOREIGN KEY (public_key) REFERENCES users (public_key)
        )
        ''')
        
        # <<< --- 新增：通知表 --- >>>
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notif_id TEXT PRIMARY KEY,
            user_key TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            timestamp REAL NOT NULL,
            FOREIGN KEY (user_key) REFERENCES users (public_key)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_key ON notifications (user_key, is_read)")
        # <<< --- 新增：好友关系表 --- >>>
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            user1_key TEXT NOT NULL,
            user2_key TEXT NOT NULL,
            status TEXT NOT NULL, -- 'PENDING', 'ACCEPTED'
            action_user_key TEXT NOT NULL, -- 记录发起请求的用户
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user1_key, user2_key),
            FOREIGN KEY (user1_key) REFERENCES users (public_key),
            FOREIGN KEY (user2_key) REFERENCES users (public_key),
            FOREIGN KEY (action_user_key) REFERENCES users (public_key)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships (status)")

        # --- 余额表 (不变) ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS balances (
            public_key TEXT PRIMARY KEY,
            balance REAL NOT NULL DEFAULT 0
        )
        ''')
        
        # --- 交易记录表 (不变) ---
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
        
        # <<< 核心修改: 新建 nfts 表 (不变) >>>
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_owner_key ON nfts (owner_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_nft_type ON nfts (nft_type)")
        
        # <<< 核心修改: 新建市场挂单表 (market_listings) >>>
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_listings (
            listing_id TEXT PRIMARY KEY,
            lister_key TEXT NOT NULL,      -- 发起人
            listing_type TEXT NOT NULL,    -- 'SALE', 'AUCTION', 'SEEK'
            nft_id TEXT,                   -- 对于 SALE 和 AUCTION, 这是被托管的NFT ID
            nft_type TEXT NOT NULL,        -- 对于 SEEK, 这是寻求的NFT类型
            description TEXT NOT NULL,     -- 挂单的描述
            price REAL NOT NULL,           -- SALE的定价, AUCTION的起拍价, SEEK的预算
            end_time TIMESTAMP,            -- AUCTION的结束时间
            status TEXT NOT NULL,          -- 'ACTIVE', 'SOLD', 'CANCELLED', 'EXPIRED', 'FULFILLED'
            highest_bidder TEXT,           -- AUCTION的最高出价人
            highest_bid REAL DEFAULT 0,    -- AUCTION的最高出价
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lister_key) REFERENCES users(public_key),
            FOREIGN KEY (nft_id) REFERENCES nfts(nft_id)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_type_status ON market_listings (listing_type, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_lister ON market_listings (lister_key)")

        # <<< 核心修改: 新建市场报价表 (market_offers) >>>
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_offers (
            offer_id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL,      -- 对应 market_listings 中的求购单
            offerer_key TEXT NOT NULL,     -- 报价人
            offered_nft_id TEXT NOT NULL,  -- 报价人提供的NFT
            status TEXT NOT NULL,          -- 'PENDING', 'ACCEPTED', 'REJECTED'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id),
            FOREIGN KEY (offerer_key) REFERENCES users(public_key),
            FOREIGN KEY (offered_nft_id) REFERENCES nfts(nft_id)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_offers_listing_id ON market_offers (listing_id)")
        
        # <<< --- 新增：拍卖出价记录表 --- >>>
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS auction_bids (
            bid_id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL,
            bidder_key TEXT NOT NULL,
            bid_amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id),
            FOREIGN KEY (bidder_key) REFERENCES users(public_key)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bids_listing_id ON auction_bids (listing_id)")

        # +++ 新增：市场成交历史表 +++
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_trade_history (
            trade_id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL,
            nft_id TEXT NOT NULL,
            nft_type TEXT NOT NULL,
            trade_type TEXT NOT NULL, -- 'SALE', 'AUCTION', 'SEEK'
            seller_key TEXT NOT NULL,
            buyer_key TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id),
            FOREIGN KEY (seller_key) REFERENCES users(public_key),
            FOREIGN KEY (buyer_key) REFERENCES users(public_key)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_history_timestamp ON market_trade_history (timestamp)")

        # +++ 新增：机器人日志表 +++
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_logs (
            log_id TEXT PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bot_key TEXT NOT NULL,
            bot_username TEXT,
            action_type TEXT NOT NULL,
            message TEXT NOT NULL,
            data_snapshot TEXT,
            FOREIGN KEY (bot_key) REFERENCES users (public_key)
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_logs_bot_key ON bot_logs (bot_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_logs_timestamp ON bot_logs (timestamp)")

        # --- 设置表等 (不变) ---
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS invitation_codes (code TEXT PRIMARY KEY, generated_by TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_used BOOLEAN DEFAULT 0, used_by TEXT, FOREIGN KEY (generated_by) REFERENCES users (public_key))')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_codes_generated_by ON invitation_codes (generated_by)")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('default_invitation_quota', str(DEFAULT_INVITATION_QUOTA)))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('welcome_bonus_amount', '300'))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('inviter_bonus_amount', '200'))

        # +++ (修改) 新增 V2 机器人全局设置 (替换旧的删除逻辑) +++
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('bot_system_enabled', 'False'))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('bot_check_interval_seconds', '30'))
        
        conn.commit()
        print("数据库初始化完成 (V3.2 Bots Re-arch)。")

# --- 核心设置函数 ---

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

# --- 核心事务逻辑 ---

def _execute_system_tx_logic(from_key, to_key, amount, note, conn):
    """(内部函数) 执行系统交易的核心逻辑，被 _create_system_transaction 调用。"""
    cursor = conn.cursor()
    try:
        if from_key != GENESIS_ACCOUNT:
            # (重构) 在事务连接中直接查询余额
            cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (from_key,))
            from_balance_row = cursor.fetchone()
            current_from_balance = from_balance_row['balance'] if from_balance_row else 0.0
            if current_from_balance < amount:
                return False, f"系统账户 {from_key} 余额不足"
            new_from_balance = current_from_balance - amount
            cursor.execute("UPDATE balances SET balance = ? WHERE public_key = ?", (new_from_balance, from_key))

        if to_key != BURN_ACCOUNT:
            cursor.execute("SELECT balance FROM balances WHERE public_key = ?", (to_key,))
            to_balance_row = cursor.fetchone()
            current_to_balance = to_balance_row['balance'] if to_balance_row else 0.0
            new_to_balance = current_to_balance + amount
            cursor.execute("INSERT OR REPLACE INTO balances (public_key, balance) VALUES (?, ?)", (to_key, new_to_balance))

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

# --- 通知函数 (新增) ---

def create_notification(user_key: str, message: str, conn):
    """
    (内部函数) 在事务连接中为指定用户创建一条通知。
    """
    try:
        cursor = conn.cursor()
        notif_id = str(uuid.uuid4())
        # 确保 timestamp 使用 time.time() 的浮点数
        cursor.execute(
            "INSERT INTO notifications (notif_id, user_key, message, is_read, timestamp) VALUES (?, ?, ?, ?, ?)",
            (notif_id, user_key, message, 0, time.time())
        )
        return True, "通知创建成功"
    except Exception as e:
        print(f"!!!!!!!!!!!!!! 严重错误：无法创建通知 for {user_key[:10]}... !!!!!!!!!!!!!!")
        print(f"错误: {e}")
        return False, f"通知创建失败: {e}"
def _create_system_transaction(from_key: str, to_key: str, amount: float, note: str = None, conn=None) -> (bool, str):
    """(重构) 创建一笔系统交易 (铸币/销毁/托管)。"""
    def run_logic(connection):
        return _execute_system_tx_logic(from_key, to_key, amount, note, connection)

    if conn:
        # 如果已在事务中，直接运行
        return run_logic(conn)
    else:
        # 否则，创建新事务
        with LEDGER_LOCK, get_db_connection() as new_conn:
            success, detail = run_logic(new_conn)
            if success:
                new_conn.commit()
            else:
                new_conn.rollback()
            return success, detail