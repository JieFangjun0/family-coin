# backend/api/routes_market.py

from fastapi import APIRouter, HTTPException
from typing import List, Dict
from backend.db import queries_market, queries_user
from backend.db.database import get_db_connection, _create_system_transaction, BURN_ACCOUNT
from backend.api.models import (
    MarketSignedRequest, MarketListingRequest, SuccessResponse,
    MarketActionMessage, MarketBidRequest, BidHistoryResponse,
    MarketOfferRequest, MarketOfferResponseRequest,
    ShopCreateNftRequest, ShopActionRequest
)
from backend.api.dependencies import get_verified_message
from backend.nft_logic import NFT_HANDLERS, get_handler
from backend.db import queries_user

router = APIRouter()

def api_get_market_listings(listing_type: str, exclude_owner: str = None, search_term: str = None): # <-- 核心修改: 添加 search_term
    items_raw = queries_market.get_market_listings( # <--- 1. 获取原始数据
        listing_type=listing_type, 
        exclude_owner=exclude_owner,
        search_term=search_term
    )

    # --- 2. 在 API 层处理业务逻辑 ---
    processed_items = []
    for item in items_raw:
        if item.get('nft_data'):
            nft_type = item.get('nft_type')
            handler = get_handler(nft_type)
            if handler:
                temp_nft_for_desc = {"data": item['nft_data'], "nft_type": nft_type}
                item['trade_description'] = handler.get_trade_description(temp_nft_for_desc)
            else:
                item['trade_description'] = item['description'] # 备用
        else:
             item['trade_description'] = item['description'] # 备用 (例如 SEEK)
        processed_items.append(item)
    # --- 处理结束 ---

    return {"listings": processed_items} # <--- 3. 返回处理后的数据

@router.get("/my_activity", tags=["Market"])
def api_get_my_activity(public_key: str):
    activity = queries_market.get_my_market_activity(public_key)
    return activity

@router.get("/offers", tags=["Market"])
def api_get_offers(listing_id: str):
    offers = queries_market.get_offers_for_listing(listing_id)
    # 为报价中的 NFT 添加
    for offer in offers:
        if offer.get('nft_data'):
            nft_type = offer.get('nft_type')
            handler = get_handler(nft_type)
            if handler:
                temp_nft_for_desc = {"data": offer['nft_data'], "nft_type": nft_type}
                offer['trade_description'] = handler.get_trade_description(temp_nft_for_desc)
            else:
                offer['trade_description'] = offer['nft_data'].get('name', offer['offered_nft_id'][:8])
        else:
            offer['trade_description'] = "未知NFT"
            
    return {"offers": offers}

@router.get("/listings/{listing_id}/bids", response_model=List[BidHistoryResponse], tags=["Market"])
def api_get_bid_history(listing_id: str):
    bids = queries_market.get_bids_for_listing(listing_id)
    return bids

