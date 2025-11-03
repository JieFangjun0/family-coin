<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { formatTimestamp, formatCurrency } from '@/utils/formatters'
import BalanceCard from '@/components/wallet/BalanceCard.vue'
import ClickableUsername from '@/components/global/ClickableUsername.vue' // 引入组件

const authStore = useAuthStore()

const balance = ref(0)
const userDetails = ref(null)
const history = ref([])
const isLoading = ref(true)
const errorMessage = ref(null)

async function fetchData() {
  isLoading.value = true
  errorMessage.value = null

  const [balanceResult, detailsResult, historyResult] = await Promise.all([
    apiCall('GET', '/balance', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/user/details', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/history', { params: { public_key: authStore.userInfo.publicKey } })
  ]);

  const [balanceData, balanceError] = balanceResult;
  if (balanceError) {
    errorMessage.value = `无法获取余额: ${balanceError}`;
  } else {
    balance.value = balanceData?.balance ?? 0;
  }

  const [detailsData, detailsError] = detailsResult;
  if (detailsError) {
    errorMessage.value = (errorMessage.value ? errorMessage.value + '\n' : '') + `无法获取用户详情: ${detailsError}`;
  } else {
    userDetails.value = detailsData;
  }

  const [historyData, historyError] = historyResult;
  if (historyError) {
    errorMessage.value = (errorMessage.value ? errorMessage.value + '\n' : '') + `无法获取交易历史: ${historyError}`;
  } else {
    history.value = historyData?.transactions ?? [];
  }

  isLoading.value = false;
}

onMounted(() => {
  fetchData();
})
</script>

<template>
  <div class="wallet-view">
    <header class="view-header">
      <h1>我的钱包</h1>
    </header>

    <div v-if="isLoading" class="loading-state">
      <p>正在加载数据...</p>
    </div>
    
    <div v-if="errorMessage" class="error-state">
      <p>{{ errorMessage }}</p>
      <button @click="fetchData">重试</button>
    </div>

    <div v-if="!isLoading && !errorMessage" class="wallet-content">
      <div class="stats-grid">
        <BalanceCard label="当前余额" :value="formatCurrency(balance)" unit="FC" />
        <BalanceCard v-if="userDetails" label="总交易次数" :value="userDetails.tx_count" />
        
        <BalanceCard v-if="userDetails" label="邀请人">
            <ClickableUsername 
                v-if="userDetails.inviter_uid"
                :uid="userDetails.inviter_uid"
                :username="userDetails.inviter_username"
            />
            <span v-else>{{ userDetails.inviter_username || '---' }}</span>
        </BalanceCard>
      </div>

      <div class="history-section">
        <h2>交易历史</h2>
        <div class="history-list">
          <div v-if="history.length === 0" class="empty-history">
            <p>没有交易记录。</p>
          </div>
          <table v-else class="history-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>方向</th>
                <th>对方</th>
                <th class="amount">金额 (FC)</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in history" :key="tx.tx_id">
                <td>{{ formatTimestamp(tx.timestamp) }}</td>
                <td>
                  <span :class="['tx-type', tx.type === 'out' ? 'out' : 'in']">
                    {{ tx.type === 'out' ? '支出' : '收入' }}
                  </span>
                </td>
                <td>
                    <template v-if="tx.type === 'out'">
                        <ClickableUsername v-if="tx.to_uid" :uid="tx.to_uid" :username="tx.to_display" />
                        <span v-else>{{ tx.to_display }}</span>
                    </template>
                    <template v-else>
                        <ClickableUsername v-if="tx.from_uid" :uid="tx.from_uid" :username="tx.from_display" />
                        <span v-else>{{ tx.from_display }}</span>
                    </template>
                </td>
                <td class="amount">{{ tx.type === 'out' ? '-' : '+' }} {{ formatCurrency(tx.amount) }}</td>
                <td>{{ tx.note || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wallet-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; margin-bottom: 2rem; }
.loading-state, .error-state, .empty-history { text-align: center; padding: 3rem; color: #718096; }
.error-state button { margin-top: 1rem; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 3rem; }
.history-section h2 { font-size: 1.5rem; font-weight: 600; color: #2d3748; margin-bottom: 1.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e2e8f0; }
.history-list { background-color: #fff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }
.history-table { width: 100%; border-collapse: collapse; }
.history-table th, .history-table td { padding: 1rem 1.25rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
.history-table th { background-color: #f7fafc; font-size: 0.8rem; text-transform: uppercase; color: #718096; }
.history-table tbody tr:last-child td { border-bottom: none; }
.history-table td { font-size: 0.9rem; color: #4a5568; }
.tx-type { font-weight: 500; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
.tx-type.in { color: #2f855a; background-color: #c6f6d5; }
.tx-type.out { color: #c53030; background-color: #fed7d7; }
.amount { text-align: right; font-family: monospace; font-size: 1rem; }
/*scoped style for BalanceCard content slot*/
:deep(.balance-card .value) {
    display: flex;
    align-items: center;
}
</style>