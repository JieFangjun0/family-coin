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
# 导入统一的渲染路由函数
from frontend.nft_renderers import render_nft, get_mint_info_for_type
import random

# --- 配置 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEZONE = pytz.timezone('Asia/Shanghai')
ADMIN_UI_PASSWORD = os.getenv("ADMIN_UI_PASSWORD", "j")

st.set_page_config(page_title="FamilyCoin V1.0", layout="wide")
st.title("🪙 FamilyCoin V1.0 (家庭币)")
st.caption(f"一个带邀请制和商店的中心化货币系统。（仅供娱乐！）")

@st.cache_data(ttl=3600) # 缓存一小时，因为这个数据不常变
def get_nft_display_names():
    """获取所有NFT类型的中文显示名称映射。"""
    data, error = api_call('GET', '/nfts/display_names')
    if error:
        # st.warning(f"无法加载NFT显示名称: {error}") # 生产环境可注释掉
        return {}
    return data
def init_session_state():
    """初始化会话状态"""
    defaults = {
        'logged_in': False,
        'private_key': "",
        'public_key': "",
        'username': "",
        'uid': "",
        'admin_secret': "",
        'admin_ui_unlocked': False,
        'user_details': None,
        'all_users_cache': None,
        'all_users_cache_time': 0,
        'needs_setup': None,
        'new_user_info': None,
        'genesis_info': None,
        'viewing_profile_of': None,
        'active_tab': "我的钱包", # <<< BUG修复 #2: 新增Tab状态
        'login_form_active': True # <<< BUG修复 #4: 新增登录/注册切换状态
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
    return api_call(method, endpoint, payload, headers, params)

def api_call(method, endpoint, payload=None, headers=None, params=None):
    """统一的 API 请求函数。"""
    url = f"{BACKEND_URL}{endpoint}"
    try:
        if method == 'GET':
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

                            
# --- 登录和注册视图 ---
def show_genesis_setup():
    """显示首次运行时的创世用户注册界面。"""
    st.header("🚀 欢迎使用 FamilyCoin - 首次系统设置")

    if st.session_state.genesis_info:
        data = st.session_state.genesis_info
        st.success(f"🎉 创世管理员 '{data['username']}' (UID: {data['uid']}) 创建成功！")
        
        # --- (核心修改：调整措辞，强调特殊性) ---
        st.error(
            "**⚠️ 关键步骤：备份管理员私钥**\n\n"
            "作为系统的第一个用户（管理员），你的所有特权操作都将由这个专属私钥签名。"
            "**这是你唯一一次看到它，请务必将其复制并保存在安全的地方（如密码管理器中）！**"
            "普通用户不会进行此操作。"
        )
        
        st.text_area("管理员公钥", data['public_key'], height=150)
        st.text_area("‼️ 管理员私钥 (最高权限) ‼️", data['private_key'], height=300)
        
        st_copy_to_clipboard_button(data['private_key'], "点此复制管理员私钥", "genesis_pk")
        
        st.info("备份私钥后，你未来将使用刚才设置的 **用户名和密码** 登录。")

        if st.button("我已安全备份私钥，进入登录页面", type="primary"):
            # 清理会话状态，准备登录
            st.session_state.genesis_info = None
            st.session_state.needs_setup = False
            st.rerun()
    else:
        # ... (表单部分代码不变) ...
        st.info(
            "系统检测到数据库为空，需要创建第一个管理员（创世）用户。\n\n"
            "这个用户将拥有超高的邀请额度，用于邀请第一批成员。"
        )

        with st.form("genesis_form"):
            st.subheader("创建创世用户")
            username = st.text_input("输入创世用户的用户名", "admin")
            password = st.text_input("设置创世用户的登录密码", type="password")
            
            genesis_password = st.text_input(
                "输入创世密钥",
                type="password",
                help="这是在 docker-compose.yml 中预设的，用于验证首次操作的密码。"
            )
            
            submitted = st.form_submit_button("创建并初始化系统", type="primary")

            if submitted:
                if not username or not genesis_password or not password:
                    st.error("所有字段均不能为空。")
                elif len(password) < 6:
                    st.error("登录密码至少需要6个字符。")
                else:
                    with st.spinner("正在创建创世用户..."):
                        payload = {
                            "username": username,
                            "password": password,
                            "genesis_password": genesis_password
                        }
                        data, error = api_call('POST', '/genesis_register', payload=payload)
                        
                        if error:
                            st.error(f"创世用户创建失败: {error}")
                        else:
                            st.session_state.genesis_info = data
                            st.rerun()
# jiefangjun0/family-coin/family-coin-6dc61cd34e5cf7dc15f5e541ca075beebc57db7f/frontend/app.py

# ... (其他代码不变) ...

# --- 创世用户设置 ---
def show_genesis_setup():
    """显示首次运行时的创世用户注册界面。"""
    st.header("🚀 欢迎使用 FamilyCoin - 首次系统设置")

    if st.session_state.genesis_info:
        data = st.session_state.genesis_info
        st.success(f"🎉 创世管理员 '{data['username']}' (UID: {data['uid']}) 创建成功！")
        
        # --- (核心修改：调整措辞，强调特殊性) ---
        st.error(
            "**⚠️ 关键步骤：备份管理员私钥**\n\n"
            "作为系统的第一个用户（管理员），你的所有特权操作都将由这个专属私钥签名。"
            "**这是你唯一一次看到它，请务必将其复制并保存在安全的地方（如密码管理器中）！**"
            "普通用户不会进行此操作。"
        )
        
        st.text_area("管理员公钥", data['public_key'], height=150)
        st.text_area("‼️ 管理员私钥 (最高权限) ‼️", data['private_key'], height=300)
        
        st_copy_to_clipboard_button(data['private_key'], "点此复制管理员私钥", "genesis_pk")
        
        st.info("备份私钥后，你未来将使用刚才设置的 **用户名和密码** 登录。")

        if st.button("我已安全备份私钥，进入登录页面", type="primary"):
            # 清理会话状态，准备登录
            st.session_state.genesis_info = None
            st.session_state.needs_setup = False
            st.rerun()
    else:
        # ... (表单部分代码不变) ...
        st.info(
            "系统检测到数据库为空，需要创建第一个管理员（创世）用户。\n\n"
            "这个用户将拥有超高的邀请额度，用于邀请第一批成员。"
        )

        with st.form("genesis_form"):
            st.subheader("创建创世用户")
            username = st.text_input("输入创世用户的用户名", "admin")
            password = st.text_input("设置创世用户的登录密码", type="password")
            
            genesis_password = st.text_input(
                "输入创世密钥",
                type="password",
                help="这是在 docker-compose.yml 中预设的，用于验证首次操作的密码。"
            )
            
            submitted = st.form_submit_button("创建并初始化系统", type="primary")

            if submitted:
                if not username or not genesis_password or not password:
                    st.error("所有字段均不能为空。")
                elif len(password) < 6:
                    st.error("登录密码至少需要6个字符。")
                else:
                    with st.spinner("正在创建创世用户..."):
                        payload = {
                            "username": username,
                            "password": password,
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
    
    # <<< --- BUG修复 #4：使用 session_state 控制默认Tab --- >>>
    tab_titles = ["登录", "注册新账户 (需要邀请码)"]
    default_index = 0 if st.session_state.login_form_active else 1
    
    login_tab, register_tab = st.tabs(tab_titles)

    with login_tab:
        st.subheader("使用账户密码登录")
        with st.form("login_form"):
            username_or_uid = st.text_input("用户名或UID")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", type="primary")

            if submitted:
                if not username_or_uid or not password:
                    st.error("请输入用户名/UID和密码。")
                else:
                    with st.spinner("正在验证..."):
                        payload = {"username_or_uid": username_or_uid, "password": password}
                        data, error = api_call('POST', '/login', payload=payload)
                        
                        if error:
                            st.error(f"登录失败: {error}")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.private_key = data['private_key']
                            st.session_state.public_key = data['public_key']
                            st.session_state.username = data['username']
                            st.session_state.uid = data['uid']
                            st.session_state.active_tab = "我的钱包" # 登录后重置Tab
                            
                            details, _ = api_call('GET', "/user/details/", params={"public_key": data['public_key']})
                            st.session_state.user_details = details
                            
                            st.success("登录成功！")
                            st.rerun()

    with register_tab:
        if st.session_state.new_user_info:
            data = st.session_state.new_user_info
            st.success(f"🎉 账户 '{data['username']}' (UID: {data['uid']}) 创建成功！")
            st.info("你现在可以使用刚刚注册的用户名和密码在“登录”页面进行登录。")
            st.balloons()

            if st.button("太棒了，立即前往登录页面", type="primary"):
                st.session_state.new_user_info = None
                st.session_state.login_form_active = True # 切换到登录Tab
                st.rerun()
        else:
            st.subheader("注册新账户")
            with st.form("register_form"):
                username = st.text_input("输入你的用户名 (3-15个字符)", key="reg_username", max_chars=15)
                password = st.text_input("设置你的密码 (至少6位)", type="password")
                confirm_password = st.text_input("确认密码", type="password")
                invitation_code = st.text_input("输入你的邀请码", key="reg_inv_code", help="邀请码不区分大小写")
                
                submitted = st.form_submit_button("注册")

                if submitted:
                    # ... (注册逻辑不变) ...
                    if not all([username, password, confirm_password, invitation_code]):
                        st.error("所有字段都必须填写。")
                    elif len(username) < 3:
                        st.error("请输入至少3个字符的用户名。")
                    elif len(password) < 6:
                        st.error("密码至少需要6位。")
                    elif password != confirm_password:
                        st.error("两次输入的密码不一致！")
                    else:
                        with st.spinner("正在创建账户..."):
                            payload = { 'username': username, 'password': password, 'invitation_code': invitation_code }
                            data, error = api_call('POST', '/register', payload=payload)
                            
                            if error:
                                st.error(f"注册失败: {error}")
                            else:
                                st.session_state.new_user_info = data
                                st.session_state.login_form_active = False # 注册成功后保持在注册Tab显示信息
                                st.rerun()
# --- 数据获取与格式化辅助函数 ---
def get_user_details(force_refresh=False):
    """获取并缓存当前用户的详细信息。"""
    if not force_refresh and st.session_state.user_details:
        return st.session_state.user_details
            
    # 如果 public_key 为空，直接返回，防止无效的 API 调用
    if not st.session_state.get('public_key'):
        st.error("会话状态异常，缺少公钥信息，请尝试重新登录。")
        st.session_state.clear()
        st.rerun()
        return None

    data, error = api_call('GET', "/user/details/", params={"public_key": st.session_state.public_key})
    if error:
        # --- 修改后的逻辑 ---
        # 不再清除会话，只是显示错误信息。
        # 用户仍然停留在当前页面，可以看到错误，并可以手动刷新。
        st.error(f"无法刷新用户详情: {error}")
        if "404" in error: 
            st.warning("你的账户可能已被禁用或删除。如果问题持续，请联系管理员或重新登录。")
        
        # 返回已缓存的旧数据（如果有的话），以防止UI完全崩溃
        return st.session_state.user_details
    
    st.session_state.user_details = data
    return data

def get_all_users_dict(force_refresh=False):
    """获取当前用户的好友列表的 {username: public_key} 字典。"""
    now = time.time()
    # 修改缓存键，以避免与旧的全用户列表缓存冲突
    if not force_refresh and st.session_state.get('friends_cache') and (now - st.session_state.get('friends_cache_time', 0) < 60):
        return st.session_state.friends_cache
        
    # --- 核心修改：调用新的 /friends/list 接口 ---
    data, error = api_call('GET', '/friends/list', params={'public_key': st.session_state.public_key})
    if error:
        st.error(f"无法获取好友列表: {error}")
        return {}
        
    user_dict = {user['username']: user['public_key'] for user in data.get('friends', [])}
    st.session_state.friends_cache = user_dict
    st.session_state.friends_cache_time = now
    return user_dict

def format_dt(timestamp):
    """格式化UTC时间戳为本地时间字符串。"""
    if not timestamp: return "N/A"
    return datetime.fromtimestamp(timestamp, TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')

def render_clickable_username(username: str, uid: str, key: str):
    """
    渲染一个可点击的用户名，点击后将导航到该用户的个人主页。
    [BUG修复] key必须是调用者提供的、在整个页面中唯一的确定性字符串。
    """
    if not username or not uid:
        st.write(username or "未知用户")
        return

    if st.button(f"**{username}**", key=key, help=f"查看 {username} 的主页"):
        st.session_state.viewing_profile_of = uid
        st.session_state.active_tab = "👥 社区"
        st.rerun()
        
# --- 新增：数据格式化与翻译 ---
LISTING_TYPE_MAP = {
    "SALE": "一口价",
    "AUCTION": "拍卖",
    "SEEK": "求购"
}

STATUS_MAP = {
    "ACTIVE": "进行中",
    "PENDING": "待处理",
    "COMPLETED": "已完成",
    "CANCELLED": "已取消",
    "REJECTED": "已拒绝",
    "EXPIRED": "已过期"
}

def translate_listing_type(t):
    """翻译挂单类型为中文显示"""
    return LISTING_TYPE_MAP.get(t, t)

def translate_status(s):
    """翻译状态为中文显示"""
    return STATUS_MAP.get(s, s)

# ==============================================================================
# --- Tab Rendering Functions (重构后的核心) ---
# ==============================================================================

def render_sidebar(details):
    """渲染侧边栏"""
    with st.sidebar:
        st.header(f"你好, {st.session_state.username}!")
        st.caption(f"UID: {st.session_state.uid}") # <--- 新增
        
        if st.button("🔄 刷新数据"):
            st.cache_data.clear() 
            st.session_state.all_users_cache = None 
            st.session_state.user_details = None 
            st.rerun()

        if details:
            st.subheader("我的邀请")
            st.metric("剩余邀请次数", details.get('invitation_quota', 0))

            if st.button("生成新邀请码", type="primary"):
                if details.get('invitation_quota', 0) <= 0:
                    st.error("邀请额度不足！")
                else:
                    with st.spinner("正在生成邀请码..."):
                        msg_dict = {"owner_key": st.session_state.public_key}
                        signed_payload = create_signed_message(msg_dict)
                        
                        if signed_payload:
                            data, error = api_call('POST', '/user/generate_invitation', payload=signed_payload)
                            if error:
                                st.session_state.global_message = {'type': 'error', 'text': f"邀请码生成失败: {error}"}
                            else:
                                st.balloons()
                                st.session_state.global_message = {'type': 'success', 'text': f"邀请码生成成功！"}
                            st.cache_data.clear()
                            st.rerun()

            with st.expander("显示我未使用的邀请码"):
                codes_data, error = api_call_cached('GET', "/user/my_invitations/", params={"public_key": st.session_state.public_key})
                if error:
                    st.error(f"无法加载邀请码: {error}")
                elif not codes_data or not codes_data.get('codes'):
                    st.info("没有可用的邀请码。")
                else:
                    codes_list = [c['code'] for c in codes_data['codes']]
                    st.text_area("可用的邀请码", "\n".join(codes_list), height=100, disabled=True)

        st.subheader("我的公钥 (地址)")
        st.text_area("Public Key", st.session_state.public_key, height=150, disabled=True, key="sidebar_pubkey")
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(st.session_state.public_key)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf, caption="我的收款码", use_container_width=True)

        
        
        if st.button("退出登录"):
            st.session_state.clear() 
            st.success("您已退出登录。")
            time.sleep(1)
            st.rerun()

def render_community_tab():
    """(修改) 渲染'社区'选项卡，用于查看用户主页和处理好友请求。"""
    st.header("👥 社区")

    # <<< BUG修复 #1 & #7: 状态检查和强制刷新 --- >>>
    # 检查是否有通过 clickable_username 跳转过来的请求
    profile_to_view = st.session_state.get('viewing_profile_of')
    
    # 使用 st.text_input 并将跳转过来的值设为默认值
    search_term = st.text_input(
        "搜索用户 (输入用户名或UID)", 
        value=profile_to_view or "",
        placeholder="例如: admin 或 123456",
        key="community_search_box"
    )

    # 在处理完跳转请求后，立即清除状态，防止下次刷新时仍然停留在该用户页面
    if profile_to_view:
        st.session_state.viewing_profile_of = None

    if search_term:
        with st.spinner(f"正在查找 '{search_term}'..."):
            # 使用非缓存的api_call来获取最新状态
            profile_data, error = api_call('GET', f'/profile/{search_term}')
            if error:
                st.error(f"查找失败: {error}")
            elif not profile_data:
                st.warning("未找到该用户。")
            else:
                target_uid = profile_data['uid']
                target_key = profile_data['public_key']
                
                st.subheader(f"✨ {profile_data['username']} 的个人主页")

                if target_key != st.session_state.public_key:
                    # 使用非缓存调用获取最新好友状态
                    status_data, err = api_call('GET', f"/friends/status/{target_key}", params={'current_user_key': st.session_state.public_key})
                    if err:
                        st.error(f"无法获取好友状态: {err}") # Bug 1: 明确显示错误
                    else:
                        friend_status = status_data.get('status')
                        action_user_key = status_data.get('action_user_key')

                        if friend_status == 'ACCEPTED':
                            st.success("✔️ 你们是好友")
                        elif friend_status == 'PENDING':
                            if action_user_key == st.session_state.public_key:
                                st.info("⏳ 好友请求已发送，等待对方回应...")
                            else:
                                st.warning("对方已向你发送好友请求，请在“好友”选项卡中处理。")
                        elif friend_status == 'NONE':
                            if st.button("➕ 添加好友", key=f"add_friend_{target_uid}"):
                                with st.spinner("正在发送好友请求..."):
                                    msg_dict = {"owner_key": st.session_state.public_key, "target_key": target_key, "timestamp": time.time()}
                                    payload = create_signed_message(msg_dict)
                                    if payload:
                                        res, err = api_call('POST', '/friends/request', payload=payload)
                                        if err:
                                            st.error(f"请求失败: {err}")
                                        else:
                                            st.success(res.get('detail'))
                                            # 清除缓存并强制刷新
                                            st.cache_data.clear()
                                            time.sleep(1)
                                            st.rerun()
                else:
                    st.caption("这是你的个人主页。")

                st.caption(f"UID: {target_uid} | 加入于: {format_dt(profile_data['created_at'])}")
                
                st.markdown("---")
                signature = profile_data.get('signature') or "这个人很懒，什么都没留下..."
                st.info(f"“{signature}”")
                st.markdown("---")
                
                st.subheader("NFT 展柜")
                nfts = profile_data.get('displayed_nfts_details', [])
                if not nfts:
                    st.caption(f"{profile_data['username']} 还没有展出任何NFT。")
                else:
                    cols = st.columns(2)
                    for i, nft in enumerate(nfts):
                        with cols[i % 2]:
                            with st.container(border=True):
                                render_nft(st, nft, 0, None, None, view_context="profile")

def render_friends_tab():
    """ (新增) 渲染'好友'选项卡 """
    st.header("🤝 好友管理")

    my_friends_tab, requests_tab = st.tabs(["我的好友", "待处理的请求"])

    with my_friends_tab:
        st.subheader("我的好友列表")
        friends_data, err = api_call_cached('GET', '/friends/list', params={'public_key': st.session_state.public_key})
        if err:
            st.error(f"无法加载好友列表: {err}")
        elif not friends_data or not friends_data.get('friends'):
            st.info("你还没有好友。快去社区添加一些吧！")
        else:
            friends = friends_data['friends']
            for friend in friends:
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.write(f"**{friend['username']}** (UID: {friend['uid']})")
                with col2:
                    if st.button("查看主页", key=f"view_friend_{friend['uid']}", use_container_width=True):
                        st.session_state.viewing_profile_of = friend['uid']
                        st.rerun()
                with col3:
                    if st.button("💔 删除好友", key=f"del_friend_{friend['uid']}", type="secondary", use_container_width=True):
                         with st.spinner(f"正在删除好友 {friend['username']}..."):
                            msg_dict = {"owner_key": st.session_state.public_key, "target_key": friend['public_key'], "timestamp": time.time()}
                            payload = create_signed_message(msg_dict)
                            if payload:
                                res, err = api_call('POST', '/friends/delete', payload=payload)
                                if err: st.error(f"删除失败: {err}")
                                else:
                                    st.success(res.get('detail'))
                                    st.cache_data.clear()
                                    time.sleep(1)
                                    st.rerun()

    with requests_tab:
        st.subheader("收到的好友请求")
        requests_data, err = api_call_cached('GET', '/friends/requests', params={'public_key': st.session_state.public_key})
        if err:
            st.error(f"无法加载好友请求: {err}")
        elif not requests_data or not requests_data.get('requests'):
            st.info("没有待处理的好友请求。")
        else:
            requests = requests_data['requests']
            for req in requests:
                st.write(f"**{req['username']}** (UID: {req['uid']}) 想添加你为好友。")
                
                b_col1, b_col2, b_col3 = st.columns([3, 1, 1])
                with b_col2:
                    if st.button("接受", key=f"accept_{req['uid']}", type="primary"):
                        with st.spinner("正在接受..."):
                            msg_dict = {"owner_key": st.session_state.public_key, "requester_key": req['public_key'], "accept": True, "timestamp": time.time()}
                            payload = create_signed_message(msg_dict)
                            if payload:
                                res, err = api_call('POST', '/friends/respond', payload=payload)
                                if err: st.error(f"操作失败: {err}")
                                else:
                                    st.success(res.get('detail'))
                                    st.cache_data.clear()
                                    time.sleep(1)
                                    st.rerun()
                with b_col3:
                    if st.button("拒绝", key=f"reject_{req['uid']}"):
                         with st.spinner("正在拒绝..."):
                            msg_dict = {"owner_key": st.session_state.public_key, "requester_key": req['public_key'], "accept": False, "timestamp": time.time()}
                            payload = create_signed_message(msg_dict)
                            if payload:
                                res, err = api_call('POST', '/friends/respond', payload=payload)
                                if err: st.error(f"操作失败: {err}")
                                else:
                                    st.success(res.get('detail'))
                                    st.cache_data.clear()
                                    time.sleep(1)
                                    st.rerun()
                st.divider()
def render_settings_tab():
    """(新增) 渲染'个人设置'选项卡"""
    st.header("⚙️ 个人设置")
    st.subheader("编辑我的个人主页")

    # 获取当前用户的个人资料以填充默认值
    my_profile, error = api_call_cached('GET', f"/profile/{st.session_state.uid}")
    if error:
        st.error(f"无法加载你的个人资料: {error}")
        return

    current_signature = my_profile.get('signature', '')
    current_displayed_ids = [nft['nft_id'] for nft in my_profile.get('displayed_nfts_details', [])]

    with st.form("profile_edit_form"):
        st.text_area("我的签名", value=current_signature, key="profile_sig_input", max_chars=100)
        
        # 获取用户的所有NFT以供选择
        my_nfts_data, nfts_error = api_call_cached('GET', '/nfts/my/', params={"public_key": st.session_state.public_key})
        if nfts_error:
            st.warning("无法加载你的NFT列表。")
            nft_options = {}
        else:
            nft_options = {
                f"{nft['data'].get('name', nft['nft_type'])} ({nft['nft_id'][:6]})": nft['nft_id']
                for nft in my_nfts_data.get('nfts', [])
            }
        
        selected_nft_ids = st.multiselect(
            "选择要展出的NFT (最多6个)",
            options=nft_options.keys(),
            default=[k for k, v in nft_options.items() if v in current_displayed_ids],
            max_selections=6
        )
        
        submitted = st.form_submit_button("保存更改", type="primary")
        if submitted:
            final_nft_ids = [nft_options[key] for key in selected_nft_ids]
            new_signature = st.session_state.profile_sig_input

            with st.spinner("正在保存..."):
                message_dict = {
                    "owner_key": st.session_state.public_key,
                    "signature": new_signature,
                    "displayed_nfts": final_nft_ids
                }
                signed_payload = create_signed_message(message_dict)
                if signed_payload:
                    res, err = api_call('POST', '/profile/update', payload=signed_payload)
                    if err:
                        st.error(f"更新失败: {err}")
                    else:
                        st.success(f"更新成功！{res.get('detail')}")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
def render_wallet_tab():
    """渲染'我的钱包'选项卡"""
    st.header("我的钱包")
    col1, col2, col3 = st.columns(3)
    
    balance_data, error = api_call_cached('GET', "/balance/", params={"public_key": st.session_state.public_key})
    balance = 0.0
    if error:
        st.error(f"无法获取余额: {error}")
    else:
        balance = balance_data.get('balance', 0.0)
    col1.metric(label="当前余额", value=f"{balance:,.2f} FC")
    
    details = get_user_details()
    if details:
        col2.metric(label="总交易次数", value=details.get('tx_count', 0))
        with col3:
            st.write("**邀请人**")
            # --- 核心修改：使邀请人可点击 ---
            inviter_username = details.get('inviter_username', 'N/A')
            inviter_uid = details.get('inviter_uid')
            if inviter_uid:
                render_clickable_username(inviter_username, inviter_uid, "inviter")
            else:
                st.write(f"**{inviter_username}**")

        st.caption(f"注册于: {format_dt(details.get('created_at'))}")
    
    st.divider()
    st.subheader("交易历史")
    
    history_data, error = api_call_cached('GET', "/history/", params={"public_key": st.session_state.public_key})
    if error:
        st.error(f"无法获取交易历史: {error}")
    elif not history_data or not history_data.get('transactions'):
        st.info("没有交易记录。")
    else:
        # --- 核心修改：手动渲染交易历史以支持按钮 ---
        st.markdown(
            """
            <style>
            .header-row {
                font-weight: bold;
            }
            .row-container {
                border-bottom: 1px solid rgba(49, 51, 63, 0.2);
                padding-top: 10px;
                padding-bottom: 10px;
            }
            </style>
            """, unsafe_allow_html=True
        )

        # 表头
        c1, c2, c3, c4, c5 = st.columns([3, 2, 3, 2, 4])
        with c1: st.markdown("**时间**", unsafe_allow_html=True)
        with c2: st.markdown("**方向**", unsafe_allow_html=True)
        with c3: st.markdown("**对方**", unsafe_allow_html=True)
        with c4: st.markdown("**金额**", unsafe_allow_html=True)
        with c5: st.markdown("**备注**", unsafe_allow_html=True)

        for tx in history_data['transactions']:
            tx_type = tx.get('type')
            direction = "支出 📤" if tx_type == 'out' else "收入 📥"
            amount_str = f"- {tx['amount']:,.2f}" if tx_type == 'out' else f"+ {tx['amount']:,.2f}"
            
            if tx_type == 'out':
                counterparty_name = tx.get('to_display')
                counterparty_uid = tx.get('to_uid')
            else:
                counterparty_name = tx.get('from_display')
                counterparty_uid = tx.get('from_uid')

            c1, c2, c3, c4, c5 = st.columns([3, 2, 3, 2, 4])
            with c1: st.text(format_dt(tx.get('timestamp')))
            with c2: st.text(direction)
            with c3:
                # 只有当对方是普通用户时才渲染按钮
                if counterparty_uid:
                    render_clickable_username(counterparty_name, counterparty_uid, f"tx_{tx['tx_id']}")
                else:
                    st.text(counterparty_name)
            with c4: st.text(amount_str)
            with c5: st.text(tx.get('note', ''))

def render_transfer_tab():
    """渲染'转账'选项卡"""
    st.header("发起转账")
    
    user_dict = get_all_users_dict()
    my_username = st.session_state.username
    details = get_user_details()
    
    # <<< --- BUG修复 #5：仅在非管理员时移除自己 --- >>>
    is_admin = details.get('invited_by') == 'GENESIS'
    if not is_admin and my_username in user_dict:
        del user_dict[my_username]
    # <<< --- 修复结束 --- >>>
    
    user_options = [""] + sorted(list(user_dict.keys()))
    
    with st.form("send_form"):
        # ... (表单其余部分不变) ...
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
                            st.rerun()


def render_shop_tab(balance):
    """渲染'商店'选项卡"""
    st.header("🛒 NFT 市场")
    
    market_tab, my_activity_tab, create_nft_tab = st.tabs(["浏览市场", "我的交易", "✨ 铸造新品"])

    with market_tab:
        sale_col, auction_col, seek_col = st.columns(3)
        
        with sale_col:
            st.subheader("一口价")
            sales, err = api_call_cached('GET', '/market/listings', params={'listing_type': 'SALE', 'exclude_owner': st.session_state.public_key})
            if err or not sales or not sales.get('listings'):
                st.caption("暂无待售NFT")
            else:
                for item in sales['listings']:
                    with st.expander(f"**{item.get('trade_description', item['description'])}**"):
                        if item.get('nft_data'):
                            temp_nft_object = { "nft_id": item['nft_id'], "nft_type": item['nft_type'], "owner_key": item['lister_key'], "data": item['nft_data'], "status": "ACTIVE" }
                            render_nft(st, temp_nft_object, balance, api_call, lambda msg: create_signed_message(msg), view_context="market")
                        
                        st.divider()
                        st.write("卖家:")
                        render_clickable_username(
                            item['lister_username'], 
                            item['lister_uid'], 
                            key=f"userlink_sale_{item['listing_id']}"
                        )
                        
                        st.success(f"价格: **{item['price']} FC**")
                        if st.button("立即购买", key=f"buy_{item['listing_id']}", type="primary", use_container_width=True):
                            with st.spinner("正在处理购买..."):
                                msg_dict = {"owner_key": st.session_state.public_key, "listing_id": item['listing_id'], "timestamp": time.time()}
                                payload = create_signed_message(msg_dict)
                                if payload:
                                    res, err = api_call('POST', '/market/buy', payload=payload)
                                    if err: st.session_state.global_message = {'type': 'error', 'text': f"购买失败: {err}"}
                                    else: st.balloons(); st.session_state.global_message = {'type': 'success', 'text': f"购买成功！{res.get('detail')}"}
                                    st.cache_data.clear(); st.rerun()

        with auction_col:
            st.subheader("拍卖行")
            auctions, err = api_call_cached('GET', '/market/listings', params={'listing_type': 'AUCTION', 'exclude_owner': st.session_state.public_key})
            if err or not auctions or not auctions.get('listings'):
                st.caption("暂无拍卖品")
            else:
                for item in auctions['listings']:
                    with st.expander(f"**{item.get('trade_description', item['description'])}**"):
                        if item.get('nft_data'):
                            temp_nft_object = { "nft_id": item['nft_id'], "nft_type": item['nft_type'], "owner_key": item['lister_key'], "data": item['nft_data'], "status": "ACTIVE" }
                            render_nft(st, temp_nft_object, balance, api_call, lambda msg: create_signed_message(msg), view_context="market")

                        st.divider()
                        end_time_str = datetime.fromtimestamp(item['end_time'], TIMEZONE).strftime('%H:%M:%S')
                        st.write(f"卖家 (今日 {end_time_str} 截止):")
                        render_clickable_username(
                            item['lister_username'], 
                            item['lister_uid'], 
                            key=f"userlink_auction_{item['listing_id']}"
                        )

                        price_label = "当前最高价" if item['highest_bid'] > 0 else "起拍价"
                        st.warning(f"{price_label}: **{item.get('highest_bid') or item.get('price')} FC**")

                        with st.form(key=f"bid_form_{item['listing_id']}"):
                            bid_amount = st.number_input("你的出价", min_value=float(item['highest_bid'] or item['price']) + 0.01, step=1.0, format="%.2f")
                            if st.form_submit_button("出价", use_container_width=True):
                                with st.spinner("正在提交出价..."):
                                    msg_dict = {"owner_key": st.session_state.public_key, "listing_id": item['listing_id'], "amount": bid_amount, "timestamp": time.time()}
                                    payload = create_signed_message(msg_dict)
                                    if payload:
                                        res, err = api_call('POST', '/market/place_bid', payload=payload)
                                        if err: st.session_state.global_message = {'type': 'error', 'text': f"出价失败: {err}"}
                                        else: st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                        st.cache_data.clear(); st.rerun()

        with seek_col:
            st.subheader("求购栏")
            seeks, err = api_call_cached('GET', '/market/listings', params={'listing_type': 'SEEK', 'exclude_owner': st.session_state.public_key})
            if err or not seeks or not seeks.get('listings'):
                st.caption("暂无求购信息")
            else:
                for item in seeks['listings']:
                    expander_title = f"**求购: {item['description']}**"
                    with st.expander(expander_title):
                        st.write("求购方:")
                        render_clickable_username(
                            item['lister_username'], 
                            item['lister_uid'], 
                            key=f"userlink_seek_{item['listing_id']}"
                        )
                        st.info(f"预算: **{item['price']} FC** | 类型: `{item['nft_type']}`")
                        
                        with st.container(border=False):
                            my_nfts, err = api_call_cached('GET', '/nfts/my/', params={"public_key": st.session_state.public_key})
                            eligible_nfts = [nft for nft in my_nfts.get('nfts', []) if nft['nft_type'] == item['nft_type'] and nft['status'] == 'ACTIVE'] if my_nfts else []
                            if not eligible_nfts:
                                st.caption(f"你没有可用于报价的`{item['nft_type']}`类型NFT。")
                            else:
                                nft_options = {f"{nft['data'].get('name', nft['nft_id'][:8])}": nft['nft_id'] for nft in eligible_nfts}
                                selected_nft_name = st.selectbox("选择你的NFT", options=list(nft_options.keys()), key=f"offer_nft_{item['listing_id']}")
                                if st.button("确认报价", key=f"offer_btn_{item['listing_id']}"):
                                    with st.spinner("正在发送报价..."):
                                        msg_dict = {"owner_key": st.session_state.public_key, "listing_id": item['listing_id'], "offered_nft_id": nft_options[selected_nft_name], "timestamp": time.time()}
                                        payload = create_signed_message(msg_dict)
                                        if payload:
                                            res, err = api_call('POST', '/market/make_offer', payload=payload)
                                            if err: st.session_state.global_message = {'type': 'error', 'text': f"报价失败: {err}"}
                                            else: st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                            st.cache_data.clear(); st.rerun()

    with my_activity_tab:
        st.subheader("我的交易看板")
        with st.container(border=True):
            st.subheader("发布求购")
            st.info("发布一个求购信息，让拥有你所需 NFT 的人来找你。发布时将暂时托管你的预算资金。")
            all_nft_types, err = api_call_cached('GET', '/admin/nft/types', headers={"X-Admin-Secret": "dummy"})
            if err or not all_nft_types:
                all_nft_types = ["SECRET_WISH"] 

            with st.form(key="seek_form"):
                seek_nft_type = st.selectbox("求购的 NFT 类型", options=all_nft_types)
                seek_description = st.text_input("求购描述", placeholder="例如：求一个金色的宠物")
                seek_price = st.number_input("我的预算 (FC)", min_value=0.01, step=1.0, format="%.2f")

                if st.form_submit_button("发布求购信息", type="primary"):
                    if not seek_description:
                        st.error("求购描述不能为空")
                    else:
                        with st.spinner("正在发布求购..."):
                            msg_dict = { "owner_key": st.session_state.public_key, "listing_type": "SEEK", "nft_id": None, "nft_type": seek_nft_type, "description": seek_description, "price": seek_price, "auction_hours": None, "timestamp": time.time() }
                            payload = create_signed_message(msg_dict)
                            if payload:
                                res, err = api_call('POST', '/market/create_listing', payload=payload)
                                if err: st.session_state.global_message = {'type': 'error', 'text': f"发布求购失败: {err}"}
                                else: st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                st.cache_data.clear(); st.rerun()
                                
        st.divider()
        activity, err = api_call_cached('GET', '/market/my_activity', params={'public_key': st.session_state.public_key})
        if err or not activity:
            st.error("无法加载您的交易活动")
        else:
            st.subheader("我挂出的:")
            my_listings = activity.get('listings', [])
            if not my_listings:
                st.caption("你没有发布任何挂单。")
            else:
                for item in my_listings:
                    expander_title = f"**[{translate_listing_type(item['listing_type'])}]** {item['description']}"
                    with st.expander(expander_title):
                        st.caption(f"状态: **{translate_status(item['status'])}** | 价格/预算: {item['price']} FC")
                        if item['status'] == 'ACTIVE':
                            if st.button("取消挂单", key=f"cancel_{item['listing_id']}"):
                                with st.spinner("正在取消挂单..."):
                                    msg_dict = {"owner_key": st.session_state.public_key, "listing_id": item['listing_id'], "timestamp": time.time()}
                                    payload = create_signed_message(msg_dict)
                                    if payload:
                                        res, err = api_call('POST', '/market/cancel_listing', payload=payload)
                                        if err: st.session_state.global_message = {'type': 'error', 'text': f"取消失败: {err}"}
                                        else: st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                        st.cache_data.clear(); st.rerun()

                        if item['listing_type'] == 'SEEK' and item['status'] == 'ACTIVE':
                            offers_data, err = api_call_cached('GET', '/market/offers', params={'listing_id': item['listing_id']})
                            offers = offers_data.get('offers', []) if offers_data else []
                            st.write("收到的报价:")
                            if not offers:
                                st.caption("暂未收到报价")
                            else:
                                for offer in offers:
                                    if offer['status'] == 'PENDING':
                                        offer_col1, offer_col2, offer_col3, offer_col4 = st.columns([4, 2, 1, 1])
                                        with offer_col1:
                                            st.write(f"来自 **{offer['offerer_username']}** 的报价:")
                                            render_clickable_username(
                                                offer['offerer_username'], 
                                                offer['offerer_uid'], 
                                                key=f"userlink_offer_{offer['offer_id']}"
                                            )
                                        
                                        with offer_col2:
                                            st.info(f"{offer.get('trade_description', offer['offered_nft_id'][:8])}")

                                        if offer_col3.button("接受", key=f"accept_{offer['offer_id']}", type="primary"):
                                            msg_dict = {"owner_key": st.session_state.public_key, "offer_id": offer['offer_id'], "accept": True, "timestamp": time.time()}
                                            with st.spinner("正在接受报价..."):
                                                payload = create_signed_message(msg_dict)
                                                if payload:
                                                    res, err = api_call('POST', '/market/respond_offer', payload=payload)
                                                    if err: st.session_state.global_message = {'type': 'error', 'text': f"操作失败: {err}"}
                                                    else: st.balloons(); st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                                    st.cache_data.clear(); st.rerun()

                                        if offer_col4.button("拒绝", key=f"reject_{offer['offer_id']}"):
                                            msg_dict = {"owner_key": st.session_state.public_key, "offer_id": offer['offer_id'], "accept": False, "timestamp": time.time()}
                                            with st.spinner("正在拒绝报价..."):
                                                payload = create_signed_message(msg_dict)
                                                if payload:
                                                    res, err = api_call('POST', '/market/respond_offer', payload=payload)
                                                    if err: st.session_state.global_message = {'type': 'error', 'text': f"操作失败: {err}"}
                                                    else: st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                                    st.cache_data.clear(); st.rerun()

    with create_nft_tab:
        st.subheader("铸造工坊")
        if 'shop_message' in st.session_state and st.session_state.shop_message:
            message_info = st.session_state.shop_message
            if message_info['type'] == 'success':
                st.success(message_info['text'])
            else:
                st.error(message_info['text'])
            del st.session_state.shop_message

        creatable_nfts, err = api_call_cached('GET', '/market/creatable_nfts')
        
        # <<< --- 核心修复：修正这里的变量名 --- >>>
        if err or not creatable_nfts:
            st.info("当前没有可通过商店铸造的NFT类型。")
        else:
            sorted_items = sorted(creatable_nfts.items(), key=lambda item: item[1].get('cost', 0))
            
            for nft_type, config in sorted_items:
                expander_title = f"**{config.get('name', nft_type)}** - 消耗 {config.get('cost', 0)} FC"
                with st.expander(expander_title, expanded=True):
                    st.caption(f"`{nft_type}`")
                    st.write(config.get('description', ''))
                    
                    with st.form(key=f"create_form_{nft_type}", border=False):
                        form_data = {}
                        for field in config.get('fields', []):
                            if field['type'] == 'text_input':
                                form_data[field['name']] = st.text_input(field['label'], help=field.get('help'))
                            elif field['type'] == 'text_area':
                                form_data[field['name']] = st.text_area(field['label'], help=field.get('help'))
                            elif field['type'] == 'number_input':
                                form_data[field['name']] = st.number_input(
                                    field['label'], 
                                    min_value=field.get('min_value'), max_value=field.get('max_value'),
                                    value=field.get('default'), step=field.get('step'),
                                    help=field.get('help')
                                )
                        button_label = config.get("action_label", "支付并铸造")
                        if st.form_submit_button(button_label, type="primary"):
                            action_type = config.get("action_type", "create")
                            endpoint = '/market/create_nft' if action_type == 'create' else '/market/shop_action'

                            msg_dict = {
                                "owner_key": st.session_state.public_key, "nft_type": nft_type,
                                "cost": config['cost'], "data": form_data,
                                "timestamp": time.time()
                            }
                            payload = create_signed_message(msg_dict)
                            if payload:
                                res, err = api_call('POST', endpoint, payload=payload)
                                if err:
                                    st.session_state.shop_message = {'type': 'error', 'text': err}
                                else:
                                    st.session_state.shop_message = {'type': 'success', 'text': res.get('detail')}
                                    st.balloons()
                                
                                st.cache_data.clear(); st.rerun()

def render_collection_tab():
    """渲染'我的收藏'选项卡 (V3 - 中文解耦分类)"""
    st.header("🖼️ 我的收藏 (NFTs)")
    st.info("这里展示你拥有的所有独特的数字藏品。")

    balance_data, _ = api_call_cached('GET', "/balance/", params={"public_key": st.session_state.public_key})
    balance = balance_data.get('balance', 0.0) if balance_data else 0.0

    nfts_data, error = api_call_cached('GET', '/nfts/my/', params={"public_key": st.session_state.public_key})

    if error:
        st.error(f"无法加载你的收藏: {error}")
    elif not nfts_data or not nfts_data.get('nfts'):
        st.info("你的收藏还是空的，快去商店逛逛或让管理员给你发行一些吧！")
    else:
        # --- 核心修改 1: 获取中文名映射 ---
        display_name_map = get_nft_display_names()

        from collections import defaultdict
        nfts_by_type = defaultdict(list)
        for nft in nfts_data['nfts']:
            nfts_by_type[nft['nft_type']].append(nft)
        
        sorted_nft_types = sorted(nfts_by_type.keys())

        # --- 核心修改 2: 使用中文名映射来生成Tab标题 ---
        tab_titles = [
            f"{display_name_map.get(nft_type, nft_type)} ({len(nfts_by_type[nft_type])})"
            for nft_type in sorted_nft_types
        ]
        
        if len(tab_titles) > 1:
            type_tabs = st.tabs(tab_titles)
        else:
            type_tabs = [st.container(border=False)] 

        for i, nft_type in enumerate(sorted_nft_types):
            with type_tabs[i]:
                nfts_in_category = nfts_by_type[nft_type]
                
                cols = st.columns(2)
                for j, nft in enumerate(nfts_in_category):
                    col = cols[j % 2]
                    
                    with col:
                        nft_data = nft.get('data', {})
                        
                        # --- 核心修改 3: 卡片标题也使用中文名 ---
                        nft_display_name = display_name_map.get(nft_type, nft_type)
                        card_title = nft_data.get('custom_name') or nft_data.get('name') or f"一个 {nft_display_name}"
                        
                        with st.expander(f"**{card_title}** (`{nft_display_name}`)", expanded=True):
                            # (内部渲染逻辑保持不变)
                            render_nft(
                                st, nft, balance, api_call, 
                                lambda msg: create_signed_message(msg),
                                view_context="collection"
                            )

                            if nft.get('status') == 'ACTIVE':
                                with st.container(border=True):
                                    st.write("**市场操作**")
                                    with st.form(key=f"sell_form_{nft['nft_id']}"):
                                        listing_type_display = st.selectbox(
                                            "挂单类型", ["SALE", "AUCTION"],
                                            format_func=translate_listing_type,
                                            key=f"sell_type_{nft['nft_id']}"
                                        )
                                        description = st.text_input(
                                            "挂单描述",
                                            value=nft_data.get('name', f"一个 {nft_display_name} NFT"),
                                            key=f"sell_desc_{nft['nft_id']}"
                                        )
                                        price = st.number_input(
                                            "价格 / 起拍价 (FC)", min_value=0.01, step=1.0, format="%.2f",
                                            key=f"sell_price_{nft['nft_id']}"
                                        )
                                        auction_hours = None
                                        if listing_type_display == 'AUCTION':
                                            auction_hours = st.number_input(
                                                "拍卖持续小时数", min_value=0.1, value=24.0, step=0.5,
                                                key=f"sell_hours_{nft['nft_id']}"
                                            )
                                        if st.form_submit_button("确认挂单", use_container_width=True):
                                            with st.spinner("正在创建挂单..."):
                                                msg_dict = {
                                                    "owner_key": st.session_state.public_key, "listing_type": listing_type_display,
                                                    "nft_id": nft['nft_id'], "nft_type": nft['nft_type'],
                                                    "description": description, "price": price,
                                                    "auction_hours": auction_hours, "timestamp": time.time()
                                                }
                                                payload = create_signed_message(msg_dict)
                                                if payload:
                                                    res, err = api_call('POST', '/market/create_listing', payload=payload)
                                                    if err: st.session_state.global_message = {'type': 'error', 'text': f"挂单失败: {err}"}
                                                    else: st.session_state.global_message = {'type': 'success', 'text': res.get('detail')}
                                                    st.cache_data.clear(); st.rerun()

                                with st.container(border=True):
                                    st.write("**危险操作**")
                                    confirm_destroy = st.checkbox(
                                        f"我确认要永久销毁此物品",
                                        key=f"destroy_confirm_{nft['nft_id']}"
                                    )
                                    if st.button("确认销毁", key=f"destroy_btn_{nft['nft_id']}", type="primary", disabled=not confirm_destroy, use_container_width=True):
                                        with st.spinner("正在发送销毁指令..."):
                                            msg_dict = {
                                                "owner_key": nft['owner_key'], "nft_id": nft['nft_id'],
                                                "action": "destroy", "action_data": {},
                                                "timestamp": time.time()
                                            }
                                            signed_payload = create_signed_message(msg_dict)
                                            if signed_payload:
                                                res_data, error = api_call('POST', '/nfts/action', payload=signed_payload)
                                                if error: st.session_state.global_message = {'type': 'error', 'text': f"销毁失败: {error}"}
                                                else:
                                                    st.balloons()
                                                    st.session_state.global_message = {'type': 'success', 'text': f"销毁成功！{res_data.get('detail')}"}
                                                st.cache_data.clear(); st.rerun()

def render_admin_tab():
    """渲染'管理员'选项卡"""
    st.header("管理员面板")
    if not st.session_state.admin_ui_unlocked:
        # ... (解锁逻辑不变)
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
        # ... (其他UI部分不变)
        st.success("管理员UI已解锁。")
        if st.button("锁定UI"):
            st.session_state.admin_ui_unlocked = False
            st.rerun()

        st.warning("你正在进行管理员操作。真正的API安全由后端的 Admin Secret 保证。")
        admin_secret = st.text_input("请输入你的后端 Admin Secret", type="password", key="admin_secret_input")
        
        if not admin_secret:
            st.info("请输入 Admin Secret以启用操作。")
        else:
            admin_headers = {"X-Admin-Secret": admin_secret}
            user_dict = get_all_users_dict(force_refresh=True) 
            # <<< --- BUG修复 #5：管理员列表不过滤自己 --- >>>
            # 管理员调用 get_all_users_dict 已经返回了所有人，所以不需要额外处理
            # <<< --- 修复结束 --- >>>
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
            # ... (用户管理 Tab 不变)
            with admin_manage_tab:
                st.subheader("用户管理")
                manage_user = st.selectbox("选择要管理的用户", options=[""] + user_options, key="admin_manage_user")
                if manage_user:
                    target_key = user_dict[manage_user]
                    st.info(f"正在管理: **{manage_user}** (`{target_key[:15]}...`)")
                    
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

                    st.divider()
                    st.write("**重置用户密码 (高风险操作)**")
                    st.error("警告：此操作将强制为用户设置一个新密码。请在用户请求或紧急情况下使用。")
                    with st.form("reset_password_form"):
                        new_password = st.text_input("输入新密码 (至少6位)", type="password")
                        if st.form_submit_button("确认重置密码", type="primary"):
                            if not new_password or len(new_password) < 6:
                                st.error("新密码至少需要6个字符。")
                            else:
                                with st.spinner("正在发送重置指令..."):
                                    payload = {"public_key": target_key, "new_password": new_password}
                                    data, error = api_call('POST', '/admin/reset_password', payload=payload, headers=admin_headers)
                                    if error:
                                        st.error(f"重置失败: {error}")
                                    else:
                                        st.success(f"重置成功！{data.get('detail')}")
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
                    
                    # <<< --- BUG修复 #6：使用session_state来触发刷新 --- >>>
                    if 'admin_nft_type_select' not in st.session_state:
                        st.session_state.admin_nft_type_select = nft_type_options[0] if nft_type_options else None
                    
                    def update_nft_type_selection():
                         st.session_state.admin_nft_type_select = st.session_state.nft_type_selector
                    
                    st.selectbox(
                        "选择要铸造的 NFT 类型", 
                        options=nft_type_options,
                        key="nft_type_selector",
                        on_change=update_nft_type_selection
                    )
                    selected_nft_type = st.session_state.admin_nft_type_select
                    # <<< --- 修复结束 --- >>>
                    
                    st.write("**输入该类型 NFT 所需的初始数据 (JSON 格式):**")
                    
                    # 现在 get_mint_info_for_type 会基于更新后的 session_state 被调用
                    mint_info = get_mint_info_for_type(selected_nft_type)
                    
                    if mint_info and mint_info.get("help_text"):
                        st.info(mint_info["help_text"])
                        
                    initial_data_str = st.text_area(
                        "初始数据", 
                        value=mint_info.get("default_json", "{}") if mint_info else "{}",
                        height=150
                    )

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
            
            with admin_settings_tab:
                 # ... (系统设置 Tab 不变) ...
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
                st.write("**新用户奖励设置**")
                st.info("在这里设置新用户通过邀请码注册后，系统自动发放的 FamilyCoin 奖励金额。")
                bonus_setting_data, bonus_error = api_call('GET', '/admin/setting/welcome_bonus_amount', headers=admin_headers)
                current_bonus = 500.0
                if bonus_error:
                    if "404" not in bonus_error:
                         st.warning(f"无法获取当前奖励设置: {bonus_error}。将使用默认值。")
                else:
                    current_bonus = float(bonus_setting_data.get('value', 500.0))
                with st.form("set_bonus_form"):
                    new_bonus_amount = st.number_input("新用户注册奖励金额 (FC)", min_value=0.0, value=current_bonus, step=10.0, help="设置为0则不发放奖励。")
                    if st.form_submit_button("更新注册奖励"):
                        payload = {"key": "welcome_bonus_amount", "value": str(new_bonus_amount)}
                        data, error = api_call('POST', '/admin/set_setting', payload=payload, headers=admin_headers)
                        if error: 
                            st.error(f"更新失败: {error}")
                        else: 
                            st.success(f"更新成功！{data.get('detail')}")
                            time.sleep(0.5)
                            st.rerun()
                st.divider()
                st.write("**邀请人奖励设置**")
                st.info("在这里设置当用户成功邀请一位新成员后，邀请人获得的 FamilyCoin 奖励金额。")
                inviter_bonus_data, inviter_bonus_error = api_call('GET', '/admin/setting/inviter_bonus_amount', headers=admin_headers)
                current_inviter_bonus = 200.0
                if inviter_bonus_error:
                    if "404" not in inviter_bonus_error:
                         st.warning(f"无法获取当前邀请奖励设置: {inviter_bonus_error}。将使用默认值。")
                else:
                    current_inviter_bonus = float(inviter_bonus_data.get('value', 200.0))
                with st.form("set_inviter_bonus_form"):
                    new_inviter_bonus = st.number_input("邀请人奖励金额 (FC)", min_value=0.0, value=current_inviter_bonus, step=10.0, help="设置为0则不发放奖励。")
                    if st.form_submit_button("更新邀请奖励"):
                        payload = {"key": "inviter_bonus_amount", "value": str(new_inviter_bonus)}
                        data, error = api_call('POST', '/admin/set_setting', payload=payload, headers=admin_headers)
                        if error: 
                            st.error(f"更新失败: {error}")
                        else: 
                            st.success(f"更新成功！{data.get('detail')}")
                            time.sleep(0.5)
                            st.rerun()
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
                    # ... (监控中心逻辑已在上一轮修复)
                     data, error = api_call('GET', '/admin/balances', headers=admin_headers)
                     if error:
                         st.error(f"查询失败: {error}")
                     elif not data or not data.get('balances'):
                         st.info("账本为空。")
                     else:
                         st.success("查询成功！")
                         balances = data['balances']
                         c1, c2, c3, c4 = st.columns(4)
                         c1.markdown("**用户名**")
                         c2.markdown("**余额**")
                         c3.markdown("**邀请人**")
                         c4.markdown("**状态**")

                         for user in balances:
                             c1, c2, c3, c4 = st.columns(4)
                             with c1:
                                 render_clickable_username(user['username'], user['uid'], f"admin_bal_{user['uid']}")
                             c2.text(f"{user['balance']:,.2f}")
                             c3.text(user.get('inviter_username', 'N/A'))
                             status_text = "✔️ 活跃" if user['is_active'] else "❌ 禁用"
                             c4.text(status_text)


def show_main_app():
    # ... (消息显示和数据获取部分不变)
    if 'global_message' in st.session_state and st.session_state.global_message:
        message_info = st.session_state.global_message
        if message_info['type'] == 'success':
            st.success(message_info['text'], icon="✅")
        else:
            st.error(message_info['text'], icon="🚨")
        del st.session_state.global_message
    details = get_user_details()
    if not details: 
        return
    if details.get('tx_count', 0) == 0 and details.get('invited_by') != 'GENESIS':
        st.warning( "👋 **欢迎新朋友！** 你的账户已成功创建，但请务必再次确认你已经**安全备份了你的私钥**。你可以随时从侧边栏的“显示我的私钥”中找到它并复制。**私钥一旦丢失，资产将永久无法找回！**", icon="🎉" )
    
    render_sidebar(details)
    
    is_admin = details.get('invited_by') == 'GENESIS'
    tabs_list = ["我的钱包", "转账", "🛒 商店", "🖼️ 我的收藏", "👥 社区", "🤝 好友", "⚙️ 个人设置"]
    if is_admin:
        tabs_list.append("⭐ 管理员 ⭐")
    
    # 获取当前激活Tab的索引
    try:
        current_tab_index = tabs_list.index(st.session_state.active_tab)
    except ValueError:
        current_tab_index = 0 # 如果找不到，默认为第一个

    # 使用 st.radio 作为隐藏的 Tab 控制器，或者直接渲染 st.tabs
    # st.tabs 不支持 default_index，所以我们需要一个 workaround
    # 我们将在渲染时手动调用 active_tab 对应的渲染函数
    
    selected_tab = st.sidebar.radio(
        "导航", 
        tabs_list, 
        index=current_tab_index, 
        key="main_nav_radio"
    )

    # 如果 radio 的选择变了，更新 session_state 并 rerun
    if selected_tab != st.session_state.active_tab:
        st.session_state.active_tab = selected_tab
        st.rerun()

    # 根据 active_tab 显示内容
    if st.session_state.active_tab == "我的钱包":
        render_wallet_tab()
    elif st.session_state.active_tab == "转账":
        render_transfer_tab()
    elif st.session_state.active_tab == "🛒 商店":
        balance_data, _ = api_call_cached('GET', "/balance/", params={"public_key": st.session_state.public_key})
        balance = balance_data.get('balance', 0.0) if balance_data else 0.0
        render_shop_tab(balance)
    elif st.session_state.active_tab == "🖼️ 我的收藏":
        render_collection_tab()
    elif st.session_state.active_tab == "👥 社区":
        render_community_tab()
    elif st.session_state.active_tab == "🤝 好友":
        render_friends_tab()
    elif st.session_state.active_tab == "⚙️ 个人设置":
        render_settings_tab()
    elif st.session_state.active_tab == "⭐ 管理员 ⭐" and is_admin:
        render_admin_tab()

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