@router.post("/create_listing", response_model=SuccessResponse, tags=["Market"])
def api_create_listing(request: MarketSignedRequest):
    message = get_verified_message(request, MarketListingRequest)
    success, detail = queries_market.create_market_listing(
        lister_key=message.owner_key,
        listing_type=message.listing_type,
        nft_id=message.nft_id,
        nft_type=message.nft_type,
        description=message.description,
        price=message.price,
        auction_hours=message.auction_hours
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/cancel_listing", response_model=SuccessResponse, tags=["Market"])
def api_cancel_listing(request: MarketSignedRequest):
    message = get_verified_message(request, MarketActionMessage)
    success, detail = queries_market.cancel_market_listing(
        lister_key=message.owner_key,
        listing_id=message.listing_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/buy", response_model=SuccessResponse, tags=["Market"])
def api_buy_nft(request: MarketSignedRequest):
    message = get_verified_message(request, MarketActionMessage)
    success, detail = queries_market.execute_sale(
        buyer_key=message.owner_key,
        listing_id=message.listing_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/place_bid", response_model=SuccessResponse, tags=["Market"])
def api_place_bid(request: MarketSignedRequest):
    message = get_verified_message(request, MarketBidRequest)
    success, detail = queries_market.place_auction_bid(
        bidder_key=message.owner_key,
        listing_id=message.listing_id,
        bid_amount=message.amount
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/make_offer", response_model=SuccessResponse, tags=["Market"])
def api_make_offer(request: MarketSignedRequest):
    message = get_verified_message(request, MarketOfferRequest)
    success, detail = queries_market.make_seek_offer(
        offerer_key=message.owner_key,
        listing_id=message.listing_id,
        offered_nft_id=message.offered_nft_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.post("/respond_offer", response_model=SuccessResponse, tags=["Market"])
def api_respond_offer(request: MarketSignedRequest):
    message = get_verified_message(request, MarketOfferResponseRequest)
    success, detail = queries_market.respond_to_seek_offer(
        seeker_key=message.owner_key,
        offer_id=message.offer_id,
        accept=message.accept
    )
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return SuccessResponse(detail=detail)

@router.get("/creatable_nfts", tags=["Market"])
def api_get_creatable_nfts():
    configs = {}
    for nft_type, handler_class in NFT_HANDLERS.items():
        config = handler_class.get_shop_config()
        if config.get("creatable"):
            configs[nft_type] = config
    return configs

@router.post("/create_nft", response_model=Dict, tags=["Market"])
def api_create_nft_from_shop(request: MarketSignedRequest):
    message = get_verified_message(request, ShopCreateNftRequest)
    
    handler = get_handler(message.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail="无效的NFT类型")
    
    config = handler.get_shop_config()
    if not config.get("creatable") or config.get("cost") != message.cost:
        raise HTTPException(status_code=400, detail="NFT创建配置不匹配或该NFT不可创建")

    if queries_user.get_balance(message.owner_key) < message.cost:
        raise HTTPException(status_code=400, detail="你的余额不足以支付铸造成本")

    with get_db_connection() as conn:
        success, detail = _create_system_transaction(message.owner_key, BURN_ACCOUNT, message.cost, f"商店铸造NFT: {message.nft_type}", conn)
        if not success:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"支付失败: {detail}")
        
        user_details = queries_user.get_user_details(message.owner_key, conn)
        if not user_details:
            conn.rollback()
            raise HTTPException(status_code=404, detail="无法找到铸造者信息")

        success, detail, db_data = handler.mint(message.owner_key, message.data, owner_username=user_details.get('username'))
        if not success:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"铸造逻辑失败: {detail}")

        from backend.db.queries_nft import mint_nft # 避免循环导入
        success, detail_mint, nft_id = mint_nft(message.owner_key, message.nft_type, db_data, conn)
        if not success:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"数据库写入失败: {detail_mint}")

        conn.commit()

    return {"detail": f"铸造成功！你获得了新的 {config.get('name', 'NFT')}!", "nft_id": nft_id}

@router.post("/shop_action", response_model=Dict, tags=["Market"])
def api_perform_shop_action(request: MarketSignedRequest):
    message = get_verified_message(request, ShopActionRequest)

    handler = get_handler(message.nft_type)
    if not handler:
        raise HTTPException(status_code=400, detail="无效的NFT类型")

    config = handler.get_shop_config()
    if not config.get("creatable") or config.get("cost") != message.cost:
        raise HTTPException(status_code=400, detail="商店配置不匹配或该物品不可用")

    if queries_user.get_balance(message.owner_key) < message.cost:
        raise HTTPException(status_code=400, detail="你的余额不足以支付此操作的费用")

    with get_db_connection() as conn:
        success, detail = _create_system_transaction(
            message.owner_key, BURN_ACCOUNT, message.cost,
            f"执行商店动作: {config.get('name', message.nft_type)}", conn
        )
        if not success:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"支付失败: {detail}")

        user_details = queries_user.get_user_details(message.owner_key, conn)
        username = user_details.get('username') if user_details else "未知用户"

        success, detail_action, new_nft_id = handler.execute_shop_action(message.owner_key, username, message.data, conn)

        if not success:
            conn.rollback()
            raise HTTPException(status_code=400, detail=detail_action)

        conn.commit()
        return {"detail": detail_action, "nft_id": new_nft_id}