# backend/bots/planet_bots.py

import random
import time
import asyncio  # <--- 导入 asyncio
from backend.bots.base_bot import BaseBot
from backend.bots.bot_client import BotClient

# --- 导入“星球”的世界观设定，让所有星球机器“理解”它们在买什么 ---
try:
    from backend.nft_logic.planet import PLANET_TYPES, STAR_CLASSES, ANOMALIES
    
    # 供 Collector Bot 使用
    ALL_PLANET_TYPES = [v[0] for v in PLANET_TYPES.values()]
    ALL_STAR_CLASSES = [v[0] for v in STAR_CLASSES.values()]
    ALL_TRAITS = list(set([trait for v in ANOMALIES.values() for trait in v[1] if trait is not None]))
    
except ImportError:
    print("❌ PlanetBots 警告: 无法导入星球设定，将使用回退值。")
    ALL_PLANET_TYPES = ["类地行星", "海洋世界", "气态巨行星"]
    ALL_STAR_CLASSES = ["G级 (黄矮星)", "M级 (红矮星)"]
    ALL_TRAITS = ["远古外星遗物", "零点能量场"]

print("--- 🪐 [PlanetBots Module Loaded] ---")


# ==============================================================================
# --- 机器人 1: 星球收藏家 (PlanetCollectorBot) ---
# ==============================================================================

# --- 收藏家的“个性”配置 ---
COLLECTOR_CONFIG = {
    "JUNK_RARITY_THRESHOLD": 50,  # 低于此稀有度的行星被视为“垃圾”
    "VALUABLE_RARITY_THRESHOLD": 200, # 高于此稀有度的行星值得“拍卖”
    "BARGAIN_SALE_PRICE": 100.0,   # 市场上低于此价格的“梦想行星”会立即购买
    "MAX_AUCTION_BID": 250.0,    # 愿意为“梦想行星”拍卖品支付的最高价格
    "SEEK_ORDER_BUDGET": 500.0,   # 当钱太多时，愿意花多少钱发布求购
    "MIN_BALANCE_FOR_SEEK": 750.0, # 至少有多少钱时才考虑发布求购
    "SCAN_COST": 5.0,             # 扫描异常信号的成本
    "EXPLORE_COST": 10.0          # 探索星空的成本
}

