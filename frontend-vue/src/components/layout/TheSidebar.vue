<script setup>
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import IconWallet from '@/components/icons/IconWallet.vue'
import IconTransfer from '@/components/icons/IconTransfer.vue'
import IconInvite from '@/components/icons/IconInvite.vue'
import IconShop from '@/components/icons/IconShop.vue'
import IconCollection from '@/components/icons/IconCollection.vue'
// +++ 1. 导入新图标 +++
import IconAdmin from '@/components/icons/IconAdmin.vue'


const authStore = useAuthStore()
const router = useRouter()

const navItems = [
  { name: '我的钱包', routeName: 'wallet', icon: IconWallet },
  { name: '转账', routeName: 'transfer', icon: IconTransfer },
  { name: '邀请', routeName: 'invitations', icon: IconInvite },
  { name: '商店', routeName: 'shop', icon: IconShop },
  { name: '我的收藏', routeName: 'collection', icon: IconCollection },
]

// +++ 2. 添加一个仅管理员可见的导航项 +++
const adminNavItems = [
  {
    name: '管理员',
    routeName: 'admin',
    icon: IconAdmin,
  }
]


async function handleLogout() {
  authStore.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <aside class="sidebar">
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

    <div class="sidebar-footer">
      <button @click="handleLogout" class="logout-button">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
/* (大部分样式保持不变) */
.sidebar {
  width: 260px;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  transition: width 0.3s ease;
}

.sidebar-header h3 {
  color: #2d3748;
  text-align: center;
  margin: 0 0 2rem 0;
  font-size: 1.5rem;
  letter-spacing: 1px;
}

.user-info {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.user-info p {
  margin: 0.25rem 0;
  color: #4a5568;
}

.user-info .uid {
  font-size: 0.8rem;
  color: #718096;
}

.main-nav {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 0.8rem 1rem;
  border-radius: 6px;
  text-decoration: none;
  color: #4a5568;
  font-weight: 500;
  transition: background-color 0.2s, color 0.2s;
}

.nav-item:hover {
  background-color: #edf2f7;
}

.nav-item.is-active {
  background-color: #42b883;
  color: white;
}

/* +++ 新增管理员链接样式 +++ */
.nav-item.admin-link.is-active {
    background-color: #c53030;
}

.nav-icon {
  width: 20px;
  height: 20px;
  margin-right: 1rem;
}

/* +++ 新增分隔线样式 +++ */
.nav-divider {
    height: 1px;
    background-color: #e2e8f0;
    margin: 1rem 0;
}

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
</style>