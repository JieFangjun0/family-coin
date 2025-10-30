# frontend/nft_renderers/planet_renderer.py

import streamlit as st
import time
from datetime import datetime
import pytz

def get_admin_mint_info():
    """ 为管理员铸造表单提供帮助信息和默认数据。 """
    return {
        "help_text": '对于“星球”，管理员可以直接铸造。留空 {} 以完全随机，或提供 {"custom_name": "Tatooine"} 等字段覆盖。',
        "default_json": '{\n  "custom_name": "New Earth"\n}'
    }

def render(st, nft, balance, api_call_func, create_signed_message_func, view_context="collection"):
    """ 专门用于渲染“星球 V2”类型 NFT 的组件。 """
    data = nft.get('data', {})
    nft_id = nft.get('nft_id')
    TIMEZONE = pytz.timezone('Asia/Shanghai')

    display_name = data.get('custom_name') or f"未命名行星 ({nft_id[:6]})"
    
    st.subheader(f"🪐 行星: {display_name}")
    st.caption(f"**坐标:** `{data.get('galactic_coordinates', '未知')}`")

    # --- 稀有度展示 ---
    rarity_data = data.get('rarity_score', {})
    total_rarity = rarity_data.get('total', 0)
    base_rarity = rarity_data.get('base', 0)
    traits_rarity = rarity_data.get('traits', 0)
    
    st.metric("综合稀有度评分", total_rarity, f"{traits_rarity:+d} 来自特质")

    # --- 天文信息 ---
    with st.container(border=True):
        st.markdown("**天文数据**")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**恒星类别:** {data.get('stellar_class', 'N/A')}")
        c2.markdown(f"**轨道区域:** {data.get('orbital_zone', 'N/A')}")
        c3.markdown(f"**星球类型:** {data.get('planet_type', 'N/A')}")

    # --- 已揭示的特质 ---
    unlocked_traits = data.get('unlocked_traits', [])
    if unlocked_traits:
        with st.container(border=True):
            st.success("**已确认的发现**")
            for trait in unlocked_traits:
                st.markdown(f"- **{trait}**")

    # --- 交互区域 (仅在收藏页面显示) ---
    if view_context == "collection":
        # --- 异常信号扫描 ---
        anomalies = data.get('anomalies', [])
        if anomalies:
            with st.expander("🛰️ 未探明的异常信号", expanded=True):
                st.info("这颗星球上存在着未解之谜。你可以消耗资源进行深度扫描，或许会有惊人的发现，也可能一无所获。")
                
                selected_anomaly = st.selectbox(
                    "选择要扫描的信号:", 
                    options=[a for a in anomalies],
                    format_func=lambda x: f"{x} (点击扫描)",
                    key=f"scan_select_{nft_id}"
                )
                
                SCAN_COST = 5.0 # 定义扫描成本
                st.warning(f"每次扫描将消耗 **{SCAN_COST} FC**。")

                if st.button("🚀 启动深度扫描", key=f"scan_btn_{nft_id}", type="primary", disabled=(balance < SCAN_COST)):
                    with st.spinner("正在传输扫描指令..."):
                        # 1. 先在后端执行扣款
                        tx_success, tx_detail = False, "初始化失败"
                        burn_payload = {
                            "from_key": nft['owner_key'],
                            "amount": SCAN_COST,
                            "note": f"扫描行星信号: {selected_anomaly}"
                        }
                        # 注意：这里直接调用 ledger._create_system_transaction 会更好，但前端只能通过API
                        # 暂用一个临时的管理员减持接口模拟，或者在后端 /nfts/action 中实现扣款
                        # 为简化，我们假设后端 action 会自行处理扣款，这里只调用 action
                        
                        # 2. 执行 NFT 动作
                        message_dict = {
                            "owner_key": nft['owner_key'], "nft_id": nft_id,
                            "action": "scan",
                            "action_data": {"anomaly": selected_anomaly},
                            "timestamp": time.time()
                        }
                        signed_payload = create_signed_message_func(message_dict)
                        if signed_payload:
                            res_data, error = api_call_func('POST', '/nfts/action', payload=signed_payload)
                            if error:
                                st.error(f"扫描失败: {error}")
                            else:
                                st.success(f"扫描报告: {res_data.get('detail')}")
                                st.balloons()
                                time.sleep(1)
                                st.cache_data.clear()
                                st.rerun()
        
        # --- 重命名操作 ---
        with st.expander("✏️ 重命名星球"):
            with st.form(key=f"rename_form_{nft_id}"):
                new_name = st.text_input("输入新的星球名称", value=data.get('custom_name', ''), max_chars=20)
                if st.form_submit_button("确认命名"):
                    with st.spinner("正在广播新名称..."):
                        message_dict = {
                            "owner_key": nft['owner_key'], "nft_id": nft_id,
                            "action": "rename", "action_data": {"new_name": new_name},
                            "timestamp": time.time()
                        }
                        signed_payload = create_signed_message_func(message_dict)
                        if signed_payload:
                            res, err = api_call_func('POST', '/nfts/action', payload=signed_payload)
                            if err: st.error(f"重命名失败: {err}")
                            else: 
                                st.success(res.get('detail'))
                                st.cache_data.clear()
                                st.rerun()