class PlanetCollectorBot(BaseBot):
    """
    “星球收藏家”机器人 (拟人化)
    个性:
    - 它有一个随机生成的“执念”(梦想的星球类型、恒星、特质)。
    - 它会积极探索(铸造)、扫描(互动)、出售(拍卖/一口价)、
      购买(一口价/竞拍)和求购。
    """

    def __init__(self, client: BotClient):
        super().__init__(client)
        # --- 随机生成“个性” ---
        self.dream_planet_type = random.choice(ALL_PLANET_TYPES)
        self.dream_stellar_class = random.choice(ALL_STAR_CLASSES)
        self.dream_trait = random.choice(ALL_TRAITS)
        
        # (修改) 使用 self.log 记录初始化
        self.log(f"已初始化。我的执念是：寻找一颗位于【{self.dream_stellar_class}】" \
                 f"星系的【{self.dream_planet_type}】，" \
                 f"它必须拥有【{self.dream_trait}】特质！", action_type="INIT")

    # --- (移除) 旧的 log 方法 (已由 BaseBot 继承) ---

    async def execute_turn(self):
        try:
            # 1. 状态检查
            balance = await self.client.get_balance()
            my_nfts = await self.client.get_my_nfts()
            my_listings, _ = await self.client.get_my_activity()
            
            listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE'}
            planet_nfts = [nft for nft in my_nfts if nft['nft_type'] == 'PLANET']
            
            # +++ (修改) 使用新的 log_turn_snapshot +++
            self.log_turn_snapshot(balance, planet_nfts, my_listings)

            # 2. (行为) 扫描我的行星上的异常信号 (玩自己的NFT)
            balance = await self._action_scan_anomalies(planet_nfts, balance, listed_nft_ids)

            # 3. (行为) 出售我不想要的“垃圾”行星 (管理库存)
            balance = await self._action_manage_portfolio(planet_nfts, listed_nft_ids, balance)
            
            # 4. (行为) 探索！
            balance = await self._action_explore(balance)

            # 5. (行为) 逛市场 (买买买)
            balance = await self._action_scan_market(balance)
            
            # 6. (行为) 发布求购
            await self._action_post_seek_order(balance, my_listings)
            
            self.log("回合评估结束。", action_type="EVALUATE_END")

        except Exception as e:
            self.log(f"❌ 执行回合时发生严重错误: {e}", action_type="ERROR")
        
        # +++ (新增) 错峰执行 +++
        await asyncio.sleep(random.uniform(0.1, 1.0))

    def _is_my_dream_planet(self, nft_data: dict) -> bool:
        """检查这颗行星是否符合我的“执念”"""
        if not nft_data: return False
        has_dream_type = nft_data.get('planet_type') == self.dream_planet_type
        has_dream_trait = self.dream_trait in nft_data.get('unlocked_traits', [])
        return has_dream_type and has_dream_trait

    async def _action_manage_portfolio(self, planet_nfts: list, listed_nft_ids: set, balance: float) -> float:
        self.log("正在评估我的行星资产...", action_type="EVALUATE_PORTFOLIO")
        for nft in planet_nfts:
            if nft['nft_id'] in listed_nft_ids: continue

            data = nft.get('data', {})
            rarity = data.get('rarity_score', {}).get('total', 0)
            name = data.get('custom_name') or f"行星 {nft['nft_id'][:6]}"

            if self._is_my_dream_planet(data):
                self.log(f"👍 {name} 是我的梦想星球！非卖品！", action_type="KEEP")
                continue

            if rarity < COLLECTOR_CONFIG["JUNK_RARITY_THRESHOLD"] and data.get('planet_type') != self.dream_planet_type:
                price = round(random.uniform(15.0, 40.0), 2)
                desc = f"机器人甩卖: {data.get('planet_type')}, 稀有度 {rarity}"
                self.log(f"正在以 {price:.2f} FC 甩卖“垃圾”行星: {name} (稀有度 {rarity})", action_type="LIST_SALE")
                await self.client.create_listing(nft['nft_id'], "PLANET", price, desc, "SALE")
            
            elif rarity > COLLECTOR_CONFIG["VALUABLE_RARITY_THRESHOLD"]:
                price = round(rarity * 1.5, 2)
                desc = f"稀有行星拍卖: {data.get('planet_type')}, 稀有度 {rarity}!"
                self.log(f"正在以 {price:.2f} FC 起拍“珍稀”行星: {name} (稀有度 {rarity})", action_type="LIST_AUCTION")
                await self.client.create_listing(nft['nft_id'], "PLANET", price, desc, "AUCTION", 24)
        return balance

    async def _action_scan_anomalies(self, planet_nfts: list, balance: float, listed_nft_ids: set) -> float:
        if balance < COLLECTOR_CONFIG["SCAN_COST"]: return balance

        scannable_planets = [
            nft for nft in planet_nfts 
            if nft.get('data', {}).get('anomalies') 
            and nft['nft_id'] not in listed_nft_ids
        ]
        
        if not scannable_planets: return balance

        nft_to_scan = random.choice(scannable_planets)
        anomaly_to_scan = random.choice(nft_to_scan['data']['anomalies'])
        name = nft_to_scan['data'].get('custom_name') or nft_to_scan['nft_id'][:6]

        self.log(f"有 {balance:.2f} FC，花费 {COLLECTOR_CONFIG['SCAN_COST']} FC 扫描行星 {name} 上的 {anomaly_to_scan}...", action_type="NFT_ACTION_SCAN")
        
        success, detail = await self.client.nft_action(
            nft_to_scan['nft_id'], 
            'scan', 
            {'anomaly': anomaly_to_scan}
        )
        
        if success:
            self.log(f"扫描成功: {detail}", action_type="NFT_ACTION_SUCCESS")
            if self.dream_trait in detail:
                self.log(f"🔥🔥🔥 扫描出了我想要的特质！！{self.dream_trait}！", action_type="FIND_DREAM_TRAIT")
            return balance - COLLECTOR_CONFIG["SCAN_COST"]
        else:
            self.log(f"扫描失败: {detail}", action_type="NFT_ACTION_FAIL")
            return balance

    async def _action_explore(self, balance: float) -> float:
        if balance < COLLECTOR_CONFIG["EXPLORE_COST"]:
            self.log("没钱了，停止探索。", action_type="SKIP_EXPLORE")
            return balance

        if random.random() < 0.75:
            self.log(f"有 {balance:.2f} FC，花费 {COLLECTOR_CONFIG['EXPLORE_COST']} FC 发射新的探测器...", action_type="SHOP_EXPLORE")
            success, detail, new_nft_id = await self.client.shop_action(
                "PLANET", 
                COLLECTOR_CONFIG["EXPLORE_COST"], 
                {}, 
                "probabilistic_mint"
            )
            if success:
                self.log(f"探索完成: {detail}", action_type="SHOP_EXPLORE_SUCCESS", data_snapshot={"new_nft_id": new_nft_id})
                if new_nft_id:
                    self.log(f"🎉 发现新行星 {new_nft_id[:6]}！赶紧去扫描一下！", action_type="INFO")
            else:
                self.log(f"探索失败: {detail}", action_type="SHOP_EXPLORE_FAIL")
            return balance - COLLECTOR_CONFIG["EXPLORE_COST"]
        return balance

    async def _action_scan_market(self, balance: float) -> float:
        listings = await self.client.get_market_listings("SALE")
        for item in listings:
            if item['nft_type'] != 'PLANET' or item.get('price', 9999) > balance: continue

            data = item.get('nft_data', {})
            price = item.get('price')
            is_dream_type = data.get('planet_type') == self.dream_planet_type
            has_dream_trait = self.dream_trait in data.get('unlocked_traits', [])

            if price < COLLECTOR_CONFIG["BARGAIN_SALE_PRICE"] and (is_dream_type or has_dream_trait):
                self.log(f"👉 捡漏！发现符合执念的行星，价格 {price:.2f} FC，立即购买！", action_type="MARKET_BUY")
                success, detail = await self.client.buy_item(item['listing_id'])
                if success:
                    self.log(f"购买成功: {detail}", action_type="MARKET_BUY_SUCCESS")
                    return balance - price
                else:
                    self.log(f"购买失败: {detail}", action_type="MARKET_BUY_FAIL")
                break

        auctions = await self.client.get_market_listings("AUCTION")
        for item in auctions:
            if item['nft_type'] != 'PLANET': continue

            data = item.get('nft_data', {})
            is_dream_type = data.get('planet_type') == self.dream_planet_type
            has_dream_trait = self.dream_trait in data.get('unlocked_traits', [])

            if is_dream_type or has_dream_trait:
                current_bid = item.get('highest_bid', 0) or item.get('price')
                my_bid = round(current_bid * 1.15, 2)
                
                if my_bid < COLLECTOR_CONFIG["MAX_AUCTION_BID"] and my_bid < balance:
                    self.log(f"👉 竞拍！发现梦想行星，出价 {my_bid:.2f} FC！", action_type="MARKET_BID")
                    success, detail = await self.client.place_bid(item['listing_id'], my_bid)
                    if success: self.log(f"出价成功: {detail}", action_type="MARKET_BID_SUCCESS")
                    else: self.log(f"出价失败: {detail}", action_type="MARKET_BID_FAIL")
                    break
        return balance

    async def _action_post_seek_order(self, balance: float, my_listings: list):
        if balance < COLLECTOR_CONFIG["MIN_BALANCE_FOR_SEEK"]: return

        has_active_seek = any(
            l['listing_type'] == 'SEEK' and l['status'] == 'ACTIVE' 
            for l in my_listings
        )
        
        if not has_active_seek:
            self.log(f"钱太多了 ({balance:.2f} FC)，发布一个 {COLLECTOR_CONFIG['SEEK_ORDER_BUDGET']} FC 的求购单！", action_type="MARKET_SEEK")
            desc = f"重金求购【{self.dream_planet_type}】，必须带【{self.dream_trait}】特质！"
            
            await self.client.create_seek(
                "PLANET", 
                desc, 
                COLLECTOR_CONFIG["SEEK_ORDER_BUDGET"]
            )


