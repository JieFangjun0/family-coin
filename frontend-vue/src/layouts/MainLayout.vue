<script setup>
import { RouterView, useRouter } from 'vue-router'
import TheSidebar from '@/components/layout/TheSidebar.vue'
import { useAuthStore } from '@/stores/auth'
import { ref, onMounted, onUnmounted } from 'vue' 
import { apiCall } from '@/api' 
import { createSignedPayload } from '@/utils/crypto' 
import { formatTimestamp } from '@/utils/formatters' 
import IconBell from '@/components/icons/IconBell.vue' 

const authStore = useAuthStore()
const router = useRouter()

// --- 通知状态 ---
const unreadCount = ref(0)
const notifications = ref([])
const showNotifDropdown = ref(false)
let notifTimer = null

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
  
  const notif = notifications.value.find(n => n.notif_id === notifId)
  if (notif && !notif.is_read) {
    notif.is_read = true;
    if (unreadCount.value > 0) unreadCount.value--;
  }
  
  apiCall('POST', '/notifications/mark_read', { payload: signedPayload });
}

function toggleDropdown() {
    showNotifDropdown.value = !showNotifDropdown.value
    if (showNotifDropdown.value) {
        notifications.value.slice(0, 5).filter(n => !n.is_read).forEach(n => markAsRead(n.notif_id));
    }
}

onMounted(() => {
    fetchNotifications() 
    notifTimer = setInterval(fetchNotifications, 30000) 
})

onUnmounted(() => {
    clearInterval(notifTimer)
})
</script>

<template>
  <div class="app-layout">
    <TheSidebar />
    <main class="main-content">
      <RouterView />
    </main>

    <div class="notification-area-wrapper">
      <div class="notification-icon-wrapper" @click="toggleDropdown">
          <IconBell class="nav-icon notification-icon" />
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

  </div>
</template>

<style scoped>
/*
 * +++ 核心修复 +++
 * .app-layout (此组件的根) 必须有 flex-grow: 1 
 * 才能填满 App.vue 的 .content-wrapper 提供的空间。
 */
.app-layout {
  display: flex;
  flex-grow: 1; /* 关键：让这个布局填满父容器 */
  background-color: #f7fafc;
  /* (移除了 height: 100vh) */
}

.main-content {
  flex-grow: 1;
  padding: 2.5rem; /* 恢复原始 padding */
  overflow-y: auto;
}

/* --- 通知区域样式 (保持不变) --- */
.notification-area-wrapper {
  position: fixed;
  top: 1.5rem;
  right: 1.5rem;
  z-index: 101;
}
.notification-icon-wrapper {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.2s ease;
}
.notification-icon-wrapper:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}
.notification-icon {
  stroke: #4a5568;
  width: 20px;
  height: 20px;
}
.unread-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background-color: #c53030;
  color: white;
  font-size: 0.75rem;
  padding: 0.1rem 0.5rem;
  border-radius: 10px;
  font-weight: 700;
  line-height: 1.2;
}
.notification-dropdown {
  position: absolute;
  top: 120%;
  right: 0;
  width: 350px;
  max-height: 500px;
  background-color: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 105;
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
    background-color: #fefcbf; 
}
.notif-list li.is-read {
    opacity: 0.7;
    background-color: #fcfcfc;
}
.notif-list li:not(.is-read) .notif-message {
    font-weight: 600;
}
.notif-message {
  font-size: 0.9rem;
  color: #2d3748;
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

/* 移动端调整 (保持不变) */
@media (max-width: 1024px) {
  .main-content {
    padding-top: 60px; 
  }
  .notification-area-wrapper {
    top: 1rem;
    right: 1rem;
  }
}
</style>