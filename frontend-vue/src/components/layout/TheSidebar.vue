<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { apiCall } from '@/api';
import { createSignedPayload } from '@/utils/crypto'; // <--- 1. 导入新的加密工具
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
  // ... (这部分函数保持不变)
  isLoading.value = true;
  errorMessage.value = null;

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
    friends.value = friendsData?.friends ?? [];
  }

  isLoading.value = false;
}

// --- Methods ---
async function handleTransfer() { // <--- 2. 完整替换 handleTransfer 函数
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

  isSubmitting.value = true;
  errorMessage.value = null;
  successMessage.value = null;

  // 准备要签名的消息
  const message = {
    from_key: authStore.userInfo.publicKey,
    to_key: form.value.recipientKey,
    amount: form.value.amount,
    note: form.value.note,
    timestamp: Date.now() / 1000 // 后端需要秒级时间戳
  };
  
  // 使用我们的加密工具创建签名载荷
  const signedPayload = await createSignedPayload(authStore.userInfo.privateKey, message);
  
  if (!signedPayload) {
    errorMessage.value = '创建交易签名失败，请检查控制台错误。';
    isSubmitting.value = false;
    return;
  }

  // 发送带有有效签名的API请求
  const [, error] = await apiCall('POST', '/transaction', { payload: signedPayload });

  if (error) {
    errorMessage.value = `转账失败: ${error}`;
  } else {
    const recipientName = friends.value.find(f => f.public_key === form.value.recipientKey)?.username || `公钥 ${form.value.recipientKey.substring(0, 15)}...`;
    successMessage.value = `成功向 ${recipientName} 转账 ${formatCurrency(form.value.amount)} FC！`;
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
  <aside class="sidebar">
    <div class="sidebar-header">
      <h3>🪙 FamilyCoin</h3>
    </div>

    <div class="user-info">
      <p>你好, <strong>{{ authStore.userInfo.username }}</strong></p>
      <p class="uid">UID: {{ authStore.userInfo.uid }}</p>
    </div>

    <nav class="main-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.routeName"
        :to="{ name: item.routeName }"
        class="nav-item"
        active-class="is-active"
      >
        <component :is="item.icon" class="nav-icon" />
        <span>{{ item.name }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar-footer">
      <button @click="handleLogout" class="logout-button">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  transition: width 0.3s ease;
}

.sidebar-header h3 {
  color: #2d3748;
  text-align: center;
  margin: 0 0 2rem 0;
  font-size: 1.5rem;
  letter-spacing: 1px;
}

.user-info {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.user-info p {
  margin: 0.25rem 0;
  color: #4a5568;
}

.user-info .uid {
  font-size: 0.8rem;
  color: #718096;
}

.main-nav {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 0.8rem 1rem;
  border-radius: 6px;
  text-decoration: none;
  color: #4a5568;
  font-weight: 500;
  transition: background-color 0.2s, color 0.2s;
}

.nav-item:hover {
  background-color: #edf2f7;
}

.nav-item.is-active {
  background-color: #42b883;
  color: white;
}

.nav-icon {
  width: 20px;
  height: 20px;
  margin-right: 1rem;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.logout-button {
  width: 100%;
  padding: 0.75rem;
  background-color: #f56565;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: background-color 0.2s;
}

.logout-button:hover {
  background-color: #e53e3e;
}
</style>