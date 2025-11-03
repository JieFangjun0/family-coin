<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import { useAuthStore } from '@/stores/auth'
import { formatTimestamp } from '@/utils/formatters'
import NftCard from '@/components/nfts/NftCard.vue'

const authStore = useAuthStore()
const route = useRoute()

const searchTerm = ref('')
const searchResult = ref(null)
const isLoading = ref(false)
const errorMessage = ref(null)
const successMessage = ref(null)
const friendStatus = ref(null)

async function handleSearch(uidOrUsername) {
  const term = uidOrUsername || searchTerm.value;
  if (!term) return;

  isLoading.value = true;
  errorMessage.value = null;
  successMessage.value = null;
  searchResult.value = null;
  friendStatus.value = null;

  const [data, error] = await apiCall('GET', `/profile/${term}`);
  if (error) {
    errorMessage.value = `查找失败: ${error}`;
  } else {
    searchResult.value = data;
    if (data.public_key !== authStore.userInfo.publicKey) {
      await checkFriendshipStatus(data.public_key);
    }
  }
  isLoading.value = false;
}

async function checkFriendshipStatus(targetKey) {
  const [data, error] = await apiCall('GET', `/friends/status/${targetKey}`, {
    params: { current_user_key: authStore.userInfo.publicKey }
  });
  if (error) {
    errorMessage.value = (errorMessage.value ? errorMessage.value + '\n' : '') + `无法获取好友状态: ${error}`;
  } else {
    friendStatus.value = data;
  }
}

async function handleAddFriend() {
  if (!searchResult.value) return;

  const message = {
    owner_key: authStore.userInfo.publicKey,
    target_key: searchResult.value.public_key,
    timestamp: Math.floor(Date.now() / 1000)
  };

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message);
  if (!signedPayload) {
    errorMessage.value = '创建签名失败';
    return;
  }

  const [data, error] = await apiCall('POST', '/friends/request', { payload: signedPayload });
  if (error) {
    errorMessage.value = `请求失败: ${error}`;
  } else {
    successMessage.value = data.detail;
    await checkFriendshipStatus(searchResult.value.public_key);
  }
}

// 监听路由参数变化
watch(() => route.params.uid, (newUid) => {
    if (newUid) {
        searchTerm.value = newUid;
        handleSearch(newUid);
    }
});

onMounted(() => {
  if (route.params.uid) {
    searchTerm.value = route.params.uid;
    handleSearch(route.params.uid);
  }
});

</script>

<template>
  <div class="community-view">
    <header class="view-header">
      <h1>👥 社区</h1>
      <p class="subtitle">搜索其他用户并查看他们的个人主页。</p>
    </header>

    <div class="search-bar">
      <form @submit.prevent="handleSearch()">
        <input type="text" v-model="searchTerm" placeholder="输入用户名或UID进行搜索..." />
        <button type="submit" :disabled="isLoading">{{ isLoading ? '搜索中...' : '搜索' }}</button>
      </form>
    </div>

    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <div v-if="searchResult" class="profile-container">
      <header class="profile-header">
        <h2>✨ {{ searchResult.username }} 的个人主页</h2>
        <div class="friend-status">
          <template v-if="searchResult.public_key !== authStore.userInfo.publicKey && friendStatus">
            <span v-if="friendStatus.status === 'ACCEPTED'" class="status-tag accepted">✔️ 你们是好友</span>
            <span v-else-if="friendStatus.status === 'PENDING' && friendStatus.action_user_key === authStore.userInfo.publicKey" class="status-tag pending">⏳ 好友请求已发送</span>
            <span v-else-if="friendStatus.status === 'PENDING'" class="status-tag incoming">📩 对方已向你发送请求</span>
            <button v-else-if="friendStatus.status === 'NONE'" @click="handleAddFriend">➕ 添加好友</button>
          </template>
        </div>
      </header>
      <p class="profile-meta">UID: {{ searchResult.uid }} | 加入于: {{ formatTimestamp(searchResult.created_at) }}</p>
      
      <div class="profile-signature" v-if="searchResult.signature">
        <p>“{{ searchResult.signature }}”</p>
      </div>
       <div class="profile-signature" v-else>
        <p>“这个人很懒，什么都没留下...”</p>
      </div>


      <div class="nft-showcase">
        <h3>NFT 展柜</h3>
        <div v-if="searchResult.displayed_nfts_details && searchResult.displayed_nfts_details.length > 0" class="nft-grid">
          <NftCard 
            v-for="nft in searchResult.displayed_nfts_details" 
            :key="nft.nft_id" 
            :nft="nft"
            context="profile"
          />
        </div>
        <p v-else class="empty-state">{{ searchResult.username }} 还没有展出任何NFT。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.community-view { max-width: 900px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; }
.subtitle { color: #718096; margin-bottom: 2rem; }
.search-bar form { display: flex; gap: 1rem; margin-bottom: 2rem; }
.search-bar input { flex-grow: 1; padding: 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; }
.profile-container { background: #fff; border-radius: 8px; border: 1px solid #e2e8f0; margin-top: 1rem; }
.profile-header { display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; gap: 1rem;}
.profile-header h2 { margin: 0; }
.profile-meta { padding: 0 1.5rem; color: #718096; }
.profile-signature { padding: 1.5rem; font-style: italic; color: #4a5568; background-color: #f7fafc; }
.nft-showcase { padding: 1.5rem; }
.nft-showcase h3 { margin-top: 0; }
.nft-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; margin-top: 1rem; }
.empty-state { color: #718096; }
.status-tag { padding: 0.3rem 0.8rem; border-radius: 12px; font-weight: 600; }
.status-tag.accepted { background-color: #c6f6d5; color: #2f855a; }
.status-tag.pending { background-color: #faf089; color: #975a16; }
.status-tag.incoming { background-color: #bee3f8; color: #2c5282; }
.message { margin-bottom: 1rem; }
</style>