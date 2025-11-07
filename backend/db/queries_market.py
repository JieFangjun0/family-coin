# backend/db/queries_market.py

import time
import json
import uuid
from typing import List
from psycopg2.extras import DictCursor

from backend.db.database import (
    get_db_connection, _create_system_transaction, 
    ESCROW_ACCOUNT, create_notification
)
from backend.db.queries_nft import _validate_nft_for_trade, _change_nft_owner
from backend.db.queries_user import get_balance


def _log_market_trade(conn, listing_id: str, nft_id: str, nft_type: str, trade_type: str, seller_key: str, buyer_key: str, price: float):
    """(内部函数) 记录一笔成功的市场交易。"""
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            trade_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO market_trade_history
                (trade_id, listing_id, nft_id, nft_type, trade_type, seller_key, buyer_key, price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (trade_id, listing_id, nft_id, nft_type, trade_type, seller_key, buyer_key, price)
            )
    except Exception as e:
        print(f"!!!!!!!!!!!!!! 严重错误：无法将市场交易 {listing_id} 写入 market_trade_history !!!!!!!!!!!!!!")
        print(f"错误: {e}")

def create_market_listing(lister_key: str, listing_type: str, nft_id: str, nft_type: str, description: str, price: float, auction_hours: float = None) -> (bool, str):
    """在市场上创建一个新的挂单（销售、拍卖或求购）。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                listing_id = str(uuid.uuid4())
                
                if listing_type in ['SALE', 'AUCTION']:
                    if not nft_id: return False, "挂卖或拍卖必须提供nft_id"
                    
                    is_tradable, reason, _ = _validate_nft_for_trade(cursor, nft_id, lister_key)
                    if not is_tradable:
                        return False, reason
                    
                    success, detail = _change_nft_owner(nft_id, ESCROW_ACCOUNT, conn)
                    if not success:
                        conn.rollback()
                        return False, detail

                    end_time_val = time.time() + auction_hours * 3600 if listing_type == 'AUCTION' and auction_hours else None
                    
                    # PostgreSQL 需要显式转换时间戳
                    end_time_sql = "to_timestamp(%s)" if end_time_val else "%s"
                    
                    cursor.execute(
                        f"""
                        INSERT INTO market_listings (listing_id, lister_key, listing_type, nft_id, nft_type, description, price, end_time, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, {end_time_sql}, 'ACTIVE')
                        """,
                        (listing_id, lister_key, listing_type, nft_id, nft_type, description, price, end_time_val)
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
                        VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')
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

def cancel_market_listing_in_tx(conn, lister_key: str, listing_id: str) -> (bool, str):
    """(内部函数) 取消挂单的核心逻辑，在事务中运行。"""
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM market_listings WHERE listing_id = %s AND lister_key = %s AND status = 'ACTIVE' FOR UPDATE", (listing_id, lister_key))
            listing = cursor.fetchone()
            if not listing: return False, "未找到您的有效挂单"

            if listing['listing_type'] in ['SALE', 'AUCTION']:
                success, detail = _change_nft_owner(listing['nft_id'], lister_key, conn)
                if not success:
                    return False, f"退还NFT失败: {detail}"

            elif listing['listing_type'] == 'SEEK':
                cursor.execute("SELECT 1 FROM market_offers WHERE listing_id = %s AND status = 'ACCEPTED'", (listing_id,))
                if cursor.fetchone():
                    return False, "已有报价被接受，无法取消此求购"

                success, detail = _create_system_transaction(ESCROW_ACCOUNT, lister_key, listing['price'], f"取消求购，退回资金", conn)
                if not success:
                    return False, f"退还资金失败: {detail}"

            cursor.execute("UPDATE market_listings SET status = 'CANCELLED' WHERE listing_id = %s", (listing_id,))
            return True, "挂单已取消"
    except Exception as e:
        return False, f"取消挂单逻辑失败: {e}"

def cancel_market_listing(lister_key: str, listing_id: str) -> (bool, str):
    """(公共接口) 取消一个挂单。"""
    with get_db_connection() as conn:
        success, detail = cancel_market_listing_in_tx(conn, lister_key, listing_id)
        if success:
            conn.commit()
        else:
            conn.rollback()
        return success, detail

def execute_sale(buyer_key: str, listing_id: str) -> (bool, str):
    """执行一个直接购买操作。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM market_listings WHERE listing_id = %s AND listing_type = 'SALE' AND status = 'ACTIVE' FOR UPDATE", (listing_id,))
                listing = cursor.fetchone()
                if not listing: return False, "未找到该出售商品"
                if listing['lister_key'] == buyer_key: return False, "不能购买自己的商品"

                price = listing['price']
                seller_key = listing['lister_key']
                nft_id = listing['nft_id']

                success, detail = _create_system_transaction(buyer_key, seller_key, price, f"购买NFT: {nft_id[:8]}", conn)
                if not success:
                    conn.rollback()
                    return False, f"支付失败: {detail}"

                success, detail = _change_nft_owner(nft_id, buyer_key, conn)
                if not success:
                    conn.rollback()
                    return False, f"交付NFT失败: {detail}"

                cursor.execute("UPDATE market_listings SET status = 'SOLD' WHERE listing_id = %s", (listing_id,))
                _log_market_trade(
                    conn=conn, listing_id=listing_id, nft_id=nft_id, nft_type=listing['nft_type'],
                    trade_type='SALE', seller_key=seller_key, buyer_key=buyer_key, price=price
                )
                
                create_notification(
                    user_key=seller_key,
                    message=f"🎉 你的 NFT (ID: {nft_id[:8]}...) 已被购买，你收到了 {price:.2f} FC！",
                    conn=conn
                )
                create_notification(
                    user_key=buyer_key,
                    message=f"🎉 你成功购买了 NFT (ID: {nft_id[:8]}...)！",
                    conn=conn
                )
            conn.commit()
            return True, "购买成功！"
        except Exception as e:
            conn.rollback()
            return False, f"购买失败: {e}"

