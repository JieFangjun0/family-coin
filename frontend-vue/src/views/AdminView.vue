<script setup>
import { ref, onMounted, reactive, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { formatCurrency, formatTimestamp } from '@/utils/formatters'

const authStore = useAuthStore()

// --- Component State ---
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)
const adminSecret = ref('')
const activeTab = ref('balances')

// --- Data ---
const allUsers = ref([])
const allBalances = ref([])
const nftTypes = ref([])
const nftMintHelpText = ref('') // For bug #3

// --- Forms ---
const forms = reactive({
  issue: { to_key: '', amount: 1000, note: '管理员增发' },
  multiIssue: { user_keys: [], amount: 100, note: '批量增发' },
  burn: { from_key: '', amount: 100, note: '管理员减持' },
  adjustQuota: { public_key: '', new_quota: 5 },
  resetPassword: { public_key: '', new_password: '' },
  purgeUser: { public_key: '', confirm_username: '' },
  mintNft: { to_key: '', nft_type: '', data: '{}' },
  settings: {
    default_invitation_quota: 5,
    welcome_bonus_amount: 500,
    inviter_bonus_amount: 200
  },
  nuke: { confirm_text: '' },
// <<< --- 1. (新增) 机器人表单状态 --- >>>
bots: {
    global_settings: {
      bot_system_enabled: false,
      bot_check_interval_seconds: 30
    },
    bot_types: {} // 将由 API 动态填充
  }
})

// --- Computed Properties ---
const userOptions = computed(() => {
  return allUsers.value.map(u => ({ text: `${u.username} (UID: ${u.uid})`, value: u.public_key }))
})

const selectedUserForManagement = computed(() => {
  const key = forms.burn.from_key
  return allBalances.value.find(u => u.public_key === key)
})

// --- Watchers ---
// +++ 核心修正 #3：监听NFT类型的变化 +++
watch(() => forms.mintNft.nft_type, async (newType) => {
  if (!newType || !adminSecret.value) return;
  
  nftMintHelpText.value = '正在加载...';
  forms.mintNft.data = '{}'; // Reset on change

  const [data, error] = await apiCall('GET', `/admin/nft/mint_info/${newType}`, { headers: adminHeaders.value });
  if (error) {
    nftMintHelpText.value = `无法加载此类型的帮助信息: ${error}`;
  } else {
    nftMintHelpText.value = data.help_text || '该类型没有提供帮助信息。';
    forms.mintNft.data = data.default_json || '{}';
  }
})

// --- API Headers ---
const adminHeaders = computed(() => ({ 'X-Admin-Secret': adminSecret.value }))