# ==============================================================================
# --- 机器人 2: 星球投机商 (PlanetSpeculatorBot) ---
# ==============================================================================

SPECULATOR_RANGES = {
    # --- 卖出策略 ---
    "SALE_PROFIT_MARGIN": (1.05, 1.40),      # 利润率在 5% 到 40% 之间
    "AUCTION_RARITY_THRESHOLD": (150, 300), # 触发拍卖的稀有度阈值
    "AUCTION_START_MARGIN": (0.8, 1.0),     # 拍卖起拍价为市场均价的 80% - 100%
    
    # --- 买入策略 ---
    "BUY_DISCOUNT_THRESHOLD": (0.6, 0.9),   # 抄底/竞拍上限为市价的 60% - 90%
    "BID_INCREMENT_FACTOR": (1.05, 1.20),   # 竞拍时加价 5% 到 20%
    
    # --- 探索策略 ---
    "EXPLORE_COST": 10.0,
    "MIN_EXPLORE_BALANCE": (40.0, 100.0),   # 余额低于 40-100 FC 时停止探索
    "MAX_INVENTORY_BEFORE_STOP_EXPLORE": (5, 15), # 库存阈值
    "MARKET_DRY_THRESHOLD": (2, 6),         # 市场冷清阈值
    "EXPLORE_CHANCE": (0.3, 0.7),           # 探索欲望
    
    # --- 市场分析默认值 ---
    "DEFAULT_PRICE_PER_RARITY": 2.0,
    "DEFAULT_FLOOR_PRICE": 20.0,
    "MIN_SALE_PRICE": 10.0
}

