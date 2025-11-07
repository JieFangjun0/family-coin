# backend/nft_logic/planet.py

import random
import time
import uuid
import math
from .base import NFTLogicHandler
from backend.db import queries_nft

# --- V3 经济与平衡性配置 ---
# (这就是你提到的“精细控制其价值”的函数所依赖的配置)
PLANET_ECONOMICS = {
    # --- 探索成本 ---
    "EXPLORE_COST": 1000.0,  # 原为 15.0 (1000 / 0.2 = 5000 FC 平均成本)
    "EXPLORE_PROBABILITY_OF_DISCOVERY": 0.20,

    # --- 扫描成本 ---
    "SCAN_COST": 500.0, # 原为 10.0 (100x 灵宠成本)

    # --- 丰收 (JCoin 产出) 配置 ---
    "HARVEST_COOLDOWN_SECONDS": 60,  # 原为 4 * 3600 (4小时)
    "HARVEST_MAX_ACCRUAL_HOURS": 24,
    "BASE_JCOIN_PER_HOUR": 42.5,   # 原为 0.05 (850x 提升)

    # --- 估值模型参数 (用于 get_economic_config_and_valuation) ---
    "VALUE_BASE_FLAT": 500.0,               # 原为 5.0 (100x)
    "VALUE_RARITY_FACTOR": 20.0,                # 原为 0.2 (100x)
    "VALUE_JPH_FACTOR": 84,                 # 原为 24 * 30 (改为 24 * 3.5, 匹配 3.5 天的回报周期)
}


# --- V3 世界观设定 ---

# 恒星等级 -> (中文名, 基础稀有度)
STAR_CLASSES = {
    "M": ("M级 (红矮星)", 5),
    "K": ("K级 (橙矮星)", 10),
    "G": ("G级 (黄矮星)", 20),
    "F": ("F级 (白星)", 35),
    "A": ("A级 (蓝白星)", 50),
    "B": ("B级 (蓝巨星)", 70),
    "O": ("O级 (蓝超巨星)", 100),
    "N": ("中子星", 250),
    "BH": ("黑洞", 500),
    "WD": ("白矮星", 40),
}

# 轨道区域 -> (中文名, 描述)
ORBITAL_ZONES = {
    "SCORCHED": ("灼热带", "离恒星太近，一切都在燃烧"),
    "HABITABLE": ("宜居带", "温度适宜，液态水的天堂"),
    "FRIGID": ("寒冷带", "远离恒星，一片冰封死寂"),
    "ABYSSAL": ("深空", "位于星系边缘的黑暗虚空"),
}

# 星球类型 -> (中文名, 基础稀有度, 适用区域)
PLANET_TYPES = {
    # --- 常见 ---
    "ROCKY": ("岩石行星", 5, ["SCORCHED", "HABITABLE", "FRIGID"]),
    "DESERT": ("沙漠世界", 10, ["SCORCHED", "HABITABLE"]),
    "GAS_GIANT": ("气态巨行星", 10, ["FRIGID", "ABYSSAL"]),
    "ICE_GIANT": ("冰巨行星", 20, ["FRIGID", "ABYSSAL"]),
    # --- 稀有 ---
    "VOLCANIC": ("火山行星", 25, ["SCORCHED"]),
    "TERRESTRIAL": ("类地行星", 40, ["HABITABLE"]),
    "OCEAN": ("海洋世界", 50, ["HABITABLE"]),
    "CARBON": ("碳行星", 60, ["SCORCHED", "FRIGID"]),
    # --- 史诗 ---
    "IRON": ("铁核行星", 100, ["SCORCHED"]),
    "ROGUE": ("流浪行星", 150, ["ABYSSAL"]),
    "GAIA": ("盖亚行星", 200, ["HABITABLE"]),
}

