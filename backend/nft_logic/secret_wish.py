# backend/nft_logic/secret_wish.py

import time
import uuid
from .base import NFTLogicHandler
from datetime import datetime

class SecretWishHandler(NFTLogicHandler):
    """
    “秘密愿望” NFT 的逻辑处理器。
    每个NFT都是一条被封存的信息，拥有一个公开的描述和私密的愿望内容。
    它会在指定的时间后自动“消失”（前端将不再显示其内容）。
    """

    def mint(self, owner_key: str, data: dict) -> (bool, str, dict):
        """
        铸造一个新的“秘密愿望”。
        管理员需要提供:
        - description (str): 对这个愿望的公开描述，所有人可见。
        - content (str): 愿望的秘密内容，仅所有者可见。
        - destroy_in_days (float): 多少天后愿望将消失 (可以带小数, e.g., 0.5代表12小时)。
        """
        description = data.get('description')
        content = data.get('content')
        destroy_in_days = data.get('destroy_in_days')

        # --- 数据校验 ---
        if not all([description, content, isinstance(destroy_in_days, (int, float))]):
            return False, "必须提供 'description'(公开描述), 'content'(秘密内容), 和 'destroy_in_days'(销毁天数)", {}

        # 允许设置最短1分钟的销毁时间，最长365天
        min_seconds = 60
        max_seconds = 365 * 24 * 60 * 60
        destroy_duration_seconds = destroy_in_days * 24 * 60 * 60

        if not (min_seconds <= destroy_duration_seconds <= max_seconds):
            return False, f"销毁天数换算后必须在 {min_seconds/60} 分钟到 {max_seconds/(24*60*60)} 天之间", {}

        # --- 计算核心数据 ---
        creation_timestamp = time.time()
        destroy_timestamp = creation_timestamp + destroy_duration_seconds
        
        # --- 构建存入数据库的 data 字典 ---
        db_data = {
            "wish_id": str(uuid.uuid4()), # 确保唯一性
            "creation_timestamp": creation_timestamp,
            "destroy_timestamp": destroy_timestamp,
            "description": description,
            "content": content, # 秘密内容被加密存储（此处为简化，实际生产可增加加密步骤）
            "is_destroyed": False # 这是一个状态位，但主要逻辑由前端时间戳判断驱动
        }
        return True, "一个新的愿望已被悄然封存。", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        """
        秘密愿望没有任何主动操作。所有者默认就能看到内容。
        """
        return False, "“秘密愿望”不支持任何主动操作。"

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str, dict):
        """
        执行操作的逻辑。由于不支持任何操作，直接返回失败。
        """
        return False, "内部错误：不应执行任何操作", {}
    
    # <<< 新增功能: 实现商店配置接口 >>>
    @classmethod
    def get_shop_config(cls) -> dict:
        return {
            "creatable": True,
            "cost": 5.0,  # 创建一个“秘密愿望”需要花费 5 FC
            "name": "秘密愿望",
            "description": "支付 5 FC 来封存一个秘密或愿望。它将完全属于你，直到在设定的时间后悄然消失。",
            "fields": [
                {
                    "name": "description", 
                    "label": "愿望的公开描述", 
                    "type": "text_input", 
                    "required": True,
                    "help": "这段话所有人都能在商店看到，例如 '一个关于未来的小小预测'"
                },
                {
                    "name": "content", 
                    "label": "愿望的秘密内容", 
                    "type": "text_area", 
                    "required": True,
                    "help": "这段话只有你和未来的自己能看到"
                },
                {
                    "name": "destroy_in_days", 
                    "label": "多少天后消失 (0.001 - 365)", 
                    "type": "number_input", 
                    "required": True, 
                    "default": 7.0,
                    "min_value": 0.001, # 约1.5分钟
                    "max_value": 365.0,
                    "step": 0.5
                }
            ]
        }