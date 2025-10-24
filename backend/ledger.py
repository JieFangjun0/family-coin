import sqlite3
import time
import uuid
import threading
import json
import os
from contextlib import contextmanager
from shared.crypto_utils import verify_signature
from backend.nft_logic import get_handler
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
        
        # --- 用户表 (不变) ---
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
        
        # <<< 核心修改: 废弃旧的 shop_items 表 >>>
        cursor.execute("DROP TABLE IF EXISTS shop_items")

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
        # 这个表专门用于响应 'SEEK' 类型的挂单
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
        
        # --- 设置表等 (不变) ---
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS invitation_codes (code TEXT PRIMARY KEY, generated_by TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_used BOOLEAN DEFAULT 0, used_by TEXT, FOREIGN KEY (generated_by) REFERENCES users (public_key))')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_codes_generated_by ON invitation_codes (generated_by)")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('default_invitation_quota', str(DEFAULT_INVITATION_QUOTA)))
        
        conn.commit()
        print("数据库初始化完成 (V3.0 Market)。")

# <<< --- 核心重构：全新的、通用的NFT验证函数 --- >>>
def _validate_nft_for_trade(cursor, nft_id: str, expected_owner: str) -> (bool, str, dict):
    """
    (内部通用函数) 验证一个NFT是否可以被交易。
    返回: (是否可交易, 错误信息, NFT数据字典)
    """
    cursor.execute("SELECT nft_id, owner_key, nft_type, data, status FROM nfts WHERE nft_id = ?", (nft_id,))
    nft_row = cursor.fetchone()

    if not nft_row:
        return False, "NFT不存在", None
    
    nft = dict(nft_row)
    nft['data'] = json.loads(nft['data']) # 提前解析data

    if nft['status'] != 'ACTIVE':
        return False, "NFT不是活跃状态", nft
    
    if nft['owner_key'] != expected_owner:
        return False, "你不是该NFT的所有者", nft

    # --- 动态调用插件的特定检查逻辑 ---
    handler = get_handler(nft['nft_type'])
    if not handler:
        # 如果找不到处理器，为安全起见，禁止交易
        return False, f"未找到类型为 {nft['nft_type']} 的处理器，交易被拒绝", nft

    # 调用插件自己的 is_tradable 方法
    is_ok, reason = handler.is_tradable(nft)
    if not is_ok:
        return False, reason, nft
            
    return True, "验证通过", nft

# <<< NFT 架构升级: 新增 NFT 数据库核心函数 >>>

def mint_nft(owner_key: str, nft_type: str, data: dict, conn=None) -> (bool, str, str):
    """(底层) 将一个新的 NFT 记录到数据库中。"""
    def run_logic(connection):
        try:
            cursor = connection.cursor()
            nft_id = str(uuid.uuid4())
            data_json = json.dumps(data, ensure_ascii=False)

            cursor.execute("SELECT 1 FROM users WHERE public_key = ?", (owner_key,))
            if not cursor.fetchone():
                return False, "NFT所有者不存在", None

            cursor.execute(
                "INSERT INTO nfts (nft_id, owner_key, nft_type, data, status) VALUES (?, ?, ?, ?, 'ACTIVE')",
                (nft_id, owner_key, nft_type, data_json)
            )
            return True, "NFT 铸造成功", nft_id
        except Exception as e:
            return False, f"NFT 铸造时数据库出错: {e}", None

    if conn:
        return run_logic(conn)
    else:
        with LEDGER_LOCK, get_db_connection() as new_conn:
            success, detail, nft_id = run_logic(new_conn)
            if success:
                new_conn.commit()
            else:
                new_conn.rollback()
            return success, detail, nft_id


def get_nft_by_id(nft_id: str) -> dict:
    """根据 ID 获取单个 NFT 的详细信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT nft_id, owner_key, nft_type, data, status, 
                   CAST(strftime('%s', created_at) AS REAL) as created_at
            FROM nfts 
            WHERE nft_id = ?
        """
        cursor.execute(query, (nft_id,))
        nft = cursor.fetchone()
        if not nft:
            return None
        nft_dict = dict(nft)
        nft_dict['data'] = json.loads(nft_dict['data'])
        return nft_dict

