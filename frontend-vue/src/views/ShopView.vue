<script setup>
import { ref, onMounted, computed, reactive } from 'vue'
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
const errorMessage = ref(null)
const successMessage = ref(null)

const balance = ref(0)
const creatableNfts = ref({})
const saleListings = ref([])
const auctionListings = ref([]) 
const seekListings = ref([])    
const allNftTypes = ref({}) 
const myNfts = ref([])      
const myActivity = ref({ listings: [], offers: [] })
const myOffersDetails = ref({}) 
const auctionBidHistory = reactive({}) // 新增：拍卖历史

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
const sortedMyListings = computed(() => {
  if (!myActivity.value.listings) return []
  return [...myActivity.value.listings].sort((a, b) => {
    if (a.status === 'ACTIVE' && b.status !== 'ACTIVE') return -1
    if (a.status !== 'ACTIVE' && b.status === 'ACTIVE') return 1
    return b.created_at - a.created_at
  })
})

const computedEligibleNfts = (seekNftType) => {
  return myNfts.value.filter(nft => nft.nft_type === seekNftType && nft.status === 'ACTIVE');
}

// --- 翻译 ---
const LISTING_TYPE_MAP = { "SALE": "一口价", "AUCTION": "拍卖", "SEEK": "求购" }
const STATUS_MAP = { "ACTIVE": "进行中", "PENDING": "待处理", "SOLD": "已售出", "CANCELLED": "已取消", "REJECTED": "已拒绝", "EXPIRED": "已过期", "FULFILLED": "已成交" }

function translateListingType(type) { return LISTING_TYPE_MAP[type] || type }
function translateStatus(status) { return STATUS_MAP[status] || status }

// --- API 调用 ---

async function fetchDataForTab(tab) {
  errorMessage.value = null;
  // successMessage.value = null; // 切换tab时不清除成功消息
  switch (tab) {
    case 'mint':
      // +++ 修复2：同时获取可铸造列表和NFT类型名称 +++
      if (Object.keys(creatableNfts.value).length === 0) {
        // 也获取NFT名称
        if (Object.keys(allNftTypes.value).length === 0) {
          await Promise.all([fetchCreatableNfts(), fetchAllNftTypes()]);
        } else {
          await fetchCreatableNfts();
        }
      }
      break;
    case 'buy':
      await fetchSaleListings();
      break;
    case 'auction': 
      await fetchAuctionListings();
      break;
    case 'seek': 
      await Promise.all([
        fetchSeekListings(),
        fetchAllNftTypes(),
        fetchMyNfts()
      ]);
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
  if (error) errorMessage.value = `无法加载余额: ${error}`
  else balance.value = data.balance
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
  // *** 修复点 3: 移除 exclude_owner ***
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: { listing_type: 'SALE' }
  })
  if (error) errorMessage.value = `无法加载在售列表: ${error}`
  else saleListings.value = data.listings
  isLoading.value.buy = false
}

async function fetchAuctionListings() {
  isLoading.value.auction = true
  // *** 修复点 3: 移除 exclude_owner ***
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: { listing_type: 'AUCTION' }
  })
  if (error) {
    errorMessage.value = `无法加载拍卖列表: ${error}`
  } else {
    auctionListings.value = data.listings
    data.listings.forEach(item => {
      if (!bidForms[item.listing_id]) {
        bidForms[item.listing_id] = parseFloat(((item.highest_bid || item.price) + 0.01).toFixed(2))
      }
    })
  }
  isLoading.value.auction = false
}

