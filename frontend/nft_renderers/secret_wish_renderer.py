# frontend/nft_renderers/secret_wish_renderer.py

import streamlit as st
import time
from datetime import datetime, timedelta
import pytz

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

def render(st, nft, balance, api_call_func, create_signed_message_func):
    """
    专门用于渲染“秘密愿望”类型 NFT 的组件。
    """
    data = nft.get('data', {})
    nft_id = nft.get('nft_id')
    TIMEZONE = pytz.timezone('Asia/Shanghai')

    st.subheader("一个秘密或者愿望")
    st.caption(f"ID: `{nft_id[:8]}`")
    
    destroy_ts = data.get('destroy_timestamp', 0)
    
    # --- 核心修改：如果已过期，提供销毁按钮 ---
    if time.time() > destroy_ts:
        st.info("“这个愿望已经随着时间消散了。”")
        with st.container(border=True):
            st.markdown(f"**愿望描述:** ~~{data.get('description', '...')}~~")
            destroy_dt = datetime.fromtimestamp(destroy_ts, TIMEZONE).strftime('%Y-%m-%d %H:%M')
            st.markdown(f"**消失于:** {destroy_dt}")
            
            st.warning("它的数据仍保留在链上，点击下方按钮可将其彻底清除。")
            if st.button("✨ 让它彻底消失", key=f"destroy_{nft_id}", type="primary"):
                with st.spinner("正在施展遗忘咒..."):
                    message_dict = {
                        "owner_key": nft['owner_key'],
                        "nft_id": nft_id,
                        "action": "destroy",
                        "action_data": {} # 此动作不需要额外数据
                    }
                    signed_payload = create_signed_message_func(message_dict)
                    if signed_payload:
                        res_data, error = api_call_func('POST', '/nfts/action', payload=signed_payload)
                        if error:
                            st.error(f"销毁失败: {error}")
                        else:
                            st.success(f"销毁成功！{res_data.get('detail')}")
                            time.sleep(1) # 稍作停留，让用户看到成功信息
                            st.cache_data.clear()
                            st.rerun()
        return

    # --- 如果愿望仍然有效 (逻辑不变) ---
    with st.container(border=True):
        st.markdown(f"**愿望描述:** {data.get('description', '...')}")
        st.markdown("**秘密内容:**")
        st.code(data.get('content', '(内容为空)'))

        time_left = timedelta(seconds=int(destroy_ts - time.time()))
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        countdown_str = f"{days}天 {hours}小时 {minutes}分钟 后消失"
        st.warning(f"⏳ {countdown_str}")