def place_auction_bid(bidder_key: str, listing_id: str, bid_amount: float) -> (bool, str):
    """对一个拍卖品出价。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM market_listings WHERE listing_id = %s AND listing_type = 'AUCTION' AND status = 'ACTIVE' FOR UPDATE", (listing_id,))
                listing = cursor.fetchone()
                if not listing: return False, "未找到该拍卖品"
                if listing['lister_key'] == bidder_key: return False, "不能对自己的商品出价"
                
                # 检查时间戳
                cursor.execute("SELECT 1 FROM market_listings WHERE listing_id = %s AND end_time < CURRENT_TIMESTAMP", (listing_id,))
                if cursor.fetchone():
                    return False, "拍卖已结束"
                
                price = listing['price']
                highest_bid = listing['highest_bid']
                
                if bid_amount <= highest_bid: return False, f"出价必须高于当前最高价 {highest_bid}"
                if bid_amount < price and highest_bid == 0: return False, f"首次出价必须不低于起拍价 {price}"

                if get_balance(bidder_key) < bid_amount: return False, "你的余额不足以支撑此出价"

                if listing['highest_bidder']:
                    success, detail = _create_system_transaction(ESCROW_ACCOUNT, listing['highest_bidder'], listing['highest_bid'], f"拍卖出价被超过，退款", conn)
                    
                    create_notification(
                        user_key=listing['highest_bidder'],
                        message=f"出价被超过！你在拍卖品 {listing_id[:8]}... 上的出价 ({listing['highest_bid']:.2f} FC) 已被 {bid_amount:.2f} FC 超越，资金已退还。",
                        conn=conn
                    )
                    if not success:
                        conn.rollback()
                        return False, f"退还上一位出价者资金失败: {detail}"
                
                create_notification(
                    user_key=listing['lister_key'],
                    message=f"你的拍卖品 {listing_id[:8]}... 收到新出价 {bid_amount:.2f} FC！",
                    conn=conn
                )
                
                success, detail = _create_system_transaction(bidder_key, ESCROW_ACCOUNT, bid_amount, f"托管拍卖出价", conn)
                if not success:
                    conn.rollback()
                    return False, f"托管您的出价资金失败: {detail}"
                
                try:
                    bid_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO auction_bids (bid_id, listing_id, bidder_key, bid_amount) VALUES (%s, %s, %s, %s)",
                        (bid_id, listing_id, bidder_key, bid_amount)
                    )
                except Exception as e:
                    print(f"⚠️ 警告: 记录拍卖出价失败: {e}")
                
                cursor.execute(
                    "UPDATE market_listings SET highest_bid = %s, highest_bidder = %s WHERE listing_id = %s",
                    (bid_amount, bidder_key, listing_id)
                )
            conn.commit()
            return True, f"出价成功！您当前是最高出价者。"
        except Exception as e:
            conn.rollback()
            return False, f"出价失败: {e}"

def resolve_finished_auctions():
    """(系统调用) 结算所有已结束的拍卖。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # 使用 CURRENT_TIMESTAMP 替换 time.time()
                cursor.execute("SELECT * FROM market_listings WHERE listing_type = 'AUCTION' AND status = 'ACTIVE' AND end_time < CURRENT_TIMESTAMP FOR UPDATE")
                auctions_to_resolve = cursor.fetchall()
                
                resolved_count = 0
                for auction in auctions_to_resolve:
                    listing_id = auction['listing_id']
                    nft_id = auction['nft_id'] 
                    
                    if auction['highest_bidder']:
                        seller_key = auction['lister_key']
                        winner_key = auction['highest_bidder']
                        final_price = auction['highest_bid']

                        success, detail = _create_system_transaction(ESCROW_ACCOUNT, seller_key, final_price, f"拍卖成功收款", conn)
                        if not success: continue
                        
                        success, detail = _change_nft_owner(nft_id, winner_key, conn)
                        if not success: continue
                        
                        cursor.execute("UPDATE market_listings SET status = 'SOLD' WHERE listing_id = %s", (listing_id,))
                        
                        _log_market_trade(
                            conn=conn, listing_id=listing_id, nft_id=nft_id, nft_type=auction['nft_type'],
                            trade_type='AUCTION', seller_key=seller_key, buyer_key=winner_key, price=final_price
                        )
                        create_notification(
                            user_key=seller_key,
                            message=f"💰 你的拍卖品 {nft_id[:8]}... 已成交，你收到了 {final_price:.2f} FC！",
                            conn=conn
                        )
                        create_notification(
                            user_key=winner_key,
                            message=f"🎉 恭喜！你以 {final_price:.2f} FC 成功拍下 NFT {nft_id[:8]}...！",
                            conn=conn
                        )
                    else:
                        # 流拍
                        success, detail = _change_nft_owner(nft_id, auction['lister_key'], conn)
                        if not success: continue
                        cursor.execute("UPDATE market_listings SET status = 'EXPIRED' WHERE listing_id = %s", (listing_id,))
                        create_notification(
                            user_key=auction['lister_key'],
                            message=f"💔 你的拍卖品 {nft_id[:8]}... 流拍，NFT已退回。",
                            conn=conn
                        )
                    
                    resolved_count += 1
            conn.commit()
            return resolved_count
        except Exception as e:
            print(f"!!!!!!!!!!!!!! 严重错误：结算拍卖失败 !!!!!!!!!!!!!!")
            print(f"错误: {e}")
            conn.rollback()
            return 0


