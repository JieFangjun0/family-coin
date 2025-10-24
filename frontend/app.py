# frontend/app.py

import streamlit as st
import requests
import json
import time
import os
import qrcode
import pandas as pd
from io import BytesIO
import streamlit.components.v1 as components
from shared.crypto_utils import (
    sign_message,
    get_public_key_from_private
)
from datetime import datetime
import pytz
# <<< NFT前端插件: 导入统一的渲染路由函数 >>>
from frontend.nft_renderers import render_nft, get_mint_info_for_type

# --- 配置 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEZONE = pytz.timezone('Asia/Shanghai')
ADMIN_UI_PASSWORD = os.getenv("ADMIN_UI_PASSWORD", "j")

st.set_page_config(page_title="FamilyCoin V1.0", layout="wide")
st.title("🪙 FamilyCoin V1.0 (家庭币)")
st.caption(f"一个带邀请制和商店的中心化货币系统。（仅供娱乐，请勿用作非法用途！）")

# --- 会话状态管理 (Session State) ---
def init_session_state():
    """初始化会话状态"""
    defaults = {
        'logged_in': False,
        'private_key': "",
        'public_key': "",
        'username': "",
        'admin_secret': "",
        'admin_ui_unlocked': False,
        'user_details': None,
        'all_users_cache': None,
        'all_users_cache_time': 0,
        'needs_setup': None,
        'new_user_info': None,
        'genesis_info': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()
    
def st_copy_to_clipboard_button(text_to_copy, button_text, key):
    """
    显示一个按钮，点击时将文本复制到剪贴板。
    """
    button_id = f"btn-copy-{key}"
    js_text = json.dumps(text_to_copy)

    html = f"""
    <style>
        .copy-btn {{
            background-color: #0068c9;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin-top: 8px;
        }}
        .copy-btn:hover {{
            background-color: #0055a4;
        }}
        .copy-btn:disabled {{
            background-color: #cccccc;
            color: #666666;
            cursor: not-allowed;
        }}
    </style>
    <script>
    function copyToClipboard_{key}() {{
        const textToCopy = {js_text};
        const tempTextArea = document.createElement('textarea');
        tempTextArea.value = textToCopy;
        tempTextArea.style.position = 'absolute';
        tempTextArea.style.left = '-9999px';
        document.body.appendChild(tempTextArea);
        
        tempTextArea.select();
        tempTextArea.setSelectionRange(0, 99999);
        
        try {{
            document.execCommand('copy');
            const btn = document.getElementById('{button_id}');
            if (btn) {{
                const originalText = btn.innerHTML;
                btn.innerHTML = '已复制!';
                btn.disabled = true;
                setTimeout(() => {{
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }}, 2000);
            }}
        }} catch (err) {{
            console.error('复制到剪贴板失败:', err);
            const btn = document.getElementById('{button_id}');
            if (btn) {{
                btn.innerHTML = '复制失败';
            }}
        }}
        
        document.body.removeChild(tempTextArea);
    }}
    </script>
    <button id="{button_id}" onclick="copyToClipboard_{key}()" class="copy-btn">{button_text}</button>
    """
    return components.html(html, height=50)

# --- API 辅助函数 ---
@st.cache_data(ttl=60)
def api_call_cached(method, endpoint, payload=None, headers=None, params=None):
    # 对于缓存的调用，我们直接转发给非缓存版本
    return api_call(method, endpoint, payload, headers, params)

def api_call(method, endpoint, payload=None, headers=None, params=None):
    """统一的 API 请求函数。"""
    url = f"{BACKEND_URL}{endpoint}"
    try:
        if method == 'GET':
            # <<< 修改: requests库会自动处理params的URL编码，非常健壮
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=payload, headers=headers, timeout=10)
        else:
            return None, "Unsupported method"
            
        if 200 <= response.status_code < 300:
            return response.json(), None
        else:
            try:
                error_detail = response.json().get('detail', response.text)
                return None, f"错误 {response.status_code}: {error_detail}"
            except json.JSONDecodeError:
                return None, f"错误 {response.status_code}: {response.text}"
                
    except requests.exceptions.ConnectionError:
        return None, "连接后端失败。请确保后端服务正在运行。"
    except Exception as e:
        return None, f"发生意外错误: {e}"

# --- 签名辅助函数 ---
def create_signed_message(message_dict):
    """构造并签名一个标准消息。"""
    message_dict['timestamp'] = time.time()
    
    signature = sign_message(st.session_state.private_key, message_dict)
    if not signature:
        st.error("签名失败！请检查私钥是否正确。")
        return None
        
    message_json = json.dumps(message_dict, sort_keys=True, ensure_ascii=False)
    
    return {
        "message_json": message_json,
        "signature": signature
    }

