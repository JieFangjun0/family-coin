// family-coin-vue-refactor/frontend-vue/src/views/LoginView.vue

<script setup>
import { ref, onBeforeMount } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'

const router = useRouter()
const authStore = useAuthStore()

const isCheckingStatus = ref(true)
const usernameOrUid = ref('')
const password = ref('')
const errorMessage = ref(null)
const isLoading = ref(false)

onBeforeMount(async () => {
  const [data, error] = await apiCall('GET', '/status')

  if (error) {
    errorMessage.value = `严重错误：无法获取系统状态。请检查后端服务。 ${error}`
    isCheckingStatus.value = false
    return
  }

  if (data.needs_setup) {
    // --- 核心修复 ---
    // 1. 静默登出，清除本地可能存在的无效登录状态
    authStore.logout(false) 
    // 2. 然后再安全地跳转到创世页面
    await router.replace({ name: 'genesis' })
  } else {
    isCheckingStatus.value = false
  }
})

async function handleLogin() {
  if (!usernameOrUid.value || !password.value) {
    errorMessage.value = '用户名/UID和密码不能为空。'
    return
  }
  isLoading.value = true
  errorMessage.value = null
  const error = await authStore.login(usernameOrUid.value, password.value)
  if (error) {
    errorMessage.value = `登录失败: ${error}`
  } else {
    await router.push({ name: 'wallet' })
  }
  isLoading.value = false
}
</script>

<template>
  <div v-if="isCheckingStatus" class="loading-container">
    <div class="spinner"></div>
    <p>正在检查系统状态...</p>
  </div>

  <main v-else class="login-container">
    <h1>欢迎回来！</h1>
    <p class="subtitle">登录 FamilyCoin 开始使用</p>
    <form @submit.prevent="handleLogin" class="login-form">
      <div class="form-group">
        <label for="username">用户名或UID</label>
        <input id="username" type="text" v-model="usernameOrUid" required />
      </div>
      <div class="form-group">
        <label for="password">密码</label>
        <input id="password" type="password" v-model="password" required />
      </div>
      <button type="submit" :disabled="isLoading">
        {{ isLoading ? '登录中...' : '登录' }}
      </button>
    </form>
    <p class="footer-link">
      还没有账户？ <RouterLink :to="{ name: 'register' }">使用邀请码注册</RouterLink>
    </p>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>
  </main>
</template>

<style scoped>
.loading-container { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; }
.spinner { border: 4px solid rgba(0, 0, 0, 0.1); width: 36px; height: 36px; border-radius: 50%; border-left-color: #42b883; animation: spin 1s ease infinite; }
.loading-container p { margin-top: 1rem; color: #718096; font-weight: 500; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

.login-container { max-width: 400px; margin: 10vh auto; padding: 2rem 2.5rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); background-color: #fff; }
.subtitle { text-align: center; color: #666; margin-bottom: 2rem; }
.login-form { display: flex; flex-direction: column; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; }
label { margin-bottom: 0.5rem; font-weight: 500; }
input { padding: 0.85rem; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; }
button { padding: 0.85rem; background-color: #42b883; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 1rem; transition: background-color 0.2s; }
button:hover { background-color: #369b6e; }
button:disabled { background-color: #ccc; cursor: not-allowed; }
.message { margin-top: 1.5rem; padding: 1rem; border-radius: 4px; text-align: center; }
.error { color: #d8000c; background-color: #ffbaba; }
.footer-link { text-align: center; margin-top: 1.5rem; font-size: 0.9rem; color: #666; }
</style>