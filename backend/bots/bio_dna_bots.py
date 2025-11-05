# backend/bots/bio_dna_bots.py

import random
import time
import asyncio
from backend.bots.base_bot import BaseBot
from backend.bots.bot_client import BotClient

# --- 核心：导入灵宠的“世界观”和“经济学” ---
from backend.nft_logic.bio_dna import (
    BioDnaHandler, PET_ECONOMICS, SPECIES_CONFIG
)

# --- 机器人个性化配置 ---
PET_BOT_CONFIG = {
    # --- 探索 (投资) 策略 ---
    "EXPLORE_COST": PET_ECONOMICS.get("EXPLORE_COST", 10.0),
    "MIN_BALANCE_TO_EXPLORE": 30.0,
    "EXPLORE_CHANCE": 0.5, # 50% 概率去探索
    "MAX_PET_COUNT": 15,    # 宠物过多时停止探索

    # --- 养成 (训练) 策略 ---
    "TRAIN_COST_PER_LEVEL": PET_ECONOMICS.get("TRAIN_COST_PER_LEVEL", 5.0),
    "MIN_BALANCE_TO_TRAIN": 20.0,
    "TRAIN_CHANCE": 0.8, # 80% 概率训练宠物
    "MAX_TRAIN_LEVEL": 10, # 机器人会停止训练超过10级的宠物（以供出售）

    # --- 繁育 (增值) 策略 ---
    "BREED_CHANCE": 0.6, # 60% 概率尝试繁育
    "MIN_BREED_LEVEL": 3, # 只繁育等级3以上的

    # --- 交易策略 (基于内在价值) ---
    "BUY_DISCOUNT_THRESHOLD": 0.8,    # 购买阈值：只买市场价 < 内在价值 * 0.8 的
    "SALE_PROFIT_MARGIN": 1.15,       # 销售利润：挂单价 = 内在价值 * 1.15
    "MIN_LISTING_PRICE": 10.0,        # 最低挂单价
    
    # --- 收藏策略 ---
    "SHOWCASE_UPDATE_CHANCE": 0.2,    # 20% 的概率更新展柜
    "SHOWCASE_SIZE": 6,               # 展柜大小
}

# --- 中文名 ---
PET_CHINESE_NAMES = ["灵宠饲养员", "基因工程师", "生物学家", "宠物小精灵大师", "JCoin繁育专家"]

def get_random_chinese_name() -> str:
    """获取一个随机中文名"""
    return random.choice(PET_CHINESE_NAMES)

# ==============================================================================
# --- 机器人: 灵宠繁育专家 (BioDnaBot) ---
# ==============================================================================

