# backend/shared/crypto_utils.py

import json
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
import base64

"""
使用 Ed25519 算法进行加密操作。
"""

def generate_key_pair():
    """生成一对新的 Ed25519 密钥（公钥和私钥）。"""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_key_str = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    public_key_str = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return private_key_str, public_key_str

def sign_message(private_key_str: str, message: dict) -> str:
    """
    (供机器人使用) 使用私钥对消息（字典）进行签名。
    这会创建后端的规范化 JSON 字符串。
    """
    try:
        private_key = serialization.load_pem_private_key(
            private_key_str.encode('utf-8'),
            password=None
        )
        
        # --- 核心：后端的规范化定义 ---
        message_bytes = json.dumps(
            message, 
            sort_keys=True, 
            ensure_ascii=False, 
            separators=(',', ':')
        ).encode('utf-8')
        
        signature = private_key.sign(message_bytes)
        return base64.b64encode(signature).decode('utf-8')
    except Exception as e:
        print(f"签名时出错: {e}")
        return None

def _verify_signature_from_dict(public_key_str: str, message: dict, signature_b64_str: str) -> bool:
    """
    (内部使用，供机器人验证) 
    使用公钥验证签名。
    注意：此函数会重新序列化字典。
    """
    try:
        public_key = serialization.load_pem_public_key(
            public_key_str.encode('utf-8')
        )

        # --- 核心：后端的规范化定义 ---
        message_bytes = json.dumps(
            message, 
            sort_keys=True, 
            ensure_ascii=False, 
            separators=(',', ':')
        ).encode('utf-8')

        # --- 调试日志（可以保留） ---
        print("\n--- Python Backend Crypto Debug (Dict Mode) ---")
        print(f"1. Public Key (first 50 chars): {public_key_str[:50]}")
        print(f"2. Received Signature (Base64): {signature_b64_str}")
        print(f"3. Canonical Message Bytes for Verification: {message_bytes!r}")
        print("-----------------------------------")

        signature = base64.b64decode(signature_b64_str.encode('utf-8'))

        # 验证
        public_key.verify(signature, message_bytes)
        print("✅ SIGNATURE VERIFICATION SUCCESSFUL (Dict Mode)\n")
        return True
    except InvalidSignature:
        print("❌ SIGNATURE VERIFICATION FAILED: InvalidSignature exception caught.\n")
        return False
    except Exception as e:
        print(f"❌ An error occurred during signature verification: {e}\n")
        return False

# +++ 核心改动：添加这个新函数 +++
def verify_signature(public_key_str: str, message_json_str: str, signature_b64_str: str) -> bool:
    """
    (供前端 API 使用)
    使用公钥验证一个 *原始 JSON 字符串* 的签名。
    这确保了我们验证的是与前端签名完全相同的字节。
    """
    try:
        public_key = serialization.load_pem_public_key(
            public_key_str.encode('utf-8')
        )

        # --- 核心：直接使用原始字符串 ---
        message_bytes = message_json_str.encode('utf-8')

        # --- 调试日志 ---
        print("\n--- Python Backend Crypto Debug (String Mode) ---")
        print(f"1. Public Key (first 50 chars): {public_key_str[:50]}")
        print(f"2. Received Signature (Base64): {signature_b64_str}")
        print(f"3. Raw Message Bytes for Verification: {message_bytes!r}")
        print("-----------------------------------")

        signature = base64.b64decode(signature_b64_str.encode('utf-8'))

        # 验证
        public_key.verify(signature, message_bytes)
        print("✅ SIGNATURE VERIFICATION SUCCESSFUL (String Mode)\n")
        return True
    except InvalidSignature:
        print("❌ SIGNATURE VERIFICATION FAILED: InvalidSignature exception caught.\n")
        return False
    except Exception as e:
        print(f"❌ An error occurred during signature verification: {e}\n")
        return False
# +++ 核心改动结束 +++


def get_public_key_from_private(private_key_str: str) -> str:
    """(辅助功能) 从私钥推导出公钥。"""
    try:
        private_key = serialization.load_pem_private_key(
            private_key_str.encode('utf-8'),
            password=None
        )
        public_key = private_key.public_key()
        public_key_str = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        return public_key_str
    except Exception:
        return None