# 特质定义 (Trait Definitions)
# 格式: "TRAIT_ID": ("中文名", 稀有度加成, "描述", { 经济影响 })
# 经济影响: 
#   'jph_add': JPH 基础值加成
#   'jph_mult': JPH 乘数加成 (1.0 = 100% = 不变)
TRAIT_DEFINITIONS = {
    # --- 资源 (Resources) ---
    "RES_ZERO_POINT": ("零点能量场", 150, "从真空虚空中汲取无尽的能量。", {'jph_mult': 2.0}),
    "RES_HEAVY_MINERAL": ("超重力矿脉", 80, "富含超重元素，价值连城。", {'jph_add': 500}),
    "RES_DIAMOND_RAIN": ("钻石雨", 100, "大气中凝结出纯粹的碳晶体。", {'jph_add': 800}),
    "RES_HELIUM_3": ("氦-3富集", 60, "完美的聚变燃料来源。", {'jph_add': 300}),
    "RES_SPICE": ("异星香料", 200, "一种神秘的致幻物质，宇宙的硬通货。", {'jph_mult': 2.5}),
    "RES_ANTIMATTER": ("反物质喷泉", 500, "极其罕见且不稳定的能量源。", {'jph_mult': 5.0}),
    "RES_ADAMANTIUM": ("艾德曼合金矿", 300, "已知最坚硬的金属。", {'jph_add': 2000}),
    "RES_CRYONIUM": ("氪冰矿", 70, "一种在极低温下呈现超导特性的冰。", {'jph_add': 400}),
    
    # --- 生命 (Lifeforms) ---
    "LIFE_SILICON": ("硅基生命痕迹", 120, "在熔岩河中繁衍的晶体生物。", {'jph_add': 100}),
    "LIFE_SENTIENT_PLANT": ("感知植物群", 90, "覆盖全球的巨大真菌网络，拥有共同意识。", {'jph_add': 200}),
    "LIFE_GAS_WHALE": ("气态巨兽", 70, "在风暴中遨游的巨大生物。", {}),
    "LIFE_EXTREMEPHILE": ("极端微生物", 30, "在最恶劣环境中也能生存的细菌。", {}),
    "LIFE_PARADISE": ("生物天堂", 250, "一个未受干扰的、极其繁荣的生态系统。", {'jph_mult': 1.5}),
    "LIFE_KRAKEN": ("深海巨妖", 150, "潜伏在冰下海洋中的巨大捕食者。", {}),

    # --- 遗迹 (Artifacts) ---
    "ART_ANCIENT_RUINS": ("远古外星遗物", 100, "一个早已消亡的文明留下的城市废墟。", {}),
    "ART_SLEEPING_SHIP": ("休眠的星际飞船", 150, "一艘巨大的飞船，静静地等待着被唤醒。", {'jph_add': 500}),
    "ART_UNSTABLE_PORTAL": ("不稳定的传送门", 180, "一个通往未知维度、时开时关的裂隙。", {}),
    "ART_FORERUNNER_MAP": ("先行者星图", 220, "指向银河系中某个秘密位置的地图。", {}),
    "ART_WORLD_ENGINE": ("世界引擎", 400, "一个能改造星球气候的巨大机器。", {'jph_mult': 3.0}),
    "ART_DYSON_SPHERE_FRAG": ("戴森球残片", 300, "环绕恒星的巨大建筑的碎片。", {'jph_add': 1500}),
    "ART_ORACLE": ("神谕AI", 350, "一个古老的超级AI，能回答任何问题...但有代价。", {}),

    # --- 奇观 (Wonders) ---
    "WON_ETERNAL_STORM": ("永恒风暴", 80, "一场持续了数百万年的超级雷暴。", {}),
    "WON_NATURAL_PULSAR": ("天然脉冲星", 130, "星球的核心是一个小型脉冲星。", {'jph_add': 700}),
    "WON_SKY_MIRROR": ("天空之镜", 90, "地表被一层完美的液态金属覆盖。", {}),
    "WON_FLOATING_ISLES": ("悬浮岛屿", 110, "巨大的陆块因磁场异常而漂浮在空中。", {}),
    "WON_CRYSTAL_FOREST": ("水晶森林", 70, "整片大陆长满了巨大的硅晶体。", {}),
    "WON_TIME_ANOMALY": ("时间泡", 200, "一个时间流速异常的区域。", {}),
    "WON_GRAVITY_RIFT": ("重力裂隙", 140, "空间在此处扭曲，物理规则不再适用。", {}),

    # --- 灾难/无价值 (Duds) ---
    "DUD_HIGH_RADIATION": ("高强度辐射", -50, "致命的辐射让一切有价值的活动都无法进行。", {'jph_mult': 0.1}),
    "DUD_UNSTABLE_CRUST": ("不稳定地壳", -30, "星球随时可能分崩离析。", {'jph_mult': 0.5}),
    "DUD_TOXIC_ATMOS": ("剧毒大气", -20, "腐蚀性的气体笼罩着一切。", {'jph_mult': 0.8}),
    "DUD_ROGUE_ASTEROIDS": ("流氓小行星带", -10, "频繁的小行星撞击。", {}),
    "DUD_ANCIENT_PLAGUE": ("远古瘟疫", -100, "一种休眠的病毒，极其致命。", {'jph_mult': 0}),
    "DUD_VOID_ORGANISM": ("虚空生物", -150, "一个正在缓慢吞噬这颗星球的巨型实体。", {'jph_mult': 0}),
    "DUD_LOST_COLONY": ("失落的殖民地", 0, "你发现了...你自己祖先的飞船残骸。", {}),
    "DUD_NOTHING": ("一无所获", 0, "信号源似乎只是普通的自然现象。", {}),
    
    # --- 填充位 (使总数超过50) ---
    "RES_WATER_ICE": ("丰富的水冰", 10, "在寒冷地带很常见，但仍有价值。", {'jph_add': 50}),
    "RES_THOLINS": ("泰坦有机S", 20, "富含有机分子的粘稠物质。", {}),
    "LIFE_FUNGAL_WASTES": ("真菌荒原", 15, "地表被奇异的真菌覆盖。", {}),
    "WON_AURORA": ("强极光", 5, "美丽的宇宙景象。", {}),
    "WON_GIANT_VOLCANO": ("超级火山", 30, "一颗巨大的、休眠中的火山。", {}),
    "ART_CRASH_SITE": ("飞船坠毁点", 25, "一艘小型飞船的残骸。", {}),
    "DUD_BARREN": ("贫瘠之地", -5, "这颗星球...什么都没有。", {'jph_mult': 0.9}),
    "DUD_FALSE_ALARM": ("虚假警报", 0, "你的探测器出错了。", {}),
    "RES_SILICATES": ("硅酸盐岩石", 0, "最常见的岩石。", {}),
    "WON_DEEP_CANYON": ("大裂谷", 10, "一个几乎贯穿地壳的大裂谷。", {}),
    "LIFE_BACTERIA": ("细菌菌落", 5, "最简单的生命形式。", {}),
    "ART_SATELLITE": ("失控的人造卫星", 15, "一颗早期文明发射的卫星。", {}),
    "DUD_MAGNETIC_FIELD": ("异常磁场", -10, "干扰了所有设备。", {'jph_mult': 0.9}),
    "RES_METHANE_LAKE": ("甲烷湖", 20, "液态甲烷构成的湖泊。", {'jph_add': 100}),
}

