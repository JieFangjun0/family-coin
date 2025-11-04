# backend/bots/bot_client.py

import httpx
import json
import time
from typing import Optional, List, Dict
from shared.crypto_utils import generate_key_pair, sign_message
from cryptography.hazmat.primitives import serialization

"""
机器人 API 客户端 (BotClient)

- 这是一个异步客户端 (使用 httpx)，允许机器人并发执行操作。
- 它模拟了前端 `apiCall` 和 `createSignedPayload` 的所有功能。
"""

class BotClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        
        self.auth_info = {}
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        print(f"🤖 BotClient for '{username}' initialized.")

    async def login(self) -> bool:
        """登录并获取公钥/私钥。"""
        try:
            response = await self.client.post("/login", json={
                "username_or_uid": self.username,
                "password": self.password
            })
            if response.status_code == 200:
                self.auth_info = response.json()
                # 加载并存储私钥对象以便后续签名
                self.private_key_obj = serialization.load_pem_private_key(
                    self.auth_info['private_key'].encode('utf-8'),
                    password=None
                )
                print(f"🤖 Bot '{self.username}' (UID: {self.auth_info['uid']}) 登录成功。")
                return True
            else:
                print(f"❌ Bot '{self.username}' 登录失败: {response.json().get('detail')}")
                return False
        except Exception as e:
            print(f"❌ Bot '{self.username}' 登录时发生网络错误: {e}")
            return False

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
            # 注意：我们在这里直接使用 cryptography 库，而不是前端的 tweetnacl，
            # 因为我们持有的是 PEM 格式的私钥。
            signature_bytes = self.private_key_obj.sign(message_bytes)
            
            # 3. Base64 编码
            import base64
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
            
            # 4. 返回 API 载荷
            # 注意：这里的 message_json 也必须是 compact 格式
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
                return response.json(), None
            else:
                error_detail = response.json().get('detail', response.text)
                return None, error_detail
        except Exception as e:
            return None, str(e)

    # --- 机器人常用动作 ---
    
    async def get_balance(self) -> float:
        data, error = await self.api_call('GET', '/balance', params={"public_key": self.public_key})
        return data.get('balance', 0.0) if data else 0.0

    async def get_my_nfts(self) -> List[dict]:
        data, error = await self.api_call('GET', '/nfts/my', params={"public_key": self.public_key})
        return data.get('nfts', []) if data else []

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

    async def shop_action(self, nft_type: str, cost: float, data: dict, action_type: str) -> (bool, str):
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
        return (True, data.get('detail')) if not error else (False, error)