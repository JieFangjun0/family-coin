# frontend/nft_renderers/__init__.py

import os
import importlib
import streamlit as st

# <<< 插件V2.0: 修改注册表结构 >>>
# 注册表现在存储一个字典，键是插件提供的功能 (e.g., "render", "admin_mint_info")
NFT_RENDERERS = {}

current_dir = os.path.dirname(__file__)
package_name = __name__

for filename in os.listdir(current_dir):
    if filename.endswith("_renderer.py"):
        nft_type_key = filename.replace("_renderer.py", "").upper()
        module_name = filename[:-3]
        
        try:
            module = importlib.import_module(f".{module_name}", package=package_name)
            
            # 初始化该类型的插件字典
            plugin_functions = {}
            
            # 检查必须的 render 函数
            if hasattr(module, "render"):
                plugin_functions["render"] = module.render
            else:
                # 如果连 render 都没有，跳过这个插件
                print(f"⚠️ Skipping {filename}: 'render' function not found.")
                continue

            # 检查可选的 admin_mint_info 函数
            if hasattr(module, "get_admin_mint_info"):
                plugin_functions["admin_mint_info"] = module.get_admin_mint_info
            
            # 注册到主字典
            NFT_RENDERERS[nft_type_key] = plugin_functions
            print(f"✅ Successfully registered NFT plugin: {nft_type_key}")

        except Exception as e:
            print(f"❌ Failed to register NFT plugin from {filename}: {e}")

# --- 默认渲染器 (不变) ---
def default_renderer(st, nft, *args, **kwargs):
    st.warning(f"未找到类型为 **{nft.get('nft_type')}** 的前端渲染器插件。")
    st.write("以下是该 NFT 的原始数据：")
    st.json(nft.get('data', {}))

# --- 统一渲染路由 (微调) ---
def render_nft(st, nft, balance, api_call_func, create_signed_message_func):
    nft_type = nft.get("nft_type")
    
    # <<< 插件V2.0: 更新字典访问方式 >>>
    # 从字典中获取 "render" 函数
    renderer_func = NFT_RENDERERS.get(nft_type, {}).get("render", default_renderer)
    
    try:
        renderer_func(st, nft, balance, api_call_func, create_signed_message_func)
    except Exception as e:
        st.error(f"渲染 NFT (类型: {nft_type}) 时出错: {e}")

# --- <<< 插件V2.0: 新增 Getter 函数供 Admin 页面调用 >>> ---
def get_mint_info_for_type(nft_type: str) -> dict:
    """
    获取指定 NFT 类型的管理员铸造信息。
    :return: 包含 "help_text" 和 "default_json" 的字典。
    """
    # 默认返回值，确保安全
    default_info = {
        "help_text": "该 NFT 类型未提供帮助信息。",
        "default_json": "{}"
    }

    if not nft_type:
        return default_info

    # 1. 查找该类型的插件字典
    plugin_functions = NFT_RENDERERS.get(nft_type)
    if not plugin_functions:
        return default_info

    # 2. 查找 "admin_mint_info" 函数
    info_func = plugin_functions.get("admin_mint_info")
    if not info_func:
        return default_info

    # 3. 执行函数并返回结果
    try:
        return info_func()
    except Exception as e:
        print(f"❌ Error executing get_admin_mint_info for {nft_type}: {e}")
        return default_info
