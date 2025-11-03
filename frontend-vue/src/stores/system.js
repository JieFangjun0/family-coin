import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiCall } from '@/api'

/**
 * 管理全局系统状态，例如是否需要初始化。
 */
export const useSystemStore = defineStore('system', () => {
  // --- State ---
  const needsSetup = ref(null) // null: 未知, true: 需要, false: 不需要
  const isLoading = ref(true)

  // --- Actions ---
  /**
   * 检查后端系统状态，并更新 needsSetup 的值。
   * 这个函数应该在应用启动时被调用一次。
   * @returns {Promise<void>}
   */
  async function checkSystemStatus() {
    isLoading.value = true
    const [data, error] = await apiCall('GET', '/status')
    if (error) {
      // 在实际应用中，这里应该显示一个全局的、阻塞性的错误页面
      console.error('CRITICAL: Cannot connect to backend to check system status.', error)
      // 为防止应用卡死，我们假设系统已设置
      needsSetup.value = false
    } else {
      needsSetup.value = data.needs_setup
    }
    isLoading.value = false
  }

  return {
    needsSetup,
    isLoading,
    checkSystemStatus,
  }
})