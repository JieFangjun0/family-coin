<script setup>
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ref, onMounted, onUnmounted } from 'vue' 
// (移除了所有通知相关的 imports)

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
// (移除了 IconBell)

// 菜单图标
import IconMenu from '@/components/icons/IconMenu.vue' 
import IconClose from '@/components/icons/IconClose.vue' 

// 如果 IconClose 不存在，可以手动定义一个简单的 SVG 组件:
const IconX = {
  template: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`
}

const authStore = useAuthStore()
const router = useRouter()

// --- 侧边栏状态 (用于折叠) ---
const isMobileSidebarOpen = ref(false)

// --- (移除了所有通知相关的 JS 逻辑) ---

const navItems = [
  { name: '我的钱包', routeName: 'wallet', icon: IconWallet },
  { name: '转账', routeName: 'transfer', icon: IconTransfer },
  { name: '邀请', routeName: 'invitations', icon: IconInvite },
  { name: '市场', routeName: 'shop', icon: IconShop },
  { name: '我的藏品', routeName: 'collection', icon: IconCollection },
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

// --- 侧边栏方法 (用于折叠) ---
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

async function handleLogout() {
  authStore.logout()
  await router.push({ name: 'login' })
}

onMounted(() => {
    // 检查桌面端
    if (window.innerWidth > 1024) {
        isMobileSidebarOpen.value = true;
    }
    // (移除了通知轮询)
})

onUnmounted(() => {
    // (移除了通知轮询)
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
      <h3><img src="/logo.png" class="sidebar-logo" alt="JCoin Logo" /> JCoin</h3>
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
    <div class="sidebar-footer">
      <button @click="handleLogout" class="logout-button">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
/* +++ 修复 2: 侧边栏 CSS 调整 +++ */
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
  /* 移除: overflow-y: auto; (让 nav-main 去滚动) */
}
/* +++ 修复 2 结束 +++ */

.sidebar-logo {
  width: 24px;
  height: 24px;
  margin-right: 8px; 
  vertical-align: middle; 
}

.sidebar-header h3 {
  display: flex;
  align-items: center;
  flex-shrink: 0; /* (新增) 确保页眉不收缩 */
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
  flex-shrink: 0; /* (新增) 确保用户信息不收缩 */
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

/* +++ 修复 2: 导航区域 CSS 调整 +++ */
.main-nav {
  flex-grow: 1;
  overflow-y: auto; /* (新增) 允许导航区域内部滚动 */
  min-height: 0; /* (新增) Flexbox 滚动修复 */
}
/* +++ 修复 2 结束 +++ */

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
    stroke: white; 
}

.nav-icon {
  margin-right: 1rem;
  width: 20px;
  height: 20px;
  stroke: #4a5568; 
  transition: stroke 0.2s;
}

.nav-item.is-active .nav-icon {
  stroke: white;
}

.nav-divider {
  border-top: 1px solid #e2e8f0;
  margin: 1rem 0;
}

/* (移除了所有 .notification-area-* 样式) */

/* +++ 修复 2: 页脚 CSS 调整 +++ */
.sidebar-footer {
  /* 移除: margin-top: auto; */
  flex-shrink: 0; /* (新增) 确保页脚不收缩 */
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}
/* +++ 修复 2 结束 +++ */

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


/* --- 移动端响应式布局 (保持不变) --- */
.mobile-toggle-button {
    display: none; 
}
.sidebar-backdrop {
    display: none; 
}


@media (max-width: 1024px) {
    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 100; 
        width: 280px; 
        max-width: 80vw;
        height: 100%;
        transform: translateX(-100%); 
        box-shadow: 3px 0 5px rgba(0, 0, 0, 0.1);
        border-right: none;
    }

    .sidebar.is-open-mobile {
        transform: translateX(0); 
    }

    .mobile-toggle-button {
        display: flex; /* (修改) 使用 flex 居中图标 */
        justify-content: center;
        align-items: center;
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
        width: 44px; /* (新增) 统一样式 */
        height: 44px; /* (新增) 统一样式 */
    }
    
    .mobile-toggle-button .nav-icon {
      margin-right: 0; /* (新增) 移除图标的 margin */
    }
    
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
    
    /* (移除了移动端 .notification-dropdown 的样式) */
}
</style>