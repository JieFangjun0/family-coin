<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { apiCall } from '@/api';
import { createSignedPayload } from '@/utils/crypto'; // 导入签名函数
import BalanceCard from '@/components/wallet/BalanceCard.vue';
import { formatCurrency } from '@/utils/formatters';

const authStore = useAuthStore();

// --- Reactive State ---
const balance = ref(0);
const friends = ref([]);
const isLoading = ref(true);
const isSubmitting = ref(false);
const errorMessage = ref(null);
const successMessage = ref(null);

// Form State
const form = ref({
  recipientKey: '',
  amount: 0.01,
  note: ''
});

// --- Data Fetching ---
async function fetchData() {
  isLoading.value = true;
  errorMessage.value = null;

  // 并行获取余额和好友列表
  const [balanceResult, friendsResult] = await Promise.all([
    apiCall('GET', '/balance', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/friends/list', { params: { public_key: authStore.userInfo.publicKey } })
  ]);

  const [balanceData, balanceError] = balanceResult;
  if (balanceError) {
    errorMessage.value = `无法获取余额: ${balanceError}`;
  } else {
    balance.value = balanceData?.balance ?? 0;
  }

  const [friendsData, friendsError] = friendsResult;
  if (friendsError) {
    errorMessage.value = (errorMessage.value ? errorMessage.value + '\n' : '') + `无法获取好友列表: ${friendsError}`;
  } else {
    // 按用户名排序好友列表
    friends.value = (friendsData?.friends ?? []).sort((a, b) => a.username.localeCompare(b.username));
  }

  isLoading.value = false;
}

// --- Methods ---
async function handleTransfer() {
  // 清空之前的消息
  errorMessage.value = null;
  successMessage.value = null;

  if (form.value.amount <= 0) {
    errorMessage.value = '转账金额必须大于 0。';
    return;
  }
  if (!form.value.recipientKey) {
    errorMessage.value = '请选择或输入一个收款人。';
    return;
  }
  if (form.value.amount > balance.value) {
    errorMessage.value = '你的余额不足。';
    return;
  }
  if (form.value.recipientKey === authStore.userInfo.publicKey) {
      errorMessage.value = '不能给自己转账。';
      return;
  }

  isSubmitting.value = true;

  // 1. 准备要签名的消息
  const message = {
    from_key: authStore.userInfo.publicKey,
    to_key: form.value.recipientKey,
    amount: form.value.amount,
    note: form.value.note,
    timestamp: Math.floor(Date.now() / 1000) // 后端需要以秒为单位的整数时间戳
  };
  
  // 2. 调用我们修复好的签名函数（注意：它是同步的，不需要 await）
  const signedPayload = createSignedPayload(authStore.userInfo.privateKey, message);

  if (!signedPayload) {
    errorMessage.value = '创建交易签名失败，请检查浏览器控制台。';
    isSubmitting.value = false;
    return;
  }

  // 3. 发送 API 请求
  const [data, error] = await apiCall('POST', '/transaction', { payload: signedPayload });

  if (error) {
    errorMessage.value = `转账失败: ${error}`;
  } else {
    successMessage.value = `转账成功！${data.detail || ''}`;
    // 重置表单并刷新数据
    form.value.recipientKey = '';
    form.value.amount = 0.01;
    form.value.note = '';
    await fetchData(); // 刷新余额
  }

  isSubmitting.value = false;
}

// --- Lifecycle Hook ---
onMounted(fetchData);

</script>

<template>
  <div class="transfer-view">
    <header class="view-header">
      <h1>转账</h1>
      <p class="subtitle">向你的好友发送 JCoin。</p>
    </header>

    <div v-if="isLoading" class="loading-state">
      <p>正在加载数据...</p>
    </div>

    <div v-if="errorMessage && !isLoading" class="error-state">
      <p>{{ errorMessage }}</p>
      <button @click="fetchData">重试</button>
    </div>

    <div v-if="!isLoading" class="transfer-content">
      <BalanceCard label="可用余额" :value="formatCurrency(balance)" unit="FC" />

      <form @submit.prevent="handleTransfer" class="transfer-form">
        <h2>交易详情</h2>

        <div class="form-group">
          <label for="recipient">收款人</label>
          <select id="recipient" v-model="form.recipientKey">
            <option disabled value="">-- 从好友中选择 --</option>
            <option v-for="friend in friends" :key="friend.public_key" :value="friend.public_key">
              {{ friend.username }} (UID: {{ friend.uid }})
            </option>
          </select>
          <textarea v-model="form.recipientKey" placeholder="或在此处直接粘贴对方的公钥" rows="4"></textarea>
        </div>

        <div class="form-group">
          <label for="amount">金额 (FC)</label>
          <input id="amount" type="number" v-model.number="form.amount" min="0.01" :max="balance" step="0.01" required />
        </div>

        <div class="form-group">
          <label for="note">备注 (可选)</label>
          <input id="note" type="text" v-model="form.note" maxlength="50" placeholder="最多50个字符" />
        </div>
        
        <div v-if="successMessage" class="message success">{{ successMessage }}</div>
        <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

        <button type="submit" :disabled="isSubmitting || form.amount > balance">
          {{ isSubmitting ? '交易处理中...' : (form.amount > balance ? '余额不足' : '签名并转账') }}
        </button>

      </form>
    </div>
  </div>
</template>

<style scoped>
.transfer-view {
  max-width: 700px;
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

.loading-state, .error-state {
  text-align: center;
  padding: 3rem;
  color: #718096;
}

.transfer-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.transfer-form {
  background-color: #fff;
  padding: 2rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.transfer-form h2 {
  margin-top: 0;
  font-size: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

label {
  font-weight: 600;
  color: #4a5568;
}

input, select, textarea {
  padding: 0.75rem;
  border: 1px solid #cbd5e0;
  border-radius: 6px;
  font-size: 1rem;
  width: 100%;
  box-sizing: border-box;
}

textarea {
  font-family: monospace;
  margin-top: 0.5rem;
  resize: vertical;
}

button {
  padding: 0.85rem;
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

.message { padding: 1rem; border-radius: 4px; text-align: center; font-weight: 500;}
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
</style>