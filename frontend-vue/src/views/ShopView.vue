<script setup>
import { ref, onMounted, computed, reactive, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import { formatTimestamp, formatCurrency } from '@/utils/formatters'
import BalanceCard from '@/components/wallet/BalanceCard.vue'
import MarketNftDetail from '@/components/nfts/MarketNftDetail.vue'
import ClickableUsername from '@/components/global/ClickableUsername.vue'

const authStore = useAuthStore()

// --- 状态 ---
const activeTab = ref('mint')
const errorMessage = ref(null) // 全局错误
const successMessage = ref(null) // 全局成功

// 局部反馈状态 (例如: { "NFT_TYPE": { text: "...", type: "success" } })
const localFeedback = ref({})

const balance = ref(0)
const creatableNfts = ref({})
const saleListings = ref([])
const auctionListings = ref([]) 
const seekListings = ref([])    
const allNftTypes = ref({}) 
const myNfts = ref([])      
const myActivity = ref({ listings: [], offers: [] })
const myOffersDetails = ref({}) 
const auctionBidHistory = reactive({})

const showInactiveListings = ref(false)

// 商店板块的子标签页状态
const activeMintTab = ref(null)
const activeBuyTab = ref(null)
const activeAuctionTab = ref(null)
const activeSeekTab = ref(null)

// 搜索状态
const searchTerm = ref('')

// --- 表单 ---
const mintForms = ref({})
const bidForms = reactive({}) 
const seekForm = reactive({   
  nft_type: '',
  description: '',
  price: 10.0
})
const offerForms = reactive({}) 

// --- 加载状态 ---
const isLoading = ref({
  balance: true,
  mint: true,
  buy: true,
  auction: true, 
  seek: true,    
  myListings: true,
  myNfts: true,  
  allTypes: true 
})

// --- Computed ---

// 排序后的“我的挂单”
const sortedMyListings = computed(() => {
  if (!myActivity.value.listings) return []
  const filtered = myActivity.value.listings.filter(item => {
    if (showInactiveListings.value) return true;
    return item.status === 'ACTIVE';
  });
  return [...filtered].sort((a, b) => {
    if (a.status === 'ACTIVE' && b.status !== 'ACTIVE') return -1
    if (a.status !== 'ACTIVE' && b.status === 'ACTIVE') return 1
    return b.created_at - a.created_at
  })
})

// 计算符合求购类型的、我拥有的 NFT
const computedEligibleNfts = (seekNftType) => {
  return myNfts.value.filter(nft => nft.nft_type === seekNftType && nft.status === 'ACTIVE');
}

// --- 分组辅助函数 ---
const groupListingsByType = (listings) => {
  const groups = {}
  for (const item of listings) {
    if (!groups[item.nft_type]) {
      groups[item.nft_type] = []
    }
    groups[item.nft_type].push(item)
  }
  return groups
}

// --- 藏品创造 (Creatable) ---
const creatableNftsByType = computed(() => {
  // creatableNfts 已经是按类型分组的对象，但值是 config，我们将其转为数组
  const groups = {}
  for (const nftType in creatableNfts.value) {
    groups[nftType] = [creatableNfts.value[nftType]] // 将 config 包装在数组中以便 v-for
  }
  return groups
})
const sortedCreatableTypes = computed(() => {
  const keys = Object.keys(creatableNftsByType.value).sort()
  if (activeMintTab.value === null && keys.length > 0) {
    activeMintTab.value = keys[0]
  }
  return keys
})

// --- 一口价 (Sale) ---
const saleListingsByType = computed(() => groupListingsByType(saleListings.value))
const sortedSaleTypes = computed(() => {
  const keys = Object.keys(saleListingsByType.value).sort()
  if (activeBuyTab.value === null && keys.length > 0) {
    activeBuyTab.value = keys[0]
  }
  return keys
})

// --- 拍卖行 (Auction) ---
const auctionListingsByType = computed(() => groupListingsByType(auctionListings.value))
const sortedAuctionTypes = computed(() => {
  const keys = Object.keys(auctionListingsByType.value).sort()
  if (activeAuctionTab.value === null && keys.length > 0) {
    activeAuctionTab.value = keys[0]
  }
  return keys
})

// --- 求购 (Seek) ---
const seekListingsByType = computed(() => groupListingsByType(seekListings.value))
const sortedSeekTypes = computed(() => {
  const keys = Object.keys(seekListingsByType.value).sort()
  if (activeSeekTab.value === null && keys.length > 0) {
    activeSeekTab.value = keys[0]
  }
  return keys
})


// --- 翻译 ---
const LISTING_TYPE_MAP = { "SALE": "一口价", "AUCTION": "拍卖", "SEEK": "求购" }
const STATUS_MAP = { "ACTIVE": "进行中", "PENDING": "待处理", "SOLD": "已售出", "CANCELLED": "已取消", "REJECTED": "已拒绝", "EXPIRED": "已过期", "FULFILLED": "已成交" }

function translateListingType(type) { return LISTING_TYPE_MAP[type] || type }
function translateStatus(status) { return STATUS_MAP[status] || status }

// --- API 调用 ---

async function fetchDataForTab(tab) {
  errorMessage.value = null;
  const currentSearchTerm = searchTerm.value;
  switch (tab) {
    case 'mint':
      if (Object.keys(creatableNfts.value).length === 0) {
        await Promise.all([fetchCreatableNfts(), fetchAllNftTypes()]);
      }
      break;
    case 'buy':
      await Promise.all([
        fetchSaleListings(currentSearchTerm), // 传入搜索词
        fetchAllNftTypes()
      ]);
      break;
    case 'auction': 
      await Promise.all([
        fetchAuctionListings(currentSearchTerm), // 传入搜索词
        fetchAllNftTypes()
      ]);
      break;
    case 'seek': 
      await Promise.all([
        fetchSeekListings(currentSearchTerm), // 传入搜索词
        fetchAllNftTypes(),
        fetchMyNfts()
      ]);
      break;
    case 'my-listings':
      await Promise.all([
        fetchMyActivity(),
        fetchAllNftTypes()
      ]);
      break;
  }
}

async function fetchBalance() {
  isLoading.value.balance = true
  const [data, error] = await apiCall('GET', '/balance', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (error) errorMessage.value = `无法加载余额: ${error}`
  else balance.value = data.balance
  isLoading.value.balance = false
}

async function fetchCreatableNfts() {
  isLoading.value.mint = true
  activeMintTab.value = null // 重置tab
  const [data, error] = await apiCall('GET', '/market/creatable_nfts')
  if (error) {
    errorMessage.value = `无法加载可创造藏品: ${error}`
  } else {
    creatableNfts.value = data
    // 初始化 mint 表单
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

async function fetchSaleListings(search_term = null) {
  isLoading.value.buy = true
  activeBuyTab.value = null 
  const params = { listing_type: 'SALE' }
  if (search_term) {
      params.search_term = search_term
  }
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: params
  })
  if (error) errorMessage.value = `无法加载在售列表: ${error}`
  else saleListings.value = data.listings
  isLoading.value.buy = false
}

async function fetchAuctionListings(search_term = null) {
  isLoading.value.auction = true
  activeAuctionTab.value = null 
  const params = { listing_type: 'AUCTION' }
  if (search_term) {
      params.search_term = search_term
  }
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: params
  })
  if (error) {
    errorMessage.value = `无法加载拍卖列表: ${error}`
  } else {
    auctionListings.value = data.listings
    // 初始化拍卖出价表单
    data.listings.forEach(item => {
      if (!bidForms[item.listing_id]) {
        bidForms[item.listing_id] = parseFloat(((item.highest_bid || item.price) + 0.01).toFixed(2))
      }
    })
  }
  isLoading.value.auction = false
}

