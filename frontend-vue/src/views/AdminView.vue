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

// --- (新增) V2 机器人状态 ---
const allBots = ref([])
const botTypes = ref({})
const showBotManager = ref(null) // 用于显示单个机器人的管理模态框

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
    inviter_bonus_amount: 200,
    // (新增) 机器人全局设置
    bot_system_enabled: 'False',
    bot_check_interval_seconds: 30
  },
  nuke: { confirm_text: '' },
  // (新增) V2 机器人表单
  bots: {
    create: {
      username: '',
      bot_type: '',
      initial_funds: 1000,
      action_probability: 0.1
    },
    manage: {
      public_key: '',
      new_probability: 0.1,
      issue_amount: 100,
      burn_amount: 100,
      confirm_purge: ''
    }
  }
})

// --- Computed Properties ---
const userOptions = computed(() => {
  return allUsers.value.map(u => ({ text: `${u.username} (UID: ${u.uid})`, value: u.public_key }))
})

// (修改) 这个计算属性现在也用于机器人管理
const selectedUserForManagement = computed(() => {
  // 优先看 'users' 标签页选中的人
  let key = forms.burn.from_key;
  if (activeTab.value === 'bots' && showBotManager.value) {
    // 如果在 'bots' 标签页，看机器人模态框选中的机器人
    key = showBotManager.value.public_key;
  }
  
  // 机器人不在 allBalances 列表里，所以我们从 allBots 找
  if (activeTab.value === 'bots' && showBotManager.value) {
     return allBots.value.find(b => b.public_key === key);
  }
  // 否则，从人类用户列表里找
  return allBalances.value.find(u => u.public_key === key);
})

// --- Watchers ---
// (NFT Watcher 保持不变)
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
  successMessage.value = null;
  
  // (修改) 并行获取 V2 机器人 API 数据
  const [usersRes, balancesRes, nftTypesRes, botListRes, botTypesRes] = await Promise.all([
    apiCall('GET', '/users/list', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/admin/balances', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/nft/types', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/bots/list', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/bots/types', { headers: adminHeaders.value })
  ]);

  // (不变) Process users
  if (usersRes[1]) errorMessage.value = `加载用户列表失败: ${usersRes[1]}`
  else allUsers.value = usersRes[0].users

  // (不变) Process balances
  if (balancesRes[1]) errorMessage.value = `加载余额列表失败: ${balancesRes[1]}`
  else allBalances.value = balancesRes[0].balances.sort((a, b) => a.username.localeCompare(b.username));

  // (不变) Process NFT types
  if (nftTypesRes[1]) errorMessage.value = `加载NFT类型失败: ${nftTypesRes[1]}`
  else {
    nftTypes.value = nftTypesRes[0]
    if (nftTypes.value.length > 0 && !forms.mintNft.nft_type) {
      forms.mintNft.nft_type = nftTypes.value[0] // Set initial value, triggers watcher
    }
  }

  // (新增) Process V2 Bot List
  if (botListRes[1]) {
    errorMessage.value = (errorMessage.value || '') + `\n加载机器人列表失败: ${botListRes[1]}`
  } else {
    allBots.value = botListRes[0].bots.sort((a,b) => a.username.localeCompare(b.username));
  }
  
  // (新增) Process V2 Bot Types
  if (botTypesRes[1]) {
     errorMessage.value = (errorMessage.value || '') + `\n加载机器人类型失败: ${botTypesRes[1]}`
  } else {
    botTypes.value = botTypesRes[0].types
    if (botTypes.value.length > 0 && !forms.bots.create.bot_type) {
      forms.bots.create.bot_type = botTypes.value[0];
    }
  }
  
  // (修改) Fetch settings (包括机器人的)
  await fetchSettings(['default_invitation_quota', 'welcome_bonus_amount', 'inviter_bonus_amount', 'bot_system_enabled', 'bot_check_interval_seconds'])

  isLoading.value = false
}

async function fetchSettings(keys) {
    for (const key of keys) {
        const [data, error] = await apiCall('GET', `/admin/setting/${key}`, { headers: adminHeaders.value });
        if (!error) {
            // (修改) 处理布尔值和数字
            if (key.includes('enabled')) {
              forms.settings[key] = data.value; // 存为 'True'/'False' 字符串
            } else {
              forms.settings[key] = Number(data.value);
            }
        }
    }
}

