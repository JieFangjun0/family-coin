# backend/nft_logic/bio_dna.py

import random
import time
import uuid
import math
from .base import NFTLogicHandler
from backend.db import queries_nft # 用于繁育时铸造新NFT和更新伴侣

# --- 灵宠世界观与经济设定 ---

# 1. 物种
# (物种名, 稀有度, 挂机资源, 基础JPH)
SPECIES_CONFIG = {
    "COMMON": [
        ("绒球兔", "COMMON", "Glimmer", 0.02),
        ("溪流蛙", "COMMON", "Glimmer", 0.02),
        ("林地松鼠", "COMMON", "Glimmer", 0.03),
    ],
    "UNCOMMON": [
        ("月光狐", "UNCOMMON", "Stardust", 0.05),
        ("苔原鹿", "UNCOMMON", "Stardust", 0.06),
        ("焰尾猫", "UNCOMMON", "Stardust", 0.07),
    ],
    "RARE": [
        ("幽影狼", "RARE", "Ember", 0.12),
        ("晶歌鸟", "RARE", "Ember", 0.15),
        ("岩背龟", "RARE", "Ember", 0.10),
    ],
    "MYTHIC": [
        ("星噬体", "MYTHIC", "Aether", 0.30),
        ("圣光麒麟", "MYTHIC", "Aether", 0.40),
    ]
}

# 2. 基因库 (定性)
# 格式: (等位基因, 是否显性)
GENE_POOL = {
    "COLOR": [
        ("Red", True), ("White", False), ("Black", True), ("Yellow", False),
        ("Blue", True), ("Green", False), ("Purple", True), ("Silver", False),
    ],
    "PATTERN": [
        ("Solid", True), ("Stripes", True), ("Spots", False), ("None", False),
    ],
    "AURA": [
        ("Sparkle", True), ("Glow", False), ("None", False), ("Shadow", True),
    ],
}

# 3. 性格 (定性, 非遗传)
PERSONALITIES = ["Timid", "Brave", "Goofy", "Calm", "Lazy", "Hyper", "Serious", "Elegant"]

# 4. 经济与平衡性
PET_ECONOMICS = {
    # --- 探索 (铸造) ---
    "EXPLORE_COST": 10.0,
    "EXPLORE_PROB_COMMON": 0.85,
    "EXPLORE_PROB_UNCOMMON": 0.12,
    "EXPLORE_PROB_RARE": 0.02,
    "EXPLORE_PROB_MYTHIC": 0.01,
    
    # --- 养成 (训练) ---
    "TRAIN_COST_PER_LEVEL": 5.0, # 训练成本 = 5 * (当前等级)
    "XP_PER_TRAIN": 25,
    "XP_NEEDED_PER_LEVEL": 100, # 升级所需XP = 100 * (当前等级)
    
    # --- 挂机 (JPH) ---
    "HARVEST_COOLDOWN_SECONDS": 1 * 3600,  # 1小时
    "HARVEST_MAX_ACCRUAL_HOURS": 12,       # 最多累积12小时
    
    # --- 繁育 ---
    "BREED_COOLDOWN_SECONDS": 8 * 3600,    # 8小时
    
    # --- 估值模型 ---
    "VALUE_BASE": 5.0,
    "VALUE_PER_LEVEL": 1.5,
    "VALUE_RARITY_MULT": {"COMMON": 1.0, "UNCOMMON": 3.0, "RARE": 10.0, "MYTHIC": 50.0},
    "VALUE_PER_JPH_FACTOR": 24 * 7, # 1 JPH 约等于 1 周产出的估值
    "VALUE_PER_BREED_REMAINING": 15.0,
    "VALUE_GENE_AURA_BONUS": 50.0, # 稀有光环的估值加成
}

