import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue' // <-- 新增 watch
import { useRouter } from 'vue-router'
import { apiCall, setLogoutHandler } from '@/api'

// 我们将用户信息存储在 localStorage 中，以便在刷新页面后保持登录状态
const usePersistentState = (key, defaultValue) => {
  const state = ref(JSON.parse(localStorage.getItem(key)) ?? defaultValue)

  watch(
    state,
    (newValue) => {
      localStorage.setItem(key, JSON.stringify(newValue))
    },
    { deep: true }
  )

  return state
}


export const useAuthStore = defineStore('auth', () => {
  const router = useRouter()

  // --- State ---
  const userInfo = usePersistentState('family-coin-user', {
    publicKey: '',
    privateKey: '',
    username: '',
    uid: '',
  })

  // --- Getters ---
  const isLoggedIn = computed(() => !!userInfo.value?.publicKey && !!userInfo.value?.privateKey)

  // --- Actions ---

  /**
   * 处理用户登录
   * @param {string} usernameOrUid
   * @param {string} password
   * @returns {Promise<string|null>} - 成功则返回 null，失败则返回错误信息
   */
  async function login(usernameOrUid, password) {
    const [data, error] = await apiCall('POST', '/login', {
      payload: {
        username_or_uid: usernameOrUid,
        password: password,
      },
    })

    if (error) {
      return error
    }

    if (data) {
      userInfo.value = {
        publicKey: data.public_key,
        privateKey: data.private_key,
        username: data.username,
        uid: data.uid,
      }
      return null
    }

    return '发生未知错误'
  }

  /**
   * 处理用户登出
   */
  function logout() {
    userInfo.value = {
      publicKey: '',
      privateKey: '',
      username: '',
      uid: '',
    }
    // 清除 localStorage
    localStorage.removeItem('family-coin-user')
    // 跳转到登录页
    router.push({ name: 'login' })
  }


  return {
    // state
    userInfo,
    // getters
    isLoggedIn,
    // actions
    login,
    logout,
  }
})