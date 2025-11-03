<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import NftCard from '@/components/nfts/NftCard.vue' // 导入新的分发组件

const authStore = useAuthStore()
const nfts = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

async function fetchNfts() {
  isLoading.value = true
  errorMessage.value = null
  successMessage.value = null

  const [data, error] = await apiCall('GET', '/nfts/my', {
    params: { public_key: authStore.userInfo.publicKey }
  })

  if (error) {
    errorMessage.value = `无法加载收藏: ${error}`
  } else {
    nfts.value = data.nfts
  }
  isLoading.value = false
}

// 这个函数现在接收来自子组件的事件负载
async function handleListForSale(payload) {
  const { nft, description, price } = payload
  successMessage.value = null
  errorMessage.value = null
  
  if (!price || price <= 0) {
    errorMessage.value = '价格必须大于 0'
    return
  }

  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    listing_type: 'SALE',
    nft_id: nft.nft_id,
    nft_type: nft.nft_type,
    description: description,
    price: price,
    auction_hours: null
  }

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建签名失败'
    return
  }

  const [data, error] = await apiCall('POST', '/market/create_listing', { payload: signedPayload })
  if (error) {
    errorMessage.value = `上架失败: ${error}`
  } else {
    successMessage.value = `上架成功！${data.detail || ''}`
    // 刷新列表，上架的 NFT 将会消失
    await fetchNfts()
  }
}

onMounted(fetchNfts)
</script>

<template>
  <div class="collection-view">
    <header class="view-header">
      <h1>🖼️ 我的收藏</h1>
      <p class="subtitle">你拥有的所有 NFT 都在这里。你可以在这里将它们上架出售。</p>
    </header>

    <div v-if="isLoading" class="loading-state">正在加载...</div>
    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <div v-if="!isLoading && nfts.length === 0" class="empty-state">
      你的收藏是空的。快去商店铸造或购买一些吧！
    </div>

    <div class="nft-grid">
      <NftCard 
        v-for="nft in nfts" 
        :key="nft.nft_id" 
        :nft="nft"
        @list-for-sale="handleListForSale"
      />
    </div>
  </div>
</template>

<style scoped>
.collection-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; }
.subtitle { color: #718096; margin-bottom: 2rem; }
.loading-state, .empty-state { text-align: center; padding: 3rem; color: #718096; font-size: 1.1rem; }

.nft-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 1.5rem;
}

.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
</style>