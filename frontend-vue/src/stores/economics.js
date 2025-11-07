import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiCall } from '@/api'

/**
 * 管理所有 NFT 类型的后端经济配置
 */
export const useEconomicsStore = defineStore('economics', () => {
  // --- State ---
  // configs 将是一个对象，键为 NFT 类型 (e.g., "PLANET", "BIO_DNA")
  const configs = ref({})
  const isLoading = ref(true)
  const error = ref(null)

  // --- Actions ---
  /**
   * (在应用启动时调用)
   * 从后端 /api/nfts/economics/all 获取所有公开的经济配置
   */
  async function fetchEconomics() {
    isLoading.value = true
    error.value = null
    const [data, apiError] = await apiCall('GET', '/nfts/economics/all')
    
    if (apiError) {
      console.error('无法加载后端经济配置:', apiError)
      error.value = apiError
    } else {
      configs.value = data
      console.log('后端经济配置已加载:', data)
    }
    isLoading.value = false
  }

  return {
    configs,
    isLoading,
    error,
    fetchEconomics,
  }
})