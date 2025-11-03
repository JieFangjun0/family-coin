// family-coin-vue-refactor/frontend-vue/src/stores/auth.js

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
// --- 1. 彻底移除 useRouter 的导入 ---
// import { useRouter } from 'vue-router' 
import { apiCall, setLogoutHandler } from '@/api'

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
  const userInfo = usePersistentState('family-coin-user', {
    publicKey: '',
    privateKey: '',
    username: '',
    uid: '',
  })

  const isLoggedIn = computed(() => !!userInfo.value?.publicKey && !!userInfo.value?.privateKey)

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

  // --- 2. 简化 logout 函数，移除所有路由相关代码 ---
  function logout() {
    userInfo.value = {
      publicKey: '',
      privateKey: '',
      username: '',
      uid: '',
    }
    localStorage.removeItem('family-coin-user')
    // 注意：这里不再有任何 router.push 的调用
  }


  return {
    userInfo,
    isLoggedIn,
    login,
    logout,
  }
})