def make_seek_offer(offerer_key: str, listing_id: str, offered_nft_id: str) -> (bool, str):
    """针对一个求购单，提供一个NFT作为报价。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM market_listings WHERE listing_id = %s AND listing_type = 'SEEK' AND status = 'ACTIVE' FOR UPDATE", (listing_id,))
                listing = cursor.fetchone()
                if not listing: return False, "求购信息不存在或已结束"
                if listing['lister_key'] == offerer_key: return False, "不能向自己的求购单报价"

                is_tradable, reason, nft_details = _validate_nft_for_trade(cursor, offered_nft_id, offerer_key)
                if not is_tradable:
                    return False, reason
                
                if nft_details['nft_type'] != listing['nft_type']: 
                    return False, f"求购的NFT类型为 {listing['nft_type']}, 您提供的是 {nft_details['nft_type']}"

                cursor.execute("SELECT 1 FROM market_offers WHERE listing_id = %s AND offered_nft_id = %s", (listing_id, offered_nft_id))
                if cursor.fetchone(): return False, "您已经用这个NFT报过价了"

                offer_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO market_offers (offer_id, listing_id, offerer_key, offered_nft_id, status) VALUES (%s, %s, %s, %s, 'PENDING')",
                    (offer_id, listing_id, offerer_key, offered_nft_id)
                )
            conn.commit()
            return True, "报价成功，请等待求购方回应。"
        except Exception as e:
            conn.rollback()
            return False, f"报价失败: {e}"

def respond_to_seek_offer(seeker_key: str, offer_id: str, accept: bool) -> (bool, str):
    """求购方回应一个报价 (接受或拒绝)。"""
    with get_db_connection() as conn:
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                query = """
                    SELECT o.*, l.lister_key, l.price, l.status as listing_status, l.nft_type
                    FROM market_offers o JOIN market_listings l ON o.listing_id = l.listing_id
                    WHERE o.offer_id = %s AND o.status = 'PENDING'
                    FOR UPDATE OF o, l
                """
                cursor.execute(query, (offer_id,))
                offer_details = cursor.fetchone()
                
                if not offer_details: return False, "报价不存在或已处理"
                if offer_details['lister_key'] != seeker_key: return False, "您不是该求购单的发布者"
                if offer_details['listing_status'] != 'ACTIVE': return False, "该求购已结束"

                # 提前定义变量以供通知使用
                offerer_key = offer_details['offerer_key']
                listing_id = offer_details['listing_id']

                if not accept:
                    cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE offer_id = %s", (offer_id,))
                    
                    create_notification(
                        user_key=offerer_key,
                        message=f"你的报价被拒。求购单 {listing_id[:8]}... 的发布者拒绝了你的 NFT 报价。",
                        conn=conn
                    )
                    conn.commit()
                    return True, "已拒绝该报价"

                offered_nft_id = offer_details['offered_nft_id']
                price = offer_details['price']
                
                success, detail = _create_system_transaction(ESCROW_ACCOUNT, offerer_key, price, f"完成求购交易", conn)
                if not success:
                    conn.rollback()
                    return False, f"支付报价人失败: {detail}"

                success, detail = _change_nft_owner(offered_nft_id, seeker_key, conn)
                if not success:
                    conn.rollback()
                    return False, f"转移NFT失败: {detail}"

                cursor.execute("UPDATE market_offers SET status = 'ACCEPTED' WHERE offer_id = %s", (offer_id,))
                cursor.execute("UPDATE market_listings SET status = 'FULFILLED' WHERE listing_id = %s", (listing_id,))
                
                create_notification(
                    user_key=offerer_key,
                    message=f"🎉 恭喜！你的 NFT 报价被接受，你收到了 {price:.2f} FC！",
                    conn=conn
                )
                create_notification(
                    user_key=seeker_key,
                    message=f"🎉 你成功完成了求购交易，获得了新的 NFT！",
                    conn=conn
                )
                cursor.execute("UPDATE market_offers SET status = 'REJECTED' WHERE listing_id = %s AND status = 'PENDING'", (listing_id,))
                
                _log_market_trade(
                    conn=conn, listing_id=listing_id, nft_id=offered_nft_id, nft_type=offer_details['nft_type'],
                    trade_type='SEEK', seller_key=offerer_key, buyer_key=seeker_key, price=price
                )
            conn.commit()
            return True, "交易成功！您已获得新的NFT。"
        except Exception as e:
            conn.rollback()
            return False, f"处理报价失败: {e}"

def get_market_listings(listing_type: str, exclude_owner: str = None, search_term: str = None) -> list:
    """获取市场上的所有挂单。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT 
                    l.listing_id, l.lister_key, l.listing_type, l.nft_id, l.nft_type,
                    l.description, l.price, 
                    EXTRACT(EPOCH FROM l.end_time) as end_time, 
                    l.status, l.highest_bidder,
                    l.highest_bid,
                    u.username as lister_username, 
                    u.uid as lister_uid, 
                    n.data as nft_data,
                    EXTRACT(EPOCH FROM l.created_at) as created_at
                FROM market_listings l
                JOIN users u ON l.lister_key = u.public_key
                LEFT JOIN nfts n ON l.nft_id = n.nft_id
                WHERE l.listing_type = %s AND l.status = 'ACTIVE'
            """
            params = [listing_type]
            if exclude_owner:
                query += " AND l.lister_key != %s"
                params.append(exclude_owner)
                
            if search_term:
                query += " AND l.description LIKE %s"
                params.append(f"%{search_term}%")
            
            query += " ORDER BY l.created_at DESC"
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                if row_dict.get('nft_data'):
                    try:
                        row_dict['nft_data'] = json.loads(row_dict['nft_data'])
                    except json.JSONDecodeError:
                        row_dict['nft_data'] = None # 处理脏数据
                
                results.append(row_dict)
            return results

def get_listing_details(listing_id: str) -> dict:
    """获取单个挂单的详细信息。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM market_listings WHERE listing_id = %s", (listing_id,))
            listing = cursor.fetchone()
            return dict(listing) if listing else None

