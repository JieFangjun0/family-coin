<script setup>
import { ref, onMounted, reactive, computed, watch } from 'vue' // +++ 引入 watch +++
import { useAuthStore } from '@/stores/auth'
import { apiCall } from '@/api'
import { formatCurrency, formatTimestamp } from '@/utils/formatters'
import ClickableUsername from '@/components/global/ClickableUsername.vue'

const authStore = useAuthStore()

// --- 组件状态 ---
const isLoading = ref(true)
const errorMessage = ref(null)
const successMessage = ref(null)

// +++ 核心修改 1：从 localStorage 读取 adminSecret +++
const adminSecret = ref(localStorage.getItem('adminSecret') || '')

const activeTab = ref('user_management') 

// --- 数据 ---
const allUsers = ref([])
const allBalances = ref([])
const nftTypes = ref([])
const nftMintHelpText = ref('') 

// 机器人状态
const allBots = ref([])
const botTypeConfigs = ref({}) 
const showBotManager = ref(null) // 用于显示单个机器人的管理模态框
const botLogs = ref([])
const logFilterKey = ref('') // 用于日志过滤
// 交易历史
const marketTradeHistory = ref([])
// --- 表单 ---
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
    bot_system_enabled: 'False',
    bot_check_interval_seconds: 30
  },
  nuke: { confirm_text: '' },
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
  },
  market_history: { 
    limit:100,
  }
})

// --- 计算属性 ---
const userOptions = computed(() => {
  return allBalances.value.map(u => ({ text: `${u.username} (UID: ${u.uid})`, value: u.public_key }))
})
const botTypes = computed(() => {
  return Object.keys(botTypeConfigs.value)
})

// 这个计算属性现在用于“用户管理”标签页中的精细管理
const selectedUserForManagement = computed(() => {
  let key = forms.burn.from_key;
  return allBalances.value.find(u => u.public_key === key);
})

const getBotDisplayName = (botType) => {
  return botTypeConfigs.value[botType]?.display_name || botType
}

// --- 侦听器 ---

// +++ 核心修改 2：添加 watch 以持久化 adminSecret +++
watch(adminSecret, (newValue) => {
  localStorage.setItem('adminSecret', newValue)
})

// 当NFT类型改变时，加载对应的帮助信息和默认JSON
watch(() => forms.mintNft.nft_type, async (newType) => {
  if (!newType || !adminSecret.value) return;
  
  nftMintHelpText.value = '正在加载...';
  forms.mintNft.data = '{}'; // 重置

  const [data, error] = await apiCall('GET', `/admin/nft/mint_info/${newType}`, { headers: adminHeaders.value });
  if (error) {
    nftMintHelpText.value = `无法加载此类型的帮助信息: ${error}`;
  } else {
    nftMintHelpText.value = data.help_text || '该类型没有提供帮助信息。';
    forms.mintNft.data = data.default_json || '{}';
  }
})

// 当机器人类型改变时，更新默认值
watch(() => forms.bots.create.bot_type, (newType) => {
  const config = botTypeConfigs.value[newType]
  if (config) {
    forms.bots.create.initial_funds = config.initial_funds
    forms.bots.create.action_probability = config.action_probability
  }
})

// --- API 请求头 ---
const adminHeaders = computed(() => ({ 'X-Admin-Secret': adminSecret.value }))