def get_nfts_by_owner(owner_key: str) -> list:
    """获取指定所有者的所有 NFT。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT nft_id, owner_key, nft_type, data, status, 
                   CAST(strftime('%s', created_at) AS REAL) as created_at
            FROM nfts 
            WHERE owner_key = ? AND status = 'ACTIVE' 
            ORDER BY created_at DESC
        """
        cursor.execute(query, (owner_key,))
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

def _change_nft_owner(nft_id: str, new_owner_key: str, conn) -> (bool, str):
    """(内部函数) 转移NFT所有权"""
    cursor = conn.cursor()
    cursor.execute("UPDATE nfts SET owner_key = ? WHERE nft_id = ?", (new_owner_key, nft_id))
    if cursor.rowcount == 0:
        return False, f"转移NFT所有权失败: 未找到NFT {nft_id}"
    return True, "NFT所有权转移成功"

def create_market_listing(lister_key: str, listing_type: str, nft_id: str, nft_type: str, description: str, price: float, auction_hours: float = None) -> (bool, str):
    """在市场上创建一个新的挂单（销售、拍卖或求购）。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            listing_id = str(uuid.uuid4())
            
            if listing_type in ['SALE', 'AUCTION']:
                if not nft_id: return False, "挂卖或拍卖必须提供nft_id"
                
                # <<< 核心重构：使用新的通用验证函数 >>>
                is_tradable, reason, _ = _validate_nft_for_trade(cursor, nft_id, lister_key)
                if not is_tradable:
                    return False, reason
                
                success, detail = _change_nft_owner(nft_id, ESCROW_ACCOUNT, conn)
                if not success:
                    conn.rollback()
                    return False, detail

                end_time = time.time() + auction_hours * 3600 if listing_type == 'AUCTION' else None
                cursor.execute(
                    """
                    INSERT INTO market_listings (listing_id, lister_key, listing_type, nft_id, nft_type, description, price, end_time, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                    """,
                    (listing_id, lister_key, listing_type, nft_id, nft_type, description, price, end_time)
                )

            elif listing_type == 'SEEK':
                if price <= 0: return False, "求购预算必须大于0"
                success, detail = _create_system_transaction(lister_key, ESCROW_ACCOUNT, price, f"托管求购资金: {description[:20]}", conn)
                if not success:
                    conn.rollback()
                    return False, f"托管求购资金失败: {detail}"
                
                cursor.execute(
                    """
                    INSERT INTO market_listings (listing_id, lister_key, listing_type, nft_type, description, price, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
                    """,
                    (listing_id, lister_key, listing_type, nft_type, description, price)
                )
            else:
                return False, "无效的挂单类型"

            conn.commit()
            return True, "挂单成功！"
        except Exception as e:
            conn.rollback()
            return False, f"创建挂单失败: {e}"

def cancel_market_listing(lister_key: str, listing_id: str) -> (bool, str):
    """取消一个挂单。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM market_listings WHERE listing_id = ? AND lister_key = ? AND status = 'ACTIVE'", (listing_id, lister_key))
            listing = cursor.fetchone()
            if not listing: return False, "未找到您的有效挂单"

            if listing['listing_type'] in ['SALE', 'AUCTION']:
                # --- 取消挂卖/拍卖: 退还NFT ---
                success, detail = _change_nft_owner(listing['nft_id'], lister_key, conn)
                if not success:
                    conn.rollback()
                    return False, f"退还NFT失败: {detail}"

            elif listing['listing_type'] == 'SEEK':
                # --- 取消求购: 退还资金 ---
                cursor.execute("SELECT 1 FROM market_offers WHERE listing_id = ? AND status = 'ACCEPTED'", (listing_id,))
                if cursor.fetchone():
                    return False, "已有报价被接受，无法取消此求购"

                success, detail = _create_system_transaction(ESCROW_ACCOUNT, lister_key, listing['price'], f"取消求购，退回资金", conn)
                if not success:
                    conn.rollback()
                    return False, f"退还资金失败: {detail}"

            cursor.execute("UPDATE market_listings SET status = 'CANCELLED' WHERE listing_id = ?", (listing_id,))
            conn.commit()
            return True, "挂单已取消"
        except Exception as e:
            conn.rollback()
            return False, f"取消挂单失败: {e}"

def execute_sale(buyer_key: str, listing_id: str) -> (bool, str):
    """执行一个直接购买操作。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM market_listings WHERE listing_id = ? AND listing_type = 'SALE' AND status = 'ACTIVE'", (listing_id,))
            listing = cursor.fetchone()
            if not listing: return False, "未找到该出售商品"
            if listing['lister_key'] == buyer_key: return False, "不能购买自己的商品"

            price = listing['price']
            seller_key = listing['lister_key']
            nft_id = listing['nft_id']

            # 1. 支付货款 (买家 -> 卖家)
            success, detail = _create_system_transaction(buyer_key, seller_key, price, f"购买NFT: {nft_id[:8]}", conn)
            if not success:
                conn.rollback()
                return False, f"支付失败: {detail}"

            # 2. 交付NFT (托管 -> 买家)
            success, detail = _change_nft_owner(nft_id, buyer_key, conn)
            if not success:
                conn.rollback()
                return False, f"交付NFT失败: {detail}"

            # 3. 更新挂单状态
            cursor.execute("UPDATE market_listings SET status = 'SOLD' WHERE listing_id = ?", (listing_id,))
            conn.commit()
            return True, "购买成功！"
        except Exception as e:
            conn.rollback()
            return False, f"购买失败: {e}"

def place_auction_bid(bidder_key: str, listing_id: str, bid_amount: float) -> (bool, str):
    """对一个拍卖品出价。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM market_listings WHERE listing_id = ? AND listing_type = 'AUCTION' AND status = 'ACTIVE'", (listing_id,))
            listing = cursor.fetchone()
            if not listing: return False, "未找到该拍卖品"
            if listing['lister_key'] == bidder_key: return False, "不能对自己的商品出价"
            if time.time() > listing['end_time']: return False, "拍卖已结束"
            
            price = listing['price']
            highest_bid = listing['highest_bid']
            
            if bid_amount <= highest_bid: return False, f"出价必须高于当前最高价 {highest_bid}"
            if bid_amount < price and highest_bid == 0: return False, f"首次出价必须不低于起拍价 {price}"

            if get_balance(bidder_key) < bid_amount: return False, "你的余额不足以支撑此出价"

            if listing['highest_bidder']:
                success, detail = _create_system_transaction(ESCROW_ACCOUNT, listing['highest_bidder'], listing['highest_bid'], f"拍卖出价被超过，退款", conn)
                if not success:
                    conn.rollback()
                    return False, f"退还上一位出价者资金失败: {detail}"
            
            success, detail = _create_system_transaction(bidder_key, ESCROW_ACCOUNT, bid_amount, f"托管拍卖出价", conn)
            if not success:
                conn.rollback()
                return False, f"托管您的出价资金失败: {detail}"
            
            cursor.execute(
                "UPDATE market_listings SET highest_bid = ?, highest_bidder = ? WHERE listing_id = ?",
                (bid_amount, bidder_key, listing_id)
            )
            conn.commit()
            return True, f"出价成功！您当前是最高出价者。"
        except Exception as e:
            conn.rollback()
            return False, f"出价失败: {e}"

def resolve_finished_auctions():
    """(系统调用) 结算所有已结束的拍卖。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM market_listings WHERE listing_type = 'AUCTION' AND status = 'ACTIVE' AND end_time < ?", (time.time(),))
        auctions_to_resolve = cursor.fetchall()
        
        resolved_count = 0
        for auction in auctions_to_resolve:
            listing_id = auction['listing_id']
            if auction['highest_bidder']:
                seller_key = auction['lister_key']
                winner_key = auction['highest_bidder']
                nft_id = auction['nft_id']
                final_price = auction['highest_bid']

                success, detail = _create_system_transaction(ESCROW_ACCOUNT, seller_key, final_price, f"拍卖成功收款", conn)
                if not success: continue
                
                success, detail = _change_nft_owner(nft_id, winner_key, conn)
                if not success: continue
                
                cursor.execute("UPDATE market_listings SET status = 'SOLD' WHERE listing_id = ?", (listing_id,))
            else:
                success, detail = _change_nft_owner(auction['nft_id'], auction['lister_key'], conn)
                if not success: continue

                cursor.execute("UPDATE market_listings SET status = 'EXPIRED' WHERE listing_id = ?", (listing_id,))
            
            resolved_count += 1
        conn.commit()
        return resolved_count

def make_seek_offer(offerer_key: str, listing_id: str, offered_nft_id: str) -> (bool, str):
    """针对一个求购单，提供一个NFT作为报价。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM market_listings WHERE listing_id = ? AND listing_type = 'SEEK' AND status = 'ACTIVE'", (listing_id,))
            listing = cursor.fetchone()
            if not listing: return False, "求购信息不存在或已结束"
            if listing['lister_key'] == offerer_key: return False, "不能向自己的求购单报价"

            # <<< 核心重构：使用新的通用验证函数 >>>
            is_tradable, reason, nft_details = _validate_nft_for_trade(cursor, offered_nft_id, offerer_key)
            if not is_tradable:
                return False, reason
            
            if nft_details['nft_type'] != listing['nft_type']: 
                return False, f"求购的NFT类型为 {listing['nft_type']}, 您提供的是 {nft_details['nft_type']}"

            cursor.execute("SELECT 1 FROM market_offers WHERE listing_id = ? AND offered_nft_id = ?", (listing_id, offered_nft_id))
            if cursor.fetchone(): return False, "您已经用这个NFT报过价了"

            offer_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO market_offers (offer_id, listing_id, offerer_key, offered_nft_id, status) VALUES (?, ?, ?, ?, 'PENDING')",
                (offer_id, listing_id, offerer_key, offered_nft_id)
            )
            conn.commit()
            return True, "报价成功，请等待求购方回应。"
        except Exception as e:
            conn.rollback()
            return False, f"报价失败: {e}"

def respond_to_seek_offer(seeker_key: str, offer_id: str, accept: bool) -> (bool, str):
    """求购方回应一个报价 (接受或拒绝)。"""
    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            query = """
                SELECT o.*, l.lister_key, l.price, l.status as listing_status
                FROM market_offers o JOIN market_listings l ON o.listing_id = l.listing_id
                WHERE o.offer_id = ? AND o.status = 'PENDING'
            """
            cursor.execute(query, (offer_id,))
            offer_details = cursor.fetchone()
            
            if not offer_details: return False, "报价不存在或已处理"
            if offer_details['lister_key'] != seeker_key: return False, "您不是该求购单的发布者"
            if offer_details['listing_status'] != 'ACTIVE': return False, "该求购已结束"

            if not accept:
                cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE offer_id = ?", (offer_id,))
                conn.commit()
                return True, "已拒绝该报价"

            offerer_key = offer_details['offerer_key']
            offered_nft_id = offer_details['offered_nft_id']
            price = offer_details['price']
            listing_id = offer_details['listing_id']
            
            success, detail = _create_system_transaction(ESCROW_ACCOUNT, offerer_key, price, f"完成求购交易", conn)
            if not success:
                conn.rollback()
                return False, f"支付报价人失败: {detail}"

            success, detail = _change_nft_owner(offered_nft_id, seeker_key, conn)
            if not success:
                conn.rollback()
                return False, f"转移NFT失败: {detail}"

            cursor.execute("UPDATE market_offers SET status = 'ACCEPTED' WHERE offer_id = ?", (offer_id,))
            cursor.execute("UPDATE market_listings SET status = 'FULFILLED' WHERE listing_id = ?", (listing_id,))
            
            cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE listing_id = ? AND status = 'PENDING'", (listing_id,))
            
            conn.commit()
            return True, "交易成功！您已获得新的NFT。"
        except Exception as e:
            conn.rollback()
            return False, f"处理报价失败: {e}"
        
def get_market_listings(listing_type: str, exclude_owner: str = None) -> list:
    """获取市场上的所有挂单。"""
    resolve_finished_auctions()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT l.*, u.username as lister_username, n.data as nft_data
            FROM market_listings l
            JOIN users u ON l.lister_key = u.public_key
            LEFT JOIN nfts n ON l.nft_id = n.nft_id
            WHERE l.listing_type = ? AND l.status = 'ACTIVE'
        """
        params = [listing_type]
        if exclude_owner:
            query += " AND l.lister_key != ?"
            params.append(exclude_owner)
        query += " ORDER BY l.created_at DESC"
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            if row_dict.get('nft_data'):
                row_dict['nft_data'] = json.loads(row_dict['nft_data'])
            results.append(row_dict)
        return results

def get_listing_details(listing_id: str) -> dict:
    """获取单个挂单的详细信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM market_listings WHERE listing_id = ?", (listing_id,))
        listing = cursor.fetchone()
        return dict(listing) if listing else None

def get_offers_for_listing(listing_id: str) -> list:
    """获取一个求购单收到的所有报价。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT o.*, u.username as offerer_username, n.nft_type, n.data as nft_data
            FROM market_offers o
            JOIN users u ON o.offerer_key = u.public_key
            JOIN nfts n ON o.offered_nft_id = n.nft_id
            WHERE o.listing_id = ?
            ORDER BY o.created_at DESC
        """
        cursor.execute(query, (listing_id,))
        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            row_dict['nft_data'] = json.loads(row_dict['nft_data'])
            results.append(row_dict)
        return results

def get_my_market_activity(public_key: str) -> dict:
    """获取我所有的市场活动（挂单和报价）。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM market_listings WHERE lister_key = ? ORDER BY created_at DESC", (public_key,))
        my_listings = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM market_offers WHERE offerer_key = ? ORDER BY created_at DESC", (public_key,))
        my_offers = [dict(row) for row in cursor.fetchall()]
        return {"listings": my_listings, "offers": my_offers}

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
            
            if (time.time() - code_data['created_at_unix']) > 86400 * 7:
                return False, "邀请码已过期"
                
            inviter_key = code_data['generated_by']
            
            default_quota_str = get_setting('default_invitation_quota')
            default_quota = int(default_quota_str) if default_quota_str and default_quota_str.isdigit() else DEFAULT_INVITATION_QUOTA
            
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
        if from_key != GENESIS_ACCOUNT:
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
                success, detail = _create_system_transaction(
                    from_key=public_key, to_key=BURN_ACCOUNT, amount=current_balance,
                    note=f"彻底清除用户 {public_key[:10]}... 并清零资产", conn=conn
                )
                if not success:
                    conn.rollback()
                    return False, f"清除用户时清零资产失败: {detail}"

            cursor.execute("SELECT listing_id FROM market_listings WHERE lister_key = ? and status = 'ACTIVE'", (public_key,))
            user_listings = cursor.fetchall()
            for listing in user_listings:
                _success, _detail = cancel_market_listing(public_key, listing['listing_id'])
                if not _success:
                    print(f"Warning: Purging user, failed to cancel listing {listing['listing_id']}: {_detail}")

            cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE listing_id IN (SELECT listing_id FROM market_listings WHERE lister_key = ?) AND status = 'PENDING'", (public_key,))

            cursor.execute("DELETE FROM market_offers WHERE offerer_key = ?", (public_key,))

            cursor.execute("UPDATE nfts SET status = 'BURNED' WHERE owner_key = ?", (public_key,))

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

def nuke_database() -> (bool, str):
    """(管理员功能) 彻底删除数据库文件并重建。"""
    with LEDGER_LOCK:
        try:
            if os.path.exists(DATABASE_PATH):
                os.remove(DATABASE_PATH)
            
            init_db()
            
            return True, "数据库已重置并重建。"
        except Exception as e:
            return False, f"重置数据库失败: {e}"

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

def count_users() -> int:
    """统计数据库中的用户总数。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        return result[0] if result else 0

def create_genesis_user(username: str, public_key: str, private_key: str) -> (bool, str):
    """创建第一个（创世）管理员用户。"""
    if count_users() > 0:
        return False, "系统已经初始化，无法创建创世用户。"

    with LEDGER_LOCK, get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            inv_quota = 999999

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

def admin_get_user_private_key(public_key: str) -> str:
    """(管理员功能) 获取用户的私钥。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT private_key_pem FROM users WHERE public_key = ?", (public_key,))
        result = cursor.fetchone()
        return result['private_key_pem'] if result and result['private_key_pem'] else None