class PlanetSpeculatorBot(BaseBot):
    """
    “星球投机商”机器人 (拟人化) V3
    - 每个实例都有自己独特的、随机生成的交易策略。
    """

    def __init__(self, client: BotClient):
        super().__init__(client)
        
        # --- 在初始化时生成“个性” ---
        self.config = {
            "SALE_PROFIT_MARGIN": random.uniform(*SPECULATOR_RANGES["SALE_PROFIT_MARGIN"]),
            "AUCTION_RARITY_THRESHOLD": random.randint(*SPECULATOR_RANGES["AUCTION_RARITY_THRESHOLD"]),
            "AUCTION_START_MARGIN": random.uniform(*SPECULATOR_RANGES["AUCTION_START_MARGIN"]),
            "BUY_DISCOUNT_THRESHOLD": random.uniform(*SPECULATOR_RANGES["BUY_DISCOUNT_THRESHOLD"]),
            "BID_INCREMENT_FACTOR": random.uniform(*SPECULATOR_RANGES["BID_INCREMENT_FACTOR"]),
            "MIN_EXPLORE_BALANCE": random.uniform(*SPECULATOR_RANGES["MIN_EXPLORE_BALANCE"]),
            "MAX_INVENTORY_BEFORE_STOP_EXPLORE": random.randint(*SPECULATOR_RANGES["MAX_INVENTORY_BEFORE_STOP_EXPLORE"]),
            "MARKET_DRY_THRESHOLD": random.randint(*SPECULATOR_RANGES["MARKET_DRY_THRESHOLD"]),
            "EXPLORE_CHANCE": random.uniform(*SPECULATOR_RANGES["EXPLORE_CHANCE"]),
            "EXPLORE_COST": SPECULATOR_RANGES["EXPLORE_COST"],
            "DEFAULT_PRICE_PER_RARITY": SPECULATOR_RANGES["DEFAULT_PRICE_PER_RARITY"],
            "DEFAULT_FLOOR_PRICE": SPECULATOR_RANGES["DEFAULT_FLOOR_PRICE"],
            "MIN_SALE_PRICE": SPECULATOR_RANGES["MIN_SALE_PRICE"],
        }
        
        # (修改) 使用 self.log 记录初始化
        self.log(f"已初始化。我的个性: 利润率 {self.config['SALE_PROFIT_MARGIN']:.1%}, "
                 f"抄底阈值 {self.config['BUY_DISCOUNT_THRESHOLD']:.1%}, "
                 f"拍卖阈值 {self.config['AUCTION_RARITY_THRESHOLD']} Rarity", action_type="INIT")

    # --- (移除) 旧的 log 方法 (已由 BaseBot 继承) ---

    async def execute_turn(self):
        try:
            balance = await self.client.get_balance()
            my_nfts = await self.client.get_my_nfts()
            my_listings, _ = await self.client.get_my_activity()
            
            listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE'}
            my_planets = [nft for nft in my_nfts if nft['nft_type'] == 'PLANET']
            my_unlisted_planets = [nft for nft in my_planets if nft['nft_id'] not in listed_nft_ids]
            
            # +++ (修改) 使用新的 log_turn_snapshot +++
            self.log_turn_snapshot(balance, my_unlisted_planets, my_listings)

            market_analysis = await self._analyze_market()
            await self._action_sell_inventory(my_unlisted_planets, market_analysis)
            balance = await self._action_scan_market_for_deals(balance, market_analysis)
            balance = await self._action_explore_for_assets(balance, len(my_unlisted_planets), market_analysis)
            
            self.log("投机周期结束。", action_type="EVALUATE_END")

        except Exception as e:
            self.log(f"❌ 执行回合时发生严重错误: {e}", action_type="ERROR")
        
        # +++ (新增) 错峰执行 +++
        await asyncio.sleep(random.uniform(0.1, 1.0))

    async def _analyze_market(self) -> dict:
        """(核心) 分析当前市场，计算 P/R 均价"""
        self.log("正在分析行星市场...", action_type="MARKET_ANALYSIS")
        sale_listings = await self.client.get_market_listings("SALE")
        auction_listings = await self.client.get_market_listings("AUCTION")
        
        all_listings = [
            item for item in (sale_listings + auction_listings) 
            if item['nft_type'] == 'PLANET' and item.get('nft_data')
        ]
        
        if not all_listings:
            self.log("市场为空，使用默认定价策略。", action_type="INFO")
            return {
                'avg_price_per_rarity': self.config["DEFAULT_PRICE_PER_RARITY"], 
                'floor_price': self.config["DEFAULT_FLOOR_PRICE"], 
                'count': 0
            }

        total_price = 0
        total_rarity = 0
        floor_price = 99999.0
        
        for item in all_listings:
            rarity = item['nft_data'].get('rarity_score', {}).get('total', 1)
            if rarity <= 0: rarity = 1
            price = item.get('highest_bid', 0) or item.get('price')
            total_price += price
            total_rarity += rarity
            if price < floor_price: floor_price = price

        avg_price_per_rarity = (total_price / total_rarity) if total_rarity > 0 else self.config["DEFAULT_PRICE_PER_RARITY"]
        
        self.log(f"市场分析: 平均P/R: {avg_price_per_rarity:.2f} FC, " \
                 f"地板价: {floor_price:.2f} FC, " \
                 f"总挂单: {len(all_listings)}", action_type="INFO")
                 
        return {
            'avg_price_per_rarity': avg_price_per_rarity, 
            'floor_price': floor_price, 
            'count': len(all_listings)
        }

    async def _action_sell_inventory(self, unlisted_planets: list, market_analysis: dict):
        """(拟人行为) 动态定价卖出"""
        if not unlisted_planets: return

        avg_price_per_rarity = market_analysis['avg_price_per_rarity']
        nft_to_sell = random.choice(unlisted_planets)
        data = nft_to_sell.get('data', {})
        rarity = data.get('rarity_score', {}).get('total', 20)
        name = data.get('custom_name') or data.get('planet_type') or "行星"
        
        base_price = max(self.config["MIN_SALE_PRICE"], rarity * avg_price_per_rarity)
        
        if rarity > self.config["AUCTION_RARITY_THRESHOLD"]:
            start_price = round(base_price * self.config["AUCTION_START_MARGIN"], 2)
            desc = f"【稀有拍卖】 {name} [稀有度 {rarity}]! 投机者出货!"
            self.log(f"正在拍卖稀有行星 {name} (Rarity {rarity})，起拍价 {start_price:.2f} FC", action_type="LIST_AUCTION")
            await self.client.create_listing(nft_to_sell['nft_id'], "PLANET", start_price, desc, "AUCTION", 12)
        else:
            sale_price = round(base_price * self.config["SALE_PROFIT_MARGIN"], 2)
            desc = f"【投机者出售】 {name} [稀有度 {rarity}]"
            self.log(f"正在出售行星 {name} (Rarity {rarity})，标价 {sale_price:.2f} FC", action_type="LIST_SALE")
            await self.client.create_listing(nft_to_sell['nft_id'], "PLANET", sale_price, desc, "SALE")

    async def _action_scan_market_for_deals(self, balance: float, market_analysis: dict) -> float:
        """(拟人行为) 扫描市场，抄底一口价商品或竞拍低价拍卖品"""
        self.log("正在扫描市场寻找被低估的资产...", action_type="MARKET_SCAN")
        avg_price_per_rarity = market_analysis['avg_price_per_rarity']
        
        # --- 1. 扫描“一口价” (抄底) ---
        listings = await self.client.get_market_listings("SALE")
        bargains = []
        for item in listings:
            if item['nft_type'] != 'PLANET' or not item.get('nft_data'): continue
            
            rarity = item['nft_data'].get('rarity_score', {}).get('total', 1)
            if rarity <= 0: rarity = 1
            price = item.get('price')
            item_price_per_rarity = price / rarity
            
            if item_price_per_rarity < (avg_price_per_rarity * self.config["BUY_DISCOUNT_THRESHOLD"]):
                if price < balance: bargains.append(item)
                else: self.log(f"发现 {item['description']} 是个好价钱，但我钱 ({balance:.2f}) 不够买 ({price:.2f})", action_type="INFO")

        if bargains:
            item_to_buy = random.choice(bargains)
            price_to_pay = item_to_buy['price']
            
            self.log(f"👉 抄底！买入 {item_to_buy['description']}，价格 {price_to_pay:.2f} FC！", action_type="MARKET_BUY")
            success, detail = await self.client.buy_item(item_to_buy['listing_id'])
            
            if success:
                self.log(f"抄底成功: {detail}", action_type="MARKET_BUY_SUCCESS")
                return balance - price_to_pay
            else:
                self.log(f"抄底失败: {detail}", action_type="MARKET_BUY_FAIL")
                return balance
        
        # --- 2. (新增) 扫描“拍卖行” (竞拍) ---
        self.log("正在扫描拍卖行寻找投机机会...", action_type="MARKET_SCAN_AUCTION")
        auctions = await self.client.get_market_listings("AUCTION")
        
        potential_bids = []
        for item in auctions:
            if item['nft_type'] != 'PLANET' or not item.get('nft_data'): continue
            
            data = item['nft_data']
            rarity = data.get('rarity_score', {}).get('total', 1)
            if rarity <= 0: rarity = 1
            
            est_market_value = rarity * avg_price_per_rarity
            my_max_spec_bid = est_market_value * self.config["BUY_DISCOUNT_THRESHOLD"]
            current_bid_price = item.get('highest_bid', 0) or item.get('price')
            
            if my_max_spec_bid > current_bid_price:
                my_bid = round(current_bid_price * self.config["BID_INCREMENT_FACTOR"], 2)
                if my_bid < (current_bid_price + 0.01):
                    my_bid = round(current_bid_price + 0.01, 2)
                if my_bid > my_max_spec_bid:
                    self.log(f"发现 {item['description']} 有利润空间，但加价后 ({my_bid:.2f}) "
                             f"超过了我的投机上限 ({my_max_spec_bid:.2f})，放弃。", action_type="INFO")
                    continue
                if my_bid > balance:
                    self.log(f"发现 {item['description']} 值得竞拍，但我钱 ({balance:.2f}) 不够出价 ({my_bid:.2f})", action_type="INFO")
                    continue
                potential_bids.append((item['listing_id'], my_bid))
        
        if not potential_bids:
            self.log("拍卖行中没有值得竞拍的资产。", action_type="MARKET_SCAN_DONE")
            return balance

        listing_id_to_bid, bid_amount = random.choice(potential_bids)
        
        self.log(f"👉 竞拍！发现 {listing_id_to_bid[:8]} 值得投机，出价 {bid_amount:.2f} FC！", action_type="MARKET_BID")
        success, detail = await self.client.place_bid(listing_id_to_bid, bid_amount)
        
        if success:
            self.log(f"竞拍出价成功: {detail}", action_type="MARKET_BID_SUCCESS")
            return balance - bid_amount 
        else:
            self.log(f"竞拍出价失败: {detail}", action_type="MARKET_BID_FAIL")
            return balance

    async def _action_explore_for_assets(self, balance: float, inventory_count: int, market_analysis: dict) -> float:
        """(拟人行为) 探索以补充库存"""
        if balance < self.config["MIN_EXPLORE_BALANCE"]: return balance

        market_is_dry = market_analysis['count'] < self.config["MARKET_DRY_THRESHOLD"]
        inventory_is_low = inventory_count < self.config["MAX_INVENTORY_BEFORE_STOP_EXPLORE"]
        
        if (market_is_dry or inventory_is_low) and random.random() < self.config["EXPLORE_CHANCE"]:
            self.log(f"市场冷清或库存不足，花费 {self.config['EXPLORE_COST']} FC 探索新行星...", action_type="SHOP_EXPLORE")
            success, detail, new_nft_id = await self.client.shop_action(
                "PLANET", 
                self.config["EXPLORE_COST"], 
                {}, 
                "probabilistic_mint"
            )
            if success:
                self.log(f"探索完成: {detail}", action_type="SHOP_EXPLORE_SUCCESS", data_snapshot={"new_nft_id": new_nft_id})
                if new_nft_id:
                    self.log(f"🎉 发现新资产 {new_nft_id[:6]}！下回合评估卖出。", action_type="INFO")
            else:
                self.log(f"探索失败: {detail}", action_type="SHOP_EXPLORE_FAIL")
            return balance - self.config["EXPLORE_COST"]
        
        return balance