async function fetchSeekListings(search_term = null) {
  isLoading.value.seek = true
  activeSeekTab.value = null 
  const params = { listing_type: 'SEEK' }
  if (search_term) {
      params.search_term = search_term
  }
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: params
  })
  if (error) {
    errorMessage.value = `无法加载求购列表: ${error}`
  } else {
    seekListings.value = data.listings
    // 初始化求购报价表单
    data.listings.forEach(item => {
      if (!offerForms[item.listing_id]) {
        offerForms[item.listing_id] = null
      }
    })
  }
  isLoading.value.seek = false
}

async function fetchAllNftTypes() {
  isLoading.value.allTypes = true
  const [data, error] = await apiCall('GET', '/nfts/display_names')
  if (error) errorMessage.value = `无法加载藏品类型: ${error}`
  else {
    allNftTypes.value = data
    // 设置求购表单的默认类型
    if (!seekForm.nft_type && Object.keys(data).length > 0) {
      seekForm.nft_type = Object.keys(data)[0] 
    }
  }
  isLoading.value.allTypes = false
}

async function fetchMyNfts() {
  isLoading.value.myNfts = true
  const [data, error] = await apiCall('GET', '/nfts/my', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (error) errorMessage.value = `无法加载我的藏品: ${error}`
  else myNfts.value = data.nfts
  isLoading.value.myNfts = false
}

async function fetchMyActivity() {
  isLoading.value.myListings = true
  myOffersDetails.value = {} // 重置报价详情
  const [data, error] = await apiCall('GET', '/market/my_activity', {
    params: { public_key: authStore.userInfo.publicKey }
  })
  if (error) errorMessage.value = `无法加载我的挂单: ${error}`
  else myActivity.value = data
  isLoading.value.myListings = false
}

// --- 事件处理 ---

function selectTab(tab) {
  activeTab.value = tab
  fetchDataForTab(tab)
}

function handleSearch() {
  // 只在市场相关的标签页触发搜索
  if (activeTab.value === 'buy' || activeTab.value === 'auction' || activeTab.value === 'seek') {
    fetchDataForTab(activeTab.value)
  }
}

async function handleMintNft(nftType, config) {
  // 清空局部和全局消息
  localFeedback.value[nftType] = null
  successMessage.value = null
  errorMessage.value = null
  
  if (balance.value < config.cost) {
    const msg = "你的余额不足以支付创造成本"
    errorMessage.value = msg // 设置全局错误
    localFeedback.value[nftType] = { text: msg, type: 'error' } // 设置局部错误
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
    const msg = '创建签名失败'
    errorMessage.value = msg
    localFeedback.value[nftType] = { text: msg, type: 'error' }
    return
  }
  
  const endpoint = config.action_type === 'create' ? '/market/create_nft' : '/market/shop_action'
  const [data, error] = await apiCall('POST', endpoint, { payload: signedPayload })
  
  if (error) {
    const msg = `操作失败: ${error}`
    errorMessage.value = msg
    localFeedback.value[nftType] = { text: error, type: 'error' } // 局部显示 API 返回的 error
  } else {
    const msg = data.detail
    successMessage.value = msg
    localFeedback.value[nftType] = { text: msg, type: 'success' }
    await fetchBalance()
  }

  // 5秒后清除局部消息
  setTimeout(() => {
    if (localFeedback.value[nftType]) {
      localFeedback.value[nftType] = null
    }
  }, 5000)
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
  if (error) errorMessage.value = `购买失败: ${error}`
  else {
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
  if (error) errorMessage.value = `取消失败: ${error}`
  else {
    successMessage.value = data.detail
    await fetchMyActivity()
  }
}

async function handlePlaceBid(item) {
  successMessage.value = null
  errorMessage.value = null

  const bidAmount = parseFloat(bidForms[item.listing_id])
  const minBid = parseFloat(((item.highest_bid || item.price) + 0.01).toFixed(2))

  if (!bidAmount || bidAmount < minBid) {
    errorMessage.value = `出价必须至少为 ${formatCurrency(minBid)} JCoin`
    return
  }
  if (balance.value < bidAmount) {
    errorMessage.value = '你的余额不足以支撑此出价'
    return
  }

  const message = {
    owner_key: authStore.userInfo.publicKey,
    listing_id: item.listing_id,
    amount: bidAmount,
    timestamp: Math.floor(Date.now() / 1000),
  }
  
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建出价签名失败'
    return
  }

  const [data, error] = await apiCall('POST', '/market/place_bid', { payload: signedPayload })
  if (error) {
    errorMessage.value = `出价失败: ${error}`
  } else {
    successMessage.value = data.detail
    await fetchBalance()
    await fetchAuctionListings()
    // 清除缓存的拍卖历史
    if (auctionBidHistory[item.listing_id]) {
      delete auctionBidHistory[item.listing_id]
    }
  }
}

async function fetchBidHistory(listingId) {
  // 如果已显示，则切换为隐藏
  if (auctionBidHistory[listingId] && auctionBidHistory[listingId].show) {
    auctionBidHistory[listingId].show = false;
    return;
  }
  
  auctionBidHistory[listingId] = { isLoading: true, bids: [], show: true };
  const [data, error] = await apiCall('GET', `/market/listings/${listingId}/bids`);
  if (error) {
    errorMessage.value = `无法加载出价历史: ${error}`;
    auctionBidHistory[listingId] = { isLoading: false, bids: [], show: true };
  } else {
    auctionBidHistory[listingId] = { isLoading: false, bids: data, show: true };
  }
}

async function handleCreateSeekListing() {
  successMessage.value = null
  errorMessage.value = null
  if (!seekForm.nft_type || !seekForm.description || seekForm.price <= 0) {
    errorMessage.value = '请填写所有求购字段'
    return
  }
  if (balance.value < seekForm.price) {
    errorMessage.value = '你的余额不足以支付求购预算'
    return
  }
  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    listing_type: 'SEEK',
    nft_id: null,
    nft_type: seekForm.nft_type,
    description: seekForm.description,
    price: seekForm.price,
    auction_hours: null
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建求购签名失败'
    return
  }
  const [data, error] = await apiCall('POST', '/market/create_listing', { payload: signedPayload })
  if (error) errorMessage.value = `发布求购失败: ${error}`
  else {
    successMessage.value = data.detail
    // 重置表单
    seekForm.description = ''
    seekForm.price = 10.0
    // 刷新数据
    await fetchBalance()
    await fetchSeekListings()
    await fetchMyActivity() 
  }
}