# 异常信号定义 (Anomaly Definitions)
# 格式: "ANOMALY_ID": ("中文信号名", 稀有度加成, [ (TRAIT_ID, 权重), ... ])
ANOMALY_DEFINITIONS = {
    # --- T1 常见信号 ---
    "SIG_GEO_FLUX": ("地质通量", 20, [
        ("RES_WATER_ICE", 20), ("RES_SILICATES", 20), ("DUD_BARREN", 15), 
        ("DUD_UNSTABLE_CRUST", 10), ("WON_GIANT_VOLCANO", 10), ("RES_CRYONIUM", 5),
        ("RES_HEAVY_MINERAL", 5)
    ]),
    "SIG_WEAK_ENERGY": ("微弱能量读数", 25, [
        ("DUD_FALSE_ALARM", 30), ("WON_AURORA", 20), ("DUD_MAGNETIC_FIELD", 20),
        ("ART_SATELLITE", 10), ("ART_CRASH_SITE", 10), ("RES_HELIUM_3", 5)
    ]),
    "SIG_FAINT_BIO": ("模糊的生命信号", 30, [
        ("DUD_NOTHING", 30), ("LIFE_BACTERIA", 25), ("LIFE_EXTREMEPHILE", 15),
        ("LIFE_FUNGAL_WASTES", 10), ("RES_THOLINS", 10), ("LIFE_SENTIENT_PLANT", 5)
    ]),
    
    # --- T2 稀有信号 ---
    "SIG_HIGH_ENERGY": ("高频能量读数", 80, [
        ("DUD_HIGH_RADIATION", 20), ("WON_NATURAL_PULSAR", 15), ("ART_UNSTABLE_PORTAL", 10),
        ("RES_ZERO_POINT", 5), ("RES_ANTIMATTER", 1)
    ]),
    "SIG_COMPLEX_STRUCTURE": ("复杂结构回波", 100, [
        ("ART_CRASH_SITE", 20), ("DUD_LOST_COLONY", 15), ("ART_ANCIENT_RUINS", 15),
        ("ART_SLEEPING_SHIP", 10), ("ART_FORERUNNER_MAP", 5), ("ART_WORLD_ENGINE", 2)
    ]),
    "SIG_DEEP_SCAN": ("深层回音", 70, [
        ("WON_DEEP_CANYON", 20), ("RES_HEAVY_MINERAL", 15), ("DUD_UNSTABLE_CRUST", 15),
        ("RES_DIAMOND_RAIN", 10), ("LIFE_SILICON", 10), ("RES_ADAMANTIUM", 5)
    ]),
    "SIG_OCEANIC_ANOMALY": ("海洋异常", 90, [
        ("LIFE_KRAKEN", 15), ("RES_WATER_ICE", 20), ("RES_METHANE_LAKE", 15),
        ("LIFE_PARADISE", 5), ("DUD_ANCIENT_PLAGUE", 5)
    ]),

    # --- T3 史诗信号 ---
    "SIG_RHYTHMIC_PULSE": ("有节律的电磁脉冲", 150, [
        ("WON_NATURAL_PULSAR", 20), ("ART_SLEEPING_SHIP", 15), ("LIFE_SENTIENT_PLANT", 15),
        ("ART_ORACLE", 5), ("ART_DYSON_SPHERE_FRAG", 2)
    ]),
    "SIG_PLANET_WIDE": ("全球范围异常", 200, [
        ("LIFE_PARADISE", 15), ("DUD_ANCIENT_PLAGUE", 10), ("WON_ETERNAL_STORM", 15),
        ("WON_SKY_MIRROR", 10), ("DUD_VOID_ORGANISM", 5), ("RES_SPICE", 5)
    ]),
}


