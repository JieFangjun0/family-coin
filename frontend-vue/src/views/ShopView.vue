<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import { formatTimestamp, formatCurrency } from '@/utils/formatters'

const authStore = useAuthStore()
const activeTab = ref('mint') // 'mint' 或 'buy'

// --- 铸造 (Mint) 状态 ---
const creatableNfts = ref({})
const mintForms = ref({})
const isMintLoading = ref(true)

// --- 购买 (Buy) 状态 ---
const saleListings = ref([])
const isBuyLoading = ref(true)

// --- 通用状态 ---
const errorMessage = ref(null)
const successMessage = ref(null)

// --- 铸造相关方法 ---
async function fetchCreatableNfts() {
  isMintLoading.value = true
  const [data, error] = await apiCall('GET', '/market/creatable_nfts')
  if (error) {
    errorMessage.value = `无法加载可铸造列表: ${error}`
  } else {
    creatableNfts.value = data
    // 初始化铸造表单
    mintForms.value = Object.keys(data).reduce((acc, nftType) => {
      acc[nftType] = data[nftType].fields.reduce((formAcc, field) => {
        formAcc[field.name] = field.default || ''
        return formAcc
      }, {})
      return acc
    }, {})
  }
  isMintLoading.value = false
}

async function handleMintNft(nftType, config) {
  successMessage.value = null
  errorMessage.value = null

  const formData = mintForms.value[nftType]
  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    nft_type: nftType,
    cost: config.cost,
    data: formData,
  }

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建签名失败'
    return
  }

  const [data, error] = await apiCall('POST', '/market/create_nft', { payload: signedPayload })
  if (error) {
    errorMessage.value = `铸造失败: ${error}`
  } else {
    successMessage.value = `铸造成功！${data.detail || ''}`
    // 重置表单
    Object.keys(formData).forEach(key => {
      formData[key] = creatableNfts.value[nftType].fields.find(f => f.name === key).default || ''
    })
    // 可以在此添加一个刷新钱包余额的调用
  }
}

// --- 购买相关方法 ---
async function fetchSaleListings() {
  isBuyLoading.value = true
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: {
      listing_type: 'SALE',
      exclude_owner: authStore.userInfo.publicKey
    }
  })
  if (error) {
    errorMessage.value = `无法加载在售列表: ${error}`
  } else {
    saleListings.value = data.listings
  }
  isBuyLoading.value = false
}

async function handleBuyNft(item) {
  successMessage.value = null
  errorMessage.value = null

  const message = {
    owner_key: authStore.userInfo.publicKey,
    listing_id: item.listing_id,
    timestamp: Math.floor(Date.now() / 1000)
  }

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建购买签名失败'
    return
  }

  const [data, error] = await apiCall('POST', '/market/buy', { payload: signedPayload })
  if (error) {
    errorMessage.value = `购买失败: ${error}`
  } else {
    successMessage.value = `购买成功！${data.detail || ''}`
    // 购买成功后，刷新列表
    await fetchSaleListings()
    // 也可以在此添加刷新钱包余额的调用
  }
}

// --- 切换 Tab ---
function selectTab(tab) {
  activeTab.value = tab
  errorMessage.value = null
  successMessage.value = null
  if (tab === 'mint' && Object.keys(creatableNfts.value).length === 0) {
    fetchCreatableNfts()
  }
  if (tab === 'buy' && saleListings.value.length === 0) {
    fetchSaleListings()
  }
}

// --- 格式化辅助 ---
function formatNftData(data) {
  const excludedKeys = ['name', 'description', 'wish_id', 'planet_id', 'creator_key', 'creator_username']
  return Object.entries(data).filter(([key]) => !excludedKeys.includes(key))
}

// --- 初始加载 ---
onMounted(() => {
  selectTab('mint') // 默认加载铸造页面
})
</script>

