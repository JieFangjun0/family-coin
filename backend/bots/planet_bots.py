# backend/bots/planet_bots.py

import random
import time
import asyncio
from backend.bots.base_bot import BaseBot
from backend.bots.bot_client import BotClient

# --- 核心：导入星球的“世界观”和“经济学” ---
# 机器人现在“理解”它在操作什么
from backend.nft_logic.planet import (
    PlanetHandler, PLANET_ECONOMICS, TRAIT_DEFINITIONS
)

# --- 机器人个性化配置 ---
CAPITALIST_CONFIG = {
    "EXPLORE_COST": PLANET_ECONOMICS.get("EXPLORE_COST", 15.0),
    "SCAN_COST": PLANET_ECONOMICS.get("SCAN_COST", 10.0),
    
    # --- 投资（探索/扫描）策略 ---
    "MIN_BALANCE_TO_EXPLORE": 50.0,   # 至少有多少钱时才开始探索
    "MIN_BALANCE_TO_SCAN": 20.0,      # 至少有多少钱时才扫描
    "EXPLORE_CHANCE": 0.4,            # 40% 的概率去探索
    "SCAN_CHANCE": 0.6,               # 60% 的概率去扫描
    "MAX_INVENTORY_SIZE": 15,         # 持有超过15颗行星时停止探索
    
    # --- 交易策略（基于内在价值） ---
    "BUY_DISCOUNT_THRESHOLD": 0.8,    # 购买阈值：只买市场价 < 内在价值 * 0.8 的
    "SALE_PROFIT_MARGIN": 1.2,        # 销售利润：挂单价 = 内在价值 * 1.2
    "MIN_LISTING_PRICE": 5.0,         # 最低挂单价
    
    # --- 收藏策略 ---
    "SHOWCASE_UPDATE_CHANCE": 0.3,    # 30% 的概率更新展柜
    "SHOWCASE_SIZE": 6,               # 展柜大小
}

# --- 中文名 ---
CAPITALIST_CHINESE_NAMES = ["星球资本家", "星河集团CEO", "JCoin矿业大亨", "行星巴菲特"]

def get_random_chinese_name(bot_type: str) -> str:
    """根据类型获取一个随机中文名"""
    if bot_type == "PlanetCapitalistBot":
        return random.choice(CAPITALIST_CHINESE_NAMES)
    # (旧的机器人名称已移除)
    return "未知机器人"

# ==============================================================================
# --- 机器人: 星球资本家 (PlanetCapitalistBot) ---
# ==============================================================================

