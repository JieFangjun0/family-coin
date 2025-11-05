// frontend-vue/src/components/layout/TheSidebar.vue

<script setup>
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ref, onMounted, onUnmounted } from 'vue' 
import { apiCall } from '@/api' 
import { createSignedPayload } from '@/utils/crypto' 
import { formatTimestamp } from '@/utils/formatters' 

// 导航图标
import IconWallet from '@/components/icons/IconWallet.vue'
import IconTransfer from '@/components/icons/IconTransfer.vue'
import IconInvite from '@/components/icons/IconInvite.vue'
import IconShop from '@/components/icons/IconShop.vue'
import IconCollection from '@/components/icons/IconCollection.vue'
import IconCommunity from '@/components/icons/IconCommunity.vue'
import IconFriends from '@/components/icons/IconFriends.vue'
import IconProfile from '@/components/icons/IconProfile.vue'
import IconAdmin from '@/components/icons/IconAdmin.vue'
import IconBell from '@/components/icons/IconBell.vue' 

// 菜单图标 (假设 IconMenu.vue 已创建，否则需要手动定义一个 SVG 组件)
import IconMenu from '@/components/icons/IconMenu.vue' 
import IconClose from '@/components/icons/IconClose.vue' // 假设 IconClose 也是一个简单的叉号 SVG