async function fetchSeekListings() {
  isLoading.value.seek = true
  // *** 修复点 3: 移除 exclude_owner ***
  const [data, error] = await apiCall('GET', '/market/listings', {
    params: { listing_type: 'SEEK' }
  })
  if (error) {
    errorMessage.value = `无法加载求购列表: ${error}`
  } else {
    seekListings.value = data.listings
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
  if (error) errorMessage.value = `无法加载NFT类型: ${error}`
  else {
    allNftTypes.value = data
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
  if (error) errorMessage.value = `无法加载我的NFT: ${error}`
  else myNfts.value = data.nfts
  isLoading.value.myNfts = false
}

async function fetchMyActivity() {
  isLoading.value.myListings = true
  myOffersDetails.value = {} 
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

async function handleMintNft(nftType, config) {
  // (此函数无修改)
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
  if (error) errorMessage.value = `操作失败: ${error}`
  else {
    successMessage.value = data.detail
    await fetchBalance()
  }
}

async function handleBuyNft(item) {
  // (此函数无修改)
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
  // (此函数无修改)
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

// *** 修复点 4: 拍卖出价 ***
async function handlePlaceBid(item) {
  successMessage.value = null
  errorMessage.value = null

  const bidAmount = parseFloat(bidForms[item.listing_id])
  // 确保比较时使用正确的最小值
  const minBid = parseFloat(((item.highest_bid || item.price) + 0.01).toFixed(2))

  if (!bidAmount || bidAmount < minBid) {
    errorMessage.value = `出价必须至少为 ${formatCurrency(minBid)} FC`
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
    // 新增：清除缓存的出价历史，以便下次点击时刷新
    if (auctionBidHistory[item.listing_id]) {
      delete auctionBidHistory[item.listing_id]
    }
  }
}

// *** 修复点 4: 获取出价历史 ***
async function fetchBidHistory(listingId) {
  if (auctionBidHistory[listingId] && auctionBidHistory[listingId].show) {
    // 如果已经加载且显示，则隐藏
    auctionBidHistory[listingId].show = false;
    return;
  }
  
  // 如果未加载，或已加载但隐藏
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
  // (此函数无修改)
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
    seekForm.description = ''
    seekForm.price = 10.0
    await fetchBalance()
    await fetchSeekListings()
    await fetchMyActivity() 
  }
}

async function handleMakeOffer(item) {
  // (此函数无修改)
  successMessage.value = null
  errorMessage.value = null
  const offeredNftId = offerForms[item.listing_id]
  if (!offeredNftId) {
    errorMessage.value = '请选择一个你拥有的NFT进行报价'
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
    await fetchMyNfts() 
    await fetchMyActivity() 
  }
}

async function fetchOffersForMyListing(listingId) {
  // (此函数无修改)
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
  // (此函数无修改)
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
      <p class="subtitle">在这里铸造新的 NFT 或与其他成员进行交易。</p>
    </header>

    <div class="balance-display">
      <BalanceCard label="当前余额" :value="isLoading.balance ? '加载中...' : formatCurrency(balance)" unit="FC" />
    </div>

    <div class="tabs">
      <button :class="{ active: activeTab === 'mint' }" @click="selectTab('mint')">铸造工坊</button>
      <button :class="{ active: activeTab === 'buy' }" @click="selectTab('buy')">一口价</button>
      <button :class="{ active: activeTab === 'auction' }" @click="selectTab('auction')">拍卖行</button>
      <button :class="{ active: activeTab === 'seek' }" @click="selectTab('seek')">求购</button>
      <button :class="{ active: activeTab === 'my-listings' }" @click="selectTab('my-listings')">我的交易</button>
    </div>

    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <div v-if="activeTab === 'mint'" class="tab-content">
      <div v-if="isLoading.mint" class="loading-state">正在加载铸造工坊...</div>
      <div v-else-if="!creatableNfts || Object.keys(creatableNfts).length === 0" class="empty-state">
        当前没有可通过商店铸造的NFT类型。
      </div>
      <div v-else class="nft-grid full-width-grid">
        <div v-for="(config, nftType) in creatableNfts" :key="nftType" class="nft-card">
          <div class="nft-header">
            <span class="nft-type">{{ allNftTypes[nftType] || nftType }}</span>
            <span class="nft-price">{{ formatCurrency(config.cost) }} FC</span>
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
              {{ balance < config.cost ? '余额不足' : (config.action_label || '支付并铸造') }}
            </button>
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

    <div v-if="activeTab === 'auction'" class="tab-content">
      <div v-if="isLoading.auction" class="loading-state">正在加载拍卖行数据...</div>
      <div v-else-if="!auctionListings || auctionListings.length === 0" class="empty-state">
        拍卖行目前没有任何物品。
      </div>
      <div v-else class="nft-grid">
        <div v-for="item in auctionListings" :key="item.listing_id" class="nft-card auction-card">
          <div class="nft-header">
            <span class="nft-type-auction">拍卖中</span>
            <span class="nft-price">{{ item.highest_bid > 0 ? '当前' : '起拍' }}: {{ formatCurrency(item.highest_bid || item.price) }} FC</span>
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
              <strong>最高出价:</strong> {{ formatCurrency(item.highest_bid) }} FC
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
                  <span>出价: <strong>{{ formatCurrency(bid.bid_amount) }} FC</strong></span>
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
    
    <div v-if="activeTab === 'seek'" class="tab-content">
      <div class="seek-create-form">
        <h3>发布求购信息</h3>
        <p class="subtitle">发布一个求购单，让拥有你所需 NFT 的人来找你。发布时将暂时托管你的预算资金。</p>
        <form @submit.prevent="handleCreateSeekListing">
          <div class="form-group">
            <label>求购的 NFT 类型</label>
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
            <label>我的预算 (FC)</label>
            <input type="number" v-model.number="seekForm.price" min="0.01" step="0.01" required />
          </div>
          <button type="submit" :disabled="balance < seekForm.price">
            {{ balance < seekForm.price ? '余额不足' : '发布求购' }}
          </button>
        </form>
      </div>

      <h3 class="divider-header">市场求购列表</h3>
      <div v-if="isLoading.seek" class="loading-state">正在加载求购数据...</div>
      <div v-else-if="!seekListings || seekListings.length === 0" class="empty-state">
        市场上目前没有任何求购信息。
      </div>
      <div v-else class="nft-grid">
        <div v-for="item in seekListings" :key="item.listing_id" class="nft-card seek-card">
          <div class="nft-header">
            <span class="nft-type-seek">求购: {{ allNftTypes[item.nft_type] || item.nft_type }}</span>
            <span class="nft-price">预算: {{ formatCurrency(item.price) }} FC</span>
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
            <p class="help-text">选择一个你拥有的、符合类型的NFT进行报价：</p>
            <template v-if="isLoading.myNfts">
              <div class="loading-state-small">正在加载你的NFT...</div>
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
              你没有符合条件的NFT
            </div>
          </form>
          <div v-else class="buy-action empty-state-small">
            这是你自己的求购单
          </div>
        </div>
      </div>
    </div>


    <div v-if="activeTab === 'my-listings'" class="tab-content">
        <div v-if="isLoading.myListings" class="loading-state">正在加载我的交易...</div>
        <div v-else-if="!myActivity.listings || myActivity.listings.length === 0" class="empty-state">
            你还没有发布过任何挂单。
        </div>
        <div v-else class="nft-grid full-width-grid">
            <div v-for="item in sortedMyListings" :key="item.listing_id" class="nft-card my-listing-card" :class="`status-${item.status.toLowerCase()}`">
                <div class="nft-header">
                    <span :class="['nft-type-listing', `type-${item.listing_type.toLowerCase()}`]">{{ translateListingType(item.listing_type) }}</span>
                    <span class="nft-price">{{ formatCurrency(item.price) }} FC</span>
                </div>
                <h3 class="nft-name">{{ item.description }}</h3>
                <ul class="nft-data">
                    <li><strong>类型:</strong> {{ allNftTypes[item.nft_type] || item.nft_type }}</li>
                    <li><strong>状态:</strong> <span class="status-text">{{ translateStatus(item.status) }}</span></li>
                    <li><strong>上架于:</strong> {{ formatTimestamp(item.created_at) }}</li>
                    <li v-if="item.listing_type === 'AUCTION' && item.highest_bidder">
                        <strong>最高出价:</strong> {{ formatCurrency(item.highest_bid) }} FC
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
                        <span>出价: <strong>{{ formatCurrency(bid.bid_amount) }} FC</strong></span>
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
</template>

<style scoped>
/* (大部分样式保持不变) */
.shop-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; }
.subtitle { color: #718096; margin-bottom: 1.5rem; }
.balance-display { margin-bottom: 2rem; max-width: 350px; }

/* +++ 核心修复：重构 Tab 布局以强制实现“单行均匀分布” +++ */
.tabs { 
    display: flex; 
    flex-direction: row; /* 1. 强制水平排列 */
    flex-wrap: nowrap; /* 2. 强制不换行 */
    gap: 0.5rem; 
    margin-bottom: 1.5rem; 
    border-bottom: 2px solid #e2e8f0;
}
.tabs button { 
    /* 3. 让所有按钮平分宽度，自动缩放 */
    flex-grow: 1;
    flex-basis: 0;
    
    /* 样式 */
    padding: 0.75rem 1rem; /* 减小左右内边距，以便在小屏幕上容纳 */
    border: none; 
    background: none; 
    font-size: 1rem; 
    font-weight: 600; 
    color: #718096; 
    cursor: pointer; 
    border-bottom: 4px solid transparent; 
    transform: translateY(2px); 
    transition: color 0.2s, border-color 0.2s;
    
    /* 4. 确保文本居中且不换行 */
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis; /* 如果空间实在不够，用省略号... */
}
/* +++ 修复结束 +++ */

.tabs button:hover { color: #4a5568; }
.tabs button.active { color: #42b883; border-bottom-color: #42b883; }

.loading-state, .empty-state { text-align: center; padding: 3rem; color: #718096; font-size: 1.1rem; }
.loading-state-small, .empty-state-small { text-align: center; padding: 1rem; color: #718096; font-size: 0.9rem; }

.nft-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
.full-width-grid { grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); } 

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
.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }

.my-listing-card .status-text { font-weight: bold; }
.my-listing-card.status-active .status-text { color: #2f855a; }
.my-listing-card:not(.status-active) { opacity: 0.6; }
.my-listing-card:not(.status-active) .status-text { color: #718096; }

/* 求购专用 */
.seek-create-form { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
.seek-create-form h3 { margin-top: 0; }
.divider-header { margin-top: 2rem; margin-bottom: 1.5rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.help-text { font-size: 0.8rem; color: #718096; margin-top: -0.5rem; margin-bottom: 0.75rem;}

/* 我的交易 - 报价 */
.offers-section { padding: 0 1.25rem 1.25rem; }
.offers-toggle { width: auto; font-size: 0.9rem; padding: 0.5rem 1rem; background-color: #718096; }
.offers-list { list-style: none; padding: 0; margin-top: 1rem; }
.offers-list li {
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
  padding: 0.75rem; border-radius: 6px; background-color: #f7fafc; margin-bottom: 0.5rem;
}
.offer-info { display: flex; align-items: center; gap: 0.5rem; flex-wrap: nowrap; overflow: hidden; text-overflow: ellipsis;}
.offer-info .status-tag { font-size: 0.7rem; padding: 0.1rem 0.5rem; margin-left: auto; }
.status-tag.status-pending { background-color: #faf089; color: #975a16; }
.status-tag.status-rejected { background-color: #fed7d7; color: #c53030; }
.offer-actions { display: flex; gap: 0.5rem; }
.offer-actions button { width: auto; padding: 0.4rem 0.8rem; font-size: 0.8rem; }
.accept-button { background-color: #48bb78; }
.reject-button { background-color: #a0aec0; }

/* *** 拍卖历史样式 *** */
.link-button {
  background: none;
  border: none;
  color: #42b883;
  cursor: pointer;
  padding: 0;
  font-size: 0.9em;
  margin-left: 0.5rem;
}
.link-button:hover {
  text-decoration: underline;
}
.bid-history {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid #f0f2f5;
  margin-top: -1.25rem; /* 抵消 .nft-data 的 padding-bottom */
  padding-top: 1.25rem;
}
.bid-time {
  font-size: 0.8rem;
  color: #718096;
  margin-left: auto;
  white-space: nowrap;
  padding-left: 0.5rem;
}
.offers-list li .offer-info {
  flex-wrap: nowrap; /* 确保出价历史在同一行 */
}

</style>