def get_offers_for_listing(listing_id: str) -> list:
    """获取一个求购单收到的所有报价。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT o.*, u.username as offerer_username, u.uid as offerer_uid, n.nft_type, n.data as nft_data,
                       EXTRACT(EPOCH FROM o.created_at) as created_at
                FROM market_offers o
                JOIN users u ON o.offerer_key = u.public_key
                JOIN nfts n ON o.offered_nft_id = n.nft_id
                WHERE o.listing_id = %s
                ORDER BY o.created_at DESC
            """
            cursor.execute(query, (listing_id,))
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                try:
                    row_dict['nft_data'] = json.loads(row_dict['nft_data'])
                except json.JSONDecodeError:
                    row_dict['nft_data'] = None
                results.append(row_dict)
            return results

def get_bids_for_listing(listing_id: str) -> list:
    """获取一个拍卖挂单的所有出价历史。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT 
                    b.bid_amount, 
                    EXTRACT(EPOCH FROM b.created_at) as created_at,
                    u.username as bidder_username,
                    u.uid as bidder_uid
                FROM auction_bids b
                JOIN users u ON b.bidder_key = u.public_key
                WHERE b.listing_id = %s
                ORDER BY b.created_at DESC
            """
            cursor.execute(query, (listing_id,))
            return [dict(row) for row in cursor.fetchall()]

