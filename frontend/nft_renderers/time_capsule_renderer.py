# frontend/nft_renderers/time_capsule_renderer.py

import time
from datetime import datetime
from pytz import timezone # 将导入移到顶部

# <<< 插件V2.0: 新增函数 >>>
def get_admin_mint_info():
    """
    (可选) 为管理员铸造表单提供帮助信息和默认数据。
    :return: 一个包含 "help_text" 和 "default_json" 的字典。
    """
    return {
        "help_text": '对于时间胶囊, 请提供: {"content": "秘密消息", "days_to_reveal": 3 (天数)}',
        "default_json": '{\n  "content": "恭喜你发现了一个秘密！",\n  "days_to_reveal": 7\n}'
    }

# (render 函数保持不变)
def render(st, nft, balance, api_call_func, create_signed_message_func):
    """
    专门用于渲染“时间胶囊”类型 NFT 的组件。
    """
    data = nft.get('data', {})
    nft_id = nft.get('nft_id')
    
    st.subheader(data.get('name', '未命名时间胶囊'))
    
    TIMEZONE = timezone('Asia/Shanghai')

    created_at = datetime.fromtimestamp(nft['created_at'], TIMEZONE).strftime('%Y-%m-%d %H:%M')
    st.caption(f"ID: `{nft_id[:8]}` | 封存于: {created_at}")

    if data.get('is_revealed'):
        st.success("已揭晓 ✅")
        st.info("秘密内容是：")
        st.code(data.get('revealed_content', '(内容为空)'))
    else:
        st.warning("待揭晓 ⏳")
        reveal_ts = data.get('reveal_timestamp', 0)
        reveal_dt = datetime.fromtimestamp(reveal_ts, TIMEZONE)
        
        if time.time() < reveal_ts:
            st.info(f"将在 **{reveal_dt.strftime('%Y-%m-%d %H:%M')}** 后才能揭示。")
        else:
            st.success("已经可以揭示了！")
            if st.button("✨ 立即揭示", key=f"reveal_{nft_id}", type="primary"):
                with st.spinner("正在签名并揭示秘密..."):
                    message_dict = {
                        "owner_key": nft['owner_key'],
                        "nft_id": nft_id,
                        "action": "reveal",
                        "action_data": {}
                    }
                    signed_payload = create_signed_message_func(message_dict)
                    if signed_payload:
                        res_data, error = api_call_func('POST', '/nfts/action', payload=signed_payload)
                        if error:
                            st.error(f"揭示失败: {error}")
                        else:
                            st.success(f"揭示成功！{res_data.get('detail')}")
                            st.balloons()
                            st.cache_data.clear()
                            st.rerun()
