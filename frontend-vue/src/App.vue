<script setup>
import { ref } from 'vue';
import axios from 'axios';

// 使用 ref 创建响应式变量，就像 Streamlit 的 session_state
const usernameOrUid = ref('');
const password = ref('');
const errorMessage = ref(null);
const successMessage = ref(null);
const isLoading = ref(false);

// 登录函数
async function handleLogin() {
  if (!usernameOrUid.value || !password.value) {
    errorMessage.value = '用户名/UID和密码不能为空。';
    return;
  }

  isLoading.value = true;
  errorMessage.value = null;
  successMessage.value = null;

  try {
    // 【关键】API 请求。注意，这里我们用了相对路径 '/api'。
    // 我们需要在 Vite 配置中设置一个代理来指向后端。
    const response = await axios.post('/api/login', {
      username_or_uid: usernameOrUid.value,
      password: password.value,
    });

    // 登录成功
    successMessage.value = response.data.message;
    console.log('用户信息:', response.data);
    // 在这里，你可以将 token 或私钥存入 Pinia store 或 localStorage

  } catch (error) {
    if (error.response) {
      errorMessage.value = `登录失败: ${error.response.data.detail}`;
    } else {
      errorMessage.value = '无法连接到服务器。';
    }
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <main class="login-container">
    <h1>欢迎回来！</h1>
    <form @submit.prevent="handleLogin" class="login-form">
      <div class="form-group">
        <label for="username">用户名或UID</label>
        <input id="username" type="text" v-model="usernameOrUid" required />
      </div>
      <div class="form-group">
        <label for="password">密码</label>
        <input id="password" type="password" v-model="password" required />
      </div>
      <button type="submit" :disabled="isLoading">
        {{ isLoading ? '登录中...' : '登录' }}
      </button>
    </form>
    <div v-if="errorMessage" class="message error">{{ errorMessage }}</div>
    <div v-if="successMessage" class="message success">{{ successMessage }}</div>
  </main>
</template>

<style scoped>
.login-container {
  max-width: 400px;
  margin: 50px auto;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.form-group {
  display: flex;
  flex-direction: column;
}
label {
  margin-bottom: 0.5rem;
}
input {
  padding: 0.75rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
button {
  padding: 0.75rem;
  background-color: #42b883;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}
button:disabled {
  background-color: #ccc;
}
.message {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 4px;
  text-align: center;
}
.error {
  color: #d8000c;
  background-color: #ffbaba;
}
.success {
  color: #270;
  background-color: #dff2bf;
}
</style>