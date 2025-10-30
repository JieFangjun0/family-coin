# backend/nft_logic/planet.py

import random
import time
import uuid
from .base import NFTLogicHandler
from backend import ledger
# --- 扩展的世界观设定 ---

# 恒星等级 -> (中文名, 基础稀有度)
STAR_CLASSES = {
    "M": ("M级 (红矮星)", 5),
    "K": ("K级 (橙矮星)", 10),
    "G": ("G级 (黄矮星)", 20),
    "F": ("F级 (白星)", 35),
    "A": ("A级 (蓝白星)", 50),
    "B": ("B级 (蓝巨星)", 70),
    "O": ("O级 (蓝超巨星)", 100)
}

# 轨道区域 -> (中文名, 描述)
ORBITAL_ZONES = {
    "SCORCHED": ("灼热带", "离恒星太近，一切都在燃烧"),
    "HABITABLE": ("宜居带", "温度适宜，液态水的天堂"),
    "FRIGID": ("寒冷带", "远离恒星，一片冰封死寂")
}

# 星球类型 -> (中文名, 基础稀有度, 适用区域)
PLANET_TYPES = {
    "VOLCANIC": ("火山行星", 15, ["SCORCHED"]),
    "TERRESTRIAL": ("类地行星", 30, ["HABITABLE"]),
    "OCEAN": ("海洋世界", 50, ["HABITABLE"]),
    "GAS_GIANT": ("气态巨行星", 10, ["FRIGID"]),
    "ICE_GIANT": ("冰巨行星", 20, ["FRIGID"]),
    "DESERT": ("沙漠世界", 10, ["SCORCHED", "HABITABLE"]),
    "CARBON": ("碳行星", 60, ["SCORCHED", "FRIGID"])
}

# 异常信号 -> (信号描述, 解析后的可能特质, 基础稀有度加成)
# "None" 表示可能一无所获
ANOMALIES = {
    "GEO_ACTIVITY": ("异常地质活动", ["零点能量场", "超重力矿脉", None, None], 50),
    "HIGH_ENERGY": ("高频能量读数", ["远古外星遗物", "不稳定的传送门", None], 100),
    "BIO_SIGN": ("微弱的生命信号", ["感知植物群", "硅基生命痕迹", None, None, None], 80),
    "RHYTHMIC_PULSE": ("有节律的电磁脉冲", ["休眠的星际飞船", "天然脉冲星", None], 120)
}

