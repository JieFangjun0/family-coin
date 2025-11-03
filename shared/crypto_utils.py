import json
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
import base64 # 确保 base64 被导入

"""
使用 Ed25519 算法进行加密操作。
"""

# ... (generate_key_pair, sign_message, get_public_key_from_private 保持不变) ...
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
    """使用私钥对消息（字典）进行签名。"""
    try:
        private_key = serialization.load_pem_private_key(
            private_key_str.encode('utf-8'),
            password=None
        )
        message_bytes = json.dumps(message, sort_keys=True, ensure_ascii=False).encode('utf-8')
        signature = private_key.sign(message_bytes)
        return base64.b64encode(signature).decode('utf-8')
    except Exception as e:
        print(f"签名时出错: {e}")
        return None

def verify_signature(public_key_str: str, message: dict, signature_b64_str: str) -> bool:
    """使用公钥验证签名。"""
    try:
        # --- DEBUGGING STEP 4: Log the data received for verification ---
        print("--- Python Crypto Debug ---")
        print(f"1. Public Key PEM (first 50 chars): {public_key_str[:50]}")
        print(f"2. Received Signature Base64: {signature_b64_str}")

        public_key = serialization.load_pem_public_key(
            public_key_str.encode('utf-8')
        )

        # 2. 准备消息（必须与签名时完全一致）
        message_bytes = json.dumps(message, sort_keys=True, ensure_ascii=False).encode('utf-8')

        # --- DEBUGGING STEP 5: Log the exact string used for verification ---
        # 使用 !r 来显示精确的字节表示，包括任何不可见的字符
        print(f"3. Canonical Message Bytes for Verification: {message_bytes!r}")
        print("---------------------------")


        # 3. 解码签名
        signature = base64.b64decode(signature_b64_str.encode('utf-8'))

        # 4. 验证
        public_key.verify(signature, message_bytes)
        return True
    except InvalidSignature:
        # 明确打印出验证失败的信息
        print("!!! SIGNATURE VERIFICATION FAILED: InvalidSignature exception caught.")
        return False
    except Exception as e:
        print(f"验证签名时出错: {e}")
        return False

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