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
    <h1><img src="/logo.png" class="login-logo" alt="JCoin Logo" /> 欢迎来到 JCoin！</h1>
  <p class="subtitle">一个充满活力的微型虚拟经济世界。</p>

  <div class="intro-text">
    <p>在这里，你可以：</p>
    <ul>
      <li><strong>探索与创造：</strong> 发现未知的“星球”，或封存一个“秘密”...</li>
      <li><strong>交易与竞拍：</strong> 在活跃的市场中买卖、拍卖你的数字资产。</li>
      <li><strong>收集与展示：</strong> 建立你的专属收藏，并在个人主页上向他人炫耀。</li>
    </ul>
  </div>
  <p class="disclaimer">
      JCoin 仅供站长个人学习与实验。所有数字资产和“JCoin”均为虚拟道具，不具有任何真实价值。请理性参与。
    </p> 
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
.login-logo {
  width: 32px;
  height: 32px;
  margin-right: 10px;
  vertical-align: bottom;
}
.login-container h1 {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.8rem;
}
.intro-text {
  font-size: 0.95rem;
  color: #4a5568;
  background-color: #f7fafc;
  padding: 0.75rem 1.25rem;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  /* (修改) 减小与下方免责声明的间距 */
  margin-bottom: 1.5rem; 
}
.intro-text p {
  margin: 0 0 0.5rem 0;
  font-weight: 500;
  color: #2d3748;
}
.intro-text ul {
  margin: 0;
  padding-left: 1.25rem;
  line-height: 1.6;
}
.intro-text li {
  margin-bottom: 0.25rem;
}
.subtitle {
  margin-bottom: 1.5rem; 
}

/* (新增) 免责声明的专属样式 */
.disclaimer {
  font-size: 0.8rem; /* 更小的字体 */
  color: #718096; /* 灰色，不显眼 */
  text-align: center; /* 居中 */
  margin-bottom: 2rem; /* 与下方登录框的间距 */
  padding: 0 1rem; /* 左右留白 */
  line-height: 1.4;
}
</style>