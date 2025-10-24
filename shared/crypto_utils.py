import json
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

"""
使用 Ed25519 算法进行加密操作。
Ed25519 速度快、安全性高，非常适合此类项目。
"""

def generate_key_pair():
    """生成一对新的 Ed25519 密钥（公钥和私钥）。"""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # 将密钥序列化为易于存储和传输的 PEM 格式字符串
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
        # 1. 加载私钥
        private_key = serialization.load_pem_private_key(
            private_key_str.encode('utf-8'),
            password=None
        )

        # 2. 准备消息：序列化为规范的 JSON 字符串
        #    ensure_ascii=False 保证中文正常显示
        #    sort_keys=True 保证每次序列化结果一致
        message_bytes = json.dumps(message, sort_keys=True, ensure_ascii=False).encode('utf-8')

        # 3. 签名
        signature = private_key.sign(message_bytes)

        # 4. 返回 base64 编码的签名字符串
        import base64
        return base64.b64encode(signature).decode('utf-8')
        
    except Exception as e:
        print(f"签名时出错: {e}")
        return None

def verify_signature(public_key_str: str, message: dict, signature_b64_str: str) -> bool:
    """使用公钥验证签名。"""
    try:
        # 1. 加载公钥
        public_key = serialization.load_pem_public_key(
            public_key_str.encode('utf-8')
        )

        # 2. 准备消息（必须与签名时完全一致）
        message_bytes = json.dumps(message, sort_keys=True, ensure_ascii=False).encode('utf-8')

        # 3. 解码签名
        import base64
        signature = base64.b64decode(signature_b64_str.encode('utf-8'))

        # 4. 验证
        public_key.verify(signature, message_bytes)
        return True
    except InvalidSignature:
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
