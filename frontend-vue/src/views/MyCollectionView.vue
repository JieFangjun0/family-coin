<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import NftCard from '@/components/nfts/NftCard.vue'

const authStore = useAuthStore()
const nfts = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

async function fetchNfts() {
  isLoading.value = true
  errorMessage.value = null
  // successMessage.value = null; // Don't clear success message on auto-refresh

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

// 通用NFT动作处理器
async function handleNftAction(event) {
    const { action, nft, payload } = event;
    successMessage.value = null;
    errorMessage.value = null;

    if (action === 'list-for-sale') {
        await handleListForSale(nft, payload);
    } else {
        // Handle generic actions like rename, scan, destroy
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

        const [data, error] = await apiCall('POST', '/nfts/action', { payload: signedPayload });

        if (error) {
            errorMessage.value = `操作失败: ${error}`;
        } else {
            successMessage.value = data.detail || '操作成功!';
            await fetchNfts(); // Refresh the list
        }
    }
}

async function handleListForSale(nft, payload) {
  const { description, price } = payload
  
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
    await fetchNfts()
  }
}

onMounted(fetchNfts)
</script>

<template>
  <div class="collection-view">
    <header class="view-header">
      <h1>🖼️ 我的收藏</h1>
      <p class="subtitle">你拥有的所有 NFT 都在这里。你可以与它们互动，或将它们上架出售。</p>
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
        @action="handleNftAction"
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
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 1.5rem;
}

.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
</style>