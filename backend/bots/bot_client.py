# backend/bots/bot_client.py

import httpx
import json
import time
from typing import Optional, List, Dict
from shared.crypto_utils import generate_key_pair, sign_message
from cryptography.hazmat.primitives import serialization

"""
机器人 API 客户端 (BotClient) V2
- 这是一个异步客户端 (使用 httpx)，允许机器人并发执行操作。
- (重构) 它不再需要登录。它在初始化时直接接收私钥。
"""

class BotClient:
    def __init__(self, base_url: str, username: str, public_key: str, private_key_pem: str):
        self.base_url = base_url
        self.username = username
        self.auth_info = {
            "public_key": public_key,
            "username": username
        }
        
        try:
            # 加载并存储私钥对象以便后续签名
            self.private_key_obj = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None
            )
        except Exception as e:
            print(f"❌ Bot '{self.username}' 严重错误: 无法加载私钥: {e}")
            raise e # 启动失败
            
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        print(f"🤖 BotClient for '{username}' (PK: {public_key[:10]}...) 已初始化。")

    # (login 方法已被移除)

    @property
    def public_key(self) -> Optional[str]:
        return self.auth_info.get('public_key')

    def _sign_payload(self, message: dict) -> dict:
        """(内部) 对消息字典进行签名，返回 API 兼容的载荷。"""
        try:
            # 1. 准备消息
            # 关键：使用 separators 匹配 Python 后端签名验证
            message_bytes = json.dumps(
                message, 
                sort_keys=True, 
                ensure_ascii=False, 
                separators=(',', ':')
            ).encode('utf-8')

            # 2. 签名
            signature_bytes = self.private_key_obj.sign(message_bytes)
            
            # 3. Base64 编码
            import base64
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
            
            # 4. 返回 API 载荷
            return {
                "message_json": json.dumps(message, sort_keys=True, ensure_ascii=False, separators=(',', ':')),
                "signature": signature_b64,
            }
        except Exception as e:
            print(f"❌ Bot '{self.username}' 签名失败: {e}")
            return None

    async def api_call(self, method: str, endpoint: str, params: dict = None, payload: dict = None) -> (Optional[dict], str):
        """通用的 API 调用辅助函数。"""
        try:
            response = await self.client.request(method, endpoint, params=params, json=payload)
            if 200 <= response.status_code < 300:
                try:
                    return response.json(), None
                except json.JSONDecodeError:
                    return {"detail": response.text}, None # 容错
            else:
                error_detail = "未知错误"
                try:
                    error_detail = response.json().get('detail', response.text)
                except json.JSONDecodeError:
                    error_detail = response.text
                return None, error_detail
        except httpx.ConnectError as e:
            return None, f"网络连接错误: {e}"
        except Exception as e:
            return None, str(e)

    # --- 机器人常用动作 ---
    
    async def get_balance(self) -> float:
        data, error = await self.api_call('GET', '/balance', params={"public_key": self.public_key})
        return data.get('balance', 0.0) if data else 0.0

    async def get_my_nfts(self) -> List[dict]:
        data, error = await self.api_call('GET', '/nfts/my', params={"public_key": self.public_key})
        return data.get('nfts', []) if data else []

    async def get_my_activity(self) -> tuple[List[dict], List[dict]]:
        """(新增) 获取机器人自己的市场活动。"""
        data, error = await self.api_call('GET', '/market/my_activity', params={"public_key": self.public_key})
        if error:
            print(f"❌ Bot '{self.username}' 无法获取 /market/my_activity: {error}")
            return [], [] # 返回空列表以防止崩溃
        return data.get('listings', []), data.get('offers', [])

    async def get_market_listings(self, listing_type: str) -> List[dict]:
        data, error = await self.api_call('GET', '/market/listings', params={
            "listing_type": listing_type,
            "exclude_owner": self.public_key # 自动排除自己的
        })
        return data.get('listings', []) if data else []

    async def buy_item(self, listing_id: str) -> (bool, str):
        message = {
            "owner_key": self.public_key,
            "listing_id": listing_id,
            "timestamp": time.time()
        }
        signed_payload = self._sign_payload(message)
        data, error = await self.api_call('POST', '/market/buy', payload=signed_payload)
        return (True, data.get('detail')) if not error else (False, error)

    async def place_bid(self, listing_id: str, amount: float) -> (bool, str):
        message = {
            "owner_key": self.public_key,
            "listing_id": listing_id,
            "amount": amount,
            "timestamp": time.time()
        }
        signed_payload = self._sign_payload(message)
        data, error = await self.api_call('POST', '/market/place_bid', payload=signed_payload)
        return (True, data.get('detail')) if not error else (False, error)

    async def create_listing(self, nft_id: str, nft_type: str, price: float, description: str, listing_type: str = "SALE", auction_hours: float = None) -> (bool, str):
        message = {
            "owner_key": self.public_key,
            "timestamp": time.time(),
            "listing_type": listing_type,
            "nft_id": nft_id,
            "nft_type": nft_type,
            "description": description,
            "price": price,
            "auction_hours": auction_hours if listing_type == "AUCTION" else None
        }
        signed_payload = self._sign_payload(message)
        data, error = await self.api_call('POST', '/market/create_listing', payload=signed_payload)
        return (True, data.get('detail')) if not error else (False, error)

    async def create_seek(self, nft_type: str, description: str, price: float) -> (bool, str):
        message = {
            "owner_key": self.public_key,
            "timestamp": time.time(),
            "listing_type": "SEEK",
            "nft_id": None,
            "nft_type": nft_type,
            "description": description,
            "price": price,
            "auction_hours": None
        }
        signed_payload = self._sign_payload(message)
        data, error = await self.api_call('POST', '/market/create_listing', payload=signed_payload)
        return (True, data.get('detail')) if not error else (False, error)

    async def shop_action(self, nft_type: str, cost: float, data: dict, action_type: str) -> (bool, str, Optional[str]):
        """ (重构) 现在返回 (success, detail, nft_id) """
        message = {
            "owner_key": self.public_key,
            "timestamp": time.time(),
            "nft_type": nft_type,
            "cost": cost,
            "data": data
        }
        signed_payload = self._sign_payload(message)
        endpoint = "/market/create_nft" if action_type == "create" else "/market/shop_action"
        
        data, error = await self.api_call('POST', endpoint, payload=signed_payload)
        if error:
            return False, error, None
        
        # (核心修改) 从响应中解析 nft_id
        return True, data.get('detail'), data.get('nft_id')
    async def update_profile(self, signature: str, displayed_nft_ids: List[str]) -> (bool, str):
        """(新增) 更新机器人的个人签名和展柜"""
        message = {
            "owner_key": self.public_key,
            "signature": signature,
            "displayed_nfts": displayed_nft_ids,
            "timestamp": time.time()
        }
        signed_payload = self._sign_payload(message)
        if not signed_payload:
            return False, "签名失败"
        
        data, error = await self.api_call('POST', '/profile/update', payload=signed_payload)
        return (True, data.get('detail')) if not error else (False, error)

    # +++ (新增) 允许机器人执行 NFT 动作 +++
    async def nft_action(self, nft_id: str, action: str, action_data: dict) -> (bool, str):
        """(新增) 对自己的 NFT 执行一个动作 (例如: 扫描, 丰收)。"""
        message = {
            "owner_key": self.public_key,
            "nft_id": nft_id,
            "action": action,
            "action_data": action_data,
            "timestamp": time.time()
        }
        signed_payload = self._sign_payload(message)
        data, error = await self.api_call('POST', '/nfts/action', payload=signed_payload)
        return (True, data.get('detail')) if not error else (False, error)