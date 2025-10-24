# backend/nft_logic/__init__.py

from .base import NFTLogicHandler
from .time_capsule import TimeCapsuleHandler

# <<< NFT 架构升级: 插件注册表 >>>
# 每当创建一个新的 NFT 逻辑处理器，都需要在这里注册。
# 键 (key) 是在 API 和数据库中使用的 nft_type 字符串。
# 值 (value) 是对应的 Handler 类。
NFT_HANDLERS = {
    "TIME_CAPSULE": TimeCapsuleHandler,
    # 当你创建 bio_dna.py后，在这里添加:
    # "BIO_DNA": BioDNAHandler,
}

def get_handler(nft_type: str) -> NFTLogicHandler:
    """
    根据 NFT 类型字符串获取对应的逻辑处理器实例。
    """
    handler_class = NFT_HANDLERS.get(nft_type)
    if not handler_class:
        return None
    return handler_class()

def get_available_nft_types() -> list:
    """获取所有已注册的 NFT 类型列表。"""
    return list(NFT_HANDLERS.keys())