class BioDnaBot(BaseBot):
    """
    “灵宠繁育专家”机器人 (V1)
    一个基于内在价值进行探索、训练、繁育和交易的智能机器人。
    """
    # --- 框架必需：默认值和显示名 ---
    DEFAULT_FUNDS = 1000.0
    DEFAULT_PROBABILITY = 0.4 # 40% 的概率被激活
    CHINESE_DISPLAY_NAME = "灵宠专家"

    @classmethod
    def get_chinese_display_name(cls) -> str:
        return cls.CHINESE_DISPLAY_NAME

    def __init__(self, client: BotClient):
        super().__init__(client)
        
        # --- 获取核心估值函数 ---
        try:
            val_config = BioDnaHandler.get_economic_config_and_valuation()
            self.calculate_pet_value = val_config["calculate_value_func"]
        except Exception as e:
            self.log(f"❌ 严重错误：无法加载灵宠估值函数: {e}", "ERROR")
            self.calculate_pet_value = lambda data: 1.0 

        # --- 生成“个性” (与星球机器人类似) ---
        self.config = {
            "BUY_DISCOUNT_THRESHOLD": random.uniform(0.75, 0.9),
            "SALE_PROFIT_MARGIN": random.uniform(1.1, 1.3),
            "MAX_TRAIN_LEVEL": random.randint(8, 15),
            "MAX_PET_COUNT": random.randint(10, 25),
        }
        
        self.log(f"已初始化。我的策略: 购买折扣 < {self.config['BUY_DISCOUNT_THRESHOLD']:.0%}, "
                 f"销售利润 > {self.config['SALE_PROFIT_MARGIN']:.0%}", "INIT")

    async def execute_turn(self):
        """执行一个完整的“灵宠专家”回合"""
        try:
            # 1. 状态检查
            balance = await self.client.get_balance()
            my_nfts = await self.client.get_my_nfts()
            my_listings, _ = await self.client.get_my_activity()
            
            listed_nft_ids = {l['nft_id'] for l in my_listings if l['status'] == 'ACTIVE'}
            my_pets = [nft for nft in my_nfts if nft['nft_type'] == 'BIO_DNA']
            my_unlisted_pets = [p for p in my_pets if p['nft_id'] not in listed_nft_ids]
            
            self.log_turn_snapshot(balance, my_unlisted_pets, my_listings)

            # 2. 丰收 (Harvest) - 优先级最高
            balance = await self._action_harvest_pets(my_pets, balance)

            # 3. 探索 (Explore) - 获取新宠物
            balance = await self._action_explore_pets(my_unlisted_pets, balance)

            # 4. 养成 (Train) - 提升宠物价值
            balance = await self._action_train_pets(my_unlisted_pets, balance)

            # 5. 繁育 (Breed) - 创造新资产
            await self._action_breed_pets(my_unlisted_pets)
            
            # 6. 交易 (Manage Portfolio - Buy & Sell)
            balance = await self._action_manage_portfolio(my_unlisted_pets, balance)
            
            # 7. 收藏 (Update Showcase)
            await self._action_update_showcase(my_pets)
            
            self.log("回合评估结束。", action_type="EVALUATE_END")

        except Exception as e:
            self.log(f"❌ 执行回合时发生严重错误: {e}", action_type="ERROR")
        
        await asyncio.sleep(random.uniform(0.1, 1.0)) # 错峰

    # --- 机器人行为 ---

    async def _action_harvest_pets(self, my_pets: list, balance: float) -> float:
        """(丰收) 检查所有灵宠并丰收"""
        self.log("检查灵宠 JPH 产出...", action_type="HARVEST_CHECK")
        harvested_count = 0
        now = time.time()
        
        for nft in my_pets:
            data = nft.get('data', {})
            jph = data.get('economic_stats', {}).get('total_jph', 0)
            if jph <= 0:
                continue
            
            last_harvest = data.get('last_harvest_time', 0)
            cooldown = PET_ECONOMICS['HARVEST_COOLDOWN_SECONDS']
            
            if now > (last_harvest + cooldown):
                name = data.get('nickname') or nft['nft_id'][:6]
                self.log(f"正在丰收 {name} (JPH: {jph:.2f})...", action_type="NFT_ACTION_HARVEST")
                success, detail = await self.client.nft_action(nft['nft_id'], 'harvest', {})
                if success:
                    harvested_count += 1
                    self.log(f"丰收成功: {detail}", "NFT_ACTION_SUCCESS")
                else:
                    self.log(f"丰收失败: {detail}", "NFT_ACTION_FAIL")
        
        if harvested_count > 0:
            new_balance = await self.client.get_balance()
            self.log(f"总共丰收了 {harvested_count} 只灵宠，新余额: {new_balance:.2f} FC", "INFO")
            return new_balance
        
        return balance

    async def _action_explore_pets(self, my_unlisted_pets: list, balance: float) -> float:
        """(探索) 探索发现新灵宠"""
        
        if (balance > PET_BOT_CONFIG["MIN_BALANCE_TO_EXPLORE"] and 
            len(my_unlisted_pets) < self.config["MAX_PET_COUNT"] and
            random.random() < PET_BOT_CONFIG["EXPLORE_CHANCE"]):
            
            cost = PET_BOT_CONFIG["EXPLORE_COST"]
            self.log(f"资本充足 ({balance:.2f} FC)，将花费 {cost} FC 探索新灵宠...", "SHOP_EXPLORE")
            success, detail, new_nft_id = await self.client.shop_action(
                "BIO_DNA", cost, {}, "probabilistic_mint"
            )
            if success:
                self.log(f"探索完成: {detail}", "SHOP_EXPLORE_SUCCESS", data_snapshot={"new_nft_id": new_nft_id})
                balance -= cost # 探索无论成功与否都扣钱
            else:
                self.log(f"探索失败: {detail}", "SHOP_EXPLORE_FAIL")
                balance -= cost 
        
        return balance

    async def _action_train_pets(self, my_unlisted_pets: list, balance: float) -> float:
        """(养成) 训练低等级灵宠"""
        
        if (balance < PET_BOT_CONFIG["MIN_BALANCE_TO_TRAIN"] or 
            random.random() > PET_BOT_CONFIG["TRAIN_CHANCE"]):
            return balance

        now = time.time()
        trainable_pets = [
            p for p in my_unlisted_pets
            if (p.get('data', {}).get('level', 1) < self.config["MAX_TRAIN_LEVEL"] and
                (p.get('data', {}).get('cooldowns', {}).get('train_until', 0) < now))
        ]
        
        if not trainable_pets:
            return balance
            
        pet_to_train = random.choice(trainable_pets)
        data = pet_to_train['data']
        name = data.get('nickname') or data.get('species_name')
        level = data.get('level', 1)
        cost = PET_BOT_CONFIG["TRAIN_COST_PER_LEVEL"] * level
        
        if balance < cost:
            self.log(f"想训练 {name} (Lv.{level})，但余额不足 (需 {cost:.2f} FC)", "INFO")
            return balance

        self.log(f"花费 {cost:.2f} FC 训练 {name} (Lv.{level})...", "NFT_ACTION_TRAIN")
        success, detail = await self.client.nft_action(pet_to_train['nft_id'], 'train', {})
        
        if success:
            self.log(f"训练成功: {detail}", "NFT_ACTION_SUCCESS")
            balance -= cost
        else:
            self.log(f"训练失败: {detail}", "NFT_ACTION_FAIL")
        
        return balance

    async def _action_breed_pets(self, my_unlisted_pets: list):
        """(繁育) 尝试在我拥有的灵宠中寻找配对"""
        
        if random.random() > PET_BOT_CONFIG["BREED_CHANCE"] or len(my_unlisted_pets) < 2:
            return

        now = time.time()
        
        # 1. 筛选出所有可繁育的 (按性别)
        eligible_females = []
        eligible_males = {} # 按物种分类: {"绒球兔": [pet1, pet2], ...}

        for pet in my_unlisted_pets:
            data = pet.get('data', {})
            cooldowns = data.get('cooldowns', {})
            breeds_left = data.get('breeding_limit', 0) - data.get('breeding_count', 0)
            
            if (breeds_left > 0 and 
                cooldowns.get('breed_until', 0) < now and
                data.get('level', 1) >= PET_BOT_CONFIG["MIN_BREED_LEVEL"]):
                
                species = data.get('species_name')
                if not species: continue

                if data.get('gender') == 'Female':
                    eligible_females.append(pet)
                elif data.get('gender') == 'Male':
                    if species not in eligible_males:
                        eligible_males[species] = []
                    eligible_males[species].append(pet)
        
        if not eligible_females or not eligible_males:
            self.log("没有找到可用的繁育配对。", "INFO")
            return

        # 2. 尝试配对
        random.shuffle(eligible_females)
        for female_pet in eligible_females:
            female_data = female_pet['data']
            species = female_data.get('species_name')
            
            if species in eligible_males and eligible_males[species]:
                male_pet = random.choice(eligible_males[species])
                
                f_name = female_data.get('nickname') or female_data.get('species_name')
                m_name = male_pet['data'].get('nickname') or male_pet['data'].get('species_name')
                
                self.log(f"找到配对！尝试用 {f_name} (F) 和 {m_name} (M) 繁育...", "NFT_ACTION_BREED")
                
                success, detail = await self.client.nft_action(
                    female_pet['nft_id'], 
                    'breed', 
                    {'partner_nft_id': male_pet['nft_id']}
                )
                
                if success:
                    self.log(f"繁育成功: {detail}", "NFT_ACTION_SUCCESS")
                else:
                    self.log(f"繁育失败: {detail}", "NFT_ACTION_FAIL")
                
                # 无论成功与否，本回合只繁育一次
                return

    async def _action_manage_portfolio(self, my_unlisted_pets: list, balance: float) -> float:
        """(交易) 基于内在价值进行买卖"""
        
        market_listings = await self.client.get_market_listings("SALE")
        pet_listings = [
            item for item in market_listings 
            if item['nft_type'] == 'BIO_DNA' and item.get('nft_data')
        ]
        
        # 1. 卖出 (清算库存)
        if my_unlisted_pets:
            pet_to_sell = random.choice(my_unlisted_pets)
            data = pet_to_sell.get('data', {})
            name = data.get('nickname') or data.get('species_name') or "灵宠"
            
            value = self.calculate_pet_value(data)
            sale_price = round(max(PET_BOT_CONFIG["MIN_LISTING_PRICE"], value * self.config["SALE_PROFIT_MARGIN"]), 2)
            
            desc = f"【专家培育】Lv.{data.get('level',1)} {name} [估值 {value:.0f}]"
            self.log(f"正在出售 {name} (内在价值 {value:.2f} FC)，挂单价 {sale_price:.2f} FC", "LIST_SALE")
            await self.client.create_listing(pet_to_sell['nft_id'], "BIO_DNA", sale_price, desc, "SALE")

        # 2. 买入 (抄底)
        bargains = []
        for item in pet_listings:
            price = item.get('price')
            if price > balance:
                continue
                
            value = self.calculate_pet_value(item.get('nft_data', {}))
            
            if price < (value * self.config["BUY_DISCOUNT_THRESHOLD"]):
                bargains.append(item)
        
        if bargains:
            item_to_buy = random.choice(bargains)
            price = item_to_buy['price']
            value = self.calculate_pet_value(item_to_buy.get('nft_data', {}))
            
            self.log(f"👉 抄底！发现 {item_to_buy['description']} 售价 {price:.2f} FC "
                     f"(内在价值 {value:.2f})，立即买入！", "MARKET_BUY")
            success, detail = await self.client.buy_item(item_to_buy['listing_id'])
            
            if success:
                self.log(f"抄底成功: {detail}", "MARKET_BUY_SUCCESS")
                return balance - price
            else:
                self.log(f"抄底失败: {detail}", "MARKET_BUY_FAIL")
        
        return balance

    async def _action_update_showcase(self, my_pets: list):
        """(收藏/展示) 更新个人资料展柜"""
        if not my_pets or random.random() > PET_BOT_CONFIG["SHOWCASE_UPDATE_CHANCE"]:
            return
            
        try:
            sorted_pets = sorted(
                my_pets, 
                key=lambda nft: self.calculate_pet_value(nft.get('data', {})), 
                reverse=True
            )
            
            top_pet_ids = [
                nft['nft_id'] for nft in sorted_pets[:PET_BOT_CONFIG["SHOWCASE_SIZE"]]
            ]
            
            profile_data, error = await self.client.api_call('GET', f"/profile/{self.client.auth_info['uid']}")
            if error:
                self.log(f"无法获取个人资料以更新展柜: {error}", "ERROR")
                return

            current_showcased_ids = [
                nft['nft_id'] for nft in profile_data.get('displayed_nfts_details', [])
            ]
            
            if set(top_pet_ids) != set(current_showcased_ids):
                self.log(f"正在更新我的个人展柜，展示 {len(top_pet_ids)} 只最佳灵宠...", "PROFILE_UPDATE")
                
                signature = (f"一个专业的灵宠饲养员，管理着 {len(my_pets)} 只灵宠。"
                             f" 最佳资产估值: {self.calculate_pet_value(sorted_pets[0]['data']):.0f} FC")
                
                success, detail = await self.client.update_profile(signature[:100], top_pet_ids)
                
                if success:
                    self.log(f"展柜更新成功: {detail}", "PROFILE_UPDATE_SUCCESS")
                else:
                    self.log(f"展柜更新失败: {detail}", "PROFILE_UPDATE_FAIL")

        except Exception as e:
            self.log(f"❌ 更新展柜时出错: {e}", "ERROR")