class BioDnaHandler(NFTLogicHandler):
    """
    "灵宠" (BIO_DNA) NFT 的逻辑处理器。
    """
    
    @classmethod
    def get_display_name(cls) -> str:
        return "灵宠"

    # --- 辅助函数 ---
    
    def _get_phenotype(self, genes: dict) -> dict:
        """根据等位基因计算显性表型"""
        visible = {}
        for gene_type, alleles in genes.items():
            pool = [g for g in GENE_POOL[gene_type] if g[0] in alleles]
            # 规则：如果任何一个等位基因是显性，则显示第一个显性性状。否则，显示第一个隐性性状。
            dominant_alleles = [g for g in pool if g[1]]
            if dominant_alleles:
                visible[gene_type.lower()] = dominant_alleles[0][0]
            elif pool:
                visible[gene_type.lower()] = pool[0][0]
            else:
                visible[gene_type.lower()] = "None"
        return visible

    def _generate_pet_data(self, owner_key: str, owner_username: str, species_rarity: str, generation: int = 0) -> dict:
        """ 内部辅助函数：生成一只随机的灵宠数据 """
        
        species_info = random.choice(SPECIES_CONFIG[species_rarity])
        species_name, _, afk_resource, base_jph = species_info
        
        # 1. 生成基础属性
        stats = {
            "vitality": random.randint(5, 20),
            "spirit": random.randint(5, 20),
            "agility": random.randint(5, 20),
            "luck": random.randint(1, 10),
        }
        
        # 2. 生成等位基因 (双份)
        genes = {}
        for gene_type, pool in GENE_POOL.items():
            genes[gene_type] = [random.choice(pool)[0], random.choice(pool)[0]]

        # 3. 计算表型
        visible_traits = self._get_phenotype(genes)
        
        # 4. 计算JPH
        # (基础JPH + (精神/100))
        total_jph = base_jph + (stats["spirit"] / 100.0)
        
        pet_data = {
            "species_name": species_name,
            "species_rarity": species_rarity,
            "afk_resource": afk_resource,
            "generation": generation,
            "nickname": species_name, # 默认昵称
            "gender": random.choice(["Male", "Female"]),
            "level": 1,
            "xp": 0,
            
            "stats": stats,
            "genes": genes,
            "visible_traits": visible_traits,
            "personality": random.choice(PERSONALITIES),
            
            "breeding_limit": random.randint(3, 8),
            "breeding_count": 0,
            
            "cooldowns": {
                "breed_until": 0,
                "train_until": 0,
            },
            
            "economic_stats": {
                "base_jph": total_jph,
                "total_jph": total_jph,
            },
            "last_harvest_time": time.time(),
        }
        return pet_data

    # --- 估值系统 ---

    @classmethod
    def get_economic_config_and_valuation(cls) -> dict:
        """
        返回经济配置，以及一个用于计算灵宠估值的函数。
        """
        
        def calculate_value(nft_data: dict) -> float:
            try:
                rarity = nft_data.get('species_rarity', 'COMMON')
                level = nft_data.get('level', 1)
                jph = nft_data.get('economic_stats', {}).get('total_jph', 0)
                breeds_left = max(0, nft_data.get('breeding_limit', 0) - nft_data.get('breeding_count', 0))
                aura = nft_data.get('visible_traits', {}).get('aura', 'None')
                
                # 1. 基础价值
                value = PET_ECONOMICS['VALUE_BASE']
                # 2. 稀有度价值
                value += PET_ECONOMICS['VALUE_RARITY_MULT'][rarity] * PET_ECONOMICS['VALUE_PER_LEVEL'] * level
                # 3. 产出价值
                value += jph * PET_ECONOMICS['VALUE_PER_JPH_FACTOR']
                # 4. 繁育价值
                value += breeds_left * PET_ECONOMICS['VALUE_PER_BREED_REMAINING']
                # 5. 基因价值
                if aura != 'None':
                    value += PET_ECONOMICS['VALUE_GENE_AURA_BONUS']
                
                return max(1.0, round(value, 2))
            except Exception:
                return 1.0 # 估值失败
        
        return {
            "config": PET_ECONOMICS,
            "calculate_value_func": calculate_value
        }

    # --- 核心框架实现 ---

    @classmethod
    def execute_shop_action(cls, owner_key: str, owner_username: str, data: dict, conn) -> (bool, str, str):
        """
        处理“探索”动作 (概率性铸造)。
        """
        prob_roll = random.random()
        
        if prob_roll < PET_ECONOMICS['EXPLORE_PROB_MYTHIC']:
            rarity = "MYTHIC"
        elif prob_roll < (PET_ECONOMICS['EXPLORE_PROB_MYTHIC'] + PET_ECONOMICS['EXPLORE_PROB_RARE']):
            rarity = "RARE"
        elif prob_roll < (PET_ECONOMICS['EXPLORE_PROB_MYTHIC'] + PET_ECONOMICS['EXPLORE_PROB_RARE'] + PET_ECONOMICS['EXPLORE_PROB_UNCOMMON']):
            rarity = "UNCOMMON"
        else:
            rarity = "COMMON"

        pet_data = cls()._generate_pet_data(owner_key, owner_username, rarity, 0)
        
        success, detail, nft_id = queries_nft.mint_nft(
            owner_key=owner_key, nft_type="BIO_DNA", data=pet_data, conn=conn
        )
        if not success: return False, f"发现灵宠但铸造失败: {detail}", None
        
        msg = f"探索成功！你发现了一只 {rarity} 级的【{pet_data['species_name']}】！"
        return True, msg, nft_id

    def mint(self, owner_key: str, data: dict, owner_username: str = None) -> (bool, str, dict):
        """管理员铸造，支持自定义覆盖"""
        rarity = data.get('species_rarity', 'COMMON')
        db_data = self._generate_pet_data(owner_key, owner_username or "管理员", rarity, 0)
        
        # 允许管理员覆盖特定字段
        if 'nickname' in data: db_data['nickname'] = data['nickname']
        if 'stats' in data: db_data['stats'].update(data['stats'])
        if 'breeding_limit' in data: db_data['breeding_limit'] = data['breeding_limit']
        
        return True, "管理员成功创造了一只灵宠。", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        if nft.get('owner_key') != requester_key:
            return False, "你不是这只灵宠的主人"
            
        data = nft['data']
        cooldowns = data.get('cooldowns', {})
        now = time.time()

        if action == 'rename':
            new_name = action_data.get('new_name')
            if not new_name or len(new_name) < 2 or len(new_name) > 30:
                return False, "昵称必须在 2 到 30 个字符之间"
            return True, "可以重命名"

        if action == 'harvest':
            # 逻辑与 Planet 类似
            if data.get('economic_stats', {}).get('total_jph', 0) <= 0:
                return False, "这只灵宠不产生任何资源"
            
            last_harvest = data.get('last_harvest_time', 0)
            cooldown = PET_ECONOMICS['HARVEST_COOLDOWN_SECONDS']
            
            if now < (last_harvest + cooldown):
                time_left = int((last_harvest + cooldown) - now)
                return False, f"灵宠正在休息中，剩余冷却时间: {time_left // 60} 分钟"
            return True, "可以收获"
            
        if action == 'train':
            if now < cooldowns.get('train_until', 0):
                return False, "灵宠正在训练中，请稍后再试"
            # 成本检查由 routes_nft.py 处理
            return True, "可以训练"

        if action == 'breed':
            if data.get('gender') != 'Female':
                return False, "只有雌性灵宠可以发起繁育"
            if data.get('breeding_count', 0) >= data.get('breeding_limit', 0):
                return False, "这只灵宠的繁育次数已达上限"
            if now < cooldowns.get('breed_until', 0):
                return False, "这只灵宠正在繁育冷却中"
                
            partner_nft_id = action_data.get('partner_nft_id')
            if not partner_nft_id:
                return False, "必须选择一只伴侣灵宠"
            if partner_nft_id == nft['nft_id']:
                return False, "不能和自己繁育"

            # 伴侣的验证将在 perform_action 中的事务内进行
            return True, "可以尝试繁育"

        return super().validate_action(nft, action, action_data, requester_key)

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str, conn=None) -> (bool, str, dict):
        """
        (重构) 执行动作。
        繁育(breed)和训练(train)动作需要 conn 事务支持。
        """
        updated_data = nft['data'].copy()
        now = time.time()

        if action == 'rename':
            new_name = action_data.get('new_name')
            updated_data['nickname'] = new_name
            return True, f"灵宠已成功命名为: {new_name}", updated_data
        
        if action == 'harvest':
            econ_stats = updated_data.get('economic_stats', {})
            total_jph = econ_stats.get('total_jph', 0)
            last_harvest = updated_data.get('last_harvest_time', 0)
            
            seconds_passed = now - last_harvest
            max_accrual_seconds = PET_ECONOMICS['HARVEST_MAX_ACCRUAL_HOURS'] * 3600
            seconds_to_harvest = min(seconds_passed, max_accrual_seconds)
            
            jcoin_produced = (seconds_to_harvest / 3600.0) * total_jph
            
            updated_data['last_harvest_time'] = now
            updated_data['__jcoin_produced__'] = round(jcoin_produced, 4)
            
            return True, f"收获成功！你从灵宠收集了 {jcoin_produced:.4f} JCoin。", updated_data

        if action == 'train':
            if not conn: return False, "训练失败：需要数据库事务支持", {}
            
            level = updated_data.get('level', 1)
            xp_needed = PET_ECONOMICS['XP_NEEDED_PER_LEVEL'] * level
            
            updated_data['xp'] = updated_data.get('xp', 0) + PET_ECONOMICS['XP_PER_TRAIN']
            msg = f"训练成功！{updated_data['nickname']} 获得了 {PET_ECONOMICS['XP_PER_TRAIN']} XP。"
            
            # --- 检查升级 ---
            if updated_data['xp'] >= xp_needed:
                updated_data['level'] += 1
                updated_data['xp'] = 0
                
                # 升级，属性点随机增长
                stats = updated_data['stats']
                stats['vitality'] += random.randint(1, 3)
                stats['spirit'] += random.randint(1, 3)
                stats['agility'] += random.randint(1, 3)
                stats['luck'] += random.randint(0, 1)
                
                # JPH 也随之增长
                base_jph = updated_data['economic_stats']['base_jph']
                updated_data['economic_stats']['total_jph'] = base_jph + (stats["spirit"] / 100.0)
                
                msg = f"🎉 升级！{updated_data['nickname']} 升到了 {updated_data['level']} 级！属性得到了提升！"
            
            updated_data['cooldowns']['train_until'] = now + (3600 * (level / 2)) # 训练冷却时间随等级增加
            return True, msg, updated_data

        if action == 'breed':
            if not conn: return False, "繁育失败：需要数据库事务支持", {}
            
            partner_nft_id = action_data.get('partner_nft_id')
            cursor = conn.cursor()
            
            # --- 1. 验证伴侣 ---
            cursor.execute("SELECT data, status FROM nfts WHERE nft_id = ? AND owner_key = ?", (partner_nft_id, requester_key))
            partner_row = cursor.fetchone()
            
            if not partner_row: return False, "选择的伴侣NFT不存在或不属于你", {}
            if partner_row['status'] != 'ACTIVE': return False, "伴侣NFT不是活跃状态", {}
            
            partner_data = json.loads(partner_row['data'])
            
            if partner_data.get('species_name') != updated_data.get('species_name'):
                return False, "繁育失败：必须是相同物种的灵宠", {}
            if partner_data.get('gender') != 'Male':
                return False, "繁育失败：伴侣必须是雄性", {}
            if partner_data.get('breeding_count', 0) >= partner_data.get('breeding_limit', 0):
                return False, "繁育失败：伴侣的繁育次数已达上限", {}
            if now < partner_data.get('cooldowns', {}).get('breed_until', 0):
                return False, "繁育失败：伴侣正在繁育冷却中", {}

            # --- 2. 执行繁育 (遗传算法) ---
            p1_data = updated_data # Female
            p2_data = partner_data # Male
            
            # 2a. 新属性
            new_gen = max(p1_data['generation'], p2_data['generation']) + 1
            new_limit = random.randint(
                min(p1_data['breeding_limit'], p2_data['breeding_limit']) - 1, 
                max(p1_data['breeding_limit'], p2_data['breeding_limit'])
            )
            new_limit = max(0, new_limit) # 确保不为负
            
            # 2b. 新数值 (均值 + 突变)
            new_stats = {}
            for stat in ["vitality", "spirit", "agility", "luck"]:
                mean = (p1_data['stats'][stat] + p2_data['stats'][stat]) / 2
                mutation = (p1_data['stats']['luck'] + p2_data['stats']['luck']) / 20.0 # 幸运影响突变
                new_stats[stat] = max(1, int(mean + random.uniform(-mutation, mutation)))
            
            # 2c. 新基因 (孟德尔遗传)
            new_genes = {}
            for gene_type in GENE_POOL.keys():
                new_genes[gene_type] = [
                    random.choice(p1_data['genes'][gene_type]),
                    random.choice(p2_data['genes'][gene_type])
                ]
            
            # --- 3. 组装新灵宠 ---
            new_pet_data = self._generate_pet_data(requester_key, nft['owner_username'], p1_data['species_rarity'], new_gen)
            # 覆盖遗传数据
            new_pet_data.update({
                "nickname": f"{p1_data['nickname'][:5]}-{p2_data['nickname'][:5]}的后代",
                "generation": new_gen,
                "stats": new_stats,
                "genes": new_genes,
                "visible_traits": self._get_phenotype(new_genes),
                "breeding_limit": new_limit,
            })
            # 重新计算JPH
            new_pet_data['economic_stats']['total_jph'] = new_pet_data['economic_stats']['base_jph'] + (new_stats["spirit"] / 100.0)

            # --- 4. 铸造新灵宠 (在事务中) ---
            success_mint, detail_mint, new_nft_id = queries_nft.mint_nft(
                requester_key, "BIO_DNA", new_pet_data, conn
            )
            if not success_mint:
                # conn.rollback() 已在 mint_nft 内部处理(并没有, mint_nft 不会 rollback)
                return False, f"繁育成功但铸造后代失败: {detail_mint}", {}

            # --- 5. 更新父母状态 (在事务中) ---
            breed_cooldown = PET_ECONOMICS['BREED_COOLDOWN_SECONDS']
            
            # 更新雌性 (self)
            updated_data['breeding_count'] += 1
            updated_data['cooldowns']['breed_until'] = now + breed_cooldown
            
            # 更新雄性 (partner)
            partner_data['breeding_count'] += 1
            partner_data['cooldowns']['breed_until'] = now + breed_cooldown
            
            try:
                cursor.execute(
                    "UPDATE nfts SET data = ? WHERE nft_id = ?",
                    (json.dumps(partner_data, ensure_ascii=False), partner_nft_id)
                )
                if cursor.rowcount == 0:
                    raise Exception("更新伴侣NFT失败")
            except Exception as e:
                return False, f"繁育成功但更新伴侣状态失败: {e}", {}
            
            return True, f"繁育成功！你获得了一只新的【{new_pet_data['species_name']}】 (G{new_gen})！", updated_data

        # --- 默认调用基类 (用于 'destroy') ---
        return super().perform_action(nft, action, action_data, requester_key)

    @classmethod
    def get_shop_config(cls) -> dict:
        """商店配置：探索"""
        cost = PET_ECONOMICS['EXPLORE_COST']
        return {
            "creatable": True,
            "cost": cost,
            "name": "探索低语森林",
            "action_type": "probabilistic_mint", # 触发 execute_shop_action
            "action_label": f"支付 {cost} FC 开始探索",
            "description": f"花费 {cost} FC 探索神秘的低语森林，有几率发现并带回一只常见的 (85%)、罕见的 (12%)、稀有的 (2%) 甚至神话的 (1%) 灵宠。",
            "fields": []
        }
        
    def get_trade_description(self, nft: dict) -> str:
        """市场描述"""
        data = nft.get('data', {})
        name = data.get('nickname') or "未命名灵宠"
        species = data.get('species_name', '未知')
        rarity = data.get('species_rarity', 'COMMON')
        level = data.get('level', 1)
        jph = data.get('economic_stats', {}).get('total_jph', 0)
        
        jph_str = f" | 💰 {jph:.2f} JPH" if jph > 0 else ""
        return f"Lv.{level} {name} ({species}) [稀有度: {rarity}]{jph_str}"
        
    @classmethod
    def get_admin_mint_config(cls) -> dict:
        """管理员铸造帮助"""
        return {
            "help_text": '为“灵宠”提供: {"species_rarity": "COMMON/UNCOMMON/RARE/MYTHIC", "nickname": "可选", "breeding_limit": 10}',
            "default_json": '''{
  "species_rarity": "RARE",
  "nickname": "管理员的宠物",
  "breeding_limit": 10
}'''
        }