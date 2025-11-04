# backend/bots/example_bots.py

import random
from backend.bots.base_bot import BaseBot
from backend.bots.bot_client import BotClient

class ShopEnthusiastBot(BaseBot):
    """
    这个机器人是“商店爱好者”。
    它会随机查看商店中可购买的任何物品 (包括 Planet, SecretWish 等) 并购买。
    """
    async def execute_turn(self):
        # ... (此函数的逻辑保持不变) ...
        print(f"🛍️ '{self.username}' (ShopEnthusiast) 正在执行回合...")
        balance = await self.client.get_balance()
        
        creatable_nfts = await self.client.get_creatable_nfts()
        if not creatable_nfts:
            print(f"🛍️ '{self.username}'：商店是空的，无事可做。")
            return
        
        target_type = random.choice(list(creatable_nfts.keys()))
        config = creatable_nfts[target_type]
        cost = config.get('cost', 99999)

        if balance < cost:
            print(f"🛍️ '{self.username}' 想买 '{target_type}' (需 {cost:.2f} FC)，但余额不足 ({balance:.2f} FC)。")
            return

        print(f"🛍️ '{self.username}' 拥有 {balance:.2f} FC，尝试购买 '{target_type}'...")
        
        form_data = {}
        if config.get("fields"):
            for field in config["fields"]:
                if field["name"] == "description":
                    form_data["description"] = f"机器人的秘密 ({random.randint(100,999)})"
                elif field["name"] == "content":
                    form_data["content"] = f"这是一个自动生成的秘密。{random.random()}"
                else:
                    form_data[field["name"]] = field.get("default", "")

        success, detail = await self.client.shop_action(
            nft_type=target_type,
            cost=cost,
            data=form_data,
            action_type=config.get("action_type", "create")
        )
        
        if success:
            print(f"🛍️ '{self.username}' 购买成功: {detail}")
        else:
            print(f"🛍️ '{self.username}' 购买失败: {detail}")


class BargainHunterBot(BaseBot):
    """
    这个机器人是个“捡漏王”。
    它会扫描市场上所有“一口价”商品，并购买任何低于 15 FC 的东西。
    """
    MAX_PRICE_TO_BUY = 15.0

    async def execute_turn(self):
        # ... (此函数的逻辑保持不变) ...
        print(f"💸 '{self.username}' (BargainHunter) 正在执行回合...")
        balance = await self.client.get_balance()
        
        if balance < self.MAX_PRICE_TO_BUY:
            print(f"💸 '{self.username}' 余额不足 ({balance:.2f} FC)，停止捡漏。")
            return

        listings = await self.client.get_market_listings(listing_type="SALE")
        if not listings:
            return
            
        cheap_items = [item for item in listings if item.get('price', 9999) <= self.MAX_PRICE_TO_BUY]
        
        if not cheap_items:
            return
            
        item_to_buy = random.choice(cheap_items)
        listing_id = item_to_buy['listing_id']
        price = item_to_buy['price']

        if balance < price:
            return
            
        print(f"💸 '{self.username}' 正在尝试购买 {listing_id}，价格: {price:.2f} FC...")
        success, detail = await self.client.buy_item(listing_id)
        
        if success:
            print(f"💸 '{self.username}' 捡漏成功! {detail}")
        else:
            print(f"💸 '{self.username}' 捡漏失败: {detail}")

class SellerBot(BaseBot):
    """
    这个机器人是“卖家”。
    它会检查自己钱包里的 NFT，如果有没有上架的，就随机挑一个上架。
    """
    MIN_PRICE = 20.0
    MAX_PRICE = 150.0

    async def execute_turn(self):
        # ... (此函数的逻辑保持不变) ...
        print(f"📈 '{self.username}' (SellerBot) 正在执行回合...")
        my_nfts = await self.client.get_my_nfts()
        my_listings, _ = await self.client.get_my_activity()
        
        listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE' and l['nft_id']}
        
        unlisted_nfts = [nft for nft in my_nfts if nft['nft_id'] not in listed_nft_ids]
        
        if not unlisted_nfts:
            print(f"📈 '{self.username}' 没有未上架的 NFT 可供出售。")
            return
            
        nft_to_sell = random.choice(unlisted_nfts)
        sell_price = round(random.uniform(self.MIN_PRICE, self.MAX_PRICE), 2)
        description = f"机器人自动上架: {nft_to_sell['nft_type']}"

        print(f"📈 '{self.username}' 尝试以 {sell_price:.2f} FC 的价格上架 NFT {nft_to_sell['nft_id'][:8]}...")

        success, detail = await self.client.create_listing(
            nft_id=nft_to_sell['nft_id'],
            nft_type=nft_to_sell['nft_type'],
            price=sell_price,
            description=description,
            listing_type="SALE"
        )
        
        if success:
            print(f"📈 '{self.username}' 上架成功! {detail}")
        else:
            print(f"📈 '{self.username}' 上架失败: {detail}")