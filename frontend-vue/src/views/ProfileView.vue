<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
// +++ 核心修改 (请求 3b): 导入 NftCard +++
import NftCard from '@/components/nfts/NftCard.vue'

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
    // 修复：确保 selectedNftIds 始终是一个数组
    form.value.selectedNftIds = (myProfile.value.displayed_nfts_details || []).map(nft => nft.nft_id)
  }

  if (nftsRes[1]) {
    errorMessage.value = (errorMessage.value || '') + `加载藏品列表失败: ${nftsRes[1]}`
  } else {
    myNfts.value = nftsRes[0].nfts
  }

  isLoading.value = false
}

// --- 核心修改 (请求 3b): 移除旧的 nftOptions computed ---

// +++ 核心修改 (请求 3b): 新增藏品点选处理函数 +++
function toggleNftSelection(nftId) {
  const index = form.value.selectedNftIds.indexOf(nftId);
  if (index > -1) {
    // 已选中, 取消选择
    form.value.selectedNftIds.splice(index, 1);
  } else {
    // 未选中, 添加选择 (并检查限制)
    if (form.value.selectedNftIds.length < 6) {
      form.value.selectedNftIds.push(nftId);
    } else {
      // 可以在这里显示一个更友好的提示，但 alert 是最简单的
      alert("最多只能选择 6 个藏品进行展出。");
    }
  }
}

// +++ 核心修改 (请求 3b): 新增辅助函数检查是否选中 +++
const isNftSelected = (nftId) => {
  return form.value.selectedNftIds.includes(nftId);
}
// +++ 修改结束 +++


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
        <label>选择要展出的藏品 (已选 {{ form.selectedNftIds.length }} / 6)</label>
        <div v-if="!myNfts || myNfts.length === 0" class="empty-state">
          你还没有任何藏品可供展出。
        </div>
        <div v-else class="nft-selection-grid">
          <div
            v-for="nft in myNfts"
            :key="nft.nft_id"
            class="nft-preview-card"
            :class="{ selected: isNftSelected(nft.nft_id) }"
            @click="toggleNftSelection(nft.nft_id)"
          >
            <div class="nft-card-wrapper">
              <NftCard :nft="nft" context="profile" />
            </div>
            <div class="selection-overlay">
              <div class="selection-checkmark">✔️</div>
            </div>
          </div>
        </div>
      </div>
      <button type="submit">保存更改</button>
    </form>
  </div>
</template>

<style scoped>
/* +++ 核心修改 (请求 3b): 调整布局宽度 +++ */
.profile-view { max-width: 900px; margin: 0 auto; }
.profile-form { background: #fff; padding: 2rem; border-radius: 8px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 1.5rem; max-width: 900px; } /* 确保表单也变宽 */
.view-profile-link {
    margin-bottom: 2rem;
}
.view-profile-link button {
    width: 100%;
    background-color: #718096;
}

/* +++ 核心修改 (请求 3b): 新增点选网格样式 +++ */
.empty-state {
  text-align: center;
  padding: 2rem;
  color: #718096;
  background: #f7fafc;
  border-radius: 6px;
  border: 1px dashed #e2e8f0;
}

.nft-selection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  max-height: 600px; /* 如果藏品太多，允许滚动 */
  overflow-y: auto;
  background: #f7fafc;
  padding: 1rem;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.nft-preview-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 3px solid transparent;
  transition: border-color 0.2s, transform 0.2s;
  background: #fff; /* NftCard 是透明的，给个背景 */
}

.nft-preview-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.nft-preview-card.selected {
  border-color: #42b883;
  box-shadow: 0 0 15px rgba(66, 184, 131, 0.5);
}

.nft-card-wrapper {
  /* 阻止 NftCard 内部的链接等被点击 */
  pointer-events: none; 
  display: block; 
  height: 100%;
}

/* 使用 :deep() 确保 NftCard 组件能正确填充
  我们在 NftCard.vue 中看到 .nft-card 是根元素
*/
:deep(.nft-card) {
    height: 100%; 
    box-shadow: none; /* 移除 NftCard 的默认阴影 */
    border: none; /* 移除 NftCard 的默认边框 */
}

.selection-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(66, 184, 131, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.2s;
  pointer-events: none; /* 允许点击穿透 */
}

.nft-preview-card.selected .selection-overlay {
  opacity: 1;
}

.selection-checkmark {
  font-size: 3rem;
  color: white;
  text-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

/* --- (以下是为请求 4 新增的样式) --- */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
label {
  font-weight: 500;
  color: #4a5568;
}
textarea {
  padding: 0.85rem;
  border: 1px solid #cbd5e0; /* 统一边框颜色 */
  border-radius: 6px; /* 统一圆角 */
  font-size: 1rem;
  font-family: inherit;
  resize: vertical;
  width: 100%;
  box-sizing: border-box;
}
textarea:focus {
  border-color: #42b883;
  box-shadow: 0 0 0 1px #42b883;
  outline: none;
}
button[type="submit"] {
  padding: 0.85rem;
  background-color: #42b883;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  font-size: 1rem;
  transition: background-color 0.2s;
  width: 100%; /* 使其占满宽度 */
  box-sizing: border-box;
}
button[type="submit"]:hover {
  background-color: #369b6e;
}
button[type="submit"]:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

/* (全局消息样式，以防万一) */
.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500; margin-bottom: 1rem;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
</style>