def get_my_market_activity(public_key: str) -> dict:
    """获取我所有的市场活动（挂单和报价）。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            
            listings_query = """
                SELECT 
                    listing_id, lister_key, listing_type, nft_id, nft_type, 
                    description, price, 
                    EXTRACT(EPOCH FROM end_time) as end_time, 
                    status, highest_bidder, 
                    highest_bid, EXTRACT(EPOCH FROM created_at) as created_at
                FROM market_listings 
                WHERE lister_key = %s 
                ORDER BY created_at DESC
            """
            cursor.execute(listings_query, (public_key,))
            my_listings = [dict(row) for row in cursor.fetchall()]
            
            offers_query = """
                SELECT 
                    offer_id, listing_id, offerer_key, offered_nft_id, status,
                    EXTRACT(EPOCH FROM created_at) as created_at
                FROM market_offers 
                WHERE offerer_key = %s 
                ORDER BY created_at DESC
            """
            cursor.execute(offers_query, (public_key,))
            my_offers = [dict(row) for row in cursor.fetchall()]

            return {"listings": my_listings, "offers": my_offers}

def admin_get_market_trade_history(limit: int = 100) -> List[dict]:
    """(管理员功能) 获取最近的市场成交记录。"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT
                    h.trade_id, h.listing_id, h.nft_id, h.nft_type, h.trade_type,
                    h.seller_key, h.buyer_key, h.price,
                    EXTRACT(EPOCH FROM h.timestamp) as timestamp,
                    seller.username as seller_username,
                    seller.uid as seller_uid,
                    buyer.username as buyer_username,
                    buyer.uid as buyer_uid,
                    l.description as listing_description
                FROM market_trade_history h
                LEFT JOIN users seller ON h.seller_key = seller.public_key
                LEFT JOIN users buyer ON h.buyer_key = buyer.public_key
                LEFT JOIN market_listings l ON h.listing_id = l.listing_id
                ORDER BY h.timestamp DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]