<template>
  <div class="shop-view">
    <header class="view-header">
      <h1>🛒 商店 & 市场</h1>
      <p class="subtitle">在这里铸造新的 NFT 或购买他人的收藏。</p>
    </header>

    <div class="tabs">
      <button :class="['tab-button', { active: activeTab === 'mint' }]" @click="selectTab('mint')">
        铸造工坊
      </button>
      <button :class="['tab-button', { active: activeTab === 'buy' }]" @click="selectTab('buy')">
        购买市场 (一口价)
      </button>
      <!-- 其他市场功能 (拍卖, 求购) 可以在此添加 -->
    </div>

    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <!-- 铸造工坊 (MINT) -->
    <div v-if="activeTab === 'mint'" class="tab-content">
      <div v-if="isMintLoading" class="loading-state">正在加载...</div>
      <div v-if="!isMintLoading && Object.keys(creatableNfts).length === 0" class="empty-state">
        当前没有可铸造的 NFT 类型。
      </div>
      <div class="nft-grid">
        <div v-for="(config, nftType) in creatableNfts" :key="nftType" class="nft-card mint-card">
          <div class="nft-header">
            <span class="nft-type">{{ config.name }}</span>
            <span class="nft-price">{{ formatCurrency(config.cost) }} FC</span>
          </div>
          <p class="nft-description">{{ config.description }}</p>
          <form class="mint-form" @submit.prevent="handleMintNft(nftType, config)">
            <div v-for="field in config.fields" :key="field.name" class="form-group">
              <label :for="field.name">{{ field.label }}</label>
              <input 
                v-if="field.type === 'text_input'" 
                :id="field.name"
                type="text" 
                v-model="mintForms[nftType][field.name]" 
                :required="field.required" 
                :placeholder="field.help"
              />
              <textarea 
                v-if="field.type === 'text_area'" 
                :id="field.name"
                v-model="mintForms[nftType][field.name]" 
                :required="field.required" 
                :placeholder="field.help"
                rows="3"
              ></textarea>
              <input 
                v-if="field.type === 'number_input'" 
                :id="field.name"
                type="number" 
                v-model.number="mintForms[nftType][field.name]" 
                :required="field.required" 
                :min="field.min_value"
                :max="field.max_value"
                :step="field.step"
                :placeholder="field.help"
              />
            </div>
            <button type="submit">{{ config.action_label || '支付并铸造' }}</button>
          </form>
        </div>
      </div>
    </div>

    <!-- 购买市场 (BUY) -->
    <div v-if="activeTab === 'buy'" class="tab-content">
      <div v-if="isBuyLoading" class="loading-state">正在加载...</div>
      <div v-if="!isBuyLoading && saleListings.length === 0" class="empty-state">
        市场上目前没有待售的 NFT。
      </div>
      <div class="nft-grid">
        <div v-for="item in saleListings" :key="item.listing_id" class="nft-card buy-card">
          <div class="nft-header">
            <span class="nft-type">{{ item.nft_type }}</span>
            <span class="nft-price">{{ formatCurrency(item.price) }} FC</span>
          </div>
          <h3 class="nft-name">{{ item.trade_description || item.description }}</h3>
          <ul class="nft-data">
            <li><strong>卖家:</strong> {{ item.lister_username }} (UID: {{ item.lister_uid }})</li>
            <li><strong>上架于:</strong> {{ formatTimestamp(item.created_at) }}</li>
            <!-- 显示 item.nft_data 中的关键信息 -->
            <li v-if="item.nft_data" v-for="([key, value]) in formatNftData(item.nft_data)" :key="key">
              <strong>{{ key }}:</strong> {{ value.toString() }}
            </li>
          </ul>
          <div class="buy-action">
            <button @click="handleBuyNft(item)">立即购买</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.shop-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; }
.subtitle { color: #718096; margin-bottom: 1.5rem; }

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid #e2e8f0;
}
.tab-button {
  padding: 0.75rem 1.5rem;
  border: none;
  background: none;
  font-size: 1rem;
  font-weight: 600;
  color: #718096;
  cursor: pointer;
  border-bottom: 4px solid transparent;
  transform: translateY(2px);
}
.tab-button.active {
  color: #42b883;
  border-bottom-color: #42b883;
}

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
  display: flex;
  justify-content: space-between;
  align-items: center;
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
.nft-price {
  font-size: 1.1rem;
  font-weight: 700;
  color: #2d3748;
}

.nft-description {
  padding: 0 1.25rem;
  font-size: 0.9rem;
  color: #718096;
}

.nft-name {
  margin: 0;
  padding: 1rem 1.25rem 0.5rem 1.25rem;
  font-size: 1.25rem;
  color: #2d3748;
}

.nft-data {
  list-style: none;
  padding: 0.5rem 1.25rem 1.25rem 1.25rem;
  margin: 0;
  flex-grow: 1;
  font-size: 0.9rem;
  color: #4a5568;
}
.nft-data li { margin-bottom: 0.5rem; }
.nft-data li strong { color: #2d3748; }

.mint-form {
  padding: 1.25rem;
  background: #f7fafc;
  border-top: 1px solid #e2e8f0;
}
.buy-action {
  padding: 1.25rem;
  background: #f7fafc;
  border-top: 1px solid #e2e8f0;
}

.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input, textarea {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  border: 1px solid #cbd5e0;
  box-sizing: border-box;
  resize: vertical;
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
