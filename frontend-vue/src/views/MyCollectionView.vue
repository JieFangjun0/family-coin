<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import { formatTimestamp } from '@/utils/formatters'

const authStore = useAuthStore()
const nfts = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

// 用于存储每个 NFT 对应的表单数据
const listingForms = ref({})

async function fetchNfts() {
  isLoading.value = true
  errorMessage.value = null
  const [data, error] = await apiCall('GET', '/nfts/my', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (error) {
    errorMessage.value = `无法加载收藏: ${error}`
  } else {
    nfts.value = data.nfts
    // 初始化表单数据
    listingForms.value = data.nfts.reduce((acc, nft) => {
      acc[nft.nft_id] = {
        description: nft.data.name || nft.data.description || `一个 ${nft.nft_type}`,
        price: 10.0,
      }
      return acc
    }, {})
  }
  isLoading.value = false
}

async function handleListForSale(nft) {
  successMessage.value = null
  errorMessage.value = null
  
  const form = listingForms.value[nft.nft_id]
  if (!form || form.price <= 0) {
    errorMessage.value = '价格必须大于 0'
    return
  }

  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    listing_type: 'SALE', // 暂时只支持 'SALE'
    nft_id: nft.nft_id,
    nft_type: nft.nft_type,
    description: form.description,
    price: form.price,
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

// 辅助函数：格式化 NFT data
function formatNftData(data) {
  // 排除掉我们不希望在列表中显示的内部键
  const excludedKeys = ['name', 'description', 'wish_id', 'planet_id', 'creator_key', 'creator_username']
  return Object.entries(data).filter(([key]) => !excludedKeys.includes(key))
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
      <div v-for="nft in nfts" :key="nft.nft_id" class="nft-card">
        <div class="nft-header">
          <span class="nft-type">{{ nft.nft_type }}</span>
          <h3 class="nft-name">{{ nft.data.name || nft.data.description || '未命名' }}</h3>
        </div>
        <ul class="nft-data">
          <li><strong>ID:</strong> {{ nft.nft_id.substring(0, 8) }}...</li>
          <li><strong>铸造于:</strong> {{ formatTimestamp(nft.created_at) }}</li>
          <li v-for="([key, value]) in formatNftData(nft.data)" :key="key">
            <strong>{{ key }}:</strong> {{ value.toString() }}
          </li>
        </ul>
        <form class="sell-form" @submit.prevent="handleListForSale(nft)">
          <h4>上架出售</h4>
          <div class="form-group">
            <label>描述</label>
            <input type="text" v-model="listingForms[nft.nft_id].description" required />
          </div>
          <div class="form-group">
            <label>价格 (FC)</label>
            <input type="number" v-model.number="listingForms[nft.nft_id].price" min="0.01" step="0.01" required />
          </div>
          <button type="submit">确认上架</button>
        </form>
      </div>
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

.nft-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
}

.nft-header {
  padding: 1.25rem;
  border-bottom: 1px solid #e2e8f0;
}

.nft-type {
  background-color: #e2e8f0;
  color: #4a5568;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.nft-name {
  margin: 0.75rem 0 0 0;
  font-size: 1.25rem;
  color: #2d3748;
}

.nft-data {
  list-style: none;
  padding: 1.25rem;
  margin: 0;
  flex-grow: 1;
  font-size: 0.9rem;
  color: #4a5568;
}

.nft-data li {
  margin-bottom: 0.5rem;
}
.nft-data li strong {
  color: #2d3748;
}

.sell-form {
  background: #f7fafc;
  padding: 1.25rem;
  border-top: 1px solid #e2e8f0;
}
.sell-form h4 {
  margin-top: 0;
  margin-bottom: 1rem;
}
.form-group {
  margin-bottom: 0.75rem;
}
.form-group label {
  display: block;
  font-size: 0.8rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
}
input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  border: 1px solid #cbd5e0;
  box-sizing: border-box;
}
button {
  width: 100%;
  padding: 0.75rem;
  font-weight: 600;
  background-color: #42b883;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
button:hover { background-color: #369b6e; }

.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
</style>
