<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import { formatTimestamp, formatCurrency } from '@/utils/formatters'
import BalanceCard from '@/components/wallet/BalanceCard.vue'
import MarketNftDetail from '@/components/nfts/MarketNftDetail.vue'
import ClickableUsername from '@/components/global/ClickableUsername.vue' // 引入组件

const authStore = useAuthStore()

const activeTab = ref('mint')
const errorMessage = ref(null)
const successMessage = ref(null)

const balance = ref(0)
const creatableNfts = ref({})
const mintForms = ref({})
const saleListings = ref([])
const myActivity = ref({ listings: [], offers: [] })

const isLoading = ref({
  balance: true,
  mint: true,
  buy: true,
  myListings: true,
})

const sortedMyListings = computed(() => {
  if (!myActivity.value.listings) return []
  return [...myActivity.value.listings].sort((a, b) => {
    if (a.status === 'ACTIVE' && b.status !== 'ACTIVE') return -1
    if (a.status !== 'ACTIVE' && b.status === 'ACTIVE') return 1
    return b.created_at - a.created_at
  })
})

async function fetchDataForTab(tab) {
  errorMessage.value = null;
  successMessage.value = null;
  switch (tab) {
    case 'mint':
      if (Object.keys(creatableNfts.value).length === 0) await fetchCreatableNfts();
      break;
    case 'buy':
      await fetchSaleListings();
      break;
    case 'my-listings':
      await fetchMyActivity();
      break;
  }
}

async function fetchBalance() {
  isLoading.value.balance = true
  const [data, error] = await apiCall('GET', '/balance', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (error) {
    errorMessage.value = `无法加载余额: ${error}`
  } else {
    balance.value = data.balance
  }
  isLoading.value.balance = false
}

async function fetchCreatableNfts() {
  isLoading.value.mint = true
  const [data, error] = await apiCall('GET', '/market/creatable_nfts')
  if (error) {
    errorMessage.value = `无法加载可铸造物品: ${error}`
  } else {
    creatableNfts.value = data
    for (const nftType in data) {
      mintForms.value[nftType] = {}
      if (data[nftType].fields) {
        for (const field of data[nftType].fields) {
          mintForms.value[nftType][field.name] = field.default ?? ''
        }
      }
    }
  }
  isLoading.value.mint = false
}

async function fetchSaleListings() {
  isLoading.value.buy = true
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: { listing_type: 'SALE' }
  })
  if (error) {
    errorMessage.value = `无法加载在售列表: ${error}`
  } else {
    saleListings.value = data.listings
  }
  isLoading.value.buy = false
}

async function fetchMyActivity() {
  isLoading.value.myListings = true
  const [data, error] = await apiCall('GET', '/market/my_activity', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (error) {
    errorMessage.value = `无法加载我的挂单: ${error}`
  } else {
    myActivity.value = data
  }
  isLoading.value.myListings = false
}

async function handleMintNft(nftType, config) {
  successMessage.value = null
  errorMessage.value = null

  if (balance.value < config.cost) {
    errorMessage.value = "你的余额不足以支付铸造成本"
    return
  }

  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    nft_type: nftType,
    cost: config.cost,
    data: mintForms.value[nftType]
  }

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建签名失败'
    return
  }
  
  const endpoint = config.action_type === 'create' ? '/market/create_nft' : '/market/shop_action'
  const [data, error] = await apiCall('POST', endpoint, { payload: signedPayload })

  if (error) {
    errorMessage.value = `操作失败: ${error}`
  } else {
    successMessage.value = data.detail
    await fetchBalance()
  }
}

async function handleBuyNft(item) {
  successMessage.value = null
  errorMessage.value = null

  const message = {
    owner_key: authStore.userInfo.publicKey,
    listing_id: item.listing_id,
    timestamp: Math.floor(Date.now() / 1000),
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
    successMessage.value = data.detail
    await fetchBalance()
    await fetchSaleListings()
  }
}

async function handleCancelListing(listingId) {
  successMessage.value = null
  errorMessage.value = null

  const message = {
    owner_key: authStore.userInfo.publicKey,
    listing_id: listingId,
    timestamp: Math.floor(Date.now() / 1000),
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建取消签名失败'
    return
  }

  const [data, error] = await apiCall('POST', '/market/cancel_listing', { payload: signedPayload })

  if (error) {
    errorMessage.value = `取消失败: ${error}`
  } else {
    successMessage.value = data.detail
    await fetchMyActivity()
  }
}

