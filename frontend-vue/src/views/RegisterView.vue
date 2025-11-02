<script setup>
import { ref } from 'vue';
import { RouterLink } from 'vue-router';
import { apiCall } from '@/api';

// --- Component State ---
const step = ref('form'); // 'form' or 'success'
const newUserInfo = ref(null);
const isLoading = ref(false);
const errorMessage = ref('');

// --- Form State ---
const form = ref({
  username: '',
  password: '',
  confirm_password: '',
  invitation_code: '',
});

// --- Methods ---
async function handleRegister() {
  if (!form.value.username || !form.value.password || !form.value.confirm_password || !form.value.invitation_code) {
    errorMessage.value = '所有字段均为必填项。';
    return;
  }
  if (form.value.username.length < 3) {
    errorMessage.value = '用户名至少需要3个字符。';
    return;
  }
  if (form.value.password.length < 6) {
    errorMessage.value = '密码至少需要6个字符。';
    return;
  }
  if (form.value.password !== form.value.confirm_password) {
    errorMessage.value = '两次输入的密码不一致。';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  const [data, error] = await apiCall('POST', '/register', { 
    payload: {
      username: form.value.username,
      password: form.value.password,
      invitation_code: form.value.invitation_code
    } 
  });

  isLoading.value = false;
  if (error) {
    errorMessage.value = `注册失败: ${error}`;
  } else {
    newUserInfo.value = data;
    step.value = 'success';
  }
}
</script>

<template>
  <main class="setup-container">
    <div v-if="step === 'form'">
      <h1>创建新账户</h1>
      <p class="subtitle">需要有效的邀请码才能注册。</p>
      <form @submit.prevent="handleRegister" class="setup-form">
        <div class="form-group">
          <label for="username">用户名 (3-15个字符)</label>
          <input id="username" type="text" v-model="form.username" required maxlength="15" />
        </div>
        <div class="form-group">
          <label for="password">密码 (至少6位)</label>
          <input id="password" type="password" v-model="form.password" required />
        </div>
        <div class="form-group">
          <label for="confirm_password">确认密码</label>
          <input id="confirm_password" type="password" v-model="form.confirm_password" required />
        </div>
        <div class="form-group">
          <label for="invitation_code">邀请码</label>
          <input id="invitation_code" type="text" v-model="form.invitation_code" required />
        </div>
        <button type="submit" :disabled="isLoading">
          {{ isLoading ? '注册中...' : '注册' }}
        </button>
      </form>
      <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>
      <p class="footer-link">已有账户？ <RouterLink :to="{ name: 'login' }">返回登录</RouterLink></p>
    </div>

    <div v-if="step === 'success' && newUserInfo" class="success-wrapper">
      <h1>🎉 注册成功！</h1>
      <p class="subtitle">欢迎加入, {{ newUserInfo.username }}!</p>
      <div class="message success">
        <p>你的账户 (UID: {{ newUserInfo.uid }}) 已成功创建。</p>
      </div>
      <RouterLink :to="{ name: 'login' }" class="primary-button">前往登录页面</RouterLink>
    </div>
  </main>
</template>

<style scoped>
/* Using styles from GenesisView for consistency */
.setup-container { max-width: 420px; margin: 10vh auto; padding: 2rem 2.5rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); background-color: #fff; }
.subtitle { text-align: center; color: #666; margin-bottom: 2rem; }
.setup-form { display: flex; flex-direction: column; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; }
label { margin-bottom: 0.5rem; font-weight: 500; }
input { padding: 0.85rem; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; }
button { padding: 0.85rem; background-color: #42b883; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 1rem; transition: background-color 0.2s; }
button:hover { background-color: #369b6e; }
button:disabled { background-color: #ccc; cursor: not-allowed; }
.primary-button { display: block; text-align: center; margin-top: 1.5rem; padding: 0.85rem; background-color: #42b883; color: white; border-radius: 4px; text-decoration: none; font-weight: bold; }
.message { margin-top: 1.5rem; padding: 1rem; border-radius: 4px; text-align: center; }
.error { color: #d8000c; background-color: #ffbaba; }
.success { color: #270; background-color: #dff2bf; }
.footer-link { text-align: center; margin-top: 1.5rem; font-size: 0.9rem; color: #666; }
.success-wrapper { display: flex; flex-direction: column; gap: 1rem; }
</style>