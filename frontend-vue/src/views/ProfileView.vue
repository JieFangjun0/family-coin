<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'

const authStore = useAuthStore()
const router = useRouter()

const myNfts = ref([])
const myProfile = ref({ signature: '', displayed_nfts: [] })
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

const form = ref({
  signature: '',
  selectedNftIds: []
})

async function fetchData() {
  isLoading.value = true
  errorMessage.value = null

  const [profileRes, nftsRes] = await Promise.all([
    apiCall('GET', `/profile/${authStore.userInfo.uid}`),
    apiCall('GET', '/nfts/my', { params: { public_key: authStore.userInfo.publicKey } })
  ])

  if (profileRes[1]) {
    errorMessage.value = `加载个人资料失败: ${profileRes[1]}`
  } else {
    myProfile.value = profileRes[0]
    form.value.signature = myProfile.value.signature || ''
    form.value.selectedNftIds = myProfile.value.displayed_nfts_details.map(nft => nft.nft_id)
  }

  if (nftsRes[1]) {
    errorMessage.value = (errorMessage.value || '') + `加载NFT列表失败: ${nftsRes[1]}`
  } else {
    myNfts.value = nftsRes[0].nfts
  }

  isLoading.value = false
}

const nftOptions = computed(() => {
    return myNfts.value.map(nft => ({
        text: `${nft.data.custom_name || nft.data.name || nft.nft_type} (${nft.nft_id.substring(0, 6)})`,
        value: nft.nft_id
    }));
});


async function handleProfileUpdate() {
  errorMessage.value = null
  successMessage.value = null

  const message = {
    owner_key: authStore.userInfo.publicKey,
    signature: form.value.signature,
    displayed_nfts: form.value.selectedNftIds,
    timestamp: Math.floor(Date.now() / 1000)
  }

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message)
  if (!signedPayload) {
    errorMessage.value = '创建签名失败'
    return
  }

  const [data, error] = await apiCall('POST', '/profile/update', { payload: signedPayload })

  if (error) {
    errorMessage.value = `更新失败: ${error}`
  } else {
    successMessage.value = data.detail
    await fetchData()
  }
}

// 核心修正：跳转到自己的社区页面
function viewMyProfile() {
    router.push({ name: 'community', params: { uid: authStore.userInfo.uid }})
}

onMounted(fetchData)
</script>

<template>
  <div class="profile-view">
    <header class="view-header">
      <h1>⚙️ 编辑资料</h1>
      <p class="subtitle">编辑你的个人签名和主页展柜。</p>
    </header>

    <div class="view-profile-link">
        <button @click="viewMyProfile">👀 预览我的公开主页</button>
    </div>


    <div v-if="isLoading" class="loading-state">正在加载...</div>
    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <form v-if="!isLoading" @submit.prevent="handleProfileUpdate" class="profile-form">
      <div class="form-group">
        <label for="signature">我的签名 (最多100字符)</label>
        <textarea id="signature" v-model="form.signature" rows="3" maxlength="100"></textarea>
      </div>

      <div class="form-group">
        <label>选择要展出的NFT (最多6个)</label>
         <select v-model="form.selectedNftIds" multiple size="8">
            <option v-for="opt in nftOptions" :key="opt.value" :value="opt.value">
                {{ opt.text }}
            </option>
         </select>
      </div>

      <button type="submit">保存更改</button>
    </form>
  </div>
</template>

<style scoped>
.profile-view { max-width: 700px; margin: 0 auto; }
.profile-form { background: #fff; padding: 2rem; border-radius: 8px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 1.5rem; }
.form-group { display: flex; flex-direction: column; gap: 0.5rem; }
select[multiple] { height: 180px; }
.view-profile-link {
    margin-bottom: 2rem;
}
.view-profile-link button {
    width: 100%;
    background-color: #718096;
}
</style>