class PlanetCapitalistBot(BaseBot):
    """
    “星球资本家”机器人 (V4)
    一个基于内在价值进行挖矿、投资和交易的智能机器人。
    """
    # --- 框架必需：默认值和显示名 ---
    DEFAULT_FUNDS = 3000.0
    DEFAULT_PROBABILITY = 0.5 # 50% 的概率被激活
    CHINESE_DISPLAY_NAME = "星球资本家"

    @classmethod
    def get_chinese_display_name(cls) -> str:
        return cls.CHINESE_DISPLAY_NAME

    def __init__(self, client: BotClient):
        super().__init__(client)
        
        # --- 获取核心估值函数 ---
        try:
            val_config = PlanetHandler.get_economic_config_and_valuation()
            self.calculate_planet_value = val_config["calculate_value_func"]
        except Exception as e:
            self.log(f"❌ 严重错误：无法加载星球估值函数: {e}", "ERROR")
            # 创建一个回退函数
            self.calculate_planet_value = lambda data: 1.0 

        # --- 生成“个性” ---
        self.config = {
            "BUY_DISCOUNT_THRESHOLD": random.uniform(0.7, 0.9),
            "SALE_PROFIT_MARGIN": random.uniform(1.15, 1.40),
            "MIN_BALANCE_TO_EXPLORE": random.uniform(50.0, 200.0),
            "MAX_INVENTORY_SIZE": random.randint(10, 20),
        }
        
        self.log(f"已初始化。我的策略: 购买折扣 < {self.config['BUY_DISCOUNT_THRESHOLD']:.0%}, "
                 f"销售利润 > {self.config['SALE_PROFIT_MARGIN']:.0%}", "INIT")

    async def execute_turn(self):
        """执行一个完整的“资本家”回合"""
        try:
            # 1. 状态检查
            balance = await self.client.get_balance()
            my_nfts = await self.client.get_my_nfts()
            my_listings, _ = await self.client.get_my_activity()
            
            listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE'}
            my_planets = [nft for nft in my_nfts if nft['nft_type'] == 'PLANET']
            my_unlisted_planets = [p for p in my_planets if p['nft_id'] not in listed_nft_ids]
            
            self.log_turn_snapshot(balance, my_unlisted_planets, my_listings)

            # 2. 挖矿 (Harvest) - 优先级最高
            balance = await self._action_harvest_planets(my_planets, balance)

            # 3. 投资 (Explore & Scan)
            balance = await self._action_invest_and_scan(my_unlisted_planets, balance)

            # 4. 交易 (Manage Portfolio - Buy & Sell)
            balance = await self._action_manage_portfolio(my_unlisted_planets, balance)
            
            # 5. 收藏 (Update Showcase)
            await self._action_update_showcase(my_planets)
            
            self.log("回合评估结束。", action_type="EVALUATE_END")

        except Exception as e:
            self.log(f"❌ 执行回合时发生严重错误: {e}", action_type="ERROR")
        
        await asyncio.sleep(random.uniform(0.1, 1.0)) # 错峰

    # --- 机器人行为 ---

    async def _action_harvest_planets(self, my_planets: list, balance: float) -> float:
        """(挖矿) 检查所有星球并丰收"""
        self.log("检查星球 JPH 产出...", action_type="HARVEST_CHECK")
        harvested_count = 0
        
        for nft in my_planets:
            data = nft.get('data', {})
            jph = data.get('economic_stats', {}).get('total_jph', 0)
            if jph <= 0:
                continue
            
            last_harvest = data.get('last_harvest_time', 0)
            cooldown = PLANET_ECONOMICS['HARVEST_COOLDOWN_SECONDS']
            
            if time.time() > (last_harvest + cooldown):
                # 可以丰收
                name = data.get('custom_name') or nft['nft_id'][:6]
                self.log(f"正在丰收 {name} (JPH: {jph:.2f})...", action_type="NFT_ACTION_HARVEST")
                success, detail = await self.client.nft_action(nft['nft_id'], 'harvest', {})
                if success:
                    harvested_count += 1
                    # (余额会在下次循环开始时更新，这里不模拟加法)
                    self.log(f"丰收成功: {detail}", "NFT_ACTION_SUCCESS")
                else:
                    self.log(f"丰收失败: {detail}", "NFT_ACTION_FAIL")
        
        if harvested_count > 0:
            new_balance = await self.client.get_balance()
            self.log(f"总共丰收了 {harvested_count} 颗星球，新余额: {new_balance:.2f} FC", "INFO")
            return new_balance
        
        return balance

    async def _action_invest_and_scan(self, my_unlisted_planets: list, balance: float) -> float:
        """(投资) 探索新星球或扫描已有星球"""
        
        # 1. 探索
        if (balance > self.config["MIN_BALANCE_TO_EXPLORE"] and 
            len(my_unlisted_planets) < self.config["MAX_INVENTORY_SIZE"] and
            random.random() < CAPITALIST_CONFIG["EXPLORE_CHANCE"]):
            
            cost = CAPITALIST_CONFIG["EXPLORE_COST"]
            self.log(f"资本充足 ({balance:.2f} FC)，将花费 {cost} FC 探索新行星...", "SHOP_EXPLORE")
            success, detail, new_nft_id = await self.client.shop_action(
                "PLANET", cost, {}, "probabilistic_mint"
            )
            if success:
                self.log(f"探索完成: {detail}", "SHOP_EXPLORE_SUCCESS", data_snapshot={"new_nft_id": new_nft_id})
                balance -= cost
            else:
                self.log(f"探索失败: {detail}", "SHOP_EXPLORE_FAIL")
                balance -= cost # 钱还是花了
        
        # 2. 扫描
        if balance < CAPITALIST_CONFIG["SCAN_COST"]:
            return balance
            
        scannable_planets = [
            p for p in my_unlisted_planets 
            if p.get('data', {}).get('anomalies')
        ]
        
        if scannable_planets and random.random() < CAPITALIST_CONFIG["SCAN_CHANCE"]:
            nft_to_scan = random.choice(scannable_planets)
            anomaly = random.choice(nft_to_scan['data']['anomalies'])
            name = nft_to_scan['data'].get('custom_name') or nft_to_scan['nft_id'][:6]
            cost = CAPITALIST_CONFIG["SCAN_COST"]

            self.log(f"花费 {cost} FC 扫描行星 {name} 上的 {anomaly}...", "NFT_ACTION_SCAN")
            success, detail = await self.client.nft_action(nft_to_scan['nft_id'], 'scan', {'anomaly': anomaly})
            
            if success:
                self.log(f"扫描成功: {detail}", "NFT_ACTION_SUCCESS")
                balance -= cost
            else:
                self.log(f"扫描失败: {detail}", "NFT_ACTION_FAIL")
                balance -= cost # 钱还是花了
        
        return balance

    async def _action_manage_portfolio(self, my_unlisted_planets: list, balance: float) -> float:
        """(交易) 基于内在价值进行买卖和拍卖 (V2 逻辑)"""
        
        # --- 同时获取拍卖和销售列表 ---
        sale_listings_raw = await self.client.get_market_listings("SALE")
        auction_listings_raw = await self.client.get_market_listings("AUCTION")
        
        planet_sales = [
            item for item in sale_listings_raw 
            if item['nft_type'] == 'PLANET' and item.get('nft_data')
        ]
        planet_auctions = [
            item for item in auction_listings_raw 
            if item['nft_type'] == 'PLANET' and item.get('nft_data')
        ]
        
        # 1. 卖出 (清算库存，支持一口价或拍卖)
        if my_unlisted_planets and random.random() < 0.5: # 50%概率本回合卖东西
            nft_to_sell = random.choice(my_unlisted_planets)
            data = nft_to_sell.get('data', {})
            name = data.get('custom_name') or data.get('planet_type') or "行星"
            value = self.calculate_planet_value(data)

            # --- 随机选择拍卖或销售 ---
            if random.random() < 0.3: # 30% 几率拍卖
                listing_type = "AUCTION"
                auction_hours = random.uniform(1, 4) # 1-4 小时拍卖
                # 起拍价为估值的 50%，最低为 1 FC
                sale_price = round(max(1.0, value * 0.5), 2)
                desc = f"【稀有拍卖】{name} [估值 {value:.0f}] - 快速拍卖！"
                self.log(f"正在拍卖 {name} (内在价值 {value:.2f} FC)，起拍价 {sale_price:.2f} FC", "LIST_AUCTION")
            else: # 70% 几率一口价
                listing_type = "SALE"
                auction_hours = None
                sale_price = round(max(CAPITALIST_CONFIG["MIN_LISTING_PRICE"], value * self.config["SALE_PROFIT_MARGIN"]), 2)
                desc = f"【资本家精选】{name} [估值 {value:.0f} | 稀有度 {data.get('rarity_score',{}).get('total',0)}]"
                self.log(f"正在出售 {name} (内在价值 {value:.2f} FC)，挂单价 {sale_price:.2f} FC", "LIST_SALE")

            await self.client.create_listing(
                nft_to_sell['nft_id'], "PLANET", sale_price, desc, 
                listing_type, auction_hours
            )

        # 2. 买入 (抄底)
        bargains = []
        for item in planet_sales:
            price = item.get('price')
            if price > balance: continue
            value = self.calculate_planet_value(item.get('nft_data', {}))
            if price < (value * self.config["BUY_DISCOUNT_THRESHOLD"]):
                bargains.append(item)
        
        if bargains:
            item_to_buy = random.choice(bargains)
            price = item_to_buy['price']
            value = self.calculate_planet_value(item_to_buy.get('nft_data', {}))
            self.log(f"👉 抄底 (一口价)！发现 {item_to_buy['description']} 售价 {price:.2f} FC "
                     f"(内在价值 {value:.2f})，立即买入！", "MARKET_BUY")
            success, detail = await self.client.buy_item(item_to_buy['listing_id'])
            if success: return balance - price # 购买成功，余额减少
            # (失败了继续执行，也许可以竞拍)

        # 3. 竞拍 (捡漏)
        auction_bargains = []
        for item in planet_auctions:
            current_bid = item.get('highest_bid') or item.get('price')
            if current_bid > balance: continue # 没钱竞拍
            
            value = self.calculate_planet_value(item.get('nft_data', {}))
            # --- 核心修复：如果当前价格低于估值，就参与竞拍 ---
            if current_bid < (value * self.config["BUY_DISCOUNT_THRESHOLD"]):
                auction_bargains.append((item, value, current_bid))
        
        if auction_bargains:
            item_to_bid, value, current_bid = random.choice(auction_bargains)
            # 我们只出价到估值的 80%，或者比当前价高 5% (取较小者)，确保不亏
            my_max_bid = value * self.config["BUY_DISCOUNT_THRESHOLD"]
            new_bid_amount = round(min(my_max_bid, current_bid * 1.05 + 1.0), 2)
            
            if new_bid_amount > balance:
                self.log(f"发现拍卖品 {item_to_bid['description']} 值得竞拍，但余额不足以出价 {new_bid_amount:.2f} FC", "INFO")
            elif new_bid_amount > current_bid:
                self.log(f"👉 竞拍！发现 {item_to_bid['description']} 现价 {current_bid:.2f} FC "
                         f"(内在价值 {value:.2f})，出价 {new_bid_amount:.2f} FC！", "MARKET_BID")
                success, detail = await self.client.place_bid(item_to_bid['listing_id'], new_bid_amount)
                if success:
                    return balance - new_bid_amount # 出价成功，余额（托管）减少
        
        return balance

    async def _action_update_showcase(self, my_planets: list):
        """(收藏/展示) 更新个人资料展柜"""
        if not my_planets or random.random() > CAPITALIST_CONFIG["SHOWCASE_UPDATE_CHANCE"]:
            return
            
        try:
            # 1. 按“内在价值”排序
            sorted_planets = sorted(
                my_planets, 
                key=lambda nft: self.calculate_planet_value(nft.get('data', {})), 
                reverse=True
            )
            
            # 2. 选出最好的
            top_planet_ids = [
                nft['nft_id'] for nft in sorted_planets[:CAPITALIST_CONFIG["SHOWCASE_SIZE"]]
            ]
            
            # 3. 获取当前展柜
            profile_data, error = await self.client.api_call('GET', f"/profile/{self.client.auth_info['uid']}")
            if error:
                self.log(f"无法获取个人资料以更新展柜: {error}", "ERROR")
                return

            current_showcased_ids = [
                nft['nft_id'] for nft in profile_data.get('displayed_nfts_details', [])
            ]
            
            # 4. 仅在需要时更新
            if set(top_planet_ids) != set(current_showcased_ids):
                self.log(f"正在更新我的个人展柜，展示 {len(top_planet_ids)} 颗最佳行星...", "PROFILE_UPDATE")
                
                signature = (f"一个理性的星球资本家，管理着 {len(my_planets)} 颗行星。"
                             f" 最佳资产稀有度: {sorted_planets[0]['data']['rarity_score']['total']}")
                
                success, detail = await self.client.update_profile(signature[:100], top_planet_ids)
                
                if success:
                    self.log(f"展柜更新成功: {detail}", "PROFILE_UPDATE_SUCCESS")
                else:
                    self.log(f"展柜更新失败: {detail}", "PROFILE_UPDATE_FAIL")
            else:
                self.log("展柜已是最新，无需更新。", "INFO")

        except Exception as e:
            self.log(f"❌ 更新展柜时出错: {e}", "ERROR")