# --- 创世用户设置 ---
def show_genesis_setup():
    """显示首次运行时的创世用户注册界面。"""
    st.header("🚀 欢迎使用 FamilyCoin - 首次系统设置")

    if st.session_state.genesis_info:
        data = st.session_state.genesis_info
        st.success(f"🎉 创世用户 '{data['username']}' 创建成功！")
        st.warning("**请立即复制并安全备份你的私钥！** 这是你唯一一次看到它。丢失后无法找回。")
        
        st.text_area("你的公钥 (你的“地址”)", data['public_key'], height=150)
        st.text_area("!! 你的私钥 (你的“密码”) !!", data['private_key'], height=300)
        
        st_copy_to_clipboard_button(data['private_key'], "点此复制私钥", "genesis_pk")
        
        st.info("复制私钥后，请点击下方按钮进入登录界面。")

        if st.button("我已保存私钥，进入登录页面", type="primary"):
            st.session_state.genesis_info = None
            st.session_state.needs_setup = False
            st.rerun()
    else:
        st.info(
            "系统检测到数据库为空，需要创建第一个管理员（创世）用户。\n\n"
            "这个用户将拥有超高的邀请额度，用于邀请第一批成员。"
        )

        with st.form("genesis_form"):
            st.subheader("创建创世用户")
            username = st.text_input("输入创世用户的用户名", "admin")
            
            genesis_password = st.text_input(
                "输入创世密码", 
                type="password",
                help="这是在代码中预设的，用于验证首次操作的密码。"
            )
            
            submitted = st.form_submit_button("创建并初始化系统", type="primary")

            if submitted:
                if not username or not genesis_password:
                    st.error("用户名和创世密码不能为空。")
                else:
                    with st.spinner("正在创建创世用户..."):
                        payload = {
                            "username": username,
                            "genesis_password": genesis_password
                        }
                        data, error = api_call('POST', '/genesis_register', payload=payload)
                        
                        if error:
                            st.error(f"创世用户创建失败: {error}")
                        else:
                            st.session_state.genesis_info = data
                            st.rerun()
                            
# --- 登录和注册视图 ---
def show_login_register():
    st.header("欢迎！")
    
    login_tab, register_tab = st.tabs(["登录", "注册新账户 (需要邀请码)"])

    with login_tab:
        st.subheader("使用私钥登录")
        st.info(" FamilyCoin 不存储你的私钥。请在下方粘贴你的私钥以登录。")
        
        private_key_input = st.text_area("在此处粘贴你的私钥 (PEM 格式)", height=250, key="login_pk_area")
        
        if st.button("登录", type="primary"):
            if not private_key_input:
                st.error("请输入私钥。")
            else:
                public_key = get_public_key_from_private(private_key_input)
                if not public_key:
                    st.error("私钥格式无效。请输入 PKCS8 PEM 格式的私钥。")
                else:
                    # <<< 核心修改 6: 使用 params 字典传递公钥
                    data, error = api_call('GET', "/user/details/", params={"public_key": public_key})
                    if error:
                        st.error(f"登录失败: {error}")
                        if "404" in error:
                            st.warning("提示：公钥未在系统中注册，请先使用邀请码注册。")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.private_key = private_key_input
                        st.session_state.public_key = public_key
                        st.session_state.user_details = data
                        st.session_state.username = data.get('username', '已登录')
                        st.success("登录成功！")
                        st.rerun() 

    with register_tab:
        if st.session_state.new_user_info:
            data = st.session_state.new_user_info
            st.success(f"账户 '{data['username']}' 创建成功！")
            st.warning("🚨 **请立即复制并安全备份你的私钥！** 🚨\n\n这是你唯一一次看到它。丢失后，你的资产将**永久无法找回**。")
            
            st.text_area("你的公钥 (你的“地址”)", data['public_key'], height=150, disabled=True)
            st.text_area("‼️ 你的私钥 (你的“密码”) ‼️", data['private_key'], height=300, disabled=True)
            
            st_copy_to_clipboard_button(data['private_key'], "点此一键复制私钥", "reg_pk")
            
            st.info("请确保已将私钥保存在安全的地方（如密码管理器）。")

            if st.button("我已复制并妥善保管私钥，立即登录", type="primary"):
                st.session_state.logged_in = True
                st.session_state.private_key = data['private_key']
                st.session_state.public_key = data['public_key']
                st.session_state.username = data['username']
                
                with st.spinner("正在完成登录..."):
                    # <<< 核心修改 7: 使用 params 字典传递公钥
                    details, details_error = api_call('GET', "/user/details/", params={"public_key": data['public_key']})
                    if details_error:
                        st.error(f"自动登录时获取详情失败: {details_error}")
                        st.info("不过别担心，你已经登录了。请稍后手动刷新数据。")
                        time.sleep(2)
                    else:
                        st.session_state.user_details = details
                
                st.session_state.new_user_info = None
                st.rerun()
        else:
            # ... (注册表单部分不变，省略)
            st.subheader("注册新账户")
            with st.form("register_form"):
                username = st.text_input("输入你的用户名 (3-15个字符)", key="reg_username", max_chars=15)
                invitation_code = st.text_input("输入你的邀请码", key="reg_inv_code", help="邀请码不区分大小写")
                
                submitted = st.form_submit_button("注册")

                if submitted:
                    if not username or len(username) < 3:
                        st.error("请输入至少3个字符的用户名。")
                    elif not invitation_code:
                        st.error("请输入邀请码。")
                    else:
                        with st.spinner("正在创建账户..."):
                            payload = {'username': username, 'invitation_code': invitation_code}
                            data, error = api_call('POST', '/register', payload=payload)
                            
                            if error:
                                st.error(f"注册失败: {error}")
                            else:
                                st.session_state.new_user_info = data
                                st.rerun()

