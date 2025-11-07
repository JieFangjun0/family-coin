<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import NftCard from '@/components/nfts/NftCard.vue'
import { nftRendererRegistry, defaultRenderer } from '@/components/nfts/renderer-registry.js'

const authStore = useAuthStore()
const nfts = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

// 存储每个 NftCard 的局部反馈消息
// 结构: { "nft-id-123": { text: "...", type: "success" } }
const localFeedback = ref({});

const activeTab = ref(null)
const nftDisplayNames = ref({})
const searchTerm = ref('')

async function fetchNfts() {
  isLoading.value = true
  errorMessage.value = null
  
  const [nftResult, typesResult] = await Promise.all([
    apiCall('GET', '/nfts/my', {
      params: { public_key: authStore.userInfo.publicKey }
    }),
    apiCall('GET', '/nfts/display_names')
  ])

  const [nftData, nftError] = nftResult
  if (nftError) {
    errorMessage.value = `无法加载收藏: ${nftError}`
  } else {
    nfts.value = nftData.nfts
  }

  const [typesData, typesError] = typesResult
  if (typesError) {
    errorMessage.value = (errorMessage.value || '') + `\n无法加载藏品类型: ${typesError}`
  } else {
    nftDisplayNames.value = typesData
  }

  isLoading.value = false
}

const filteredNfts = computed(() => {
    const term = searchTerm.value.toLowerCase().trim()
    if (!term) return nfts.value
    
    return nfts.value.filter(nft => {
        const data = nft.data || {}
        const handler = nftRendererRegistry[nft.nft_type] || defaultRenderer
        const getSpecificSearchText = handler.getSearchableText
        
        const searchableText = [
            nft.nft_type,
            (nftDisplayNames.value[nft.nft_type] || ''), 
            nft.nft_id.substring(0, 8),
            data.custom_name, 
            data.name,
            data.description,
            data.nickname,
            data.species_name,
            getSpecificSearchText(data) 
        ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
        
        const rawDataString = JSON.stringify(data).toLowerCase();

        return searchableText.includes(term) || rawDataString.includes(term)
    })
})

const nftsByType = computed(() => {
  const groups = {}
  for (const nft of filteredNfts.value) { 
    if (!groups[nft.nft_type]) {
      groups[nft.nft_type] = []
    }
    groups[nft.nft_type].push(nft)
  }
  const sortedKeys = Object.keys(groups).sort()
  if (activeTab.value === null || !sortedKeys.includes(activeTab.value)) {
    activeTab.value = sortedKeys.length > 0 ? sortedKeys[0] : null
  }
  return groups
})

const sortedNftTypes = computed(() => {
    return Object.keys(nftsByType.value).sort()
})

async function handleNftAction(event) {
    const { action, nft, payload } = event;

    // 清空此 NFT 的局部消息和全局消息
    localFeedback.value[nft.nft_id] = null;
    successMessage.value = null;
    errorMessage.value = null;

    if (action === 'list-for-sale') {
        // handleCreateListing 会设置自己的局部消息
        await handleCreateListing(nft, payload);
        return;
    }

    const isDestructiveAction = (action === 'destroy');

    const message = {
        owner_key: authStore.userInfo.publicKey,
        nft_id: nft.nft_id,
        action: action,
        action_data: payload,
        timestamp: Math.floor(Date.now() / 1000)
    };

    const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message);
    if (!signedPayload) {
        const msg = '创建签名失败';
        errorMessage.value = msg;
        localFeedback.value[nft.nft_id] = { text: msg, type: 'error' };
        return;
    }

    const [data, error] = await apiCall('POST', '/nfts/action', { payload: signedPayload });

    if (error) {
        const msg = `操作失败: ${error}`;
        errorMessage.value = msg;
        localFeedback.value[nft.nft_id] = { text: `操作失败: ${error}`, type: 'error' };
    } else {
        const msg = data.detail || '操作成功!';
        successMessage.value = msg;
        localFeedback.value[nft.nft_id] = { text: msg, type: 'success' };
        
        if (isDestructiveAction) {
            nfts.value = nfts.value.filter(item => item.nft_id !== nft.nft_id);
        } else {
            const [updatedNft, nftError] = await apiCall('GET', `/nfts/${nft.nft_id}`);
            if (updatedNft) {
                const index = nfts.value.findIndex(item => item.nft_id === nft.nft_id);
                if (index !== -1) {
                    nfts.value[index] = updatedNft;
                } else {
                    await fetchNfts();
                }
            } else {
                await fetchNfts();
            }
        }
    }
    
    // 5秒后自动清除此 NFT 的局部消息
    setTimeout(() => {
        if (localFeedback.value[nft.nft_id]) {
            localFeedback.value[nft.nft_id] = null;
        }
    }, 5000);
}