class PlanetHandler(NFTLogicHandler):
    """
    “星球” NFT 的逻辑处理器 (V3 - 资源产出版)。
    """
    @classmethod
    def get_harvest_cooldown_info(cls, nft_data: dict) -> (bool, int):
        """(新增) 检查收获冷却状态"""
        cooldown = PLANET_ECONOMICS['HARVEST_COOLDOWN_SECONDS']
        last_harvest = nft_data.get('last_harvest_time', 0)
        time_left = (last_harvest + cooldown) - time.time()
        if time_left <= 0:
            return True, 0
        return False, int(time_left)

    @classmethod
    def get_accumulated_jph(cls, nft_data: dict) -> float:
        """(新增) 计算当前累积的 JPH，无论是否在冷却中"""
        econ_stats = nft_data.get('economic_stats', {})
        total_jph = econ_stats.get('total_jph', 0)
        if total_jph <= 0: return 0.0

        last_harvest = nft_data.get('last_harvest_time', 0)
        seconds_passed = time.time() - last_harvest

        # 限制在最大累积时间内
        max_accrual_seconds = PLANET_ECONOMICS['HARVEST_MAX_ACCRUAL_HOURS'] * 3600
        seconds_to_harvest = min(seconds_passed, max_accrual_seconds)

        jcoin_produced = (seconds_to_harvest / 3600.0) * total_jph
        return round(jcoin_produced, 6)
    @classmethod
    def get_display_name(cls) -> str:
        return "星球"

    def _recalculate_stats(self, planet_data: dict) -> dict:
        """
        (核心辅助函数) 根据已解锁特质，重新计算星球的稀有度和JPH。
        """
        base_rarity = planet_data.get('rarity_score', {}).get('base', 10)
        base_jph = planet_data.get('economic_stats', {}).get('base_jph', 0)
        
        total_trait_rarity = 0
        jph_add_bonus = 0.0
        jph_mult_bonus = 1.0
        
        for trait_id in planet_data.get('unlocked_traits', []):
            trait = TRAIT_DEFINITIONS.get(trait_id)
            if trait:
                total_trait_rarity += trait[1]
                effects = trait[3]
                jph_add_bonus += effects.get('jph_add', 0.0)
                jph_mult_bonus *= effects.get('jph_mult', 1.0)
        
        # 更新稀有度
        planet_data['rarity_score']['traits'] = total_trait_rarity
        planet_data['rarity_score']['total'] = base_rarity + total_trait_rarity
        
        # 更新JPH
        # 公式: (基础JPH + 累加JPH) * 乘数JPH
        planet_data['economic_stats']['total_jph'] = (base_jph + jph_add_bonus) * jph_mult_bonus
        
        return planet_data

    def _generate_planet_data(self, owner_key: str, owner_username: str) -> dict:
        """ 内部辅助函数：逻辑化地生成一颗随机星球的数据 (V3) """
        
        # --- 1. 生成星系坐标和恒星 ---
        galactic_coord = f"G-{random.randint(100,999)}X-{random.randint(100,999)}Y-{random.randint(100,999)}Z"
        star_type_key = random.choices(list(STAR_CLASSES.keys()), weights=[30, 20, 15, 10, 5, 3, 1, 1, 0.5, 5], k=1)[0]
        star_info = STAR_CLASSES[star_type_key]

        # --- 2. 决定轨道区域 ---
        zone_weights = {"SCORCHED": 20, "HABITABLE": 30, "FRIGID": 30, "ABYSSAL": 20}
        if star_type_key in ['O', 'B', 'A']:
            zone_weights = {"SCORCHED": 70, "HABITABLE": 20, "FRIGID": 10, "ABYSSAL": 0}
        elif star_type_key == 'M':
            zone_weights = {"SCORCHED": 5, "HABITABLE": 15, "FRIGID": 50, "ABYSSAL": 30}
        elif star_type_key in ['N', 'BH', 'WD']:
             zone_weights = {"SCORCHED": 10, "HABITABLE": 5, "FRIGID": 35, "ABYSSAL": 50}
        zone_key = random.choices(list(zone_weights.keys()), weights=list(zone_weights.values()), k=1)[0]

        # --- 3. 决定星球类型 ---
        possible_planets = [pt for pt, attr in PLANET_TYPES.items() if zone_key in attr[2]]
        if not possible_planets: # 备用，防止区域中没有行星
            possible_planets = ["ROCKY"]
        planet_type_key = random.choice(possible_planets)
        planet_info = PLANET_TYPES[planet_type_key]

        # --- 4. 计算基础稀有度和JPH ---
        base_rarity = star_info[1] + planet_info[1]
        base_jph = PLANET_ECONOMICS['BASE_JCOIN_PER_HOUR']
        
        # 宜居带的行星有基础JPH加成
        if zone_key == 'HABITABLE':
            base_jph *= 1.5
        # 特殊星系有基础JPH加成
        if star_type_key in ['N', 'BH']:
            base_jph *= 2.0

        # --- 5. 生成异常信号 (决定了星球的“潜力”) ---
        anomalies_list = []
        num_anomalies = random.choices([0, 1, 2, 3], weights=[30, 40, 25, 5], k=1)[0]
        if num_anomalies > 0:
            weights = [v[1] for v in ANOMALY_DEFINITIONS.values()] # Use rarity as weight
            anomalies_list = random.choices(list(ANOMALY_DEFINITIONS.keys()), weights=weights, k=num_anomalies)

        # --- 6. 组装数据 ---
        planet_data = {
            "planet_id": str(uuid.uuid4()),
            "galactic_coordinates": galactic_coord,
            "discovered_by_key": owner_key,
            "discovered_by_username": owner_username,
            "discovery_timestamp": time.time(),
            "custom_name": None,

            "stellar_class": star_info[0],
            "orbital_zone": ORBITAL_ZONES[zone_key][0],
            "planet_type": planet_info[0],
            "radius_km": random.randint(1000, 90000),

            "anomalies": anomalies_list, # 未解析的异常信号
            "unlocked_traits": [],       # 已揭示的特质
            
            # --- 经济和稀有度数据 ---
            "rarity_score": {
                "base": base_rarity,
                "traits": 0,
                "total": base_rarity
            },
            "economic_stats": {
                "base_jph": base_jph,
                "total_jph": base_jph # 初始JPH等于基础JPH
            },
            "last_harvest_time": time.time() # 初始丰收时间
        }
        
        # 初始计算 (虽然没有特质，但保持流程一致)
        return self._recalculate_stats(planet_data)


    @classmethod
    def get_economic_config_and_valuation(cls) -> dict:
        """
        (V3 新增 - 满足需求 4)
        返回经济配置，以及一个用于计算星球估值的函数。
        """
        
        def calculate_value(nft_data: dict) -> float:
            """
            根据配置计算星球的参考估值。
            估值 = 基础价值 + 稀有度价值 + 产出价值
            """
            try:
                rarity = nft_data.get('rarity_score', {}).get('total', 0)
                jph = nft_data.get('economic_stats', {}).get('total_jph', 0)
                
                # 1. 基础价值
                value = PLANET_ECONOMICS['VALUE_BASE_FLAT']
                
                # 2. 稀有度价值 (负稀有度会降低价值)
                value += rarity * PLANET_ECONOMICS['VALUE_RARITY_FACTOR']
                
                # 3. JPH 价值 (产出价值)
                value += jph * PLANET_ECONOMICS['VALUE_JPH_FACTOR']
                
                # 确保价值不会低于0
                return max(0.01, round(value, 2))
            except Exception:
                return 0.01 # 估值失败
        
        return {
            "config": PLANET_ECONOMICS,
            "calculate_value_func": calculate_value
        }

    # --- 框架核心实现 ---

    @classmethod
    def execute_shop_action(cls, owner_key: str, owner_username: str, data: dict, conn) -> (bool, str, str):
        """
        (V3 修改) 处理“探索星空”动作。
        """
        cost = PLANET_ECONOMICS['EXPLORE_COST']
        prob = PLANET_ECONOMICS['EXPLORE_PROBABILITY_OF_DISCOVERY']
        
        if random.random() < prob:
            # 成功发现！
            planet_data = cls()._generate_planet_data(owner_key, owner_username)
            success, detail, nft_id = queries_nft.mint_nft(
                owner_key=owner_key, nft_type="PLANET", data=planet_data, conn=conn
            )
            if not success: return False, f"发现星球但铸造失败: {detail}", None
            
            rarity = planet_data['rarity_score']['total']
            jph = planet_data['economic_stats']['total_jph']
            msg = f"恭喜！你发现了一颗行星！(稀有度: {rarity}, 产出: {jph:.2f} JPH)"
            return True, msg, nft_id
        else:
            # 探索失败
            return True, "信号消失在深空中... 什么也没有发现。再试一次吧！", None

    def mint(self, owner_key: str, data: dict, owner_username: str = None) -> (bool, str, dict):
        """(V3 修改) 管理员铸造，支持自定义覆盖"""
        db_data = self._generate_planet_data(owner_key, owner_username or "管理员")
        
        # 允许管理员覆盖特定字段
        if 'custom_name' in data: db_data['custom_name'] = data['custom_name']
        if 'rarity_score' in data: db_data['rarity_score'] = data['rarity_score']
        if 'economic_stats' in data: db_data['economic_stats'] = data['economic_stats']
        
        # 重新计算以确保一致性
        db_data = self._recalculate_stats(db_data)
        
        return True, "管理员成功创建了一颗人造行星。", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        if nft.get('owner_key') != requester_key:
            return False, "你不是这颗星球的所有者"

        if action == 'rename':
            new_name = action_data.get('new_name')
            if not new_name or len(new_name) < 2 or len(new_name) > 30:
                return False, "新的星球名称必须在 2 到 30 个字符之间"
            return True, "可以重命名"

        if action == 'scan':
            anomaly_to_scan = action_data.get('anomaly')
            if not anomaly_to_scan:
                return False, "必须指定要扫描的异常信号"
            if anomaly_to_scan not in nft.get('data', {}).get('anomalies', []):
                return False, "该异常信号不存在或已被扫描"
            # 成本检查由 routes_nft.py 处理
            return True, "可以进行深度扫描"

        if action == 'harvest':
            nft_data = nft.get('data', {})
            econ_stats = nft_data.get('economic_stats', {})
            
            if econ_stats.get('total_jph', 0) <= 0:
                return False, "这颗贫瘠的星球不产出任何资源"
            
            last_harvest = nft_data.get('last_harvest_time', 0)
            cooldown = PLANET_ECONOMICS['HARVEST_COOLDOWN_SECONDS']
            
            if time.time() < (last_harvest + cooldown):
                time_left = int((last_harvest + cooldown) - time.time())
                return False, f"资源正在再生中，剩余冷却时间: {time_left // 60} 分钟 {time_left % 60} 秒"
            
            return True, "可以丰收"

        return super().validate_action(nft, action, action_data, requester_key)

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str, conn=None) -> (bool, str, dict): # <<< (1) 新增 conn=None
        updated_data = nft['data'].copy()

        if action == 'rename':
            new_name = action_data.get('new_name')
            updated_data['custom_name'] = new_name
            return True, f"星球已成功命名为: {new_name}", updated_data
        
        if action == 'scan':
            anomaly_to_scan = action_data.get('anomaly')
            
            # --- 解析异常信号 ---
            anomaly_details = ANOMALY_DEFINITIONS.get(anomaly_to_scan)
            if not anomaly_details:
                return False, "内部错误：找不到异常信号定义", {}
            
            possible_outcomes = anomaly_details[2]
            trait_ids = [t[0] for t in possible_outcomes]
            weights = [t[1] for t in possible_outcomes]
            
            # 随机选择一个特质
            discovered_trait_id = random.choices(trait_ids, weights=weights, k=1)[0]
            discovered_trait_info = TRAIT_DEFINITIONS.get(discovered_trait_id)

            if not discovered_trait_info:
                 return False, "内部错误：找不到特质定义", {}
            
            trait_name, trait_rarity, trait_desc, _ = discovered_trait_info

            # --- 更新数据 (核心) ---
            updated_data['anomalies'].remove(anomaly_to_scan) # 消耗信号
            
            if discovered_trait_id != "DUD_NOTHING" and discovered_trait_id != "DUD_FALSE_ALARM":
                updated_data['unlocked_traits'].append(discovered_trait_id)
                # 重新计算整个星球的属性
                updated_data = self._recalculate_stats(updated_data)
                
                msg = f"扫描完成！你发现了: **{trait_name}**！({trait_desc}) "
                if trait_rarity > 0:
                    msg += "星球稀有度已提升！"
                elif trait_rarity < 0:
                    msg += "这是一个...不幸的发现。"
                return True, msg, updated_data
            else:
                return True, f"扫描完成...信号源似乎只是普通的自然现象: {trait_name}。", updated_data
        
        if action == 'harvest':
            econ_stats = updated_data.get('economic_stats', {})
            total_jph = econ_stats.get('total_jph', 0)
            last_harvest = updated_data.get('last_harvest_time', 0)
            
            seconds_passed = time.time() - last_harvest
            max_accrual_seconds = PLANET_ECONOMICS['HARVEST_MAX_ACCRUAL_HOURS'] * 3600
            
            # 限制在最大累积时间内
            seconds_to_harvest = min(seconds_passed, max_accrual_seconds)
            
            # (V3 修正) 只有在冷却时间过后才能收获
            if seconds_passed < PLANET_ECONOMICS['HARVEST_COOLDOWN_SECONDS']:
                 return False, "冷却时间未到", {} # 理论上 validate 会阻止

            # JPH 是每小时，所以要除以 3600
            jcoin_produced = (seconds_to_harvest / 3600.0) * total_jph
            
            if jcoin_produced <= 0:
                return False, "产出为0，无法丰收", {}
                
            updated_data['last_harvest_time'] = time.time()
            
            # --- (V3 核心) 使用特殊键传回产出 ---
            updated_data['__jcoin_produced__'] = round(jcoin_produced, 4)
            
            return True, f"丰收成功！你从星球收集了 {jcoin_produced:.4f} JCoin。", updated_data

        return super().perform_action(nft, action, action_data, requester_key, conn) # <<< (2) 传递 conn

    @classmethod
    def get_shop_config(cls) -> dict:
        """(V3 修改) 使用经济配置"""
        cost = PLANET_ECONOMICS['EXPLORE_COST']
        prob = PLANET_ECONOMICS['EXPLORE_PROBABILITY_OF_DISCOVERY']
        return {
            "creatable": True,
            "cost": cost,
            "name": "探索星空",
            "action_type": "probabilistic_mint", # 触发 execute_shop_action
            "action_label": f"支付 {cost} FC 并发射探测器",
            # +++ 核心修改: 替换这里的描述 +++
            "description": f"踏入未知的星云，你将花费 {cost} FC 启动一枚高精度恒星探测器。这是一场高风险的宇宙赌博：它有 {prob*100:.0f}% 的概率为你发现一颗拥有独特坐标和未知潜力的行星！",
            # +++ 修改结束 +++
            "fields": []
        }
        
    def get_trade_description(self, nft: dict) -> str:
        """(V3 修改) 显示稀有度和JPH"""
        data = nft.get('data', {})
        name = data.get('custom_name') or f"行星 {data.get('planet_id', '???')[:6]}"
        rarity = data.get('rarity_score', {}).get('total', 0)
        jph = data.get('economic_stats', {}).get('total_jph', 0)
        
        jph_str = f" | 💰 {jph:.2f} JPH" if jph > 0 else ""
        return f"行星: {name} [稀有度: {rarity}]{jph_str}"
        
    @classmethod
    def get_admin_mint_config(cls) -> dict:
        """为管理员铸造表单提供帮助信息和默认数据。"""
        return {
            "help_text": '对于“星球”，管理员可以直接铸造。留空 {} 以完全随机，或提供 {"custom_name": "Tatooine"} 等字段覆盖。',
            "default_json": '{\n  "custom_name": "New Earth"\n}'
        }