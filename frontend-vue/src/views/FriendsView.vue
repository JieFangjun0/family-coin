<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import ClickableUsername from '@/components/global/ClickableUsername.vue' // 引入组件

const authStore = useAuthStore()

const friends = ref([])
const requests = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)
const activeTab = ref('friends')

const sortedFriends = computed(() => [...friends.value].sort((a, b) => a.username.localeCompare(b.username)))

async function fetchData() {
  isLoading.value = true
  errorMessage.value = null
  const [friendsResult, requestsResult] = await Promise.all([
    apiCall('GET', '/friends/list', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/friends/requests', { params: { public_key: authStore.userInfo.publicKey } })
  ])

  const [friendsData, friendsError] = friendsResult
  if (friendsError) errorMessage.value = `加载好友列表失败: ${friendsError}`
  else friends.value = friendsData.friends

  const [requestsData, requestsError] = requestsResult
  if (requestsError) errorMessage.value = (errorMessage.value || '') + `加载好友请求失败: ${requestsError}`
  else requests.value = requestsData.requests

  isLoading.value = false
}

async function handleRespondRequest(requesterKey, accept) {
  const message = {
    owner_key: authStore.userInfo.publicKey,
    requester_key: requesterKey,
    accept: accept,
    timestamp: Math.floor(Date.now() / 1000)
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  const [data, error] = await apiCall('POST', '/friends/respond', { payload: signedPayload })
  if (error) errorMessage.value = `操作失败: ${error}`
  else {
    successMessage.value = data.detail
    await fetchData()
  }
}

async function handleDeleteFriend(targetKey) {
  if (!confirm('确定要删除这位好友吗？')) return
  const message = {
    owner_key: authStore.userInfo.publicKey,
    target_key: targetKey,
    timestamp: Math.floor(Date.now() / 1000)
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  const [data, error] = await apiCall('POST', '/friends/delete', { payload: signedPayload })
  if (error) errorMessage.value = `删除失败: ${error}`
  else {
    successMessage.value = data.detail
    await fetchData()
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="friends-view">
    <header class="view-header">
      <h1>🤝 好友管理</h1>
      <p class="subtitle">管理你的好友列表和待处理的请求。</p>
    </header>

    <div class="tabs">
      <button :class="{ active: activeTab === 'friends' }" @click="activeTab = 'friends'">我的好友 ({{ friends.length }})</button>
      <button :class="{ active: activeTab === 'requests' }" @click="activeTab = 'requests'">待处理的请求 ({{ requests.length }})</button>
    </div>

    <div v-if="isLoading" class="loading-state">正在加载...</div>
    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <div v-if="!isLoading">
      <div v-if="activeTab === 'friends'" class="tab-content">
        <div v-if="sortedFriends.length === 0" class="empty-state">你还没有好友。</div>
        <ul v-else class="friend-list">
          <li v-for="friend in sortedFriends" :key="friend.public_key">
            <ClickableUsername :uid="friend.uid" :username="friend.username" />
            <button @click="handleDeleteFriend(friend.public_key)" class="delete-button">删除</button>
          </li>
        </ul>
      </div>
      <div v-if="activeTab === 'requests'" class="tab-content">
        <div v-if="requests.length === 0" class="empty-state">没有待处理的好友请求。</div>
        <ul v-else class="request-list">
          <li v-for="req in requests" :key="req.public_key">
            <span class="request-text">
                <ClickableUsername :uid="req.uid" :username="req.username" />
                想添加你为好友。
            </span>
            <div class="actions">
              <button @click="handleRespondRequest(req.public_key, true)" class="accept-button">接受</button>
              <button @click="handleRespondRequest(req.public_key, false)" class="reject-button">拒绝</button>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.friends-view { max-width: 800px; margin: 0 auto; }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #e2e8f0; }
.tabs button { padding: 0.75rem 1.5rem; border: none; background: none; font-size: 1rem; font-weight: 600; cursor: pointer; border-bottom: 4px solid transparent; transform: translateY(2px); }
.tabs button.active { color: #42b883; border-bottom-color: #42b883; }
.friend-list, .request-list { list-style: none; padding: 0; }
.friend-list li, .request-list li { display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: #fff; border-radius: 6px; margin-bottom: 0.5rem; border: 1px solid #e2e8f0; }
.request-text { flex-grow: 1; }
.actions { display: flex; gap: 0.5rem; }
.delete-button { background-color: #f56565; }
.accept-button { background-color: #48bb78; }
.reject-button { background-color: #a0aec0; }
</style>