# --- 数据获取辅助函数 ---

def get_user_details(force_refresh=False):
    """获取并缓存当前用户的详细信息。"""
    if not force_refresh and st.session_state.user_details:
        return st.session_state.user_details
            
    # <<< 核心修改 8: 使用 params 字典传递公钥
    data, error = api_call('GET', "/user/details/", params={"public_key": st.session_state.public_key})
    if error:
        st.error(f"无法获取用户详情: {error}")
        if "404" in error: 
            st.warning("你的会话可能已失效或账户被禁用，请重新登录。")
            st.session_state.clear()
            st.rerun()
        return None
    st.session_state.user_details = data
    return data

def get_all_users_dict(force_refresh=False):
    """获取所有用户的 {username: public_key} 字典。"""
    now = time.time()
    if not force_refresh and st.session_state.all_users_cache and (now - st.session_state.all_users_cache_time < 60):
        return st.session_state.all_users_cache
        
    data, error = api_call('GET', '/users/list')
    if error:
        st.error(f"无法获取用户列表: {error}")
        return {}
        
    user_dict = {user['username']: user['public_key'] for user in data.get('users', [])}
    st.session_state.all_users_cache = user_dict
    st.session_state.all_users_cache_time = now
    return user_dict

def format_dt(timestamp):
    """格式化UTC时间戳为本地时间字符串。"""
    if not timestamp: return "N/A"
    return datetime.fromtimestamp(timestamp, TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')

# --- 主应用视图 (登录后) ---
def show_main_app():
    details = get_user_details()
    if not details: # 如果获取失败，停止渲染
        return

    # ... (欢迎语部分不变，省略)
    if details and details.get('tx_count', 0) == 0 and details.get('invited_by') != 'GENESIS':
        st.warning(
            "👋 **欢迎新朋友！** 你的账户已成功创建，但请务必再次确认你已经**安全备份了你的私钥**。"
            "你可以随时从侧边栏的“显示我的私钥”中找到它并复制。"
            "**私钥一旦丢失，资产将永久无法找回！**", 
            icon="🎉"
        )

    # --- 侧边栏 ---
    with st.sidebar:
        st.header(f"你好, {st.session_state.username}!")
        
        if st.button("🔄 刷新数据"):
            st.cache_data.clear() 
            st.session_state.all_users_cache = None 
            st.session_state.user_details = None 
            st.rerun()

        if details:
            st.subheader("我的邀请")
            st.metric("剩余邀请次数", details.get('invitation_quota', 0))

            if st.button("生成新邀请码", type="primary"):
                # ... (生成邀请码逻辑不变，省略)
                if details.get('invitation_quota', 0) <= 0:
                    st.error("邀请额度不足！")
                else:
                    with st.spinner("正在生成邀请码..."):
                        msg_dict = {"owner_key": st.session_state.public_key}
                        signed_payload = create_signed_message(msg_dict)
                        
                        if signed_payload:
                            data, error = api_call('POST', '/user/generate_invitation', payload=signed_payload)
                            if error:
                                st.error(f"生成失败: {error}")
                            else:
                                st.success(f"生成成功！新邀请码: {data.get('code')}")
                                st.cache_data.clear()
                                st.session_state.user_details = None 
                                st.rerun()

            with st.expander("显示我未使用的邀请码"):
                # <<< 核心修改 9: 使用 params 字典传递公钥
                codes_data, error = api_call_cached('GET', "/user/my_invitations/", params={"public_key": st.session_state.public_key})
                if error:
                    st.error(f"无法加载邀请码: {error}")
                elif not codes_data or not codes_data.get('codes'):
                    st.info("没有可用的邀请码。")
                else:
                    codes_list = [c['code'] for c in codes_data['codes']]
                    st.text_area("可用的邀请码", "\n".join(codes_list), height=100, disabled=True)
        # ... (侧边栏剩余部分不变，省略)
        st.subheader("我的公钥 (地址)")
        st.text_area("Public Key", st.session_state.public_key, height=150, disabled=True, key="sidebar_pubkey")
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(st.session_state.public_key)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf, caption="我的收款码", use_container_width=True)

        with st.expander("显示我的私钥"):
            st.warning("不要泄露你的私钥！")
            st.text_area("Private Key", st.session_state.private_key, height=250, disabled=True, key="sidebar_privkey")
            st_copy_to_clipboard_button(st.session_state.private_key, "复制私钥", "sidebar_pk")
        
        if st.button("退出登录"):
            st.session_state.clear() 
            st.success("您已退出登录。")
            time.sleep(1)
            st.rerun()
            
    # --- 主导航 ---
    is_admin = details and details.get('invited_by') == 'GENESIS'
    # <<< NFT 架构升级: 在主导航中增加“我的收藏” >>>
    tabs_list = ["我的钱包", "转账", "🛒 商店", "🖼️ 我的收藏"]
    
    if is_admin:
        tabs_list.append("⭐ 管理员 ⭐")
    
    tabs = st.tabs(tabs_list)

    # --- 1. 钱包视图 ---
    with tabs[0]:
        st.header("我的钱包")
        col1, col2, col3 = st.columns(3)
        
        # <<< 核心修改 10: 使用 params 字典传递公钥
        balance_data, error = api_call_cached('GET', "/balance/", params={"public_key": st.session_state.public_key})
        balance = 0.0
        if error:
            st.error(f"无法获取余额: {error}")
        else:
            balance = balance_data.get('balance', 0.0)
        col1.metric(label="当前余额", value=f"{balance:,.2f} FC")
        
        if details:
            col2.metric(label="总交易次数", value=details.get('tx_count', 0))
            col3.metric(label="邀请人", value=details.get('inviter_username', 'N/A'))
            st.caption(f"注册于: {format_dt(details.get('created_at'))}")
        
        st.divider()
        st.subheader("交易历史")
        
        # <<< 核心修改 11: 使用 params 字典传递公钥
        history_data, error = api_call_cached('GET', "/history/", params={"public_key": st.session_state.public_key})
        if error:
            st.error(f"无法获取交易历史: {error}")
        elif not history_data or not history_data.get('transactions'):
            st.info("没有交易记录。")
        else:
            df = pd.DataFrame(history_data['transactions'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
            df['方向'] = df['type'].apply(lambda x: "支出 📤" if x == 'out' else "收入 📥")
            df['对方'] = df.apply(lambda row: row['to_display'] if row['type'] == 'out' else row['from_display'], axis=1)
            df['金额'] = df.apply(lambda row: f"- {row['amount']:,.2f}" if row['type'] == 'out' else f"+ {row['amount']:,.2f}", axis=1)
            df['时间'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df['备注'] = df['note'].fillna('')
            st.dataframe(df[['时间', '方向', '对方', '金额', '备注']], use_container_width=True, hide_index=True)

    # --- 2. 转账视图 ---
    with tabs[1]:
        st.header("发起转账")
        
        user_dict = get_all_users_dict()
        my_username = st.session_state.username
        if my_username in user_dict:
            del user_dict[my_username]
        
        user_options = [""] + sorted(list(user_dict.keys()))
        
        with st.form("send_form"):
            selected_username = st.selectbox("选择收款人", options=user_options, index=0)
            amount = st.number_input("转账金额", min_value=0.01, step=0.01, format="%.2f")
            note = st.text_input("备注 (可选, 最多50字符)", max_chars=50)
            to_key = user_dict.get(selected_username, "") if selected_username else ""
            st.caption("手动粘贴公钥 (如果对方不在列表中或用于精确输入)")
            manual_to_key = st.text_area("收款方公钥", value=to_key, height=150)
            
            submitted = st.form_submit_button("签名并发送", type="primary")

            if submitted:
                if not manual_to_key or amount <= 0:
                    st.error("请输入有效的收款人公钥和金额。")
                else:
                    with st.spinner("正在签名并提交交易..."):
                        message_dict = {
                            "from_key": st.session_state.public_key,
                            "to_key": manual_to_key,
                            "amount": amount,
                            "note": note
                        }
                        signed_payload = create_signed_message(message_dict)
                        if signed_payload:
                            data, error = api_call('POST', '/transaction', payload=signed_payload)
                            if error:
                                st.error(f"转账失败: {error}")
                            else:
                                st.success(f"转账成功！详情: {data.get('detail')}")
                                st.balloons()
                                st.cache_data.clear()
                                st.session_state.user_details = None

    # --- 3. 商店视图 ---
    with tabs[2]:
        st.header("🛒 商店")
        shop_browse_tab, shop_post_tab, shop_my_items_tab = st.tabs(["浏览市场", "发布商品", "我的商品"])
        
        with shop_browse_tab:
            # ... (商店浏览部分不变，省略)
            st.subheader("市场上的商品")
            col_sale, col_wanted = st.columns(2)
            with col_sale:
                st.info("其他人正在出售 (点击购买)")
                items_data, error = api_call_cached(
                    'GET', '/shop/list', 
                    params={'item_type': 'FOR_SALE', 'exclude_owner': st.session_state.public_key}
                )
                if error:
                    st.error(f"无法加载待售商品: {error}")
                elif not items_data or not items_data.get('items'):
                    st.write("目前没有人在出售商品。")
                else:
                    for item in items_data['items']:
                        item_id = item['item_id']
                        with st.container(border=True):
                            st.write(f"**{item['description']}**")
                            st.write(f"价格: **{item['price']} FC** | 卖家: {item['username']}")
                            if st.button(f"购买", key=f"buy_{item_id}", type="primary"):
                                if balance < item['price']:
                                    st.error("你的余额不足以购买此商品！")
                                else:
                                    with st.spinner("正在准备购买..."):
                                        tx_message = {
                                            "from_key": st.session_state.public_key,
                                            "to_key": item['owner_key'],
                                            "amount": item['price'],
                                            "note": f"购买商品: {item['description'][:20]}..."
                                        }
                                        signed_tx = create_signed_message(tx_message)
                                        if signed_tx:
                                            buy_payload = {
                                                "item_id": item_id,
                                                "transaction_message_json": signed_tx['message_json'],
                                                "transaction_signature": signed_tx['signature']
                                            }
                                            data, error = api_call('POST', '/shop/buy', payload=buy_payload)
                                            if error:
                                                st.error(f"购买失败: {error}")
                                            else:
                                                st.success(f"购买成功！{data.get('detail')}")
                                                st.balloons()
                                                st.cache_data.clear() 
                                                st.session_state.user_details = None
                                                st.rerun()

            with col_wanted:
                st.info("其他人正在求购")
                items_data, error = api_call_cached(
                    'GET', '/shop/list',
                    params={'item_type': 'WANTED', 'exclude_owner': st.session_state.public_key}
                )
                if error:
                    st.error(f"无法加载求购商品: {error}")
                elif not items_data or not items_data.get('items'):
                    st.write("目前没有人发布求购信息。")
                else:
                    for item in items_data['items']:
                        item_id = item['item_id']
                        with st.container(border=True):
                            st.write(f"**{item['description']}**")
                            st.write(f"出价: **{item['price']} FC** | 买家: {item['username']}")
                            if st.button("向他出售", key=f"sell_{item_id}", type="primary"):
                                with st.spinner("正在完成交易..."):
                                    message_dict = {
                                        "owner_key": st.session_state.public_key, 
                                        "item_id": item_id
                                    }
                                    signed_payload = create_signed_message(message_dict)
                                    if signed_payload:
                                        data, error = api_call('POST', '/shop/fulfill_wanted', payload=signed_payload)
                                        if error:
                                            st.error(f"出售失败: {error}")
                                        else:
                                            st.success(f"成功！{data.get('detail')}")
                                            st.balloons()
                                            st.cache_data.clear()
                                            st.session_state.user_details = None
                                            st.rerun()

        with shop_post_tab:
            st.subheader("发布一个新商品")
            with st.form("post_item_form"):
                item_type = st.radio("你想做什么?", ["出售商品", "求购商品"], 
                                     captions=["我有东西，想换FC", "我有FC，想换东西"])
                item_type_val = 'FOR_SALE' if item_type == "出售商品" else 'WANTED'
                description = st.text_area("商品/服务描述", max_chars=100)
                price = st.number_input("价格 (FC)", min_value=0.01, step=0.01, format="%.2f")
                submitted = st.form_submit_button("签名并发布")
                if submitted:
                    if not description or price <= 0:
                        st.error("请输入有效的描述和价格。")
                    else:
                        with st.spinner("正在签名并发布..."):
                            message_dict = {
                                "owner_key": st.session_state.public_key,
                                "item_type": item_type_val,
                                "description": description,
                                "price": price
                            }
                            signed_payload = create_signed_message(message_dict)
                            if signed_payload:
                                data, error = api_call('POST', '/shop/post', payload=signed_payload)
                                if error:
                                    st.error(f"发布失败: {error}")
                                else:
                                    st.success(f"发布成功！{data.get('detail')}")
                                    st.cache_data.clear() 

        with shop_my_items_tab:
            st.subheader("我发布的商品")
            # <<< 核心修改 12: 使用 params 字典传递公钥
            items_data, error = api_call_cached('GET', "/shop/my_items/", params={"public_key": st.session_state.public_key})
            if error:
                st.error(f"无法加载我的商品: {error}")
            # ... (商店我的商品，剩余部分不变，省略)
            elif not items_data or not items_data.get('items'):
                st.info("你没有发布过任何商品。")
            else:
                st.write("在这里你可以管理你发布的商品。")
                for item in items_data['items']:
                    item_id = item['item_id']
                    status = item['status']
                    with st.container(border=True):
                        st.write(f"**{item['description']}** ({item['item_type'].replace('_', ' ').title()})")
                        st.write(f"价格: **{item['price']} FC** | 状态: **{status}**")
                        if status == 'ACTIVE':
                            if st.button("取消发布", key=f"cancel_{item_id}"):
                                with st.spinner("正在取消..."):
                                    message_dict = {
                                        "owner_key": st.session_state.public_key,
                                        "item_id": item_id,
                                    }
                                    signed_payload = create_signed_message(message_dict)
                                    if signed_payload:
                                        data, error = api_call('POST', '/shop/cancel', payload=signed_payload)
                                        if error:
                                            st.error(f"取消失败: {error}")
                                        else:
                                            st.success(f"取消成功！{data.get('detail')}")
                                            st.cache_data.clear() 
                                            st.rerun()
    # --- 4. 收藏视图 ---
    # <<< NFT 架构升级: 新增“我的收藏”视图 >>>
    with tabs[3]: # 我的收藏
        st.header("🖼️ 我的收藏 (NFTs)")
        st.info("这里展示你拥有的所有独特的数字藏品。")

        balance_data, _ = api_call_cached('GET', "/balance/", params={"public_key": st.session_state.public_key})
        balance = balance_data.get('balance', 0.0) if balance_data else 0.0

        nfts_data, error = api_call_cached('GET', '/nfts/my/', params={"public_key": st.session_state.public_key})

        if error:
            st.error(f"无法加载你的收藏: {error}")
        elif not nfts_data or not nfts_data.get('nfts'):
            st.info("你的收藏还是空的，快去让管理员给你发行一些吧！")
        else:
            # 遍历所有NFT
            for nft in nfts_data['nfts']:
                with st.container(border=True):
                    # 只需要调用统一的渲染入口函数，不再需要if/elif判断！
                    # 我们将 create_signed_message 函数也作为参数传进去
                    render_nft(
                        st, 
                        nft, 
                        balance, 
                        api_call, 
                        lambda msg: create_signed_message(msg)
                    )
                                
    # --- 5. 管理员视图 ---
    if is_admin:
        with tabs[4]:
            st.header("管理员面板")
            # ... (解锁逻辑不变)
            if not st.session_state.admin_ui_unlocked:
                st.info("这是一个轻量级的UI锁，防止误操作。")
                with st.form("admin_unlock_form"):
                    admin_pwd = st.text_input("请输入管理员UI密码", type="password", key="admin_ui_pwd_form")
                    if st.form_submit_button("解锁"):
                        if admin_pwd == ADMIN_UI_PASSWORD:
                            st.session_state.admin_ui_unlocked = True
                            st.rerun() 
                        else:
                            st.error("密码错误")
            else:
                st.success("管理员UI已解锁。")
                if st.button("锁定UI"):
                    st.session_state.admin_ui_unlocked = False
                    st.rerun()

                st.warning("你正在进行管理员操作。真正的API安全由后端的 Admin Secret 保证。")
                admin_secret = st.text_input("请输入你的后端 Admin Secret", type="password", key="admin_secret_input")
                
                if not admin_secret:
                    st.info("请输入 Admin Secret (在 backend/main.py 中设置) 以启用操作。")
                else:
                    admin_headers = {"X-Admin-Secret": admin_secret}
                    user_dict = get_all_users_dict(force_refresh=True) 
                    user_options = sorted(list(user_dict.keys()))
                    admin_tabs_list = ["货币发行", "用户管理", "💎 NFT 管理", "系统设置"]
                    admin_issue_tab, admin_manage_tab, admin_nft_tab, admin_settings_tab = st.tabs(admin_tabs_list)
                    
                    # ... (货币发行 Tab 不变)
                    with admin_issue_tab:
                        st.subheader("增发货币 (Mint)")
                        with st.form("mint_form"):
                            selected_username = st.selectbox("选择目标用户", options=[""] + user_options, key="admin_mint_user")
                            mint_to_key = user_dict.get(selected_username, "") if selected_username else ""
                            mint_to_key_input = st.text_area("目标公钥", value=mint_to_key, height=150, placeholder="选择用户后自动填充，或手动粘贴...")
                            mint_amount = st.number_input("发行金额", min_value=1.0, step=1.0)
                            mint_note = st.text_input("备注 (可选)")
                            if st.form_submit_button("确认发行 (单人)", type="primary"):
                                payload = {"to_key": mint_to_key_input, "amount": mint_amount, "note": mint_note}
                                data, error = api_call('POST', '/admin/issue', payload=payload, headers=admin_headers)
                                if error: st.error(f"发行失败: {error}")
                                else: st.success(f"发行成功！{data.get('detail')}")
    
                        st.divider()
                        st.subheader("批量增发货币")
                        with st.form("multi_mint_form"):
                            selected_users = st.multiselect("选择目标用户 (可多选)", options=user_options, key="admin_multi_mint_users")
                            multi_amount = st.number_input("统一发行金额", min_value=1.0, step=1.0)
                            multi_note = st.text_input("备注 (可选)")
                            if st.form_submit_button("确认发行 (批量)", type="primary"):
                                targets = [{"key": user_dict.get(u), "amount": multi_amount} for u in selected_users if u in user_dict]
                                if not targets:
                                    st.warning("请至少选择一个用户。")
                                else:
                                    payload = {"targets": targets, "note": multi_note}
                                    data, error = api_call('POST', '/admin/multi_issue', payload=payload, headers=admin_headers)
                                    if error: st.error(f"批量发行失败: {error}")
                                    else: st.success(f"批量发行完成！{data.get('detail')}")

                    with admin_manage_tab:
                        st.subheader("用户管理")
                        manage_user = st.selectbox("选择要管理的用户", options=[""] + user_options, key="admin_manage_user")
                        if manage_user:
                            target_key = user_dict[manage_user]
                            st.info(f"正在管理: **{manage_user}** (`{target_key[:15]}...`)")
                            
                            # ... (减持和额度调整不变)
                            st.write("**减持货币 (Burn)**")
                            with st.form("burn_form"):
                                burn_amount = st.number_input("减持金额", min_value=0.01, step=1.0)
                                burn_note = st.text_input("减持备注 (必填)", max_chars=50)
                                if st.form_submit_button("确认减持", type="primary"):
                                    if not burn_note:
                                        st.error("必须填写减持备注。")
                                    else:
                                        payload = {"from_key": target_key, "amount": burn_amount, "note": burn_note}
                                        data, error = api_call('POST', '/admin/burn', payload=payload, headers=admin_headers)
                                        if error: st.error(f"减持失败: {error}")
                                        else: st.success(f"减持成功！{data.get('detail')}")
                            st.divider()
                            st.write("**调整邀请额度**")
                            with st.form("adjust_quota_form"):
                                new_quota = st.number_input("设置新的邀请额度", min_value=0, step=1)
                                if st.form_submit_button("确认调整"):
                                    payload = {"public_key": target_key, "new_quota": new_quota}
                                    data, error = api_call('POST', '/admin/adjust_quota', payload=payload, headers=admin_headers)
                                    if error: st.error(f"调整失败: {error}")
                                    else: st.success(f"调整成功！{data.get('detail')}")
                            st.divider()

                            st.write("**禁用/启用用户**")
                            # <<< 核心修改 13: 使用 params 字典传递公钥
                            is_active_data, error = api_call('GET', "/user/details/", params={"public_key": target_key})
                            is_active = is_active_data.get('is_active', True) if is_active_data else True

                            if is_active:
                                st.warning(f"用户 {manage_user} 当前是**活跃**状态。禁用后对方将无法登录。")
                                if st.button(f"禁用用户 {manage_user}", type="secondary"):
                                    payload = {"public_key": target_key, "is_active": False}
                                    data, error = api_call('POST', '/admin/set_user_active_status', payload=payload, headers=admin_headers)
                                    if error: st.error(f"禁用失败: {error}")
                                    else: st.success(f"禁用成功！{data.get('detail')}"); st.rerun()
                            else:
                                st.info(f"用户 {manage_user} 当前是**禁用**状态。")
                                if st.button(f"重新启用用户 {manage_user}"):
                                    payload = {"public_key": target_key, "is_active": True}
                                    data, error = api_call('POST', '/admin/set_user_active_status', payload=payload, headers=admin_headers)
                                    if error: st.error(f"启用失败: {error}")
                                    else: st.success(f"启用成功！{data.get('detail')}"); st.rerun()

                            # ... (清除用户部分不变)
                            st.divider()
                            st.write("**彻底清除用户 (极度危险)**")
                            st.error("警告：此操作将从数据库中**彻底删除**该用户、其余额、商店物品和邀请码。用户名将被释放。此操作无法撤销！")
                            if st.checkbox(f"我确认要**彻底删除**用户 {manage_user} 及其所有数据", key="purge_confirm"):
                                confirmation_text = st.text_input(f"请输入用户名 '{manage_user}' 以确认删除：")
                                if st.button("彻底清除此用户 (不可逆)", type="primary"):
                                    if confirmation_text != manage_user:
                                        st.error("确认文本不匹配！")
                                    else:
                                        with st.spinner(f"正在彻底清除 {manage_user}..."):
                                            payload = {"public_key": target_key}
                                            data, error = api_call('POST', '/admin/purge_user', payload=payload, headers=admin_headers)
                                            if error: st.error(f"清除失败: {error}")
                                            else: 
                                                st.success(f"清除成功！{data.get('detail')}")
                                                st.cache_data.clear() 
                                                st.rerun()

                            # 核心修改 1: (新增UI) 增加查询用户私钥的功能
                            st.divider()
                            st.write("**查询用户私钥 (高风险操作)**")
                            st.error("警告：此操作将会在界面上显示用户的私钥。请确保在安全的环境下操作，不要截图或分享。")

                            if st.button(f"查询用户 '{manage_user}' 的私钥"):
                                with st.spinner("正在向后端请求私钥..."):
                                    params = {"public_key": target_key}
                                    data, error = api_call('GET', '/admin/private_key/', params=params, headers=admin_headers)

                                    if error:
                                        st.error(f"查询私钥失败: {error}")
                                        if 'retrieved_private_key' in st.session_state:
                                            del st.session_state['retrieved_private_key']
                                    else:
                                        st.session_state.retrieved_private_key = {
                                            'public_key': target_key,
                                            'username': manage_user,
                                            'private_key': data.get('private_key')
                                        }
                                        st.rerun() 
                            
                            if 'retrieved_private_key' in st.session_state and st.session_state.retrieved_private_key['public_key'] == target_key:
                                retrieved_data = st.session_state.retrieved_private_key
                                st.success(f"已成功获取用户 '{retrieved_data['username']}' 的私钥：")
                                st.text_area(
                                    "用户私钥",
                                    retrieved_data['private_key'],
                                    height=300,
                                    disabled=True,
                                    key=f"retrieved_pk_{target_key}"
                                )
                                st_copy_to_clipboard_button(
                                    retrieved_data['private_key'],
                                    "点此复制该私钥",
                                    f"copy_retrieved_pk_{target_key}"
                                )
                    
                    # <<< 插件V2.0: 修改 NFT 管理标签页 UI >>>
                    with admin_nft_tab:
                        st.subheader("💎 NFT 铸造与发行")
                        
                        nft_types, error = api_call_cached('GET', '/admin/nft/types', headers=admin_headers)
                        if error:
                            st.error(f"无法获取 NFT 类型: {error}")
                            nft_type_options = []
                        else:
                            nft_type_options = nft_types

                        with st.form("mint_nft_form"):
                            st.info("在这里，你可以为系统中的任何用户铸造一个新的、独一无二的数字资产。")
                            
                            selected_username = st.selectbox("选择接收用户", options=[""] + user_options, key="admin_mint_nft_user")
                            mint_to_key = user_dict.get(selected_username, "") if selected_username else ""
                            mint_to_key_input = st.text_area("目标公钥", value=mint_to_key, height=100)
                            
                            selected_nft_type = st.selectbox("选择要铸造的 NFT 类型", options=nft_type_options)
                            
                            st.write("**输入该类型 NFT 所需的初始数据 (JSON 格式):**")
                            
                            # --- <<< 移除硬编码的 IF/ELSE 块 >>> ---
                            # 动态获取所选类型的帮助信息和默认值
                            mint_info = get_mint_info_for_type(selected_nft_type)
                            
                            if mint_info["help_text"]:
                                st.help(mint_info["help_text"])
                                
                            initial_data_str = st.text_area(
                                "初始数据", 
                                mint_info["default_json"],
                                height=150
                            )
                            # --- <<< 动态加载结束 >>> ---

                            if st.form_submit_button("确认铸造", type="primary"):
                                if not mint_to_key_input or not selected_nft_type:
                                    st.error("请选择用户和 NFT 类型。")
                                else:
                                    try:
                                        initial_data = json.loads(initial_data_str)
                                        payload = {
                                            "to_key": mint_to_key_input,
                                            "nft_type": selected_nft_type,
                                            "data": initial_data
                                        }
                                        data, error = api_call('POST', '/admin/nft/mint', payload=payload, headers=admin_headers)
                                        if error:
                                            st.error(f"NFT 铸造失败: {error}")
                                        else:
                                            st.success(f"NFT 铸造成功！{data.get('detail')}")
                                            st.balloons()
                                    except json.JSONDecodeError:
                                        st.error("初始数据不是有效的 JSON 格式！") 
                                         
                    # ... (系统设置和监控中心 Tab 不变)
                    with admin_settings_tab:
                        st.subheader("系统设置")
                        st.write("**邀请系统设置**")
                        current_quota = 5 
                        setting_data, error = api_call('GET', '/admin/setting/default_invitation_quota', headers=admin_headers)
                        if error:
                            if "404" not in error:
                                st.warning(f"无法获取当前邀请额度设置: {error}。将使用默认值 5。")
                        else:
                            current_quota = int(setting_data.get('value', 5))
                        with st.form("set_quota_form"):
                            new_default_quota = st.number_input("新用户默认邀请额度", min_value=0, value=int(current_quota))
                            if st.form_submit_button("更新全局设置"):
                                payload = {"key": "default_invitation_quota", "value": str(new_default_quota)}
                                data, error = api_call('POST', '/admin/set_setting', payload=payload, headers=admin_headers)
                                if error: st.error(f"更新失败: {error}")
                                else: st.success(f"更新成功！{data.get('detail')}")

                        st.divider()
                        st.subheader("危险区域")
                        st.error("警告：以下操作将立即删除所有数据并重置系统！")
                        with st.form("nuke_system_form"):
                            st.write("此操作将删除服务器上的 `ledger.db` 文件并重启服务，所有人（包括管理员）都将被登出，系统将返回到初始设置状态。")
                            nuke_confirm = st.text_input("请输入 `NUKE ALL DATA` 确认：")
                            if st.form_submit_button("重置系统 (!!!)", type="primary"):
                                if nuke_confirm == "NUKE ALL DATA":
                                    with st.spinner("正在发送重置信号..."):
                                        data, error = api_call('POST', '/admin/nuke_system', payload={}, headers=admin_headers)
                                        if error:
                                            st.error(f"重置失败: {error}")
                                        else:
                                            st.success(f"重置成功！{data.get('detail')} 正在刷新...")
                                            time.sleep(2)
                                            st.session_state.clear()
                                            st.rerun()
                                else:
                                    st.error("确认文本不匹配！")

                        st.divider()
                        st.subheader("监控中心 (Ledger)")
                        if st.button("查询所有用户余额 (包含已禁用)"):
                            data, error = api_call('GET', '/admin/balances', headers=admin_headers)
                            if error:
                                st.error(f"查询失败: {error}")
                            elif not data or not data.get('balances'):
                                st.info("账本为空。")
                            else:
                                st.success("查询成功！")
                                df = pd.DataFrame(data['balances'])
                                display_columns = {
                                    'username': '用户名', 'balance': '余额', 'invitation_quota': '剩余邀请',
                                    'inviter_username': '邀请人', 'is_active': '是否活跃', 'public_key': '公钥'
                                }
                                existing_columns = [col for col in display_columns.keys() if col in df.columns]
                                df_display = df[existing_columns].rename(columns=display_columns)
                                st.dataframe(df_display, use_container_width=True, hide_index=True)


# --- 主逻辑：根据系统和登录状态显示不同视图 ---
def main():
    if st.session_state.needs_setup is None:
        with st.spinner("正在连接后端，请稍候..."):
            status_data, error = api_call('GET', '/status')
            if error:
                st.error(f"无法连接到后端服务: {error}")
                st.warning("请确保后端容器已启动并运行在正确的地址。")
                st.stop() 
            else:
                st.session_state.needs_setup = status_data.get('needs_setup', False)
                st.rerun()

    if st.session_state.needs_setup:
        show_genesis_setup()
    elif not st.session_state.logged_in:
        show_login_register()
    else:
        show_main_app()

if __name__ == "__main__":
    main()