// --- 方法 ---
async function fetchData() {
  if (!adminSecret.value) {
    errorMessage.value = '请输入 Admin Secret 以加载数据。'
    isLoading.value = false
    return
  }
  isLoading.value = true
  errorMessage.value = null
  successMessage.value = null;
  
  const [usersRes, balancesRes, nftTypesRes, botListRes, botTypesRes, botLogsRes, marketHistoryRes] = await Promise.all([
    apiCall('GET', '/users/list', { params: { public_key: authStore.userInfo.publicKey } }),
    apiCall('GET', '/admin/balances', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/nft/types', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/bots/list', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/bots/types', { headers: adminHeaders.value }),
    apiCall('GET', '/admin/bots/logs', { 
      headers: adminHeaders.value,
      params: { public_key: logFilterKey.value || null, limit: 100 }
    }),
    apiCall('GET', '/admin/market/history', { 
        headers: adminHeaders.value,
        params: { limit: forms.market_history.limit }
    })
  ]);

  // 处理用户
  if (usersRes[1]) errorMessage.value = `加载用户列表失败: ${usersRes[1]}`
  else allUsers.value = usersRes[0].users

  // 处理余额
  if (balancesRes[1]) errorMessage.value = `加载余额列表失败: ${balancesRes[1]}`
  else allBalances.value = balancesRes[0].balances.sort((a, b) => a.username.localeCompare(b.username));

  // 处理NFT类型
  if (nftTypesRes[1]) errorMessage.value = `加载NFT类型失败: ${nftTypesRes[1]}`
  else {
    nftTypes.value = nftTypesRes[0]
    if (nftTypes.value.length > 0 && !forms.mintNft.nft_type) {
      forms.mintNft.nft_type = nftTypes.value[0] 
    }
  }

  // 处理机器人列表
  if (botListRes[1]) {
    errorMessage.value = (errorMessage.value || '') + `\n加载机器人列表失败: ${botListRes[1]}`
  } else {
    allBots.value = botListRes[0].bots.sort((a,b) => a.username.localeCompare(b.username));
  }
  
  // 处理机器人类型配置
  if (botTypesRes[1]) {
     errorMessage.value = (errorMessage.value || '') + `\n加载机器人类型失败: ${botTypesRes[1]}`
  } else {
    botTypeConfigs.value = botTypesRes[0].types 
    if (botTypes.value.length > 0 && !forms.bots.create.bot_type) {
      forms.bots.create.bot_type = botTypes.value[0];
    }
  }

  // 处理机器人日志
  if (botLogsRes[1]) {
    errorMessage.value = (errorMessage.value || '') + `\n加载机器人日志失败: ${botLogsRes[1]}`
  } else {
    botLogs.value = botLogsRes[0].logs
  }

  // Process Market History
  if (marketHistoryRes[1]) {
      errorMessage.value = (errorMessage.value || '') + `\n加载市场日志失败: ${marketHistoryRes[1]}`
  } else {
      marketTradeHistory.value = marketHistoryRes[0].history
  }
  
  // 获取设置 (包括机器人的)
  await fetchSettings(['default_invitation_quota', 'welcome_bonus_amount', 'inviter_bonus_amount', 'bot_system_enabled', 'bot_check_interval_seconds'])

  isLoading.value = false
}

async function fetchLogsOnly() {
  const [botLogsRes, error] = await apiCall('GET', '/admin/bots/logs', { 
    headers: adminHeaders.value,
    params: { public_key: logFilterKey.value || null, limit: 100 }
  });
  if (error) {
    errorMessage.value = `加载机器人日志失败: ${error}`;
  } else {
    botLogs.value = botLogsRes.logs;
    successMessage.value = "日志已刷新";
  }
}
async function fetchMarketHistoryOnly() {
  const [data, error] = await apiCall('GET', '/admin/market/history', { 
    headers: adminHeaders.value,
    params: { limit: forms.market_history.limit }
  });
  if (error) {
    errorMessage.value = `加载市场日志失败: ${error}`;
  } else {
    marketTradeHistory.value = data.history;
    successMessage.value = "市场日志已刷新";
  }
}

async function fetchSettings(keys) {
    for (const key of keys) {
        const [data, error] = await apiCall('GET', `/admin/setting/${key}`, { headers: adminHeaders.value });
        if (!error) {
            // 处理布尔值和数字
            if (key.includes('enabled')) {
              forms.settings[key] = data.value; // 存为 'True'/'False' 字符串
            } else {
              forms.settings[key] = Number(data.value);
            }
        }
    }
}

async function handleApiCall(apiPromise, successMsg, errorPrefix) {
  successMessage.value = null
  errorMessage.value = null
  const [data, error] = await apiPromise
  if (error) {
    errorMessage.value = `${errorPrefix}: ${error}`
    return false
  } else {
    successMessage.value = data.detail || successMsg
    return true
  }
}

// +++ BUG 修复 1：添加 handleSetSetting 函数 +++
async function handleSetSetting(key) {
  const value = forms.settings[key];
  if (value === undefined) {
    errorMessage.value = `内部错误：找不到设置 ${key}`;
    return;
  }

  // 后端需要字符串格式的值
  const payload = {
    key: key,
    value: String(value)
  };

  const success = await handleApiCall(
    apiCall('POST', '/admin/set_setting', { 
      payload, 
      headers: adminHeaders.value 
    }),
    `设置 '${key}' 已成功更新！`,
    `更新 '${key}' 失败`
  );
  
  if (success) {
    // 重新获取该设置以确认
    await fetchSettings([key]); 
  }
}

// +++ BUG 修复 2：添加 handleSaveBotGlobalSettings 函数 +++
async function handleSaveBotGlobalSettings() {
  successMessage.value = null;
  errorMessage.value = null;
  
  const key1 = 'bot_system_enabled';
  const key2 = 'bot_check_interval_seconds';
  
  const payload1 = { key: key1, value: String(forms.settings[key1]) };
  const payload2 = { key: key2, value: String(forms.settings[key2]) };

  // 并行发送两个更新请求
  const [res1, res2] = await Promise.all([
    apiCall('POST', '/admin/set_setting', { payload: payload1, headers: adminHeaders.value }),
    apiCall('POST', '/admin/set_setting', { payload: payload2, headers: adminHeaders.value })
  ]);

  let hasError = false;
  let errorMsg = '';
  
  if (res1[1]) { // res1[1] 是 error
    hasError = true;
    errorMsg += `更新 '${key1}' 失败: ${res1[1]} \n`;
  }
  if (res2[1]) { // res2[1] 是 error
    hasError = true;
    errorMsg += `更新 '${key2}' 失败: ${res2[1]} \n`;
  }

  if (hasError) {
    errorMessage.value = errorMsg;
  } else {
    successMessage.value = "机器人全局设置已保存！";
  }
}
// +++ BUG 修复结束 +++

//
// --- 🚩🚩🚩 开始：补全所有缺失的函数 🚩🚩🚩 ---
//

async function handleToggleUserStatus(user) {
  const newStatus = !user.is_active;
  const payload = {
    public_key: user.public_key,
    is_active: newStatus
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/set_user_active_status', { payload, headers: adminHeaders.value }),
    `用户 ${user.username} 状态已更新为 ${newStatus ? '活跃' : '禁用'}` ,
    '更新用户状态失败'
  );
  if (success) {
    await fetchData(); // 刷新所有数据
  }
}

async function handleSingleIssue() {
  const payload = { ...forms.issue };
  const success = await handleApiCall(
    apiCall('POST', '/admin/issue', { payload, headers: adminHeaders.value }),
    '增发成功！',
    '增发失败'
  );
  if (success) {
    forms.issue.to_key = '';
    forms.issue.amount = 1000;
    await fetchData(); // 刷新余额
  }
}

async function handleMultiIssue() {
  const targets = forms.multiIssue.user_keys.map(key => ({
    key: key,
    amount: forms.multiIssue.amount
  }));
  
  if (targets.length === 0) {
    errorMessage.value = "请至少选择一个用户。";
    return;
  }

  const payload = {
    targets: targets,
    note: forms.multiIssue.note
  };
  
  const success = await handleApiCall(
    apiCall('POST', '/admin/multi_issue', { payload, headers: adminHeaders.value }),
    '批量增发成功！',
    '批量增发失败'
  );
  if (success) {
    forms.multiIssue.user_keys = [];
    await fetchData(); // 刷新余额
  }
}

async function handleBurn() {
  // 确保选择了用户
  if (!forms.burn.from_key) {
      errorMessage.value = "请先在“精细管理”下拉菜单中选择一个用户。";
      return;
  }
  const payload = { ...forms.burn };
  const success = await handleApiCall(
    apiCall('POST', '/admin/burn', { payload, headers: adminHeaders.value }),
    '减持成功！',
    '减持失败'
  );
  if (success) {
    await fetchData(); // 刷新余额
  }
}

async function handleAdjustQuota() {
  // 确保选择了用户
  if (!forms.burn.from_key) {
      errorMessage.value = "请先在“精细管理”下拉菜单中选择一个用户。";
      return;
  }
  const payload = {
    public_key: forms.burn.from_key, // 使用所选用户
    new_quota: forms.adjustQuota.new_quota
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/adjust_quota', { payload, headers: adminHeaders.value }),
    '额度调整成功！',
    '额度调整失败'
  );
  if (success) {
    await fetchData(); // 刷新用户列表
  }
}

async function handleResetPassword() {
  // 确保选择了用户
  if (!forms.burn.from_key) {
      errorMessage.value = "请先在“精细管理”下拉菜单中选择一个用户。";
      return;
  }
  const payload = {
    public_key: forms.burn.from_key, // 使用所选用户
    new_password: forms.resetPassword.new_password
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/reset_password', { payload, headers: adminHeaders.value }),
    '密码重置成功！',
    '密码重置失败'
  );
  if (success) {
    forms.resetPassword.new_password = '';
  }
}

async function handlePurgeUser(publicKey, confirmUsername, actualUsername) {
  if (confirmUsername !== actualUsername) {
    errorMessage.value = "确认用户名输入不正确，操作已取消。";
    return;
  }
  if (!confirm(`【极度危险】你真的要清除用户 ${actualUsername} 吗？此操作不可逆！`)) {
    return;
  }

  const payload = { public_key: publicKey };
  const success = await handleApiCall(
    apiCall('POST', '/admin/purge_user', { payload, headers: adminHeaders.value }),
    '用户清除成功！',
    '用户清除失败'
  );
  if (success) {
    forms.burn.from_key = ''; // 清除所选用户
    forms.purgeUser.confirm_username = '';
    await fetchData(); // 刷新所有数据
  }
}

async function handleMintNft() {
  let jsonData;
  try {
    jsonData = JSON.parse(forms.mintNft.data);
  } catch (e) {
    errorMessage.value = `Data 字段中的 JSON 格式错误: ${e.message}`;
    return;
  }
  
  if (!forms.mintNft.to_key || !forms.mintNft.nft_type) {
      errorMessage.value = "请选择接收用户和 NFT 类型。";
      return;
  }

  const payload = {
    to_key: forms.mintNft.to_key,
    nft_type: forms.mintNft.nft_type,
    data: jsonData
  };
  
  const success = await handleApiCall(
    apiCall('POST', '/admin/nft/mint', { payload, headers: adminHeaders.value }),
    'NFT 铸造成功！',
    'NFT 铸造失败'
  );
  // (成功后不重置表单，方便管理员连续铸造)
}

async function handleNukeSystem() {
  if (forms.nuke.confirm_text !== 'NUKE ALL DATA') {
    errorMessage.value = "确认文本输入不正确，操作已取消。";
    return;
  }
  if (!confirm('【【【 终极危险 】】】你确定要删除所有数据并重置系统吗？！？！？')) {
    return;
  }

  const success = await handleApiCall(
    apiCall('POST', '/admin/nuke_system', { headers: adminHeaders.value }),
    '系统已重置！请重新加载页面以注册创世用户。',
    '系统重置失败'
  );
  if (success) {
    // 强制重新加载页面
    setTimeout(() => window.location.reload(), 2000);
  }
}

// --- 机器人相关函数 ---

async function handleCreateBot() {
  const { username, bot_type, initial_funds, action_probability } = forms.bots.create
  
  const payload = {
    username: username || null, 
    bot_type: bot_type,
    initial_funds: initial_funds,
    action_probability: action_probability
  }

  const success = await handleApiCall(
    apiCall('POST', '/admin/bots/create', { payload, headers: adminHeaders.value }),
    `机器人 ${username || bot_type} 创建成功！`,
    '创建机器人失败'
  )
  
  if (success) {
    forms.bots.create.username = ''
    await fetchData()
  }
}

function openBotManager(bot) {
  forms.bots.manage.public_key = bot.public_key;
  forms.bots.manage.new_probability = bot.action_probability;
  forms.bots.manage.issue_amount = 100;
  forms.bots.manage.burn_amount = 100;
  forms.bots.manage.confirm_purge = '';
  showBotManager.value = bot; // This shows the modal
}

function closeBotManager() {
  showBotManager.value = null;
}

async function handleToggleBotStatus(bot) {
  const newStatus = !bot.is_active;
  const payload = {
    public_key: bot.public_key,
    is_active: newStatus
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/set_user_active_status', { payload, headers: adminHeaders.value }),
    `机器人 ${bot.username} 状态已更新为 ${newStatus ? '活跃' : '禁用'}` ,
    '更新机器人状态失败'
  );
  if (success) {
    await fetchData();
  }
}

async function handleSetBotProbability() {
  const payload = {
    public_key: forms.bots.manage.public_key,
    action_probability: forms.bots.manage.new_probability
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/bots/set_config', { payload, headers: adminHeaders.value }),
    '机器人概率已更新！',
    '更新机器人概率失败'
  );
  if (success) {
    await fetchData();
    closeBotManager();
  }
}

async function handleIssueToBot() {
  const payload = {
    to_key: forms.bots.manage.public_key,
    amount: forms.bots.manage.issue_amount,
    note: "管理员为机器人增发"
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/issue', { payload, headers: adminHeaders.value }),
    '机器人增发成功！',
    '机器人增发失败'
  );
  if (success) {
    await fetchData();
    closeBotManager();
  }
}

async function handleBurnFromBot() {
  const payload = {
    from_key: forms.bots.manage.public_key,
    amount: forms.bots.manage.burn_amount,
    note: "管理员从机器人减持"
  };
  const success = await handleApiCall(
    apiCall('POST', '/admin/burn', { payload, headers: adminHeaders.value }),
    '机器人减持成功！',
    '机器人减持失败'
  );
  if (success) {
    await fetchData();
    closeBotManager();
  }
}

async function handlePurgeBot() {
  if (forms.bots.manage.confirm_purge !== showBotManager.value.username) {
    errorMessage.value = "确认用户名输入不正确，操作已取消。";
    return;
  }
  if (!confirm(`【危险】你真的要清除机器人 ${showBotManager.value.username} 吗？`)) {
    return;
  }
  
  const payload = { public_key: forms.bots.manage.public_key };
  const success = await handleApiCall(
    apiCall('POST', '/admin/purge_user', { payload, headers: adminHeaders.value }),
    '机器人清除成功！',
    '机器人清除失败'
  );
  if (success) {
    await fetchData();
    closeBotManager();
  }
}
//
// --- 🚩🚩🚩 结束：补全所有缺失的函数 🚩🚩🚩 ---
//


// +++ 核心修改 3：更新 onMounted 逻辑 +++
onMounted(() => {
  if (adminSecret.value) {
    // 如果 localStorage 中有密钥，自动加载数据
    fetchData()
  } else {
    // 如果没有，则停在输入密码的界面
    isLoading.value = false
  }
})
</script>

<template>
  <div class="admin-view">
    <header class="view-header">
      <h1>管理员面板</h1>
      <p class="subtitle">在这里管理 JCoin 系统的方方面面。</p>
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
        <button :class="{ active: activeTab === 'user_management' }" @click="activeTab = 'user_management'">用户管理</button>
        <button :class="{ active: activeTab === 'bot_management' }" @click="activeTab = 'bot_management'">机器人管理</button>
        <button :class="{ active: activeTab === 'market_history' }" @click="activeTab = 'market_history'">📈 市场日志</button>
        <button :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">系统设置</button>
      </div>

      <div v-if="activeTab === 'user_management'" class="tab-content">
        <h2>人类用户管理</h2>
        
        <h3 class="divider-header">用户列表</h3>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>UID</th>
                <th>余额 (JCoin)</th>
                <th>邀请人</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in allBalances" :key="user.public_key">
                <td>
                  <ClickableUsername :uid="user.uid" :username="user.username" />
                  </td>
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
        
        <h3 class="divider-header">货币管理 (人类)</h3>
        <div class="grid-2-col">
          <form @submit.prevent="handleSingleIssue" class="admin-form">
            <h4>增发货币 (单人)</h4>
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
              <h4>批量增发</h4>
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

        <h3 class="divider-header">精细管理 (人类)</h3>
        <div class="form-group">
          <label>选择要管理的用户</label>
          <select v-model="forms.burn.from_key">
              <option disabled value="">-- 选择用户 --</option>
              <option v-for="opt in userOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
          </select>
        </div>
        <div v-if="selectedUserForManagement" class="grid-2-col">
          <form @submit.prevent="handleBurn" class="admin-form">
              <h4>减持货币</h4>
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
              <h4>调整邀请额度</h4>
              <div class="form-group">
                  <label>新的邀请额度</label>
                  <input type="number" v-model.number="forms.adjustQuota.new_quota" min="0" />
              </div>
              <button type="submit">确认调整</button>
          </form>
          <form @submit.prevent="handleResetPassword" class="admin-form">
              <h4>重置密码</h4>
              <div class="form-group">
                  <label>新密码 (至少6位)</label>
                  <input type="password" v-model="forms.resetPassword.new_password" required minlength="6" />
              </div>
              <button type="submit">确认重置</button>
          </form>
          <form @submit.prevent="handlePurgeUser(selectedUserForManagement.public_key, forms.purgeUser.confirm_username, selectedUserForManagement.username)" class="admin-form danger-zone">
              <h4>彻底清除用户 (危险)</h4>
              <p>此操作不可逆，将删除用户所有数据！</p>
                <div class="form-group">
                  <label>输入用户名 `{{ selectedUserForManagement.username }}` 以确认</label>
                  <input type="text" v-model="forms.purgeUser.confirm_username" />
                </div>
              <button type="submit" class="danger-button">确认清除</button>
          </form>
        </div>
        
        <h3 class="divider-header">NFT 铸造 (人类)</h3>
        <form @submit.prevent="handleMintNft" class="admin-form">
          <div class="grid-2-col">
              <div class="form-group">
                  <label>接收用户</label>
                  <select v-model="forms.mintNft.to_key">
                      <option disabled value="">-- 选择人类用户 --</option>
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

      <div v-if="activeTab === 'bot_management'" class="tab-content">
        <h2>机器人系统管理</h2>
        
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
                <input id="bot_username" type="text" v-model="forms.bots.create.username" placeholder="例如: 行星收藏家 (留空可自动命名)" />
             </div>
             <div class="form-group">
                <label for="bot_type">机器人类型</label>
                <select id="bot_type" v-model="forms.bots.create.bot_type">
                  <option v-for="btype in botTypes" :key="btype" :value="btype">{{ getBotDisplayName(btype) }} ({{ btype }})</option>
                </select>
                </div>
             <div class="form-group">
                <label for="bot_funds">初始资金 (默认 {{ formatCurrency(botTypeConfigs[forms.bots.create.bot_type]?.initial_funds || 1000.0) }} JCoin)</label>
                <input id="bot_funds" type="number" v-model.number="forms.bots.create.initial_funds" min="0" />
             </div>
             <div class="form-group">
                <label for="bot_prob">行动概率 (默认 {{ botTypeConfigs[forms.bots.create.bot_type]?.action_probability || 0.1 }})</label>
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
                <th class="amount">余额 (JCoin)</th>
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
                <td>
                  <ClickableUsername :uid="bot.uid" :username="bot.username" />
                  </td>
                <td>{{ bot.uid }}</td>
                <td>{{ getBotDisplayName(bot.bot_type) }}</td>
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

        <h3 class="divider-header">机器人日志</h3>
        <p class="subtitle">查看机器人最近的操作。日志按时间倒序排列。</p>
        
        <div class="log-filter-bar">
          <div class="form-group">
            <label for="log_filter">按机器人筛选</label>
            <select id="log_filter" v-model="logFilterKey">
              <option value="">-- 显示所有机器人的日志 --</option>
              <option v-for="bot in allBots" :key="bot.public_key" :value="bot.public_key">
                {{ bot.username }} ({{ getBotDisplayName(bot.bot_type) }})
              </option>
            </select>
          </div>
          <button @click="fetchLogsOnly">刷新日志</button>
        </div>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>机器人</th>
                <th>动作类型</th>
                <th>日志消息</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="botLogs.length === 0">
                <td colspan="4" style="text-align: center; padding: 2rem;">没有找到日志记录。</td>
              </tr>
              <tr v-for="log in botLogs" :key="log.log_id">
                <td class="timestamp">{{ formatTimestamp(log.timestamp) }}</td>
                <td>
                   <ClickableUsername v-if="log.bot_uid" :uid="log.bot_uid" :username="log.bot_username" />
                   <span v-else>{{ log.bot_username }}</span>
                   </td>
                <td class="action-type">
                  <span :class="['action-tag', log.action_type.toLowerCase()]">
                    {{ log.action_type }}
                  </span>
                </td>
                <td class="log-message">{{ log.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3 class="divider-header">NFT 铸造 (机器人)</h3>
        <form @submit.prevent="handleMintNft" class="admin-form">
          <div class="grid-2-col">
              <div class="form-group">
                  <label>接收机器人</label>
                  <select v-model="forms.mintNft.to_key">
                      <option disabled value="">-- 选择机器人 --</option>
                      <option v-for="bot in allBots" :key="bot.public_key" :value="bot.public_key">{{ bot.username }}</option>
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
      <div v-if="activeTab === 'market_history'" class="tab-content">
    <h2>📈 市场成交日志</h2>
    <p class="subtitle">查看最近在市场上完成的交易（买卖、拍卖、求购）。</p>

    <div class="log-filter-bar">
        <div class="form-group">
        <label for="market_history_limit">显示最近</label>
        <select id="market_history_limit" v-model.number="forms.market_history.limit">
            <option value="50">50 条</option>
            <option value="100">100 条</option>
            <option value="250">250 条</option>
        </select>
        </div>
        <button @click="fetchMarketHistoryOnly">刷新日志</button>
    </div>

    <div class="table-wrapper">
        <table>
        <thead>
            <tr>
            <th>时间</th>
            <th>类型</th>
            <th>描述</th>
            <th>卖家</th>
            <th>买家</th>
            <th class="amount">成交价 (JCoin)</th>
            </tr>
        </thead>
        <tbody>
            <tr v-if="marketTradeHistory.length === 0">
            <td colspan="6" style="text-align: center; padding: 2rem;">没有找到市场成交记录。</td>
            </tr>
            <tr v-for="trade in marketTradeHistory" :key="trade.trade_id">
            <td class="timestamp">{{ formatTimestamp(trade.timestamp) }}</td>
            <td>
                <span :class="['action-tag', trade.trade_type.toLowerCase()]">
                {{ trade.trade_type }}
                </span>
            </td>
            <td class="log-message">{{ trade.listing_description || 'N/A' }}</td>
            <td>
                <span v-if="!trade.seller_uid">{{ trade.seller_username }}</span>
                <ClickableUsername v-else :uid="trade.seller_uid" :username="trade.seller_username" />
                </td>
            <td>
                <span v-if="!trade.buyer_uid">{{ trade.buyer_username }}</span>
                <ClickableUsername v-else :uid="trade.buyer_uid" :username="trade.buyer_username" />
                </td>
            <td class="amount">{{ formatCurrency(trade.price) }}</td>
            </tr>
        </tbody>
        </table>
    </div>
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
            <label>注册奖励金额 (JCoin)</label>
            <input type="number" v-model.number="forms.settings.welcome_bonus_amount" min="0" step="0.01"/>
          </div>
          <button type="submit">更新注册奖励</button>
        </form>
         <form @submit.prevent="handleSetSetting('inviter_bonus_amount')" class="admin-form">
          <h2>邀请人奖励</h2>
          <div class="form-group">
            <label>成功邀请奖励 (JCoin)</label>
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
/* (Styles are large and remain the same) */
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
.admin-form h3, .admin-form h4 { margin: 0 0 0.5rem 0; }
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
.log-filter-bar {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.log-filter-bar .form-group {
  flex-grow: 1;
  margin: 0;
}
.log-filter-bar button {
  height: 44px; 
  flex-shrink: 0;
}

td.timestamp {
  font-family: monospace;
  font-size: 0.85rem;
  color: #718096;
}
td.log-message {
  white-space: normal;
  word-break: break-word;
  min-width: 300px;
}
.action-type .action-tag {
  font-family: monospace;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  background-color: #e2e8f0;
  color: #4a5568;
}
.action-type .action-tag.error { background-color: #fed7d7; color: #c53030; }
.action-type .action-tag.evaluate_start { background-color: #f7fafc; border: 1px solid #e2e8f0; }
.action-type .action-tag.list_sale { background-color: #e6fffa; color: #234e52; }
.action-type .action-tag.list_auction { background-color: #fefcbf; color: #744210; }
.action-type .action-tag.market_buy { background-color: #c6f6d5; color: #2f855a; }
.action-type .action-tag.market_bid { background-color: #bee3f8; color: #2c5282; }
.action-type .action-tag.shop_explore { background-color: #faf5ff; color: #553c9a; }
.action-type .action-tag.nft_action_scan { background-color: #feebc8; color: #975a16; }

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
.action-type .action-tag.sale,
.action-tag.sale { background-color: #c6f6d5; color: #2f855a; }
.action-type .action-tag.auction,
.action-tag.auction { background-color: #feebc8; color: #975a16; }
.action-type .action-tag.seek,
.action-tag.seek { background-color: #bee3f8; color: #2c5282; }
</style>