async function handleMakeOffer(item) {
  successMessage.value = null
  errorMessage.value = null
  const offeredNftId = offerForms[item.listing_id]
  if (!offeredNftId) {
    errorMessage.value = '请选择一个你拥有的藏品进行报价'
    return
  }
  const message = {
    owner_key: authStore.userInfo.publicKey,
    listing_id: item.listing_id,
    offered_nft_id: offeredNftId,
    timestamp: Math.floor(Date.now() / 1000),
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建报价签名失败'
    return
  }
  const [data, error] = await apiCall('POST', '/market/make_offer', { payload: signedPayload })
  if (error) errorMessage.value = `报价失败: ${error}`
  else {
    successMessage.value = data.detail
    await fetchMyNfts() // 刷新我的 NFT 列表 (因为报价的 NFT 状态会改变)
    await fetchMyActivity() // 刷新我的交易活动
  }
}

async function fetchOffersForMyListing(listingId) {
  myOffersDetails.value[listingId] = { isLoading: true, offers: [] }
  const [data, error] = await apiCall('GET', '/market/offers', {
    params: { listing_id: listingId }
  })
  if (error) {
    errorMessage.value = `无法加载报价: ${error}`
    myOffersDetails.value[listingId] = { isLoading: false, offers: [] }
  } else {
    myOffersDetails.value[listingId] = { isLoading: false, offers: data.offers }
  }
}