class PlanetHandler(NFTLogicHandler):
    """
    “星球” NFT 的逻辑处理器 (V2 - 深度探索版)。
    """
    @classmethod
    def get_display_name(cls) -> str:
        return "星球"
    def _generate_planet_data(self, owner_key: str, owner_username: str) -> dict:
        """ 内部辅助函数：逻辑化地生成一颗随机星球的数据 """
        
        # --- 1. 生成星系坐标和恒星 ---
        galactic_coord = f"G-{random.randint(100,999)}X-{random.randint(100,999)}Y-{random.randint(100,999)}Z"
        star_type_key = random.choices(list(STAR_CLASSES.keys()), weights=[30, 25, 20, 15, 7, 2, 1], k=1)[0]
        star_info = STAR_CLASSES[star_type_key]

        # --- 2. 决定轨道区域 ---
        zone_weights = {"SCORCHED": 20, "HABITABLE": 40, "FRIGID": 40} # G, K, F 型星的默认权重
        if star_type_key in ['O', 'B', 'A']:
            zone_weights = {"SCORCHED": 70, "HABITABLE": 25, "FRIGID": 5}
        elif star_type_key == 'M':
            zone_weights = {"SCORCHED": 5, "HABITABLE": 25, "FRIGID": 70}
        zone_key = random.choices(list(zone_weights.keys()), weights=list(zone_weights.values()), k=1)[0]

        # --- 3. 决定星球类型 ---
        possible_planets = [pt for pt, attr in PLANET_TYPES.items() if zone_key in attr[2]]
        planet_type_key = random.choice(possible_planets)
        planet_info = PLANET_TYPES[planet_type_key]

        # --- 4. 计算基础稀有度 ---
        base_rarity = star_info[1] + planet_info[1]
        
        # --- 5. 生成异常信号 (决定了星球的“潜力”) ---
        anomalies_list = []
        num_anomalies = random.choices([0, 1, 2], weights=[40, 50, 10], k=1)[0]
        if num_anomalies > 0:
            anomalies_list = random.sample(list(ANOMALIES.keys()), k=num_anomalies)

        return {
            "planet_id": str(uuid.uuid4()),
            "galactic_coordinates": galactic_coord,
            "discovered_by_key": owner_key,
            "discovered_by_username": owner_username,
            "discovery_timestamp": time.time(),
            "custom_name": None,

            "stellar_class": star_info[0],
            "orbital_zone": ORBITAL_ZONES[zone_key][0],
            "planet_type": planet_info[0],
            "radius_km": random.randint(2000, 70000),

            "anomalies": anomalies_list, # 未解析的异常信号
            "unlocked_traits": [],       # 已揭示的特质
            
            "rarity_score": {
                "base": base_rarity,
                "traits": 0,
                "total": base_rarity
            }
        }

    # --- 框架核心实现 ---

    @classmethod
    def execute_shop_action(cls, owner_key: str, owner_username: str, data: dict, conn) -> (bool, str, str):
        PROBABILITY_OF_DISCOVERY = 0.15 # 提高一点发现概率
        
        if random.random() < PROBABILITY_OF_DISCOVERY:
            planet_data = cls()._generate_planet_data(owner_key, owner_username)
            success, detail, nft_id = ledger.mint_nft(
                owner_key=owner_key, nft_type="PLANET", data=planet_data, conn=conn
            )
            if not success: return False, f"发现星球但铸造失败: {detail}", None
            return True, f"恭喜！你发现了一颗新的行星！坐标: {planet_data['galactic_coordinates']}", nft_id
        else:
            return True, "信号消失在深空中... 什么也没有发现。再试一次吧！", None

    def mint(self, owner_key: str, data: dict, owner_username: str = None) -> (bool, str, dict):
        db_data = self._generate_planet_data(owner_key, owner_username or "管理员")
        if 'custom_name' in data: db_data['custom_name'] = data['custom_name']
        return True, "管理员成功创建了一颗人造行星。", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        if nft.get('owner_key') != requester_key:
            return False, "你不是这颗星球的所有者"

        if action == 'rename':
            new_name = action_data.get('new_name')
            if not new_name or len(new_name) < 2 or len(new_name) > 20:
                return False, "新的星球名称必须在 2 到 20 个字符之间"
            return True, "可以重命名"

        if action == 'scan':
            anomaly_to_scan = action_data.get('anomaly')
            if not anomaly_to_scan:
                return False, "必须指定要扫描的异常信号"
            if anomaly_to_scan not in nft.get('data', {}).get('anomalies', []):
                return False, "该异常信号不存在或已被扫描"
            return True, "可以进行深度扫描"

        return super().validate_action(nft, action, action_data, requester_key)

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str, dict):
        updated_data = nft['data'].copy()

        if action == 'rename':
            new_name = action_data.get('new_name')
            updated_data['custom_name'] = new_name
            return True, f"星球已成功命名为: {new_name}", updated_data
        
        if action == 'scan':
            anomaly_to_scan = action_data.get('anomaly')
            
            # --- 解析异常信号 ---
            anomaly_details = ANOMALIES[anomaly_to_scan]
            possible_outcomes = anomaly_details[1]
            trait_rarity_bonus = anomaly_details[2]
            
            discovered_trait = random.choice(possible_outcomes)
            
            # --- 更新数据 (核心) ---
            updated_data['anomalies'].remove(anomaly_to_scan)
            
            if discovered_trait:
                updated_data['unlocked_traits'].append(discovered_trait)
                updated_data['rarity_score']['traits'] += trait_rarity_bonus
                updated_data['rarity_score']['total'] = updated_data['rarity_score']['base'] + updated_data['rarity_score']['traits']
                return True, f"扫描完成！你发现了惊人的特质: **{discovered_trait}**！星球稀有度大幅提升！", updated_data
            else:
                return True, "扫描完成...信号源似乎只是普通的自然现象，没有发现任何特殊之处。", updated_data

        return super().perform_action(nft, action, action_data, requester_key)

    @classmethod
    def get_shop_config(cls) -> dict:
        return {
            "creatable": True, "cost": 10.0, "name": "探索星空",
            "action_type": "probabilistic_mint", "action_label": "支付并发射探测器",
            "description": "花费 10 FC 向未知深空发射一枚恒星探测器。它有一定概率为你发现一颗拥有独特坐标和未知潜力的行星！",
            "fields": []
        }
        
    def get_trade_description(self, nft: dict) -> str:
        data = nft.get('data', {})
        name = data.get('custom_name') or f"行星 {data.get('planet_id', '???')[:6]}"
        rarity = data.get('rarity_score', {}).get('total', 0)
        num_anomalies = len(data.get('anomalies', []))
        anomaly_str = f" | {num_anomalies}个未探明信号" if num_anomalies > 0 else ""
        return f"行星: {name} [稀有度: {rarity}]{anomaly_str}"