# backend/nft_admin_utils.py

from backend.nft_logic import NFT_HANDLERS

def get_mint_info_for_type(nft_type: str) -> dict:
    """
    从后端的 NFT Logic Handler 获取指定 NFT 类型的管理员铸造信息。
    这是对旧 Streamlit 前端 get_admin_mint_info 功能的后端原生实现。
    """
    default_info = {
        "help_text": "该 NFT 类型未提供帮助信息。",
        "default_json": "{}"
    }

    if not nft_type:
        return default_info

    handler_class = NFT_HANDLERS.get(nft_type)
    if not handler_class or not hasattr(handler_class, 'get_admin_mint_config'):
        # 如果 Handler 不存在或没有实现 get_admin_mint_config 方法，返回默认值
        return default_info

    try:
        # 调用 Handler 上的类方法
        return handler_class.get_admin_mint_config()
    except Exception as e:
        print(f"❌ Error executing get_admin_mint_config for {nft_type}: {e}")
        return default_info