async function handleRespondToOffer(offerId, accept) {
  successMessage.value = null
  errorMessage.value = null
  const message = {
    owner_key: authStore.userInfo.publicKey,
    offer_id: offerId,
    accept: accept,
    timestamp: Math.floor(Date.now() / 1000),
  }
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建回应签名失败'
    return
  }
  const [data, error] = await apiCall('POST', '/market/respond_offer', { payload: signedPayload })
  if (error) errorMessage.value = `操作失败: ${error}`
  else {
    successMessage.value = data.detail
    // 刷新所有相关数据
    await fetchBalance()
    await fetchMyActivity()
    await fetchMyNfts() 
  }
}


onMounted(() => {
  fetchBalance()
  selectTab('mint')
})
</script>

<template>
  <div class="shop-view">
    <header class="view-header">
      <h1>🛒 商店 & 市场</h1>
      <p class="subtitle">在这里创造新的藏品或与其他成员进行交易。</p>
    </header>

    <div class="balance-display">
      <BalanceCard label="当前余额" :value="isLoading.balance ? '加载中...' : formatCurrency(balance)" unit="JCoin" />
    </div>

    <div class="tabs">
      <button :class="{ active: activeTab === 'mint' }" @click="selectTab('mint')">藏品创造</button>
      <button :class="{ active: activeTab === 'buy' }" @click="selectTab('buy')">一口价</button>
      <button :class="{ active: activeTab === 'auction' }" @click="selectTab('auction')">拍卖行</button>
      <button :class="{ active: activeTab === 'seek' }" @click="selectTab('seek')">求购</button>
      <button :class="{ active: activeTab === 'my-listings' }" @click="selectTab('my-listings')">我的交易</button>
    </div>

    <div 
        v-if="activeTab !== 'mint' && activeTab !== 'my-listings'"
        class="search-bar"
    >
        <form @submit.prevent="handleSearch">
            <input type="text" v-model="searchTerm" placeholder="搜索挂单描述 (例如: 稀有行星, 秘密愿望...)" />
            <button type="submit">搜索</button>
        </form>
    </div>
    
    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

        <div v-if="activeTab === 'mint'" class="tab-content">
      <div v-if="isLoading.mint" class="loading-state">正在加载藏品创造界面...</div>
      <div v-else-if="!sortedCreatableTypes || sortedCreatableTypes.length === 0" class="empty-state">
        当前没有可通过商店创造的藏品类型。
      </div>
      <div v-else>
                <div class="tabs sub-tabs" v-if="sortedCreatableTypes.length > 1">
          <button
            v-for="nftType in sortedCreatableTypes"
            :key="nftType"
            :class="{ active: activeMintTab === nftType }"
            @click="activeMintTab = nftType"
          >
            {{ allNftTypes[nftType] || nftType }} ({{ creatableNftsByType[nftType].length }})
          </button>
        </div>
        
                <div v-for="nftType in sortedCreatableTypes" :key="nftType" v-show="activeMintTab === nftType" class="tab-content">
          <div class="nft-grid full-width-grid">
            <div v-for="config in creatableNftsByType[nftType]" :key="nftType" class="nft-card">
              <div class="nft-header">
                <span class="nft-type">{{ allNftTypes[nftType] || nftType }}</span>
                <span class="nft-price">{{ formatCurrency(config.cost) }} JCoin</span>
              </div>
              <h3 class="nft-name">{{ config.name }}</h3>
              <p class="nft-description">{{ config.description }}</p>

              <form @submit.prevent="handleMintNft(nftType, config)" class="mint-form">
                <template v-if="config.fields && config.fields.length > 0">
                  <div v-for="field in config.fields" :key="field.name" class="form-group">
                    <label :for="`${nftType}-${field.name}`">{{ field.label }}</label>
                    <input 
                      v-if="field.type === 'text_input'" 
                      type="text" 
                      :id="`${nftType}-${field.name}`"
                      v-model="mintForms[nftType][field.name]"
                      :required="field.required"
                      :placeholder="field.help"
                    />
                    <textarea 
                      v-if="field.type === 'text_area'" 
                      :id="`${nftType}-${field.name}`"
                      v-model="mintForms[nftType][field.name]"
                      :required="field.required"
                      :placeholder="field.help"
                      rows="3"
                    ></textarea>
                    <input 
                      v-if="field.type === 'number_input'" 
                      type="number" 
                      :id="`${nftType}-${field.name}`"
                      v-model.number="mintForms[nftType][field.name]"
                      :required="field.required"
                      :min="field.min_value"
                      :max="field.max_value"
                      :step="field.step"
                    />
                    <p v-if="field.help && field.type !== 'text_input' && field.type !== 'text_area'" class="help-text">{{ field.help }}</p>
                  </div>
                </template>
                <button type="submit" :disabled="balance < config.cost">
                  {{ balance < config.cost ? '余额不足' : (config.action_label || '支付并创造') }}
                </button>
                
                                <div 
                  v-if="localFeedback[nftType]" 
                  :class="['local-feedback', localFeedback[nftType].type]"
                >
                  {{ localFeedback[nftType].text }}
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
    
        <div v-else-if="activeTab === 'buy'" class="tab-content">
      <div v-if="isLoading.buy" class="loading-state">正在加载市场数据...</div>
      <div v-else-if="!sortedSaleTypes || sortedSaleTypes.length === 0" class="empty-state">
        市场上目前没有任何挂单。
      </div>
      <div v-else>
                <div class="tabs sub-tabs" v-if="sortedSaleTypes.length > 1">
          <button
            v-for="nftType in sortedSaleTypes"
            :key="nftType"
            :class="{ active: activeBuyTab === nftType }"
            @click="activeBuyTab = nftType"
          >
            {{ allNftTypes[nftType] || nftType }} ({{ saleListingsByType[nftType].length }})
          </button>
        </div>

                <div v-for="nftType in sortedSaleTypes" :key="nftType" v-show="activeBuyTab === nftType" class="tab-content">
          <div class="nft-grid">
            <div v-for="item in saleListingsByType[nftType]" :key="item.listing_id" class="nft-card buy-card">
              <div class="nft-header">
                <span class="nft-type">{{ allNftTypes[item.nft_type] || item.nft_type }}</span>
                <span class="nft-price">{{ formatCurrency(item.price) }} JCoin</span>
              </div>
              <h3 class="nft-name">{{ item.trade_description || item.description }}</h3>
              
              <template v-if="item.nft_data">
                  <MarketNftDetail :item="item" />
              </template>

              <ul class="nft-data">
                <li><strong>卖家:</strong> 
                    <ClickableUsername :uid="item.lister_uid" :username="item.lister_username" />
                    <span v-if="item.lister_key === authStore.userInfo.publicKey" class="my-item-tag">(这是你)</span>
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
      </div>
    </div>

        <div v-else-if="activeTab === 'auction'" class="tab-content">
      <div v-if="isLoading.auction" class="loading-state">正在加载拍卖行数据...</div>
      <div v-else-if="!sortedAuctionTypes || sortedAuctionTypes.length === 0" class="empty-state">
        拍卖行目前没有任何物品。
      </div>
      <div v-else>
                <div class="tabs sub-tabs" v-if="sortedAuctionTypes.length > 1">
          <button
            v-for="nftType in sortedAuctionTypes"
            :key="nftType"
            :class="{ active: activeAuctionTab === nftType }"
            @click="activeAuctionTab = nftType"
          >
            {{ allNftTypes[nftType] || nftType }} ({{ auctionListingsByType[nftType].length }})
          </button>
        </div>
        
                <div v-for="nftType in sortedAuctionTypes" :key="nftType" v-show="activeAuctionTab === nftType" class="tab-content">
          <div class="nft-grid">
            <div v-for="item in auctionListingsByType[nftType]" :key="item.listing_id" class="nft-card auction-card">
              <div class="nft-header">
                <span class="nft-type-auction">拍卖: {{ allNftTypes[item.nft_type] || item.nft_type }}</span>
                <span class="nft-price">{{ item.highest_bid > 0 ? '当前' : '起拍' }}: {{ formatCurrency(item.highest_bid || item.price) }} JCoin</span>
              </div>
              <h3 class="nft-name">{{ item.trade_description || item.description }}</h3>
              
              <template v-if="item.nft_data">
                  <MarketNftDetail :item="item" />
              </template>

              <ul class="nft-data">
                <li><strong>卖家:</strong> 
                    <ClickableUsername :uid="item.lister_uid" :username="item.lister_username" />
                    <span v-if="item.lister_key === authStore.userInfo.publicKey" class="my-item-tag">(这是你)</span>
                </li>
                <li><strong>结束于:</strong> <span class="countdown">{{ formatTimestamp(item.end_time) }}</span></li>
                <li v-if="item.highest_bidder">
                  <strong>最高出价:</strong> {{ formatCurrency(item.highest_bid) }} JCoin
                  <button class="link-button" @click.prevent="fetchBidHistory(item.listing_id)">
                    ({{ auctionBidHistory[item.listing_id]?.show ? '隐藏' : '查看' }}历史)
                  </button>
                </li>
                <li v-else><strong>最高出价:</strong> 暂无出价</li>
              </ul>

                            <div v-if="auctionBidHistory[item.listing_id]?.show" class="bid-history">
                <div v-if="auctionBidHistory[item.listing_id].isLoading" class="loading-state-small">加载历史...</div>
                <ul v-else-if="auctionBidHistory[item.listing_id].bids.length > 0" class="offers-list">
                  <li v-for="(bid, index) in auctionBidHistory[item.listing_id].bids" :key="index">
                    <div class="offer-info">
                      <ClickableUsername :uid="bid.bidder_uid" :username="bid.bidder_username" />
                      <span>出价: <strong>{{ formatCurrency(bid.bid_amount) }} JCoin</strong></span>
                      <span class="bid-time">@ {{ formatTimestamp(bid.created_at) }}</span>
                    </div>
                  </li>
                </ul>
                <div v-else class="empty-state-small">暂无出价记录</div>
              </div>

                            <form class="buy-action" @submit.prevent="handlePlaceBid(item)">
                <div class="form-group small-form-group">
                    <input 
                        type="number" 
                        v-model.number="bidForms[item.listing_id]" 
                        :min="parseFloat(((item.highest_bid || item.price) + 0.01).toFixed(2))" 
                        step="0.01" 
                        required 
                    />
                </div>
                <button type="submit" :disabled="balance < (bidForms[item.listing_id] || 0) || item.lister_key === authStore.userInfo.publicKey">
                  {{ item.lister_key === authStore.userInfo.publicKey ? '你自己的商品' : '出价' }}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
    
        <div v-else-if="activeTab === 'seek'" class="tab-content">
            <div class="seek-create-form">
        <h3>发布求购信息</h3>
        <p class="subtitle">发布一个求购单，让拥有你所需 藏品 的人来找你。发布时将暂时托管你的预算资金。</p>
        <form @submit.prevent="handleCreateSeekListing">
          <div class="form-group">
            <label>求购的 藏品 类型</label>
            <select v-model="seekForm.nft_type" :disabled="isLoading.allTypes">
              <option v-if="isLoading.allTypes" value="">加载中...</option>
              <option v-for="(name, type) in allNftTypes" :key="type" :value="type">{{ name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>求购描述 (例如：求一个金色的宠物)</label>
            <input type="text" v-model="seekForm.description" required placeholder="例如：求一个金色的宠物" />
          </div>
          <div class="form-group">
            <label>我的预算 (JCoin)</label>
            <input type="number" v-model.number="seekForm.price" min="0.01" step="0.01" required />
          </div>
          <button type="submit" :disabled="balance < seekForm.price">
            {{ balance < seekForm.price ? '余额不足' : '发布求购' }}
          </button>
        </form>
      </div>

            <h3 class="divider-header">市场求购列表</h3>
      <div v-if="isLoading.seek" class="loading-state">正在加载求购数据...</div>
      <div v-else-if="!sortedSeekTypes || sortedSeekTypes.length === 0" class="empty-state">
        市场上目前没有任何求购信息。
      </div>
      <div v-else>
                  <div class="tabs sub-tabs" v-if="sortedSeekTypes.length > 1">
          <button
            v-for="nftType in sortedSeekTypes"
            :key="nftType"
            :class="{ active: activeSeekTab === nftType }"
            @click="activeSeekTab = nftType"
          >
            {{ allNftTypes[nftType] || nftType }} ({{ seekListingsByType[nftType].length }})
          </button>
        </div>
        
                <div v-for="nftType in sortedSeekTypes" :key="nftType" v-show="activeSeekTab === nftType" class="tab-content">
          <div class="nft-grid">
            <div v-for="item in seekListingsByType[nftType]" :key="item.listing_id" class="nft-card seek-card">
              <div class="nft-header">
                <span class="nft-type-seek">求购: {{ allNftTypes[item.nft_type] || item.nft_type }}</span>
                <span class="nft-price">预算: {{ formatCurrency(item.price) }} JCoin</span>
              </div>
              <h3 class="nft-name">“{{ item.description }}”</h3>

              <ul class="nft-data">
                <li><strong>求购方:</strong> 
                    <ClickableUsername :uid="item.lister_uid" :username="item.lister_username" />
                    <span v-if="item.lister_key === authStore.userInfo.publicKey" class="my-item-tag">(这是你)</span>
                </li>
                <li><strong>发布于:</strong> {{ formatTimestamp(item.created_at) }}</li>
              </ul>
              
                            <form v-if="item.lister_key !== authStore.userInfo.publicKey" class="buy-action" @submit.prevent="handleMakeOffer(item)">
                <p class="help-text">选择一个你拥有的、符合类型的藏品进行报价：</p>
                <template v-if="isLoading.myNfts">
                  <div class="loading-state-small">正在加载你的藏品...</div>
                </template>
                <template v-else-if="computedEligibleNfts(item.nft_type).length > 0">
                  <div class="form-group small-form-group">
                    <select v-model="offerForms[item.listing_id]" required>
                        <option :value="null" disabled>-- 选择你的 {{ allNftTypes[item.nft_type] }} --</option>
                        <option v-for="nft in computedEligibleNfts(item.nft_type)" :key="nft.nft_id" :value="nft.nft_id">
                            {{ nft.data.custom_name || nft.data.name || nft.nft_id.substring(0, 8) }}
                        </option>
                    </select>
                  </div>
                  <button type="submit">
                    提交报价
                  </button>
                </template>
                <div v-else class="empty-state-small">
                  你没有符合条件的藏品
                </div>
              </form>
              <div v-else class="buy-action empty-state-small">
                这是你自己的求购单
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

        <div v-else-if="activeTab === 'my-listings'" class="tab-content">
        <div v-if="isLoading.myListings" class="loading-state">正在加载我的交易...</div>
        <div v-else-if="!myActivity.listings || myActivity.listings.length === 0" class="empty-state">
            你还没有发布过任何挂单。
        </div>
        <div v-else>
                        <div class="filter-toggle">
              <label>
                <input type="checkbox" v-model="showInactiveListings" />
                显示已完成/已取消的交易
              </label>
            </div>
            
                        <div class="nft-grid full-width-grid">
                <div v-for="item in sortedMyListings" :key="item.listing_id" class="nft-card my-listing-card" :class="`status-${item.status.toLowerCase()}`">
                    <div class="nft-header">
                        <span :class="['nft-type-listing', `type-${item.listing_type.toLowerCase()}`]">{{ translateListingType(item.listing_type) }}</span>
                        <span class="nft-price">{{ formatCurrency(item.price) }} JCoin</span>
                    </div>
                    <h3 class="nft-name">{{ item.description }}</h3>
                    <ul class="nft-data">
                        <li><strong>类型:</strong> {{ allNftTypes[item.nft_type] || item.nft_type }}</li>
                        <li><strong>状态:</strong> <span class="status-text">{{ translateStatus(item.status) }}</span></li>
                        <li><strong>上架于:</strong> {{ formatTimestamp(item.created_at) }}</li>
                        <li v-if="item.listing_type === 'AUCTION' && item.highest_bidder">
                            <strong>最高出价:</strong> {{ formatCurrency(item.highest_bid) }} JCoin
                            <button class="link-button" @click.prevent="fetchBidHistory(item.listing_id)">
                                ({{ auctionBidHistory[item.listing_id]?.show ? '隐藏' : '查看' }}历史)
                            </button>
                        </li>
                    </ul>

                                        <div v-if="item.listing_type === 'AUCTION' && auctionBidHistory[item.listing_id]?.show" class="bid-history">
                      <div v-if="auctionBidHistory[item.listing_id].isLoading" class="loading-state-small">加载历史...</div>
                      <ul v-else-if="auctionBidHistory[item.listing_id].bids.length > 0" class="offers-list">
                        <li v-for="(bid, index) in auctionBidHistory[item.listing_id].bids" :key="index">
                          <div class="offer-info">
                            <ClickableUsername :uid="bid.bidder_uid" :username="bid.bidder_username" />
                            <span>出价: <strong>{{ formatCurrency(bid.bid_amount) }} JCoin</strong></span>
                            <span class="bid-time">@ {{ formatTimestamp(bid.created_at) }}</span>
                          </div>
                        </li>
                      </ul>
                      <div v-else class="empty-state-small">暂无出价记录</div>
                    </div>

                                        <div v-if="item.status === 'ACTIVE'" class="cancel-action">
                        <button class="cancel-button" @click="handleCancelListing(item.listing_id)">取消挂单</button>
                    </div>

                                        <div v-if="item.listing_type === 'SEEK' && item.status === 'ACTIVE'" class="offers-section">
                        <button class="offers-toggle" @click="fetchOffersForMyListing(item.listing_id)">
                            {{ myOffersDetails[item.listing_id] ? '刷新报价' : '查看收到的报价' }}
                        </button>
                        <div v-if="myOffersDetails[item.listing_id]">
                            <div v-if="myOffersDetails[item.listing_id].isLoading" class="loading-state-small">加载中...</div>
                            <div v-else-if="myOffersDetails[item.listing_id].offers.length === 0" class="empty-state-small">暂未收到报价</div>
                            <ul v-else class="offers-list">
                                <li v-for="offer in myOffersDetails[item.listing_id].offers" :key="offer.offer_id">
                                    <div class="offer-info">
                                        <ClickableUsername :uid="offer.offerer_uid" :username="offer.offerer_username" />
                                        <span>: {{ offer.trade_description || offer.nft_data.name }}</span>
                                        <span :class="['status-tag', `status-${offer.status.toLowerCase()}`]">{{ translateStatus(offer.status) }}</span>
                                    </div>
                                    <div v-if="offer.status === 'PENDING'" class="offer-actions">
                                        <button class="accept-button" @click="handleRespondToOffer(offer.offer_id, true)">接受</button>
                                        <button class="reject-button" @click="handleRespondToOffer(offer.offer_id, false)">拒绝</button>
                                    </div>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
/* 视图和头部 */
.shop-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; }
.subtitle { color: #718096; margin-bottom: 1.5rem; }
.balance-display { margin-bottom: 2rem; max-width: 350px; }

/* 主标签页 */
.tabs { 
    display: flex; 
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 0.5rem; 
    margin-bottom: 1.5rem; 
    border-bottom: 2px solid #e2e8f0;
}
.tabs button { 
    flex-grow: 1;
    flex-basis: 0;
    padding: 0.75rem 1rem;
    border: none; 
    background: none; 
    font-size: 1rem; 
    font-weight: 600; 
    color: #718096; 
    cursor: pointer; 
    border-bottom: 4px solid transparent; 
    transform: translateY(2px); 
    transition: color 0.2s, border-color 0.2s;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.tabs button:hover { color: #4a5568; }
.tabs button.active { color: #42b883; border-bottom-color: #42b883; }

/* 子标签页 (用于类型分组) */
.tabs.sub-tabs {
  margin-top: 1rem;
  margin-bottom: 1.5rem;
  border-bottom-width: 1px;
}
.tabs.sub-tabs button {
  font-size: 0.9rem;
  padding: 0.5rem 0.75rem;
  color: #4a5568;
  border-bottom-width: 2px;
  transform: translateY(1px);
  flex-grow: 0; /* 子标签不自动撑开 */
  flex-basis: auto;
}
.tabs.sub-tabs button.active {
  color: #42b883;
  border-bottom-color: #42b883;
}
.tab-content {
  animation: fadeIn 0.3s;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 搜索栏 */
.search-bar {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.search-bar form { 
    display: flex; 
    gap: 1rem; 
}
.search-bar input { 
    flex-grow: 1; 
    padding: 0.75rem; 
    border-radius: 6px; 
    border: 1px solid #cbd5e0; 
    box-sizing: border-box;
}

/* 通用状态 */
.loading-state, .empty-state { text-align: center; padding: 3rem; color: #718096; font-size: 1.1rem; }
.loading-state-small, .empty-state-small { text-align: center; padding: 1rem; color: #718096; font-size: 0.9rem; }

/* NFT 卡片网格 */
.nft-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
.full-width-grid { grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); } 

/* NFT 卡片基础样式 */
.nft-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); display: flex; flex-direction: column; transition: opacity 0.3s; }
.nft-header { padding: 1.25rem; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
.nft-type, .nft-type-auction, .nft-type-seek, .nft-type-listing {
  padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
}
.nft-type { background-color: #e2e8f0; color: #4a5568; }
.nft-type-auction { background-color: #feebc8; color: #975a16; }
.nft-type-seek { background-color: #cceefb; color: #2c5282; }
.nft-type-listing { background-color: #e2e8f0; color: #4a5568; }
.nft-type-listing.type-sale { background-color: #e2e8f0; color: #4a5568; }
.nft-type-listing.type-auction { background-color: #feebc8; color: #975a16; }
.nft-type-listing.type-seek { background-color: #cceefb; color: #2c5282; }

.nft-price { font-size: 1.1rem; font-weight: 700; color: #2d3748; }
.nft-description { padding: 0 1.25rem; font-size: 0.9rem; color: #718096; margin: 1rem 0;}
.mint-form { padding: 1.25rem; background: #f7fafc; border-top: 1px solid #e2e8f0; margin-top: auto; }

.nft-name { margin: 0; padding: 1rem 1.25rem 0.5rem 1.25rem; font-size: 1.25rem; color: #2d3748; }
.nft-data { list-style: none; padding: 0.5rem 1.25rem 1.25rem 1.25rem; margin: 0; flex-grow: 1; font-size: 0.9rem; color: #4a5568; }
.nft-data li { margin-bottom: 0.5rem; }
.nft-data li strong { color: #2d3748; }
.countdown { color: #c53030; font-weight: 600; }
.my-item-tag { font-size: 0.8rem; color: #975a16; font-weight: 600; margin-left: 0.5rem; }

/* 表单和动作区域 */
.mint-form, .buy-action, .cancel-action { padding: 1.25rem; background: #f7fafc; border-top: 1px solid #e2e8f0; margin-top: auto; }
.buy-action { display: flex; gap: 1rem; align-items: center; }
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
.small-form-group { flex-grow: 1; margin: 0; }
input, textarea, select { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; resize: vertical; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
button:hover { background-color: #369b6e; }
button:disabled { background-color: #a0aec0; cursor: not-allowed; }
.cancel-button { background-color: #f56565; }
.cancel-button:hover { background-color: #e53e3e; }

/* 全局消息 */
.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }

/* 局部反馈样式 (用于表单内部) */
.local-feedback {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 4px;
  text-align: center;
  font-weight: 500;
  font-size: 0.9rem;
  animation: fadeIn 0.3s;
}
.local-feedback.success {
  color: #155724; 
  background-color: #d4edda;
}
.local-feedback.error {
  color: #d8000c; 
  background-color: #ffbaba;
}

/* “我的交易”特定样式 */
.my-listing-card .status-text { font-weight: bold; }
.my-listing-card.status-active .status-text { color: #2f855a; }
.my-listing-card:not(.status-active) { opacity: 0.6; }
.my-listing-card:not(.status-active) .status-text { color: #718096; }

/* 求购专用 */
.seek-create-form { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
.seek-create-form h3 { margin-top: 0; }
.divider-header { margin-top: 2rem; margin-bottom: 1.5rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.help-text { font-size: 0.8rem; color: #718096; margin-top: -0.5rem; margin-bottom: 0.75rem;}
.offers-section { padding: 0 1.25rem 1.25rem; }
.offers-toggle { width: auto; font-size: 0.9rem; padding: 0.5rem 1rem; background-color: #718096; }
.offers-list { list-style: none; padding: 0; margin-top: 1rem; }
.offers-list li { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; padding: 0.75rem; border-radius: 6px; background-color: #f7fafc; margin-bottom: 0.5rem; }
.offer-info { display: flex; align-items: center; gap: 0.5rem; flex-wrap: nowrap; overflow: hidden; text-overflow: ellipsis;}
.offer-info .status-tag { font-size: 0.7rem; padding: 0.1rem 0.5rem; margin-left: auto; }
.status-tag.status-pending { background-color: #faf089; color: #975a16; }
.status-tag.status-rejected { background-color: #fed7d7; color: #c53030; }
.offer-actions { display: flex; gap: 0.5rem; }
.offer-actions button { width: auto; padding: 0.4rem 0.8rem; font-size: 0.8rem; }
.accept-button { background-color: #48bb78; }
.reject-button { background-color: #a0aec0; }
.link-button { background: none; border: none; color: #42b883; cursor: pointer; padding: 0; font-size: 0.9em; margin-left: 0.5rem; }
.link-button:hover { text-decoration: underline; }
.bid-history { padding: 0 1.25rem 1.25rem; border-top: 1px solid #f0f2f5; margin-top: -1.25rem; padding-top: 1.25rem; }
.bid-time { font-size: 0.8rem; color: #718096; margin-left: auto; white-space: nowrap; padding-left: 0.5rem; }
.offers-list li .offer-info { flex-wrap: nowrap; }
.filter-toggle { margin-bottom: 1.5rem; padding: 1rem; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }
.filter-toggle label { display: flex; align-items: center; gap: 0.5rem; font-weight: 500; cursor: pointer; }

</style>