// 如果 IconClose 不存在，可以手动定义一个简单的 SVG 组件:
const IconX = {
  template: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`
}


const authStore = useAuthStore()
const router = useRouter()

// --- 侧边栏状态 (新增用于折叠) ---
const isMobileSidebarOpen = ref(false)
// --- 通知状态 ---
const unreadCount = ref(0)
const notifications = ref([])
const showNotifDropdown = ref(false)
let notifTimer = null

const navItems = [
  { name: '我的钱包', routeName: 'wallet', icon: IconWallet },
  { name: '转账', routeName: 'transfer', icon: IconTransfer },
  { name: '邀请', routeName: 'invitations', icon: IconInvite },
  { name: '商店', routeName: 'shop', icon: IconShop },
  { name: '我的NFT', routeName: 'collection', icon: IconCollection },
  { name: '社区', routeName: 'community', icon: IconCommunity },
  { name: '好友', routeName: 'friends', icon: IconFriends },
  { name: '个人展示主页', routeName: 'profile', icon: IconProfile },
]

const adminNavItems = [
  {
    name: '管理员',
    routeName: 'admin',
    icon: IconAdmin,
  }
]

// --- 侧边栏方法 (新增用于折叠) ---
function toggleMobileSidebar() {
  isMobileSidebarOpen.value = !isMobileSidebarOpen.value
  if (isMobileSidebarOpen.value) {
    document.body.style.overflow = 'hidden' // 阻止背景滚动
  } else {
    document.body.style.overflow = ''
  }
}

// 路由切换时关闭侧边栏
router.afterEach(() => {
  if (isMobileSidebarOpen.value) {
    isMobileSidebarOpen.value = false
    document.body.style.overflow = ''
  }
})

// --- 通知方法 ---
async function fetchNotifications() {
  if (!authStore.isLoggedIn) return;
  const [data, error] = await apiCall('GET', '/notifications/my', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (!error) {
    unreadCount.value = data.unread_count
    notifications.value = data.notifications
  }
}

async function markAsRead(notifId) {
  const message = {
    owner_key: authStore.userInfo.publicKey,
    listing_id: notifId, 
    timestamp: Math.floor(Date.now() / 1000),
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) return;
  
  // 乐观更新 UI
  const notif = notifications.value.find(n => n.notif_id === notifId)
  if (notif && !notif.is_read) {
    notif.is_read = true;
    if (unreadCount.value > 0) unreadCount.value--;
  }
  
  await apiCall('POST', '/notifications/mark_read', { payload: signedPayload });
}

function toggleDropdown() {
    showNotifDropdown.value = !showNotifDropdown.value
    // 如果打开下拉菜单，对列表前几条未读消息进行标记
    if (showNotifDropdown.value) {
        // 自动标记前 5 条未读消息为已读
        notifications.value.slice(0, 5).filter(n => !n.is_read).forEach(n => markAsRead(n.notif_id));
    }
}

async function handleLogout() {
  authStore.logout()
  await router.push({ name: 'login' })
}

onMounted(() => {
    fetchNotifications() 
    // 增加一个检查，确保在桌面端默认关闭下拉菜单
    if (window.innerWidth > 1024) {
        isMobileSidebarOpen.value = true;
    }
    notifTimer = setInterval(fetchNotifications, 30000) 
})

onUnmounted(() => {
    clearInterval(notifTimer)
    document.body.style.overflow = '' // 清除锁定
})
</script>

<template>
  <button class="mobile-toggle-button" @click="toggleMobileSidebar">
    <component :is="isMobileSidebarOpen ? IconX : IconMenu" class="nav-icon" />
  </button>
  
  <div v-if="isMobileSidebarOpen" class="sidebar-backdrop" @click="toggleMobileSidebar"></div>

  <aside class="sidebar" :class="{ 'is-open-mobile': isMobileSidebarOpen }">
    <div class="sidebar-header">
      <h3>🪙 FamilyCoin</h3>
    </div>

    <div class="user-info">
      <p>你好, <strong>{{ authStore.userInfo.username }}</strong></p>
      <p class="uid">UID: {{ authStore.userInfo.uid }}</p>
    </div>

    <nav class="main-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.routeName"
        :to="{ name: item.routeName }"
        class="nav-item"
        active-class="is-active"
      >
        <component :is="item.icon" class="nav-icon" />
        <span>{{ item.name }}</span>
      </RouterLink>

      <template v-if="authStore.userInfo.uid === '000'">
        <div class="nav-divider"></div>
        <RouterLink
          v-for="item in adminNavItems"
          :key="item.routeName"
          :to="{ name: item.routeName }"
          class="nav-item admin-link"
          active-class="is-active"
        >
          <component :is="item.icon" class="nav-icon" />
          <span>{{ item.name }}</span>
        </RouterLink>
      </template>
    </nav>
    
    <div class="notification-area">
        <div class="nav-divider"></div>
        <div class="notification-icon-wrapper" @click="toggleDropdown">
            <IconBell class="nav-icon notification-icon" />
            <span>通知</span>
            <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount }}</span>
        </div>
        
        <div v-if="showNotifDropdown" class="notification-dropdown">
            <h4 v-if="notifications.length > 0">最新通知 ({{ unreadCount }} 未读)</h4>
            <h4 v-else>无最新通知</h4>
            <div class="notif-list-wrapper">
                <ul class="notif-list">
                    <li v-for="notif in notifications" :key="notif.notif_id" :class="{ 'is-read': notif.is_read }" @click="!notif.is_read && markAsRead(notif.notif_id)">
                        <div class="notif-message">{{ notif.message }}</div>
                        <div class="notif-time">{{ formatTimestamp(notif.timestamp) }}</div>
                    </li>
                </ul>
            </div>
            <div class="notif-footer">
                <a href="#" @click.prevent="fetchNotifications">刷新列表</a>
            </div>
        </div>
    </div>
    <div class="sidebar-footer">
      <button @click="handleLogout" class="logout-button">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
/* 默认桌面布局 */
.sidebar {
  width: 280px;
  height: 100vh;
  padding: 1rem;
  background-color: #f7fafc;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: transform 0.3s ease-in-out;
}

.sidebar-header h3 {
  color: #42b883;
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
}

.user-info {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e2e8f0;
}
.user-info p {
  margin: 0.2rem 0;
  color: #4a5568;
}
.user-info strong {
  color: #2d3748;
}
.uid {
  font-size: 0.75rem;
  opacity: 0.7;
}

.main-nav {
  flex-grow: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 0.8rem 1rem;
  margin-bottom: 0.5rem;
  border-radius: 6px;
  text-decoration: none;
  color: #4a5568;
  font-weight: 500;
  transition: background-color 0.2s;
}

.nav-item:hover {
  background-color: #edf2f7;
}

.nav-item.is-active {
  background-color: #42b883;
  color: white;
}
.nav-item.is-active .nav-icon {
    stroke: white; /* 激活状态下图标颜色变白 */
}

.nav-icon {
  margin-right: 1rem;
  width: 20px;
  height: 20px;
  stroke: #4a5568; /* 默认图标颜色 */
  transition: stroke 0.2s;
}

.nav-item.is-active .nav-icon {
  stroke: white;
}

.nav-divider {
  border-top: 1px solid #e2e8f0;
  margin: 1rem 0;
}

/* --- 通知区域样式 --- */
.notification-area {
    position: relative;
    padding-bottom: 1rem;
}
.notification-icon-wrapper {
    display: flex;
    align-items: center;
    padding: 0.8rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    color: #4a5568;
    font-weight: 500;
    transition: background-color 0.2s;
    position: relative;
}
.notification-icon-wrapper:hover {
    background-color: #edf2f7;
}
.notification-icon {
    margin-right: 1rem;
}
.unread-badge {
    position: absolute;
    top: 0.5rem;
    left: 1.8rem;
    background-color: #c53030;
    color: white;
    font-size: 0.7rem;
    padding: 0.1rem 0.4rem;
    border-radius: 10px;
    line-height: 1;
    min-width: 15px;
    text-align: center;
    font-weight: 700;
}

.notification-dropdown {
    position: absolute;
    /* 默认定位（桌面）: 在侧边栏的右侧 */
    bottom: 100%; 
    left: 100%; 
    transform: translate(10px, -10px); 
    width: 350px;
    max-height: 500px;
    background-color: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 20;
    display: flex;
    flex-direction: column;
}

.notification-dropdown h4 {
    margin: 0;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    font-weight: 600;
    color: #2d3748;
    border-bottom: 1px solid #e2e8f0;
    flex-shrink: 0;
}

.notif-list-wrapper {
    overflow-y: auto;
    flex-grow: 1;
}

.notif-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.notif-list li {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #f7fafc;
    cursor: pointer;
    transition: background-color 0.2s;
}
.notif-list li:last-child {
    border-bottom: none;
}
.notif-list li:hover {
    background-color: #f7fafc;
}

.notif-list li:not(.is-read) {
    background-color: #fefcbf; /* 未读消息突出显示 */
}

.notif-list li.is-read {
    opacity: 0.7;
    background-color: #fcfcfc;
}

.notif-list li:not(.is-read) .notif-message {
    font-weight: 600;
}
.notif-time {
    font-size: 0.75rem;
    color: #718096;
    margin-top: 0.25rem;
}
.notif-footer {
    padding: 0.5rem 1rem;
    text-align: center;
    border-top: 1px solid #e2e8f0;
    flex-shrink: 0;
}
.notif-footer a {
    font-size: 0.8rem;
    color: #42b883;
    text-decoration: none;
}

/* --- 侧边栏底部和登出按钮 --- */
.sidebar-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}
.logout-button {
  width: 100%;
  padding: 0.75rem;
  background-color: #f56565;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: background-color 0.2s;
}

.logout-button:hover {
  background-color: #e53e3e;
}


/* --- 移动端响应式布局 (1024px 及以下) --- */
/* 隐藏侧边栏切换按钮 */
.mobile-toggle-button {
    display: none; 
}
.sidebar-backdrop {
    display: none; 
}


@media (max-width: 1024px) {
    /* 1. 侧边栏本身：固定定位，默认隐藏 */
    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 100; /* 确保在内容之上 */
        width: 280px; 
        max-width: 80vw;
        height: 100%;
        transform: translateX(-100%); /* 默认移出屏幕 */
        box-shadow: 3px 0 5px rgba(0, 0, 0, 0.1);
        border-right: none;
    }

    /* 2. 侧边栏打开状态 */
    .sidebar.is-open-mobile {
        transform: translateX(0); /* 滑入屏幕 */
    }

    /* 3. 移动端切换按钮：显示在页面内容区域的顶部 */
    .mobile-toggle-button {
        display: block; 
        position: fixed;
        top: 1rem;
        left: 1rem;
        z-index: 101; 
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 0.5rem;
        cursor: pointer;
        color: #4a5568;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    /* 4. 移动端背景遮罩：显示，点击关闭侧边栏 */
    .sidebar-backdrop {
        display: block; 
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: rgba(0, 0, 0, 0.5);
        z-index: 99;
    }

    /* 5. 调整通知下拉菜单的定位，使其在移动端位于侧边栏内部 */
    .notification-dropdown {
        top: auto; 
        bottom: auto; 
        left: 100%; 
        transform: translate(10px, 0); 
        
        /* 避免在移动端打开侧边栏后，通知下拉菜单还跑到屏幕外面 */
        /* 可以根据需要调整，例如让它全屏覆盖或限制在侧边栏内 */
        left: 100%; /* 保持右侧弹出 */
    }
    
    /* 当侧边栏全屏时，通知下拉菜单位于侧边栏右侧，这在小屏幕上可能不合理。
       更好的做法是让它在侧边栏内部下拉。*/
    .sidebar.is-open-mobile .notification-dropdown {
        position: absolute;
        bottom: auto;
        top: 0;
        left: 100%;
        transform: translate(10px, 0);
        /* 也可以尝试让它在底部弹出，但需要调整CSS */
    }
    
    /* 如果希望通知菜单在侧边栏内部弹出 */
    .notification-dropdown {
        /* 取消绝对定位，让它跟随内容流 */
        position: relative; 
        width: 100%;
        max-height: 300px;
        transform: none; 
        left: 0;
        bottom: auto;
        top: auto;
        margin-top: 10px;
        box-shadow: none;
        border: none;
        border-top: 1px solid #e2e8f0;
    }

}
</style>