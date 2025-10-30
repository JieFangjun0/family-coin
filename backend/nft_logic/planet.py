# backend/nft_logic/planet.py

import random
import time
import uuid
from .base import NFTLogicHandler
from backend import ledger # 引入 ledger 以便在动作中调用 mint_nft

# --- 静态数据，用于生成星球 ---
STAR_CLASSES_CN = ["M级 (红矮星)", "K级 (橙矮星)", "G级 (黄矮星)", "F级 (白星)", "A级 (蓝白星)", "B级 (蓝巨星)", "O级 (蓝超巨星)"]
PLANET_TYPES_CN = ["类地行星", "气态巨行星", "冰巨行星", "海洋世界", "火山行星", "碳行星", "沙漠世界"]
ATMOSPHERES_CN = ["氮氧大气", "二氧化碳大气", "富甲烷大气", "氢氦大气", "氨气大气", "无大气层"]
RARE_RESOURCES_CN = ["晶格结构", "奇异气体", "感知植物群", "远古外星遗物", "零点能量场"]

class PlanetHandler(NFTLogicHandler):
    """
    “星球” NFT 的逻辑处理器。
    这是一个通过概率性商店动作获得的 NFT。
    """
    
    def _generate_planet_data(self, owner_key: str, owner_username: str) -> dict:
        """ 内部辅助函数：生成一颗随机星球的数据 """
        
        rarity_score = random.randint(1, 100)
        has_rings = random.random() < 0.2  # 20% 概率有行星环
        has_life = random.random() < 0.05 # 5% 概率有生命
        has_rare_resource = random.random() < 0.02 # 2% 概率有稀有资源
        
        if has_rare_resource: rarity_score += 150
        if has_life: rarity_score += 100
        if has_rings: rarity_score += 20
        
        return {
            "planet_id": str(uuid.uuid4()),
            "discovered_by_key": owner_key,
            "discovered_by_username": owner_username,
            "discovery_timestamp": time.time(),
            "custom_name": None, # 允许用户命名
            "is_showcased": False, # 是否在个人主页展示
            
            # 物理属性
            "stellar_class": random.choice(STAR_CLASSES_CN),
            "planet_type": random.choice(PLANET_TYPES_CN),
            "atmosphere_composition": random.choice(ATMOSPHERES_CN),
            "radius_km": random.randint(2000, 70000),
            "surface_gravity_g": round(random.uniform(0.5, 3.5), 2),
            
            # 稀有属性
            "has_rings": has_rings,
            "biotic_presence": has_life,
            "rare_resource": random.choice(RARE_RESOURCES_CN) if has_rare_resource else None,
            
            # 综合评分
            "rarity_score": rarity_score,
        }

    # --- 框架核心实现 ---

    @classmethod
    def execute_shop_action(cls, owner_key: str, owner_username: str, data: dict, conn) -> (bool, str, str):
        """
        处理“探索星空”动作。
        """
        PROBABILITY_OF_DISCOVERY = 0.1 # 10% 的发现概率
        
        if random.random() < PROBABILITY_OF_DISCOVERY:
            # 成功发现星球！
            planet_data = cls()._generate_planet_data(owner_key, owner_username)
            
            # 使用 ledger 提供的底层函数在当前事务中铸造 NFT
            success, detail, nft_id = ledger.mint_nft(
                owner_key=owner_key,
                nft_type="PLANET",
                data=planet_data,
                conn=conn
            )
            
            if not success:
                return False, f"发现星球但铸造失败: {detail}", None
                
            return True, f"恭喜！你发现了一颗新的行星！稀有度: {planet_data['rarity_score']}", nft_id
        else:
            # 什么都没发现，这是一个“成功”的业务结果，而不是一个系统错误。
            # 我们返回 True，这样后端主程序就会提交交易（扣款），并将这条消息正常返回给用户。
            return True, "信号消失在深空中... 什么也没有发现。再试一次吧！", None

    def mint(self, owner_key: str, data: dict, owner_username: str = None) -> (bool, str, dict):
        """
        (供管理员使用) 直接铸造一颗星球。
        """
        db_data = self._generate_planet_data(owner_key, owner_username or "管理员")
        # 管理员可以直接覆盖部分数据
        if 'rarity_score' in data:
            db_data['rarity_score'] = data['rarity_score']
        if 'custom_name' in data:
            db_data['custom_name'] = data['custom_name']
        
        return True, "管理员成功创建了一颗人造行星。", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        """
        验证命名、设为展品等操作。
        """
        if nft.get('owner_key') != requester_key:
            return False, "你不是这颗星球的所有者"

        if action == 'rename':
            new_name = action_data.get('new_name')
            if not new_name or len(new_name) < 2 or len(new_name) > 20:
                return False, "新的星球名称必须在 2 到 20 个字符之间"
            return True, "可以重命名"
        
        if action == 'toggle_showcase':
            return True, "可以设置展品状态"

        # 兼容基类的通用销毁
        return super().validate_action(nft, action, action_data, requester_key)

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str, dict):
        """
        执行命名、设为展品等操作。
        """
        updated_data = nft['data'].copy()

        if action == 'rename':
            new_name = action_data.get('new_name')
            updated_data['custom_name'] = new_name
            return True, f"星球已成功命名为: {new_name}", updated_data
        
        if action == 'toggle_showcase':
            current_status = updated_data.get('is_showcased', False)
            updated_data['is_showcased'] = not current_status
            status_text = "公开展示" if not current_status else "取消展示"
            return True, f"星球已设为 {status_text}", updated_data
            
        # 兼容基类的通用销毁
        return super().perform_action(nft, action, action_data, requester_key)

    @classmethod
    def get_shop_config(cls) -> dict:
        return {
            "creatable": True,
            "cost": 10.0,
            "name": "探索星空",
            "action_type": "probabilistic_mint", # 使用我们新的动作类型
            "action_label": "支付并发射探测器",
            "description": "花费 10 FC 向未知深空发射一枚恒星探测器。绝大多数时候它会一去不复返，但偶尔，它会为你发现一颗独一无二的行星！",
            "fields": [] # 不需要用户输入任何字段
        }
        
    def get_trade_description(self, nft: dict) -> str:
        data = nft.get('data', {})
        name = data.get('custom_name') or f"行星 {data.get('planet_id', '???')[:6]}"
        rarity = data.get('rarity_score', 0)
        planet_type = data.get('planet_type', '未知类型')
        return f"行星: {name} [{planet_type}] | 稀有度: {rarity}"