async function handleCreateListing(nft, payload) {
  // 清空此 NFT 的局部消息
  localFeedback.value[nft.nft_id] = null;
  
  const { 
    description, 
    price, 
    listing_type = 'SALE', 
    auction_hours = null
  } = payload
  
  if (!price || price <= 0) {
    const msg = '价格必须大于 0';
    errorMessage.value = msg;
    localFeedback.value[nft.nft_id] = { text: msg, type: 'error' };
    return
  }
  
  if (listing_type === 'AUCTION' && (!auction_hours || auction_hours <= 0)) {
    const msg = '拍卖小时数必须大于 0';
    errorMessage.value = msg;
    localFeedback.value[nft.nft_id] = { text: msg, type: 'error' };
    return
  }

  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    listing_type: listing_type, 
    nft_id: nft.nft_id,
    nft_type: nft.nft_type,
    description: description,
    price: price,
    auction_hours: listing_type === 'AUCTION' ? auction_hours : null
  }

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    const msg = '创建签名失败';
    errorMessage.value = msg;
    localFeedback.value[nft.nft_id] = { text: msg, type: 'error' };
    return
  }

  const [data, error] = await apiCall('POST', '/market/create_listing', { payload: signedPayload })
  if (error) {
    const msg = `上架失败: ${error}`;
    errorMessage.value = msg;
    localFeedback.value[nft.nft_id] = { text: msg, type: 'error' };

    // 5秒后自动清除此 NFT 的局部消息
    setTimeout(() => {
        if (localFeedback.value[nft.nft_id]) {
            localFeedback.value[nft.nft_id] = null;
        }
    }, 5000);

  } else {
    // 上架成功后，卡片会消失，所以局部消息不重要，只显示全局消息
    successMessage.value = `上架成功！${data.detail || ''}`
    await fetchNfts()
  }
}

onMounted(fetchNfts)
</script>

<template>
  <div class="collection-view">
    <header class="view-header">
      <h1>我的藏品</h1>
      <p class="subtitle">你拥有的所有 藏品 都在这里。你可以与它们互动，或将它们上架出售。</p>
    </header>

    <div v-if="isLoading" class="loading-state">正在加载...</div>
    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>
    
    <div class="search-bar">
      <input type="text" v-model="searchTerm" placeholder="搜索 藏品 名称、描述、类型或 ID..." />
    </div>
    <div v-if="!isLoading && nfts.length === 0" class="empty-state">
      你的收藏是空的。快去商店创造或购买一些吧！
    </div>

    <div v-if="!isLoading && filteredNfts.length === 0 && nfts.length > 0" class="empty-state">
        没有找到与 “{{ searchTerm }}” 匹配的 藏品。
    </div>
    
    <div v-if="!isLoading && filteredNfts.length > 0">
      <div class="tabs" v-if="sortedNftTypes.length > 1">
        <button
          v-for="nftType in sortedNftTypes"
          :key="nftType"
          :class="{ active: activeTab === nftType }"
          @click="activeTab = nftType"
        >
          {{ nftDisplayNames[nftType] || nftType }} ({{ nftsByType[nftType].length }})
        </button>
      </div>

      <div v-for="nftType in sortedNftTypes" :key="nftType" v-show="activeTab === nftType" class="tab-content">
        <div class="nft-grid">
          <NftCard 
            v-for="nft in nftsByType[nftType]" 
            :key="nft.nft_id" 
            :nft="nft"
            @action="handleNftAction"
            :local-feedback-message="localFeedback[nft.nft_id]" 
          />
        </div>
      </div>
    </div>
    </div>
</template>

<style scoped>
.collection-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; }
.subtitle { color: #718096; margin-bottom: 2rem; }
.loading-state, .empty-state { text-align: center; padding: 3rem; color: #718096; font-size: 1.1rem; }

.tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #e2e8f0; flex-wrap: wrap; }
.tabs button { padding: 0.75rem 1rem; border: none; background: none; font-size: 1rem; font-weight: 600; color: #718096; cursor: pointer; border-bottom: 4px solid transparent; transform: translateY(2px); transition: color 0.2s, border-color 0.2s; }
.tabs button:hover { color: #4a5568; }
.tabs button.active { color: #42b883; border-bottom-color: #42b883; }
.tab-content { animation: fadeIn 0.3s; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.search-bar { margin-bottom: 2rem; padding: 1.5rem; background: #fff; border-radius: 8px; border: 1px solid #e2e8f0; }
.search-bar input { width: 100%; padding: 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; }

.nft-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 1.5rem; }

.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }

/* 为 NftCard 内部的局部反馈添加动画 
  我们使用 :deep() 来穿透 NftCard 的 scoped 样式
*/
:deep(.local-feedback) {
  animation: fadeIn 0.3s;
}
</style>