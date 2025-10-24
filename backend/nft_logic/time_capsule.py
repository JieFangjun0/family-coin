# backend/nft_logic/time_capsule.py

from .base import NFTLogicHandler
import time
from datetime import datetime, timedelta

class TimeCapsuleHandler(NFTLogicHandler):
    """
    “时间胶囊”NFT 的逻辑处理器。
    """

    def mint(self, owner_key: str, data: dict) -> (bool, str, dict):
        """
        铸造一个时间胶囊。
        管理员需要提供: 
        - content (str): 胶囊的秘密内容。
        - days_to_reveal (int): 多少天后可以揭示。
        """
        content = data.get('content')
        days_to_reveal = data.get('days_to_reveal')

        if not content or not isinstance(days_to_reveal, int) or days_to_reveal <= 0:
            return False, "必须提供 'content' (字符串) 和 'days_to_reveal' (正整数)", {}

        reveal_timestamp = time.time() + (days_to_reveal * 86400)
        
        db_data = {
            "name": f"封存了 {days_to_reveal} 天的秘密",
            "content": content,
            "reveal_timestamp": reveal_timestamp,
            "is_revealed": False,
            "revealed_content": None
        }
        return True, "时间胶囊已成功封存！", db_data

    def validate_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str):
        if action != 'reveal':
            return False, "不支持的动作"
        
        if nft['owner_key'] != requester_key:
            return False, "你不是此时间胶囊的所有者"

        nft_data = nft.get('data', {})
        if nft_data.get('is_revealed'):
            return False, "这个胶囊已经被揭示过了"

        if time.time() < nft_data.get('reveal_timestamp', float('inf')):
            reveal_time_str = datetime.fromtimestamp(nft_data['reveal_timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            return False, f"还没到揭示时间！请于 {reveal_time_str} 后再试。"

        return True, "可以揭示"

    def perform_action(self, nft: dict, action: str, action_data: dict, requester_key: str) -> (bool, str, dict):
        if action == 'reveal':
            updated_data = nft['data'].copy()
            updated_data['is_revealed'] = True
            updated_data['revealed_content'] = updated_data.get('content')
            # 为安全起见，可以清除原始内容
            # del updated_data['content'] 
            return True, "秘密已揭晓！", updated_data
            
        return False, "内部错误：执行了未验证的动作", {}