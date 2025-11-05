<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { apiCall } from '@/api';

const router = useRouter();

// --- Component State ---
const step = ref('form'); // 'form' or 'backup'
const genesisInfo = ref(null);
const isLoading = ref(false);
const errorMessage = ref('');

// --- Form State ---
const form = ref({
  username: 'admin',
  password: '',
  genesis_password: '',
});

// --- Methods ---
async function handleGenesisRegister() {
  if (!form.value.username || !form.value.password || !form.value.genesis_password) {
    errorMessage.value = '所有字段均为必填项。';
    return;
  }
  if (form.value.password.length < 6) {
    errorMessage.value = '登录密码至少需要6个字符。';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  const [data, error] = await apiCall('POST', '/genesis_register', { payload: form.value });

  isLoading.value = false;
  if (error) {
    errorMessage.value = `创世用户创建失败: ${error}`;
  } else {
    genesisInfo.value = data;
    step.value = 'backup';
  }
}

function completeSetup() {
  // 创世页面完成任务后，只需跳转到登录页即可。
  // 下次用户访问时，LoginView 会重新检查 /status 并发现系统已设置。
  router.push({ name: 'login' });
}
</script>

<template>
  <main class="setup-container">
    <div v-if="step === 'form'" class="form-wrapper">
      <h1>JCoin - 首次系统设置</h1>
      <p class="subtitle">创建第一个管理员（创世）用户。</p>
      <form @submit.prevent="handleGenesisRegister" class="setup-form">
        <div class="form-group">
          <label for="username">创世用户名</label>
          <input id="username" type="text" v-model="form.username" required />
        </div>
        <div class="form-group">
          <label for="password">登录密码 (至少6位)</label>
          <input id="password" type="password" v-model="form.password" required />
        </div>
        <div class="form-group">
          <label for="genesis_password">创世密钥</label>
          <input id="genesis_password" type="password" v-model="form.genesis_password" required placeholder="在 docker-compose.yml 中预设" />
        </div>
        <button type="submit" :disabled="isLoading">
          {{ isLoading ? '创建中...' : '创建并初始化系统' }}
        </button>
      </form>
      <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>
    </div>

    <div v-if="step === 'backup' && genesisInfo" class="backup-wrapper">
      <h1>🎉 创建成功！</h1>
      <p class="subtitle">创世管理员 '{{ genesisInfo.username }}' (UID: {{ genesisInfo.uid }}) 已创建。</p>
      
      <div class="message critical">
        <strong>⚠️ 关键步骤：备份管理员私钥</strong>
        <p>这是你唯一一次看到它，请务必将其复制并保存在安全的地方！普通用户无需此操作。</p>
      </div>

      <div class="key-group">
        <label>管理员公钥</label>
        <textarea :value="genesisInfo.public_key" readonly></textarea>
      </div>
      <div class="key-group">
        <label>‼️ 管理员私钥 (最高权限) ‼️</label>
        <textarea :value="genesisInfo.private_key" readonly rows="8"></textarea>
      </div>
      
      <button @click="completeSetup" class="primary-button">我已安全备份，进入登录页</button>
    </div>
  </main>
</template>

<style scoped>
/* Scoped styles adapted for this component */
.setup-container {
  max-width: 500px;
  margin: 10vh auto;
  padding: 2rem 2.5rem;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  background-color: #fff;
}
.subtitle { text-align: center; color: #666; margin-bottom: 2rem; }
.setup-form { display: flex; flex-direction: column; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; }
label { margin-bottom: 0.5rem; font-weight: 500; }
input, textarea { padding: 0.85rem; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; font-family: inherit; width: 100%; box-sizing: border-box; }
textarea { resize: vertical; }
button { padding: 0.85rem; background-color: #42b883; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 1rem; transition: background-color 0.2s; }
button:hover { background-color: #369b6e; }
button:disabled { background-color: #ccc; cursor: not-allowed; }
.primary-button { width: 100%; margin-top: 1.5rem; }
.message { margin-top: 1.5rem; padding: 1rem; border-radius: 4px; text-align: center; }
.error { color: #d8000c; background-color: #ffbaba; }
.critical { color: #9f6000; background-color: #feefb3; border: 1px solid #9f6000; }
.critical p { margin: 0.5rem 0 0 0; }
.backup-wrapper { display: flex; flex-direction: column; gap: 1rem; }
.key-group { display: flex; flex-direction: column; }
.key-group label { font-weight: bold; margin-bottom: 0.5rem; }
</style>