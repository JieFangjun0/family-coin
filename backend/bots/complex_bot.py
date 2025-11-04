# backend/bots/complex_bot.py

import random
import time
from backend.bots.base_bot import BaseBot
from backend.bots.bot_client import BotClient

# --- 机器人的“个性”配置 ---
MINT_CHANCE = 0.2
SELL_CHANCE = 0.4
BUY_CHANCE = 0.4 # Mint + Sell + Buy 的概率总和应为 1.0

# 它只对“星球”感兴趣
INTERESTED_NFT_TYPE = "PLANET"
# 它认为低于 50 FC 的星球就是“便宜货”
BARGAIN_PRICE_LIMIT = 50.0
# 它出售自己物品的定价范围
SELL_PRICE_MIN = 75.0
SELL_PRICE_MAX = 300.0


class ComplexBot(BaseBot):
    """
    一个更复杂的机器人，模拟人类玩家行为。
    它会铸造新物品、出售自己的物品，以及购买市场上的便宜货。
    """
    
    async def execute_turn(self):
        """
        执行一个逻辑回合。
        随机决定是铸造、出售还是购买。
        """
        print(f"🤖 '{self.username}' (ComplexBot) 正在执行回合...")
        
        try:
            # 随机选择一个动作
            action = random.choices(
                ["MINT", "SELL", "BUY"], 
                weights=[MINT_CHANCE, SELL_CHANCE, BUY_CHANCE], 
                k=1
            )[0]

            if action == "MINT":
                await self._action_mint()
            elif action == "SELL":
                await self._action_sell()
            elif action == "BUY":
                await self._action_buy()

        except Exception as e:
            print(f"❌ '{self.username}' (ComplexBot) 执行回合时出错: {e}")

    async def _action_mint(self):
        """尝试铸造一个感兴趣的NFT。"""
        creatable_nfts = await self.client.get_creatable_nfts()
        if INTERESTED_NFT_TYPE not in creatable_nfts:
            print(f"🤖 '{self.username}': 想铸造 {INTERESTED_NFT_TYPE}，但商店里没有。")
            return

        config = creatable_nfts[INTERESTED_NFT_TYPE]
        cost = config.get('cost', 99999)
        balance = await self.client.get_balance()

        if balance < cost:
            print(f"🤖 '{self.username}': 想铸造 {INTERESTED_NFT_TYPE} (需 {cost:.2f} FC)，但余额不足 ({balance:.2f} FC)。")
            return
            
        print(f"🤖 '{self.username}' 正在尝试铸造 {INTERESTED_NFT_TYPE}...")
        
        # 我们的 ComplexBot 对 SECRET_WISH 不感兴趣，所以我们只处理 PLANET
        # 如果是其他类型，需要在这里构建 form_data
        form_data = {} 
        
        success, detail, new_nft_id = await self.client.shop_action(
            nft_type=INTERESTED_NFT_TYPE,
            cost=cost,
            data=form_data,
            action_type=config.get("action_type", "create")
        )
        
        if success:
            print(f"🤖 '{self.username}' 铸造成功: {detail} (NFT ID: {new_nft_id})")
        else:
            print(f"🤖 '{self.username}' 铸造失败: {detail}")

    async def _action_sell(self):
        """尝试出售一个自己拥有的NFT。"""
        my_nfts = await self.client.get_my_nfts()
        if not my_nfts:
            print(f"🤖 '{self.username}': 没有任何 NFT 可以出售。")
            return
            
        # 筛选出未上架的、感兴趣的NFT
        my_listings, my_offers = await self.client.get_my_activity()
        listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE' and l['nft_id']}
        
        unlisted_nfts = [
            nft for nft in my_nfts 
            if nft['nft_id'] not in listed_nft_ids 
            and nft['nft_type'] == INTERESTED_NFT_TYPE
        ]

        if not unlisted_nfts:
            print(f"🤖 '{self.username}': 没有未上架的 {INTERESTED_NFT_TYPE} 可供出售。")
            return
            
        nft_to_sell = random.choice(unlisted_nfts)
        sell_price = round(random.uniform(SELL_PRICE_MIN, SELL_PRICE_MAX), 2)
        
        # 尝试从NFT数据中获取一个好的描述
        nft_data = nft_to_sell.get('data', {})
        description = nft_data.get('custom_name') or nft_data.get('planet_type') or f"一颗{INTERESTED_NFT_TYPE}"
        description = f"机器人出售: {description}"

        print(f"🤖 '{self.username}' 尝试以 {sell_price:.2f} FC 的价格上架 {description}...")

        success, detail = await self.client.create_listing(
            nft_id=nft_to_sell['nft_id'],
            nft_type=nft_to_sell['nft_type'],
            price=sell_price,
            description=description,
            listing_type="SALE"
        )
        
        if success:
            print(f"🤖 '{self.username}' 上架成功! {detail}")
        else:
            print(f"🤖 '{self.username}' 上架失败: {detail}")

    async def _action_buy(self):
        """尝试低价购买市场上的NFT。"""
        balance = await self.client.get_balance()
        if balance < BARGAIN_PRICE_LIMIT:
            print(f"🤖 '{self.username}': 余额 ({balance:.2f} FC) 不足，无法捡漏。")
            return

        listings = await self.client.get_market_listings(listing_type="SALE")
        if not listings:
            return
            
        # 筛选出便宜的、感兴趣的NFT
        bargain_items = [
            item for item in listings 
            if item.get('price', 9999) <= BARGAIN_PRICE_LIMIT
            and item.get('nft_type') == INTERESTED_NFT_TYPE
        ]
        
        if not bargain_items:
            print(f"🤖 '{self.username}': 市场上没有便宜的 {INTERESTED_NFT_TYPE}。")
            return
            
        item_to_buy = random.choice(bargain_items)
        listing_id = item_to_buy['listing_id']
        price = item_to_buy['price']

        if balance < price:
            return
            
        print(f"🤖 '{self.username}' 正在尝试捡漏 {listing_id}，价格: {price:.2f} FC...")
        success, detail = await self.client.buy_item(listing_id)
        
        if success:
            print(f"🤖 '{self.username}' 捡漏成功! {detail}")
        else:
            print(f"🤖 '{self.username}' 捡漏失败: {detail}")