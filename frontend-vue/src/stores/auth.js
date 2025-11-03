// family-coin-vue-refactor/frontend-vue/src/stores/auth.js

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
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
  const router = useRouter()

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

  /**
   * 处理用户登出
   * @param {boolean} [shouldRedirect=true] - 是否在登出后跳转到登录页
   */
  function logout(shouldRedirect = true) {
    userInfo.value = {
      publicKey: '',
      privateKey: '',
      username: '',
      uid: '',
    }
    localStorage.removeItem('family-coin-user')

    // 只有在需要时才执行跳转
    if (shouldRedirect) {
      router.push({ name: 'login' })
    }
  }


  return {
    userInfo,
    isLoggedIn,
    login,
    logout,
  }
})