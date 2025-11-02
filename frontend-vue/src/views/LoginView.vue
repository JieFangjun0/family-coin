<script setup>
import { ref, onBeforeMount } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'

const router = useRouter()
const authStore = useAuthStore()

// --- State ---
const isCheckingStatus = ref(true) // 新增：用于在检查期间显示加载状态
const usernameOrUid = ref('')
const password = ref('')
const errorMessage = ref(null)
const isLoading = ref(false)

/**
 * 在组件挂载到 DOM 前执行。
 * 这是执行重定向或权限检查的理想位置。
 */
onBeforeMount(async () => {
  const [data, error] = await apiCall('GET', '/status')

  if (error) {
    // 如果无法连接后端，显示一个错误，而不是白屏
    errorMessage.value = `严重错误：无法获取系统状态。请检查后端服务。 ${error}`
    isCheckingStatus.value = false // 停止加载，以显示错误信息
    return
  }

  // 核心逻辑：根据后端返回的状态决定下一步操作
  if (data.needs_setup) {
    // 如果需要初始化，立即替换当前路由到创世页面
    // 使用 replace 是为了防止用户通过浏览器“后退”按钮回到这个中间状态
    await router.replace({ name: 'genesis' })
  } else {
    // 如果系统已设置好，则结束加载状态，正常显示登录表单
    isCheckingStatus.value = false
  }
})

async function handleLogin() {
  // 登录逻辑保持不变...
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
/* 样式保持不变，但新增 loading-container 的样式 */
.loading-container { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; }
.spinner { border: 4px solid rgba(0, 0, 0, 0.1); width: 36px; height: 36px; border-radius: 50%; border-left-color: #42b883; animation: spin 1s ease infinite; }
.loading-container p { margin-top: 1rem; color: #718096; font-weight: 500; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

/* ... 其他样式 ... */
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