// --- Methods ---
async function fetchData() {
  if (!adminSecret.value) {
    errorMessage.value = '请输入 Admin Secret 以加载数据。'
    isLoading.value = false
    return
  }
  isLoading.value = true
  errorMessage.value = null
  
  // Clear success message on refresh
  successMessage.value = null;
  // <<< --- 2. (修改) 并行获取机器人配置 --- >>>
  const [usersRes, balancesRes, nftTypesRes, botConfigRes] = await Promise.all([
    apiCall('GET', '/users/list', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/admin/balances', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/nft/types', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/bots/config', { headers: adminHeaders.value }) // <-- 修改
  ]);

  // Process users
  if (usersRes[1]) errorMessage.value = `加载用户列表失败: ${usersRes[1]}`
  else allUsers.value = usersRes[0].users

  // Process balances
  if (balancesRes[1]) errorMessage.value = `加载余额列表失败: ${balancesRes[1]}`
  else allBalances.value = balancesRes[0].balances.sort((a, b) => a.username.localeCompare(b.username));

  // Process NFT types
  if (nftTypesRes[1]) errorMessage.value = `加载NFT类型失败: ${nftTypesRes[1]}`
  else {
    nftTypes.value = nftTypesRes[0]
    if (nftTypes.value.length > 0 && !forms.mintNft.nft_type) {
      forms.mintNft.nft_type = nftTypes.value[0] // Set initial value, triggers watcher
    }
  }
  // <<< --- 3. (新增) 处理机器人配置响应 --- >>>
  if (botConfigRes[1]) {
    errorMessage.value = (errorMessage.value || '') + `\n加载机器人配置失败: ${botConfigRes[1]}`
  } else if (botConfigRes[0]) {
    // 使用后端返回的动态结构填充表单
    forms.bots.global_settings = botConfigRes[0].global_settings;
    forms.bots.bot_types = botConfigRes[0].bot_types;
  }
  // <<< --- 新增结束 --- >>>
  
  // Fetch settings
  await fetchSettings()

  isLoading.value = false
}

async function fetchSettings() {
    const keys = ['default_invitation_quota', 'welcome_bonus_amount', 'inviter_bonus_amount'];
    for (const key of keys) {
        const [data, error] = await apiCall('GET', `/admin/setting/${key}`, { headers: adminHeaders.value });
        if (!error) {
            forms.settings[key] = Number(data.value);
        }
    }
}
async function handleApiCall(method, endpoint, payload, successMsg) {
  successMessage.value = null
  errorMessage.value = null
  const [data, error] = await apiCall(method, endpoint, { payload, headers: adminHeaders.value })
  if (error) {
    errorMessage.value = `操作失败: ${error}`
  } else {
    successMessage.value = `${successMsg}: ${data.detail}`
    // 只有非机器人配置的调用才需要刷新所有数据
    if (endpoint !== '/admin/bots/config') {
      await fetchData()
    }
  }
}

function handleSingleIssue() {
  handleApiCall('POST', '/admin/issue', forms.issue, '增发成功')
}

function handleMultiIssue() {
    const targets = forms.multiIssue.user_keys.map(key => ({ key, amount: forms.multiIssue.amount }));
    handleApiCall('POST', '/admin/multi_issue', { targets, note: forms.multiIssue.note }, '批量增发成功');
}

function handleBurn() {
    forms.burn.from_key = selectedUserForManagement.value?.public_key;
    handleApiCall('POST', '/admin/burn', forms.burn, '减持成功');
}

function handleAdjustQuota() {
    forms.adjustQuota.public_key = selectedUserForManagement.value?.public_key;
    handleApiCall('POST', '/admin/adjust_quota', forms.adjustQuota, '额度调整成功');
}
function handleToggleUserStatus(user) {
    const payload = { public_key: user.public_key, is_active: !user.is_active };
    handleApiCall('POST', '/admin/set_user_active_status', payload, '用户状态更新成功');
}

function handleResetPassword() {
    forms.resetPassword.public_key = selectedUserForManagement.value?.public_key;
    handleApiCall('POST', '/admin/reset_password', forms.resetPassword, '密码重置成功');
}

function handlePurgeUser() {
    if (forms.purgeUser.confirm_username !== selectedUserForManagement.value?.username) {
        errorMessage.value = '确认用户名输入不正确！';
        return;
    }
    forms.purgeUser.public_key = selectedUserForManagement.value?.public_key;
    handleApiCall('POST', '/admin/purge_user', { public_key: forms.purgeUser.public_key }, '用户清除成功');
}

function handleMintNft() {
    try {
        const data = JSON.parse(forms.mintNft.data);
        const payload = { ...forms.mintNft, data };
        handleApiCall('POST', '/admin/nft/mint', payload, 'NFT 铸造成功');
    } catch (e) {
        errorMessage.value = 'NFT 初始数据不是有效的 JSON 格式！';
    }
}

function handleSetSetting(key) {
    const payload = { key, value: String(forms.settings[key]) };
    handleApiCall('POST', '/admin/set_setting', payload, '系统设置更新成功');
}

function handleNukeSystem() {
    if (forms.nuke.confirm_text !== 'NUKE ALL DATA') {
        errorMessage.value = '确认文本不匹配！';
        return;
    }
    handleApiCall('POST', '/admin/nuke_system', {}, '系统重置成功');
}
// <<< --- 4. (新增) 保存机器人配置的处理函数 --- >>>
async function handleSaveBotConfig() {
  // 创建一个干净的有效载荷，以确保类型正确
  const payload = {
    global_settings: {
      bot_system_enabled: forms.bots.global_settings.bot_system_enabled,
      bot_check_interval_seconds: Number(forms.bots.global_settings.bot_check_interval_seconds) || 30
    },
    bot_types: {}
  }

  // 迭代动态的机器人类型并清理它们的数据
  for (const botName in forms.bots.bot_types) {
    const config = forms.bots.bot_types[botName];
    payload.bot_types[botName] = {
      // 我们只发送回后端需要的数据
      count: Number(config.count) || 0,
      action_probability: Number(config.action_probability) || 0.1
    }
  }
  
  await handleApiCall('POST', '/admin/bots/config', payload, '机器人配置已保存')
  // 保存后立即刷新，以获取可能由后端纠正的配置 (例如新添加的机器人)
  await fetchData();
}
// <<< --- 新增结束 --- >>>

onMounted(() => {
  isLoading.value = false;
})
</script>

<template>
  <div class="admin-view">
    <header class="view-header">
      <h1>管理员面板</h1>
      <p class="subtitle">在这里管理 FamilyCoin 系统的方方面面。</p>
    </header>

    <div class="admin-secret-wrapper">
      <label for="admin-secret">Admin Secret</label>
      <input id="admin-secret" type="password" v-model="adminSecret" placeholder="输入后端的 ADMIN_SECRET_KEY" />
      <button @click="fetchData" :disabled="!adminSecret">加载管理数据</button>
    </div>

    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>

    <div v-if="isLoading" class="loading-state">正在加载管理数据...</div>

    <div v-if="!isLoading && adminSecret" class="admin-content">
      <div class="admin-tabs">
        <button :class="{ active: activeTab === 'balances' }" @click="activeTab = 'balances'">监控中心</button>
        <button :class="{ active: activeTab === 'currency' }" @click="activeTab = 'currency'">货币管理</button>
        <button :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">用户管理</button>
        <button :class="{ active: activeTab === 'nft' }" @click="activeTab = 'nft'">NFT 管理</button>
        <button :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">系统设置</button>
        <button :class="{ active: activeTab === 'bots' }" @click="activeTab = 'bots'">🤖 机器人管理</button>
      </div>

      <div v-if="activeTab === 'balances'" class="tab-content">
        <h2>监控中心 (Ledger)</h2>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>UID</th>
                <th>余额 (FC)</th>
                <th>邀请人</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in allBalances" :key="user.public_key">
                <td>{{ user.username }}</td>
                <td>{{ user.uid }}</td>
                <td class="amount">{{ formatCurrency(user.balance) }}</td>
                <td>{{ user.inviter_username || '---' }}</td>
                <td>
                  <span :class="['status-tag', user.is_active ? 'active' : 'inactive']">
                    {{ user.is_active ? '活跃' : '禁用' }}
                  </span>
                </td>
                <td>
                  <button class="small-button" @click="handleToggleUserStatus(user)">
                    {{ user.is_active ? '禁用' : '启用' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="activeTab === 'currency'" class="tab-content grid-2-col">
        <form @submit.prevent="handleSingleIssue" class="admin-form">
          <h2>增发货币 (单人)</h2>
          <div class="form-group">
            <label>目标用户</label>
            <select v-model="forms.issue.to_key">
              <option disabled value="">-- 选择用户 --</option>
              <option v-for="opt in userOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>发行金额</label>
            <input type="number" v-model.number="forms.issue.amount" min="1" step="0.01" />
          </div>
          <div class="form-group">
            <label>备注</label>
            <input type="text" v-model="forms.issue.note" />
          </div>
          <button type="submit">确认发行</button>
        </form>

        <form @submit.prevent="handleMultiIssue" class="admin-form">
            <h2>批量增发</h2>
             <div class="form-group">
                <label>目标用户 (可多选)</label>
                <select v-model="forms.multiIssue.user_keys" multiple size="5">
                    <option v-for="opt in userOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
                </select>
             </div>
             <div class="form-group">
                <label>统一发行金额</label>
                <input type="number" v-model.number="forms.multiIssue.amount" min="1" step="0.01" />
             </div>
             <div class="form-group">
                <label>备注</label>
                <input type="text" v-model="forms.multiIssue.note" />
             </div>
             <button type="submit">确认批量发行</button>
        </form>
      </div>

      <div v-if="activeTab === 'users'" class="tab-content">
        <h2>用户管理</h2>
         <div class="form-group">
            <label>选择要管理的用户</label>
            <select v-model="forms.burn.from_key">
                <option disabled value="">-- 选择用户 --</option>
                <option v-for="opt in userOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
            </select>
         </div>
         <div v-if="selectedUserForManagement" class="grid-2-col">
            <form @submit.prevent="handleBurn" class="admin-form">
                <h3>减持货币</h3>
                <div class="form-group">
                    <label>减持金额</label>
                    <input type="number" v-model.number="forms.burn.amount" min="0.01" step="0.01" />
                </div>
                <div class="form-group">
                    <label>减持备注 (必填)</label>
                    <input type="text" v-model="forms.burn.note" required />
                </div>
                <button type="submit">确认减持</button>
            </form>
            <form @submit.prevent="handleAdjustQuota" class="admin-form">
                <h3>调整邀请额度</h3>
                <div class="form-group">
                    <label>新的邀请额度</label>
                    <input type="number" v-model.number="forms.adjustQuota.new_quota" min="0" />
                </div>
                <button type="submit">确认调整</button>
            </form>
            <form @submit.prevent="handleResetPassword" class="admin-form">
                <h3>重置密码</h3>
                <div class="form-group">
                    <label>新密码 (至少6位)</label>
                    <input type="password" v-model="forms.resetPassword.new_password" required minlength="6" />
                </div>
                <button type="submit">确认重置</button>
            </form>
            <form @submit.prevent="handlePurgeUser" class="admin-form danger-zone">
                <h3>彻底清除用户 (危险)</h3>
                <p>此操作不可逆，将删除用户所有数据！</p>
                 <div class="form-group">
                    <label>输入用户名 `{{ selectedUserForManagement.username }}` 以确认</label>
                    <input type="text" v-model="forms.purgeUser.confirm_username" />
                 </div>
                <button type="submit" class="danger-button">确认清除</button>
            </form>
         </div>
      </div>

      <div v-if="activeTab === 'nft'" class="tab-content">
         <h2>NFT 铸造与发行</h2>
         <form @submit.prevent="handleMintNft" class="admin-form">
            <div class="grid-2-col">
                <div class="form-group">
                    <label>接收用户</label>
                    <select v-model="forms.mintNft.to_key">
                        <option disabled value="">-- 选择用户 --</option>
                        <option v-for="opt in userOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>NFT 类型</label>
                    <select v-model="forms.mintNft.nft_type">
                        <option v-for="type in nftTypes" :key="type" :value="type">{{ type }}</option>
                    </select>
                </div>
            </div>
             <div class="form-group">
                <label>初始数据 (JSON格式)</label>
                <p class="help-text">{{ nftMintHelpText }}</p>
                <textarea v-model="forms.mintNft.data" rows="8" :key="forms.mintNft.nft_type"></textarea>
             </div>
             <button type="submit">确认铸造</button>
         </form>
      </div>

      <div v-if="activeTab === 'settings'" class="tab-content grid-2-col">
        <form @submit.prevent="handleSetSetting('default_invitation_quota')" class="admin-form">
          <h2>邀请系统设置</h2>
          <div class="form-group">
            <label>新用户默认邀请额度</label>
            <input type="number" v-model.number="forms.settings.default_invitation_quota" min="0" />
          </div>
          <button type="submit">更新全局设置</button>
        </form>
        <form @submit.prevent="handleSetSetting('welcome_bonus_amount')" class="admin-form">
          <h2>新用户奖励</h2>
          <div class="form-group">
            <label>注册奖励金额 (FC)</label>
            <input type="number" v-model.number="forms.settings.welcome_bonus_amount" min="0" step="0.01"/>
          </div>
          <button type="submit">更新注册奖励</button>
        </form>
         <form @submit.prevent="handleSetSetting('inviter_bonus_amount')" class="admin-form">
          <h2>邀请人奖励</h2>
          <div class="form-group">
            <label>成功邀请奖励 (FC)</label>
            <input type="number" v-model.number="forms.settings.inviter_bonus_amount" min="0" step="0.01"/>
          </div>
          <button type="submit">更新邀请奖励</button>
        </form>
        <form @submit.prevent="handleNukeSystem" class="admin-form danger-zone">
            <h2>危险区域</h2>
            <p>此操作将删除所有数据并重置系统！</p>
            <div class="form-group">
                <label>输入 `NUKE ALL DATA` 以确认</label>
                <input type="text" v-model="forms.nuke.confirm_text" />
            </div>
            <button type="submit" class="danger-button">重置系统 (!!!)</button>
        </form>
      </div>
    </div>
<div v-if="activeTab === 'bots'" class="tab-content">
        <h2>🤖 机器人系统管理</h2>
        <form @submit.prevent="handleSaveBotConfig" class="admin-form">
          <h3>全局设置</h3>
          <div class="form-group-checkbox">
            <input type="checkbox" id="bot_system_enabled" v-model="forms.bots.global_settings.bot_system_enabled" />
            <label for="bot_system_enabled">启用机器人系统 (Bots will activate on next cycle)</label>
          </div>
          <div class="form-group">
            <label for="bot_check_interval_seconds">机器人检查间隔 (秒)</label>
            <input id="bot_check_interval_seconds" type="number" v.model.number="forms.bots.global_settings.bot_check_interval_seconds" min="5" />
            <p class="help-text">系统每隔这么久“唤醒”一次，然后根据各自的概率决定机器人是否行动。</p>
          </div>

          <h3 class="divider">机器人实例配置</h3>
          
          <div 
            v-for="(config, botName) in forms.bots.bot_types" 
            :key="botName" 
            class="bot-config-group"
          >
            <h4>{{ botName }}</h4>
            <p class="help-text">{{ config.description || '没有为此机器人提供描述。' }}</p>
            <div class="grid-2-col">
              <div class="form-group">
                <label :for="`bot_${botName}_count`">实例数量</label>
                <input :id="`bot_${botName}_count`" type="number" v.model.number="config.count" min="0" max="10" />
              </div>
              <div class="form-group">
                <label :for="`bot_${botName}_prob`">行动概率 (0.0 - 1.0)</label>
                <input :id="`bot_${botName}_prob`" type="number" v.model.number="config.action_probability" min="0" max="1" step="0.05" />
              </div>
            </div>
          </div>
          
          <div v-if="!Object.keys(forms.bots.bot_types).length" class="empty-state-small">
            后端没有注册任何机器人逻辑。
          </div>

          <button type="submit" class="save-button">保存机器人设置</button>
        </form>
      </div>
      <!-- </div> -->
  </div>
</template>

<style scoped>
/* (大部分样式保持不变) */
.admin-view { max-width: 1200px; margin: 0 auto; }
.view-header h1 { font-size: 2rem; font-weight: 700; color: #2d3748; }
.subtitle { color: #718096; margin-bottom: 2rem; }
.admin-secret-wrapper { background: #fff; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 1rem; }
.admin-secret-wrapper label { font-weight: 600; }
.admin-secret-wrapper input { flex-grow: 1; }
.loading-state { text-align: center; padding: 3rem; color: #718096; }
.admin-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #e2e8f0; }
.admin-tabs button { padding: 0.75rem 1.5rem; border: none; background: none; font-size: 1rem; font-weight: 600; color: #718096; cursor: pointer; border-bottom: 4px solid transparent; transform: translateY(2px); }
.admin-tabs button.active { color: #c53030; border-bottom-color: #c53030; }
.tab-content h2 { margin-top: 0; margin-bottom: 1.5rem; }
.grid-2-col { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem; }
.admin-form { background: #fff; padding: 1.5rem; border-radius: 8px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 1rem; }
.admin-form h3 { margin: 0 0 0.5rem 0; }
.form-group { display: flex; flex-direction: column; gap: 0.5rem; }
.help-text { font-size: 0.8rem; color: #718096; margin-top: -0.5rem; white-space: pre-wrap; }
label { font-weight: 500; color: #4a5568; }
input, select, textarea { padding: 0.75rem; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 1rem; width: 100%; box-sizing: border-box; }
select[multiple] { height: 120px; }
button { padding: 0.85rem; background-color: #4a5568; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 1rem; transition: background-color 0.2s; }
button:hover { background-color: #2d3748; }
button:disabled { background-color: #a0aec0; cursor: not-allowed; }
.table-wrapper { background-color: #fff; border-radius: 8px; border: 1px solid #e2e8f0; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
th { background-color: #f7fafc; font-size: 0.8rem; text-transform: uppercase; color: #718096; }
td { font-size: 0.9rem; }
.amount { text-align: right; font-family: monospace; }
.status-tag { padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.status-tag.active { background-color: #c6f6d5; color: #2f855a; }
.status-tag.inactive { background-color: #fed7d7; color: #c53030; }
.small-button { padding: 0.3rem 0.6rem; font-size: 0.8rem; font-weight: 500; }
.danger-zone { border-color: #e53e3e; }
.danger-button { background-color: #c53030; }
.danger-button:hover { background-color: #9b2c2c; }
.message { padding: 1rem; border-radius: 4px; text-align: center; margin-bottom: 1rem; }
.success { color: #155724; background-color: #d4edda; }
.error { color: #d8000c; background-color: #ffbaba; }
/* <<< --- 7. (新增) 机器人管理面板的特定样式 --- >>> */
.form-group-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #f7fafc;
  padding: 1rem;
  border-radius: 6px;
}
.form-group-checkbox input[type="checkbox"] {
  width: auto;
  height: 1.2em;
  width: 1.2em;
}
.form-group-checkbox label {
  font-weight: 600;
  color: #2d3748;
}

h3.divider {
  margin-top: 2rem;
  border-top: 1px dashed #cbd5e0;
  padding-top: 1.5rem;
}

.bot-config-group {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  background-color: #fdfdfd;
}
.bot-config-group h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.1rem;
  color: #2b6cb0;
}
.bot-config-group .help-text {
  margin-top: 0;
  margin-bottom: 1rem;
  font-style: italic;
  color: #4a5568;
}
.save-button {
  background-color: #3182ce;
  margin-top: 1rem;
}
.save-button:hover {
  background-color: #2b6cb0;
}
</style>