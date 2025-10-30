# frontend/nft_renderers/planet_renderer.py

import streamlit as st
import time
from datetime import datetime
import pytz

def get_admin_mint_info():
    """ 为管理员铸造表单提供帮助信息和默认数据。 """
    return {
        "help_text": '对于“星球”，管理员可以直接铸造。可留空 {} 以完全随机，或提供 {"custom_name": "Tatooine", "rarity_score": 500} 等字段覆盖。',
        "default_json": '''{
  "custom_name": "New Earth"
}'''
    }

def render(st, nft, balance, api_call_func, create_signed_message_func, view_context="collection"):
    """ 专门用于渲染“星球”类型 NFT 的组件。 """
    data = nft.get('data', {})
    nft_id = nft.get('nft_id')
    TIMEZONE = pytz.timezone('Asia/Shanghai')

    display_name = data.get('custom_name') or f"未命名行星 ({nft_id[:6]})"
    
    st.subheader(f"🪐 行星: {display_name}")

    if data.get('is_showcased', False):
        st.success("这颗星球正在你的个人主页公开展示中。")

    col1, col2, col3 = st.columns(3)
    col1.metric("稀有度评分", data.get('rarity_score', 0))
    col2.metric("行星类型", data.get('planet_type', '未知'))
    col3.metric("半径 (km)", f"{data.get('radius_km', 0):,}")

    with st.container(border=True):
        st.markdown("**发现信息**")
        c1, c2 = st.columns(2)
        discovered_at = datetime.fromtimestamp(data.get('discovery_timestamp', 0), TIMEZONE).strftime('%Y-%m-%d %H:%M')
        c1.markdown(f"**发现者:** {data.get('discovered_by_username', '未知')}")
        c2.markdown(f"**发现时间:** {discovered_at}")

    with st.container(border=True):
        st.markdown("**物理特征**")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**恒星类别:** {data.get('stellar_class', 'N/A')}")
        c2.markdown(f"**大气成分:** {data.get('atmosphere_composition', 'N/A')}")
        c3.markdown(f"**表面重力:** {data.get('surface_gravity_g', 0)} G")

    if data.get('has_rings') or data.get('biotic_presence') or data.get('rare_resource'):
        with st.container(border=True):
            st.markdown("**稀有属性**")
            if data.get('has_rings'):
                st.info("🪐 这颗星球拥有壮丽的行星环。")
            if data.get('biotic_presence'):
                st.warning("🧬 探测器在这颗星球上发现了生命的迹象！")
            if data.get('rare_resource'):
                st.error(f"💎 蕴藏着极其稀有的资源: {data.get('rare_resource')}！")
    # --- 交互区域 ---
    # --- 修复：交互按钮已移回 app.py, 渲染器只负责展示 ---
    if view_context == "collection":
        # 可以在此添加仅供收藏页面查看的、非交互性的信息
        pass