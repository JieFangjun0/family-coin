<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { createSignedPayload } from '@/utils/crypto'
import BalanceCard from '@/components/wallet/BalanceCard.vue'
import { formatTimestamp } from '@/utils/formatters'

const authStore = useAuthStore()

// --- Reactive State ---
const userDetails = ref(null)
const myCodes = ref([])
const isLoading = ref(true)
const isGenerating = ref(false)
const errorMessage = ref(null)
const successMessage = ref(null)
const copiedCode = ref(null) // 新增：用于跟踪哪个邀请码被复制了

// --- Data Fetching ---
async function fetchData() {
  isLoading.value = true
  errorMessage.value = null

  const [detailsResult, codesResult] = await Promise.all([
    apiCall('GET', '/user/details', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/user/my_invitations', { params: { public_key: authStore.userInfo.publicKey } })
  ]);

  const [detailsData, detailsError] = detailsResult;
  if (detailsError) {
    errorMessage.value = `无法获取用户详情: ${detailsError}`;
  } else {
    userDetails.value = detailsData;
  }

  const [codesData, codesError] = codesResult;
  if (codesError) {
    errorMessage.value = (errorMessage.value ? errorMessage.value + '\n' : '') + `无法获取邀请码列表: ${codesError}`;
  } else {
    myCodes.value = codesData?.codes ?? [];
  }

  isLoading.value = false;
}

// --- Methods ---
async function handleGenerateCode() {
  isGenerating.value = true;
  successMessage.value = null;
  errorMessage.value = null;

  const message = {
    owner_key: authStore.userInfo.publicKey,
    timestamp: Date.now() / 1000,
  };

  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message);
  if (!signedPayload) {
    errorMessage.value = '创建签名失败。';
    isGenerating.value = false;
    return;
  }

  const [data, error] = await apiCall('POST', '/user/generate_invitation', { payload: signedPayload });

  if (error) {
    errorMessage.value = `生成失败: ${error}`;
  } else {
    successMessage.value = `成功生成新的邀请码: ${data.code}`;
    await fetchData();
  }

  isGenerating.value = false;
}

// --- 新增：复制到剪贴板的方法 ---
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    copiedCode.value = text; // 记录哪个码被复制了，用于UI反馈
    setTimeout(() => {
      copiedCode.value = null; // 2秒后重置状态
    }, 2000);
  } catch (err) {
    console.error('复制失败: ', err);
    // 可以在这里添加一个错误提示
  }
}

// --- Lifecycle Hook ---
onMounted(fetchData);
</script>

<template>
  <div class="invitation-view">
    <header class="view-header">
      <h1>邀请新成员</h1>
      <p class="subtitle">邀请你的家人和朋友加入 FamilyCoin。</p>
    </header>

    <div v-if="isLoading" class="loading-state">
      <p>正在加载邀请数据...</p>
    </div>

    <div v-if="errorMessage && !isLoading" class="error-state">
      <p>{{ errorMessage }}</p>
      <button @click="fetchData">重试</button>
    </div>

    <div v-if="!isLoading && !errorMessage" class="invitation-content">
      <div class="stats-grid">
        <BalanceCard v-if="userDetails" label="剩余邀请次数" :value="userDetails.invitation_quota" />
        <div class="generate-card">
          <p>每次生成将消耗 1 次邀请次数。</p>
          <button @click="handleGenerateCode" :disabled="isGenerating || !userDetails || userDetails.invitation_quota <= 0">
            {{ isGenerating ? '生成中...' : '生成新邀请码' }}
          </button>
        </div>
      </div>

      <div v-if="successMessage" class="message success">{{ successMessage }}</div>

      <div class="codes-section">
        <h2>我未使用的邀请码</h2>
        <div class="codes-list">
          <div v-if="myCodes.length === 0" class="empty-state">
            <p>你没有可用的邀请码。</p>
          </div>
          <table v-else class="codes-table">
            <thead>
              <tr>
                <th>邀请码</th>
                <th>生成时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="code in myCodes" :key="code.code">
                <td class="code-value">{{ code.code }}</td>
                <td>{{ formatTimestamp(code.created_at) }}</td>
                <td>
                  <button @click="copyToClipboard(code.code)" :disabled="copiedCode === code.code">
                    {{ copiedCode === code.code ? '已复制!' : '复制' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.invitation-view {
  max-width: 900px;
  margin: 0 auto;
}

.view-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #2d3748;
}

.subtitle {
  color: #718096;
  margin-bottom: 2rem;
}

.loading-state, .error-state, .empty-state {
  text-align: center;
  padding: 3rem;
  color: #718096;
}

.invitation-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.generate-card {
  background-color: #fff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 1rem;
}

.generate-card p {
  margin: 0;
  color: #4a5568;
  text-align: center;
}

button {
  padding: 0.75rem 1.5rem;
  background-color: #42b883;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  font-size: 1rem;
  transition: background-color 0.2s;
}
button:hover { background-color: #369b6e; }
button:disabled { background-color: #a0aec0; cursor: not-allowed; }

.codes-section h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 1.5rem;
}

.codes-list {
  background-color: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.codes-table {
  width: 100%;
  border-collapse: collapse;
}
.codes-table th, .codes-table td {
  padding: 1rem 1.25rem;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}
.codes-table th {
  background-color: #f7fafc;
}
.codes-table tbody tr:last-child td {
  border-bottom: none;
}
.code-value {
  font-family: monospace;
  font-weight: bold;
  font-size: 1.1rem;
  color: #2d3748;
}

.message { padding: 1rem; border-radius: 4px; text-align: center; margin-bottom: 1rem; }
.success { color: #155724; background-color: #d4edda; border-color: #c3e6cb; }
</style>