# ==============================================================================
# --- 机器人 3: 星球赌徒 (PlanetGamblerBot) ---
# ==============================================================================

GAMBLER_CONFIG = {
    "EXPLORE_COST": 10.0,
    "SCAN_COST": 5.0,
    "ACTION_CHANCE": 0.5, # 50% 的概率在回合内搞事
    
    # --- 核心：混乱的定价 ---
    "SELL_PRICE_MIN": 1.0,     # 卖价可能低至 1 FC
    "SELL_PRICE_MAX": 1500.0,  # 卖价可能高达 1500 FC
    "BID_OVERPAY_FACTOR_MIN": 1.05, # 最少加价 5%
    "BID_OVERPAY_FACTOR_MAX": 1.75, # 最多疯狂加价 75%
}

class PlanetGamblerBot(BaseBot):
    """
    “星球赌徒”机器人 (拟人化)
    
    个性:
    - 纯粹的混乱。
    - 它的行为完全随机，不基于市场分析。
    - 它会随机探索、随机卖货（价格离谱）、随机买货（不管划不划算）。
    """

    def __init__(self, client: BotClient):
        super().__init__(client)
        self.log(f"已初始化。我感觉今天手气不错！", action_type="INIT")

    # --- (移除) 旧的 log 方法 (已由 BaseBot 继承) ---

    async def execute_turn(self):
        """
        赌徒的回合：随机三选一
        """
        try:
            balance = await self.client.get_balance()
            my_nfts = await self.client.get_my_nfts()
            my_listings, _ = await self.client.get_my_activity()
            
            listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE'}
            my_unlisted_planets = [
                nft for nft in my_nfts 
                if nft['nft_type'] == 'PLANET' and nft['nft_id'] not in listed_nft_ids
            ]
            
            # +++ (修改) 使用新的 log_turn_snapshot +++
            self.log_turn_snapshot(balance, my_unlisted_planets, my_listings)

            if random.random() < GAMBLER_CONFIG["ACTION_CHANCE"]:
                # 随机决定做什么
                possible_actions = []
                if balance > GAMBLER_CONFIG["EXPLORE_COST"]:
                    possible_actions.append("EXPLORE")
                if my_unlisted_planets:
                    possible_actions.append("SELL")
                if balance > 1.0: # 只要有钱就可能去买
                    possible_actions.append("BUY")
                
                if not possible_actions:
                    self.log("哎，啥也干不了。", action_type="SKIP_TURN")
                    return

                action = random.choice(possible_actions)
                self.log(f"我决定... {action}！", action_type="DECISION")

                if action == "EXPLORE":
                    await self._action_explore(balance)
                elif action == "SELL":
                    await self._action_sell(my_unlisted_planets)
                elif action == "BUY":
                    await self._action_buy(balance)
            
            else:
                self.log("这回合我选择“观望”。", action_type="SKIP_TURN")

        except Exception as e:
            self.log(f"❌ 执行回合时发生严重错误: {e}", action_type="ERROR")
        
        # +++ (新增) 错峰执行 +++
        await asyncio.sleep(random.uniform(0.1, 1.0))

    async def _action_explore(self, balance: float):
        """(赌徒行为) 探索，就是为了开奖"""
        self.log(f"搏一搏！花费 {GAMBLER_CONFIG['EXPLORE_COST']} FC 探索！", action_type="SHOP_EXPLORE")
        success, detail, new_nft_id = await self.client.shop_action(
            "PLANET", 
            GAMBLER_CONFIG["EXPLORE_COST"], 
            {}, 
            "probabilistic_mint"
        )
        if success:
            self.log(f"探索结果: {detail}", action_type="SHOP_EXPLORE_SUCCESS", data_snapshot={"new_nft_id": new_nft_id})
            if new_nft_id: self.log(f"新玩具 {new_nft_id[:6]} 到手！", action_type="INFO")
        else:
            self.log(f"探索失败: {detail}", action_type="SHOP_EXPLORE_FAIL")

    async def _action_sell(self, unlisted_planets: list):
        """(赌徒行为) 随机选一个，标个离谱的价卖掉"""
        nft_to_sell = random.choice(unlisted_planets)
        data = nft_to_sell.get('data', {})
        name = data.get('custom_name') or data.get('planet_type') or "一颗行星"
        
        # 核心：混乱定价
        price = round(random.uniform(GAMBLER_CONFIG["SELL_PRICE_MIN"], GAMBLER_CONFIG["SELL_PRICE_MAX"]), 2)
        listing_type = random.choice(["SALE", "AUCTION"])
        auction_hours = random.randint(1, 48) if listing_type == "AUCTION" else None
        
        desc = f"【赌徒的珍藏】 {name} [稀有度 {data.get('rarity_score', {}).get('total', '?')}]"
        
        self.log(f"我要把 {name} 卖 {price:.2f} FC！ ({listing_type})，它肯定值这个价！", action_type=f"LIST_{listing_type.upper()}")
        await self.client.create_listing(
            nft_to_sell['nft_id'], "PLANET", price, desc, listing_type, auction_hours
        )

    async def _action_buy(self, balance: float):
        """(赌徒行为) 随机买一个我买得起的"""
        self.log("逛逛市场，看上哪个买哪个...", action_type="MARKET_SCAN")
        sale_listings = await self.client.get_market_listings("SALE")
        auction_listings = await self.client.get_market_listings("AUCTION")
        
        all_listings = [
            item for item in (sale_listings + auction_listings) 
            if item['nft_type'] == 'PLANET'
        ]

        if not all_listings:
            self.log("市场是空的，没得买。", action_type="MARKET_SCAN_DONE")
            return

        # 找出所有我买得起的
        buyable_items = []
        for item in all_listings:
            current_price = item.get('highest_bid', 0) or item.get('price')
            if current_price < balance:
                buyable_items.append(item)

        if not buyable_items:
            self.log("都太贵了，买不起。", action_type="MARKET_SCAN_DONE")
            return
            
        # 随机挑一个
        item_to_buy = random.choice(buyable_items)
        
        if item_to_buy['listing_type'] == "SALE":
            price_to_pay = item_to_buy['price']
            self.log(f"👉 我看上了 {item_to_buy['description']}！{price_to_pay:.2f} FC，买了！", action_type="MARKET_BUY")
            success, detail = await self.client.buy_item(item_to_buy['listing_id'])
            if success:
                self.log(f"购买成功: {detail}", action_type="MARKET_BUY_SUCCESS")
            else:
                self.log(f"购买失败: {detail}", action_type="MARKET_BUY_FAIL")
        
        elif item_to_buy['listing_type'] == "AUCTION":
            current_price = item_to_buy.get('highest_bid', 0) or item_to_buy.get('price')
            
            # 核心：疯狂出价
            my_bid_factor = random.uniform(GAMBLER_CONFIG["BID_OVERPAY_FACTOR_MIN"], GAMBLER_CONFIG["BID_OVERPAY_FACTOR_MAX"])
            my_bid = round(current_price * my_bid_factor, 2)
            
            if my_bid < (current_price + 0.01): # 确保至少加价
                my_bid = round(current_price + 0.01, 2)

            if my_bid > balance:
                self.log(f"我看上了 {item_to_buy['description']}，但我的疯狂出价 ({my_bid:.2f}) 超过了我的余额 ({balance:.2f})", action_type="MARKET_BID_FAIL")
                return

            self.log(f"👉 我一定要得到 {item_to_buy['description']}！出价 {my_bid:.2f} FC！", action_type="MARKET_BID")
            success, detail = await self.client.place_bid(item_to_buy['listing_id'], my_bid)
            if success:
                self.log(f"出价成功: {detail}", action_type="MARKET_BID_SUCCESS")
            else:
                self.log(f"出价失败: {detail}", action_type="MARKET_BID_FAIL")