function selectTab(tab) {
  activeTab.value = tab
  fetchDataForTab(tab)
}

const LISTING_TYPE_MAP = { "SALE": "一口价", "AUCTION": "拍卖", "SEEK": "求购" }
const STATUS_MAP = { "ACTIVE": "进行中", "PENDING": "待处理", "COMPLETED": "已完成", "CANCELLED": "已取消", "REJECTED": "已拒绝", "EXPIRED": "已过期", "SOLD": "已售出", "FULFILLED": "已成交" }

function translateListingType(type) { return LISTING_TYPE_MAP[type] || type }
function translateStatus(status) { return STATUS_MAP[status] || status }

onMounted(() => {
  fetchBalance()
  selectTab('mint')
})
</script>

<template>
  <div class="shop-view">
    <header class="view-header">
      <h1>🛒 商店 & 市场</h1>
      <p class="subtitle">在这里铸造新的 NFT 或与其他成员进行交易。</p>
    </header>

    <div class="balance-display">
      <BalanceCard label="当前余额" :value="isLoading.balance ? '加载中...' : formatCurrency(balance)" unit="FC" />
    </div>

    <div class="tabs">
      <button :class="{ active: activeTab === 'mint' }" @click="selectTab('mint')">铸造工坊</button>
      <button :class="{ active: activeTab === 'buy' }" @click="selectTab('buy')">浏览市场</button>
      <button :class="{ active: activeTab === 'my-listings' }" @click="selectTab('my-listings')">我的挂单</button>
    </div>

    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <div v-if="activeTab === 'mint'" class="tab-content">
      <div v-if="isLoading.mint" class="loading-state">正在加载可铸造物品...</div>
      <div v-else-if="Object.keys(creatableNfts).length === 0" class="empty-state">
        当前没有可铸造的 NFT 类型。
      </div>
      <div v-else class="nft-grid">
         <div v-for="(config, nftType) in creatableNfts" :key="nftType" class="nft-card mint-card">
          <div class="nft-header">
            <span class="nft-type">{{ config.name }}</span>
            <span class="nft-price">{{ formatCurrency(config.cost) }} FC</span>
          </div>
          <p class="nft-description">{{ config.description }}</p>
          <form v-if="mintForms[nftType]" class="mint-form" @submit.prevent="handleMintNft(nftType, config)">
            <div v-for="field in config.fields" :key="field.name" class="form-group">
              <label :for="`${nftType}-${field.name}`">{{ field.label }}</label>
              <input 
                v-if="field.type === 'text_input'" 
                :id="`${nftType}-${field.name}`" type="text" v-model="mintForms[nftType][field.name]" 
                :required="field.required" :placeholder="field.help"
              />
              <textarea 
                v-if="field.type === 'text_area'" 
                :id="`${nftType}-${field.name}`" v-model="mintForms[nftType][field.name]" 
                :required="field.required" :placeholder="field.help" rows="3"
              ></textarea>
              <input 
                v-if="field.type === 'number_input'" 
                :id="`${nftType}-${field.name}`" type="number" v-model.number="mintForms[nftType][field.name]" 
                :required="field.required" :min="field.min_value" :max="field.max_value"
                :step="field.step || 'any'" :placeholder="field.help"
              />
            </div>
            <button type="submit" :disabled="balance < config.cost">{{ config.action_label || '支付并铸造' }}</button>
          </form>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'buy'" class="tab-content">
      <div v-if="isLoading.buy" class="loading-state">正在加载市场数据...</div>
      <div v-else-if="!saleListings || saleListings.length === 0" class="empty-state">
        市场上目前没有任何挂单。
      </div>
      <div v-else class="nft-grid">
        <div v-for="item in saleListings" :key="item.listing_id" class="nft-card buy-card">
          <div class="nft-header">
            <span class="nft-type">{{ item.nft_type }}</span>
            <span class="nft-price">{{ formatCurrency(item.price) }} FC</span>
          </div>
          <h3 class="nft-name">{{ item.trade_description || item.description }}</h3>
          
          <template v-if="item.nft_data">
              <MarketNftDetail :item="item" />
          </template>

          <ul class="nft-data">
            <li><strong>卖家:</strong> 
                <ClickableUsername :uid="item.lister_uid" :username="item.lister_username" />
                <span v-if="item.lister_key === authStore.userInfo.publicKey"> (这是你)</span>
            </li>
            <li><strong>上架于:</strong> {{ formatTimestamp(item.created_at) }}</li>
          </ul>

          <div class="buy-action">
            <button @click="handleBuyNft(item)" :disabled="balance < item.price || item.lister_key === authStore.userInfo.publicKey">
              {{ item.lister_key === authStore.userInfo.publicKey ? '你自己的商品' : '立即购买' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'my-listings'" class="tab-content">
        <div v-if="isLoading.myListings" class="loading-state">正在加载我的挂单...</div>
        <div v-else-if="!myActivity.listings || myActivity.listings.length === 0" class="empty-state">
            你还没有发布过任何挂单。
        </div>
        <div v-else class="nft-grid">
            <div v-for="item in sortedMyListings" :key="item.listing_id" class="nft-card my-listing-card" :class="`status-${item.status.toLowerCase()}`">
                <div class="nft-header">
                    <span class="nft-type-listing">{{ translateListingType(item.listing_type) }}</span>
                    <span class="nft-price">{{ formatCurrency(item.price) }} FC</span>
                </div>
                <h3 class="nft-name">{{ item.description }}</h3>
                <ul class="nft-data">
                    <li><strong>类型:</strong> {{ item.nft_type }}</li>
                    <li><strong>状态:</strong> <span class="status-text">{{ translateStatus(item.status) }}</span></li>
                    <li><strong>上架于:</strong> {{ formatTimestamp(item.created_at) }}</li>
                </ul>
                <div v-if="item.status === 'ACTIVE'" class="cancel-action">
                    <button class="cancel-button" @click="handleCancelListing(item.listing_id)">取消挂单</button>
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
.balance-display { margin-bottom: 2rem; max-width: 350px; }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #e2e8f0; }
.tabs button { padding: 0.75rem 1.5rem; border: none; background: none; font-size: 1rem; font-weight: 600; color: #718096; cursor: pointer; border-bottom: 4px solid transparent; transform: translateY(2px); transition: color 0.2s, border-color 0.2s; }
.tabs button:hover { color: #4a5568; }
.tabs button.active { color: #42b883; border-bottom-color: #42b883; }
.loading-state, .empty-state { text-align: center; padding: 3rem; color: #718096; font-size: 1.1rem; }
.nft-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
.nft-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); display: flex; flex-direction: column; transition: opacity 0.3s; }
.nft-header { padding: 1.25rem; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
.nft-type { background-color: #e2e8f0; color: #4a5568; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.nft-type-listing { background-color: #bee3f8; color: #2c5282; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.nft-price { font-size: 1.1rem; font-weight: 700; color: #2d3748; }
.nft-description { padding: 0 1.25rem; font-size: 0.9rem; color: #718096; margin: 1rem 0;}
.nft-name { margin: 0; padding: 1rem 1.25rem 0.5rem 1.25rem; font-size: 1.25rem; color: #2d3748; }
.nft-data { list-style: none; padding: 0.5rem 1.25rem 1.25rem 1.25rem; margin: 0; flex-grow: 1; font-size: 0.9rem; color: #4a5568; }
.nft-data li { margin-bottom: 0.5rem; }
.nft-data li strong { color: #2d3748; }
.mint-form, .buy-action, .cancel-action { padding: 1.25rem; background: #f7fafc; border-top: 1px solid #e2e8f0; margin-top: auto; }
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input, textarea { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; resize: vertical; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
button:hover { background-color: #369b6e; }
button:disabled { background-color: #a0aec0; cursor: not-allowed; }
.cancel-button { background-color: #f56565; }
.cancel-button:hover { background-color: #e53e3e; }
.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
.my-listing-card .status-text { font-weight: bold; }
.my-listing-card.status-active .status-text { color: #2f855a; }
.my-listing-card:not(.status-active) { opacity: 0.6; }
.my-listing-card:not(.status-active) .status-text { color: #718096; }
</style>