async function handleApiCall(method, endpoint, payload, successMsg, options = {}) {
  const { skipFetch = false } = options;
  successMessage.value = null
  errorMessage.value = null
  const [data, error] = await apiCall(method, endpoint, { payload, headers: adminHeaders.value })
  if (error) {
    errorMessage.value = `操作失败: ${error}`
  } else {
    successMessage.value = `${successMsg}: ${data.detail || '成功'}`
    if (!skipFetch) {
      await fetchData() // 自动刷新数据
    }
  }
}

// --- (修改) 拆分设置保存逻辑 ---
function handleSetSetting(key) {
    let value = forms.settings[key];
    // (新增) 布尔值需要转为 'True' 或 'False' 字符串
    if (key.includes('enabled')) {
        value = (forms.settings[key] === true || forms.settings[key] === 'True') ? 'True' : 'False';
    }
    const payload = { key, value: String(value) };
    handleApiCall('POST', '/admin/set_setting', payload, '系统设置更新成功', { skipFetch: true });
}

// (不变) 人类用户管理
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
function handlePurgeUser(userKey, confirmUsername, expectedUsername) {
    if (confirmUsername !== expectedUsername) {
        errorMessage.value = '确认用户名输入不正确！';
        return;
    }
    handleApiCall('POST', '/admin/purge_user', { public_key: userKey }, '用户清除成功');
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
function handleNukeSystem() {
    if (forms.nuke.confirm_text !== 'NUKE ALL DATA') {
        errorMessage.value = '确认文本不匹配！';
        return;
    }
    handleApiCall('POST', '/admin/nuke_system', {}, '系统重置成功');
}

// --- (新增) V2 机器人管理方法 ---

function handleSaveBotGlobalSettings() {
  // 两个设置是分开保存的
  handleSetSetting('bot_system_enabled');
  handleSetSetting('bot_check_interval_seconds');
}

async function handleCreateBot() {
  const payload = { ...forms.bots.create };
  if (payload.username === '') {
    payload.username = null; // 发送 null 以触发后端自动命名
  }
  await handleApiCall('POST', '/admin/bots/create', payload, '机器人创建成功');
  // 重置表单
  forms.bots.create.username = '';
  forms.bots.create.initial_funds = 1000;
  forms.bots.create.action_probability = 0.1;
}

function openBotManager(bot) {
  showBotManager.value = bot;
  // 预填充管理表单
  forms.bots.manage.public_key = bot.public_key;
  forms.bots.manage.new_probability = bot.action_probability;
  forms.bots.manage.issue_amount = 100;
  forms.bots.manage.burn_amount = 100;
  forms.bots.manage.confirm_purge = '';
}

function closeBotManager() {
  showBotManager.value = null;
}

// (新增) 切换机器人状态
async function handleToggleBotStatus(bot) {
  const payload = { public_key: bot.public_key, is_active: !bot.is_active };
  await handleApiCall('POST', '/admin/set_user_active_status', payload, '机器人状态更新成功');
}

// (新增) 微观管理 - 调整概率
async function handleSetBotProbability() {
  const payload = {
    public_key: forms.bots.manage.public_key,
    action_probability: forms.bots.manage.new_probability
  };
  await handleApiCall('POST', '/admin/bots/set_config', payload, '机器人概率更新成功');
  closeBotManager();
}

// (新增) 微观管理 - 增发
async function handleIssueToBot() {
  const payload = {
    to_key: forms.bots.manage.public_key,
    amount: forms.bots.manage.issue_amount,
    note: '管理员为机器人增发'
  };
  await handleApiCall('POST', '/admin/issue', payload, '机器人增发成功');
  closeBotManager();
}

// (新增) 微观管理 - 减持
async function handleBurnFromBot() {
  const payload = {
    from_key: forms.bots.manage.public_key,
    amount: forms.bots.manage.burn_amount,
    note: '管理员为机器人减持'
  };
  await handleApiCall('POST', '/admin/burn', payload, '机器人减持成功');
  closeBotManager();
}

// (新增) 微观管理 - 清除
async function handlePurgeBot() {
  if (forms.bots.manage.confirm_purge !== showBotManager.value.username) {
    errorMessage.value = '确认用户名输入不正确！';
    return;
  }
  await handleApiCall('POST', '/admin/purge_user', { public_key: forms.bots.manage.public_key }, '机器人清除成功');
  closeBotManager();
}


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
        <button :class="{ active: activeTab === 'balances' }" @click="activeTab = 'balances'">人类用户</button>
        <button :class="{ active: activeTab === 'bots' }" @click="activeTab = 'bots'">🤖 机器人管理</button>
        <button :class="{ active: activeTab === 'currency' }" @click="activeTab = 'currency'">货币管理</button>
        <button :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">用户管理 (旧)</button>
        <button :class="{ active: activeTab === 'nft' }" @click="activeTab = 'nft'">NFT 管理</button>
        <button :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">系统设置</button>
      </div>

      <div v-if="activeTab === 'balances'" class="tab-content">
        <h2>人类用户 (Ledger)</h2>
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

      <div v-if="activeTab === 'bots'" class="tab-content">
        <h2>🤖 机器人系统管理 (V2)</h2>
        
        <div class="grid-2-col">
          <form @submit.prevent="handleSaveBotGlobalSettings" class="admin-form">
            <h3>全局宏观设置</h3>
            <div class="form-group-checkbox">
              <input type="checkbox" id="bot_system_enabled" v-model="forms.settings.bot_system_enabled" true-value="True" false-value="False" />
              <label for="bot_system_enabled">启用机器人系统</label>
            </div>
            <div class="form-group">
              <label for="bot_check_interval_seconds">机器人检查间隔 (秒)</label>
              <input id="bot_check_interval_seconds" type="number" v-model.number="forms.settings.bot_check_interval_seconds" min="5" />
              <p class="help-text">系统每隔这么久“唤醒”一次，决定是否行动。</p>
            </div>
            <button type="submit" class="save-button">保存全局设置</button>
          </form>

          <form @submit.prevent="handleCreateBot" class="admin-form">
            <h3>创建新机器人</h3>
             <div class="form-group">
                <label for="bot_username">机器人用户名 (留空则自动生成)</label>
                <input id="bot_username" type="text" v-model="forms.bots.create.username" placeholder="例如: Bot_Seller_001" />
             </div>
             <div class="form-group">
                <label for="bot_type">机器人类型</label>
                <select id="bot_type" v-model="forms.bots.create.bot_type">
                  <option v-for="btype in botTypes" :key="btype" :value="btype">{{ btype }}</option>
                </select>
             </div>
             <div class="form-group">
                <label for="bot_funds">初始资金</label>
                <input id="bot_funds" type="number" v-model.number="forms.bots.create.initial_funds" min="0" />
             </div>
             <div class="form-group">
                <label for="bot_prob">行动概率 (0.0 - 1.0)</label>
                <input id="bot_prob" type="number" v-model.number="forms.bots.create.action_probability" min="0" max="1" step="0.05" />
             </div>
             <button type="submit" class="save-button">确认创建</button>
          </form>
        </div>

        <h3 class="divider-header">机器人实例列表</h3>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>UID</th>
                <th>类型</th>
                <th class="amount">余额 (FC)</th>
                <th>概率</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="allBots.length === 0">
                <td colspan="7" style="text-align: center; padding: 2rem;">没有找到机器人实例。</td>
              </tr>
              <tr v-for="bot in allBots" :key="bot.public_key">
                <td>{{ bot.username }}</td>
                <td>{{ bot.uid }}</td>
                <td>{{ bot.bot_type }}</td>
                <td class="amount">{{ formatCurrency(bot.balance) }}</td>
                <td>{{ bot.action_probability }}</td>
                <td>
                  <span :class="['status-tag', bot.is_active ? 'active' : 'inactive']">
                    {{ bot.is_active ? '活跃' : '禁用' }}
                  </span>
                </td>
                <td class="actions-cell">
                  <button class="small-button" @click="handleToggleBotStatus(bot)">
                    {{ bot.is_active ? '禁用' : '启用' }}
                  </button>
                  <button class="small-button manage-button" @click="openBotManager(bot)">
                    管理
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
            <label>目标用户 (人类)</label>
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
            <h2>批量增发 (人类)</h2>
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
        <h2>(旧) 人类用户管理</h2>
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
            <form @submit.prevent="handlePurgeUser(selectedUserForManagement.public_key, forms.purgeUser.confirm_username, selectedUserForManagement.username)" class="admin-form danger-zone">
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
                    <label>接收用户 (包括机器人)</label>
                    <select v-model="forms.mintNft.to_key">
                        <option disabled value="">-- 选择用户 --</option>
                        <optgroup label="人类用户">
                          <option v-for="opt in userOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
                        </optgroup>
                        <optgroup label="机器人">
                          <option v-for="bot in allBots" :key="bot.public_key" :value="bot.public_key">{{ bot.username }}</option>
                        </optgroup>
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
          <button type="submit">更新邀请额度</button>
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

    <div v-if="showBotManager" class="modal-overlay" @click.self="closeBotManager">
      <div class="modal-content admin-form">
        <button class="close-button" @click="closeBotManager">×</button>
        <h2>管理机器人: {{ showBotManager.username }}</h2>
        <p class="help-text">UID: {{ showBotManager.uid }}</p>

        <div class="grid-2-col">
          <form @submit.prevent="handleSetBotProbability">
            <h3>调整概率</h3>
            <div class="form-group">
              <label :for="`manage_prob_${showBotManager.uid}`">行动概率 (0.0 - 1.0)</label>
              <input :id="`manage_prob_${showBotManager.uid}`" type="number" v-model.number="forms.bots.manage.new_probability" min="0" max="1" step="0.05" />
            </div>
            <button type="submit" class="save-button">保存概率</button>
          </form>
          
          <form @submit.prevent="handleIssueToBot">
            <h3>增发货币</h3>
            <div class="form-group">
              <label :for="`manage_issue_${showBotManager.uid}`">增发金额</label>
              <input :id="`manage_issue_${showBotManager.uid}`" type="number" v-model.number="forms.bots.manage.issue_amount" min="1" />
            </div>
            <button type="submit">确认增发</button>
          </form>

          <form @submit.prevent="handleBurnFromBot">
            <h3>减持货币</h3>
            <div class="form-group">
              <label :for="`manage_burn_${showBotManager.uid}`">减持金额</label>
              <input :id="`manage_burn_${showBotManager.uid}`" type="number" v-model.number="forms.bots.manage.burn_amount" min="1" :max="showBotManager.balance" />
            </div>
            <button type="submit" :disabled="forms.bots.manage.burn_amount > showBotManager.balance">确认减持</button>
          </form>
          
          <form @submit.prevent="handlePurgeBot" class="danger-zone">
            <h3>彻底清除 (危险)</h3>
            <div class="form-group">
              <label>输入 `{{ showBotManager.username }}` 以确认</label>
              <input type="text" v-model="forms.bots.manage.confirm_purge" />
            </div>
            <button type="submit" class="danger-button">确认清除此机器人</button>
          </form>
        </div>

      </div>
    </div>

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
.admin-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #e2e8f0; flex-wrap: wrap; }
.admin-tabs button { padding: 0.75rem 1rem; border: none; background: none; font-size: 0.9rem; font-weight: 600; color: #718096; cursor: pointer; border-bottom: 4px solid transparent; transform: translateY(2px); }
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
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
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

/* (新增) V2 机器人管理面板的特定样式 */
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
  cursor: pointer;
}

h3.divider-header {
  margin-top: 2rem;
  border-top: 1px dashed #cbd5e0;
  padding-top: 1.5rem;
}

.save-button {
  background-color: #3182ce;
  margin-top: 1rem;
}
.save-button:hover {
  background-color: #2b6cb0;
}
.actions-cell {
  display: flex;
  gap: 0.5rem;
}
.manage-button {
  background-color: #3182ce;
}

/* (新增) 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.modal-content {
  position: relative;
  background: #fff;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  overflow-y: auto;
}
.close-button {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  font-size: 2rem;
  color: #718096;
  cursor: pointer;
  padding: 0.5rem;
  line-height: 1;
}
.modal-content .admin-form {
  border: none;
  padding: 0;
}
.modal-content .grid-2-col {
  gap: 2rem;
}
.modal-content .danger-zone {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 2px solid #e53e3e;
}
</style>