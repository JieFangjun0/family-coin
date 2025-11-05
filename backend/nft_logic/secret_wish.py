# backend/nft_logic/secret_wish.py

import time
import uuid
from .base import NFTLogicHandler
from datetime import datetime, timedelta

class SecretWishHandler(NFTLogicHandler):
    """
    “秘密愿望” NFT 的逻辑处理器。
    """
    @classmethod
    def get_display_name(cls) -> str:
        return "秘密"
    def mint(self, owner_key: str, data: dict, owner_username: str = None) -> (bool, str, dict):
        """
        铸造一个新的“秘密愿望”。
        """
        description = data.get('description')
        content = data.get('content')
        destroy_in_days = data.get('destroy_in_days')

        if not all([description, content, isinstance(destroy_in_days, (int, float))]):
            return False, "必须提供 'description'(公开描述), 'content'(秘密内容), 和 'destroy_in_days'(销毁天数)", {}

        min_seconds = 60
        max_seconds = 365 * 24 * 60 * 60
        destroy_duration_seconds = destroy_in_days * 24 * 60 * 60

        if not (min_seconds <= destroy_duration_seconds <= max_seconds):
            return False, f"销毁天数换算后必须在 {min_seconds/60} 分钟到 {max_seconds/(24*60*60)} 天之间", {}

        creation_timestamp = time.time()
        destroy_timestamp = creation_timestamp + destroy_duration_seconds
        
        db_data = {
            "wish_id": str(uuid.uuid4()),
            "creation_timestamp": creation_timestamp,
            "destroy_timestamp": destroy_timestamp,
            "description": description,
            "content": content,
            "is_destroyed": False,
            "creator_key": owner_key,
            "creator_username": owner_username or "未知"
        }
        return True, "一个新的秘密已被悄然封存。", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        """
        验证用户操作。
        """
        if action == 'destroy':
            destroy_ts = nft.get('data', {}).get('destroy_timestamp', 0)
            if time.time() > destroy_ts:
                return True, "可以销毁"
          # 如果时间未到，则交给基类处理通用的所有者销毁逻辑

        # 调用基类的方法来处理通用的 'destroy' 动作或其他未来可能添加的通用动作
        return super().validate_action(nft, action, action_data, requester_key)
        

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str, conn=None) -> (bool, str, dict): # <<< (1) 新增 conn=None
        """
        执行销毁操作。
        """
        if action == 'destroy':
            updated_data = nft['data'].copy()
            updated_data['is_destroyed'] = True
            updated_data['content'] = "内容已随风而逝..." # 清理敏感信息
            
            # --- 核心: 使用新协议请求状态变更 ---
            updated_data['__new_status__'] = 'DESTROYED'
            
            return True, "这个愿望已经彻底消失了。", updated_data

        return super().perform_action(nft, action, action_data, requester_key, conn) # <<< (2) 传递 conn
    
    @classmethod
    def get_shop_config(cls) -> dict:
        return {
            "creatable": True,
            "cost": 5.0,
            "name": "秘密愿望",
            # +++ 在这里添加下面这一行 +++
            "action_type": "create", # 告诉前端调用 /market/create_nft
            # +++ 修复结束 +++
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
                    "min_value": 0.001,
                    "max_value": 365.0,
                    "step": 0.001,
                }
            ]
        }
        
    # <<< --- 核心重构：实现具体的“可交易性”检查 --- >>>
    def is_tradable(self, nft: dict) -> (bool, str):
        """
        重写基类方法，实现“秘密愿望”的特定交易规则。
        """
        try:
            data = nft.get('data', {})
            destroy_ts = data.get('destroy_timestamp', 0)
            if time.time() > destroy_ts:
                return False, "该“秘密愿望”已到期，无法进行任何交易，请在“我的收藏”中将其销毁"
        except Exception:
            # 如果数据解析出错，也视为不可交易
            return False, "NFT数据异常，无法交易"
        
        return True, "OK"
    
    def get_trade_description(self, nft: dict) -> str:
        """
        为“秘密愿望”生成一个动态的、吸引人的市场描述。
        """
        try:
            data = nft.get('data', {})
            description = data.get('description', '一个秘密')
            creator_name = data.get('creator_username', '未知用户')
            destroy_ts = data.get('destroy_timestamp', 0)
            
            time_left_seconds = max(0, int(destroy_ts - time.time()))
            time_left = timedelta(seconds=time_left_seconds)
            
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            
            if days > 0:
                countdown_str = f"约 {days} 天 {hours} 小时"
            else:
                minutes, _ = divmod(remainder, 60)
                countdown_str = f"约 {hours} 小时 {minutes} 分钟"
            
            return f"“{description}” (来自 {creator_name}) - 这个秘密还剩下 {countdown_str} 就会消失。"
        except Exception as e:
            # 如果出现任何错误，返回一个安全的默认值
            return f"{data.get('description', '一个神秘的愿望')} (来自 {data.get('creator_username', '未知')})"
    @classmethod
    def get_admin_mint_config(cls) -> dict:
        """为管理员铸造表单提供帮助信息和默认数据。"""
        return {
            "help_text": '对于“秘密”，请提供: {"description": "公开的描述", "content": "秘密内容", "destroy_in_days": 消失天数 (天)}',
            "default_json": '''{
  "description": "我今天中午吃了什么？",
  "content": "丝瓜炒鸡蛋，非常美味！",
  "destroy_in_days": 7
}'''
        }