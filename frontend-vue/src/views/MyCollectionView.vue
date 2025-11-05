<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import NftCard from '@/components/nfts/NftCard.vue'

const authStore = useAuthStore()
const nfts = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

// --- 修复问题 3: 新增状态 ---
const activeTab = ref(null)
const nftDisplayNames = ref({})
// +++ 核心修改：新增搜索状态 +++
const searchTerm = ref('')
// +++ 核心修改结束 +++
// --- 修复结束 ---

async function fetchNfts() {
  isLoading.value = true
  errorMessage.value = null
  // successMessage.value = null; // Don't clear success message on auto-refresh

  // --- 修复问题 3: 并行获取藏品s和类型名称 ---
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
  // --- 修复结束 ---

  isLoading.value = false
}

// +++ 核心修改：新增本地过滤的计算属性（解耦方式：字符串化搜索） +++
const filteredNfts = computed(() => {
    const term = searchTerm.value.toLowerCase().trim()
    if (!term) return nfts.value
    
    return nfts.value.filter(nft => {
        const data = nft.data || {}
        // 1. 藏品 元数据
        let searchableText = nft.nft_type.toLowerCase() + ' ';
        searchableText += (nftDisplayNames.value[nft.nft_type] || '').toLowerCase() + ' ';
        searchableText += (nft.nft_id || '').substring(0, 8).toLowerCase() + ' ';

        // 2. 将整个 data 对象（包含所有如 planet_type 的内部字段）字符串化进行搜索
        // 这是最解耦的本地搜索方法
        try {
            searchableText += JSON.stringify(data).toLowerCase();
        } catch (e) {
            // 如果 JSON 字符串化失败，尝试搜索已知的通用字段
            searchableText += (data.custom_name || '').toLowerCase() + ' ';
            searchableText += (data.name || '').toLowerCase() + ' ';
            searchableText += (data.description || '').toLowerCase() + ' ';
        }
        
        return searchableText.includes(term)
    })
})
// +++ 核心修改结束 +++


// --- 修复问题 3: 更新 Computed 属性以使用过滤后的列表 ---
const nftsByType = computed(() => {
  const groups = {}
  // 核心：使用过滤后的列表进行分组
  for (const nft of filteredNfts.value) { 
    if (!groups[nft.nft_type]) {
      groups[nft.nft_type] = []
    }
    groups[nft.nft_type].push(nft)
  }
  // 自动设置激活的 tab
  const sortedKeys = Object.keys(groups).sort()
  if (activeTab.value === null || !sortedKeys.includes(activeTab.value)) {
    activeTab.value = sortedKeys.length > 0 ? sortedKeys[0] : null
  }
  return groups
})

const sortedNftTypes = computed(() => {
    return Object.keys(nftsByType.value).sort()
})
// --- 修复结束 ---


async function handleNftAction(event) {
    const { action, nft, payload } = event;
    successMessage.value = null;
    errorMessage.value = null;

    // 1. “上架”动作有单独的逻辑，因为它调用不同的 API
    if (action === 'list-for-sale') {
        // handleCreateListing 内部会调用 fetchNfts()，
        // 这是正确的，因为 NFT 会离开“我的收藏”。
        await handleCreateListing(nft, payload);
        return;
    }

    // 2. 处理所有其他动作 (rename, scan, harvest, train, breed, destroy)
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
        errorMessage.value = '创建签名失败';
        return;
    }

    // 调用通用的 /nfts/action 接口
    const [data, error] = await apiCall('POST', '/nfts/action', { payload: signedPayload });

    if (error) {
        errorMessage.value = `操作失败: ${error}`;
    } else {
        successMessage.value = data.detail || '操作成功!';
        if (isDestructiveAction) {
            // 如果是销毁，我们从本地列表中移除它
            nfts.value = nfts.value.filter(item => item.nft_id !== nft.nft_id);
        } else {
            // 如果是修改 (scan, rename, harvest, train, breed)...
            // 我们只获取这一个 NFT 的新数据来更新它
            const [updatedNft, nftError] = await apiCall('GET', `/nfts/${nft.nft_id}`);
            if (updatedNft) {
                // 找到它在列表中的索引
                const index = nfts.value.findIndex(item => item.nft_id === nft.nft_id);
                if (index !== -1) {
                    // 原地替换数据，这不会导致组件重建
                    nfts.value[index] = updatedNft;
                } else {
                    // 如果找不到（理论上不该发生），则回退到完整刷新
                    await fetchNfts();
                }
            } else {
                // 如果获取单个 NFT 失败，也回退到完整刷新
                await fetchNfts();
            }
        }
    }
}

// *** 核心修改：此函数现在支持一口价和拍卖 ***
async function handleCreateListing(nft, payload) {
  // 从 payload 中解构新参数，并提供默认值
  const { 
    description, 
    price, 
    listing_type = 'SALE', // 默认为 SALE
    auction_hours = null   // 默认为 null
  } = payload
  
  if (!price || price <= 0) {
    errorMessage.value = '价格必须大于 0'
    return
  }
  
  if (listing_type === 'AUCTION' && (!auction_hours || auction_hours <= 0)) {
    errorMessage.value = '拍卖小时数必须大于 0'
    return
  }

  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Math.floor(Date.now() / 1000),
    listing_type: listing_type, // 使用新参数
    nft_id: nft.nft_id,
    nft_type: nft.nft_type,
    description: description,
    price: price,
    auction_hours: listing_type === 'AUCTION' ? auction_hours : null // 仅在拍卖时传递
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

/* --- 修复问题 3: 新增 Tab 样式 --- */
.tabs { 
    display: flex; 
    gap: 0.5rem; 
    margin-bottom: 1.5rem; 
    border-bottom: 2px solid #e2e8f0;
    flex-wrap: wrap;
}
.tabs button { 
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
}
.tabs button:hover { color: #4a5568; }
.tabs button.active { color: #42b883; border-bottom-color: #42b883; }
.tab-content {
  animation: fadeIn 0.3s;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
/* --- 修复结束 --- */

/* +++ 核心修改：新增搜索栏样式 +++ */
.search-bar {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.search-bar input {
    width: 100%;
    padding: 0.75rem;
    border-radius: 6px;
    border: 1px solid #cbd5e0;
    box-sizing: border-box;
}
/* +++ 核心修改结束 +++ */


.nft-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 1.5rem;
}

.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
</style>