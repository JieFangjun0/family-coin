# frontend/nft_renderers/secret_wish_renderer.py

import streamlit as st
import time
from datetime import datetime, timedelta
import pytz

# --- 1. 管理员铸造界面的帮助信息 ---
def get_admin_mint_info():
    """
    为管理员铸造表单提供帮助信息和默认数据。
    """
    return {
        "help_text": '对于“秘密愿望”，请提供: {"description": "公开的描述", "content": "秘密内容", "destroy_in_days": 1.5 (天)}',
        "default_json": '''{
  "description": "一个关于未来的小小预测",
  "content": "我打赌我会踩到狗屎！",
  "destroy_in_days": 7
}'''
    }

# --- 2. 在“我的收藏”中渲染该NFT的UI ---
def render(st, nft, balance, api_call_func, create_signed_message_func):
    """
    专门用于渲染“秘密愿望”类型 NFT 的组件。
    """
    data = nft.get('data', {})
    nft_id = nft.get('nft_id')
    TIMEZONE = pytz.timezone('Asia/Shanghai')

    st.subheader("一个秘密或者愿望")
    st.caption(f"ID: `{nft_id[:8]}`")
    
    # --- 检查愿望是否已“消失” ---
    destroy_ts = data.get('destroy_timestamp', 0)
    
    if time.time() > destroy_ts:
        st.info("“这个愿望已经随着时间消散了。”")
        with st.container(border=True):
            st.markdown(f"**愿望描述:** ~~{data.get('description', '...')}~~")
            st.markdown(f"**秘密内容:** `已销毁`")
            destroy_dt = datetime.fromtimestamp(destroy_ts, TIMEZONE).strftime('%Y-%m-%d %H:%M')
            st.markdown(f"**消失于:** {destroy_dt}")
        return # 结束渲染

    # --- 如果愿望仍然有效 ---
    with st.container(border=True):
        # 1. 公开的描述
        st.markdown(f"**愿望描述:** {data.get('description', '...')}")
        
        # 2. 仅所有者可见的秘密内容
        st.markdown("**秘密内容:**")
        st.code(data.get('content', '(内容为空)'))

        # 3. 销毁倒计时
        time_left = timedelta(seconds=int(destroy_ts - time.time()))
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        countdown_str = f"{days}天 {hours}小时 {minutes}分钟 后消失"
        st.warning(f"⏳ {countdown_str}")

    # 这个NFT没有任何按钮或交互，它只是一个安静的观察者。
    # 所以我们不需要像 time_capsule 那样创建表单和按钮。