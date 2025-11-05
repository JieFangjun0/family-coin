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

// +++ 核心修改 1: 为同意声明添加新的响应式状态 +++
const agreedToTerms = ref(false);

// --- Methods ---
async function handleRegister() {
  // +++ 核心修改 2: 在提交时再次校验 (虽然按钮已禁用, 但作为安全防线) +++
  if (!agreedToTerms.value) {
    errorMessage.value = '您必须阅读并同意网站性质声明才能注册。';
    return;
  }
  // +++ 修改结束 +++

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

        <div class="disclaimer-box">
          <h4 class="disclaimer-title">【网站性质声明】</h4>
          <p class="disclaimer-subtitle">本网站为个人技术实验性项目，非商业性网络游戏</p>
          <div class="disclaimer-content">
            <p><strong>1. 性质界定：</strong> 本网站 (JCoin) 是站长个人用于学习和实践的实验性项目，其核心目的是技术研究（如后端架构、虚拟经济算法模拟），而非提供娱乐性网络游戏服务。</p>
            <p><strong>2. 非商业性：</strong> 本项目不涉及任何形式的商业运营。**无任何充值入口、广告投放、虚拟资产变现或现实交易功能。** 网站运营费用均由个人承担，无任何营收。</p>
            <p><strong>3. 用户范围：</strong> 当前开放注册仅限于受邀请的、对模拟系统和技术实验感兴趣的极小范围用户（好友）进行体验与测试，并非面向不特定公众的开放性服务。</p>
            <p><strong>4. 不稳定性与免责：</strong> 本项目处于极不稳定的实验阶段，**可能随时暂停、重置数据（包括“JCoin”和“NFT”）或终止服务**，且不承担任何由此产生的责任。</p>
            <p><strong>5. 与网络游戏的区别：</strong> 本项目缺乏网络游戏必备的娱乐性目标、平衡性设计和长期运营规划。所有“NFT”和“JCoin”均为无价值的虚拟道具，仅用于算法测试。本项目本质是一个“活的”代码实验环境。</p>
          </div>
          <div class="terms-check">
            <input type="checkbox" v-model="agreedToTerms" id="terms" />
            <label for="terms">我已阅读并同意上述声明，理解本网站为个人实验项目而非游戏。</label>
          </div>
        </div>
        <button type="submit" :disabled="isLoading || !agreedToTerms">
          {{ isLoading ? '注册中...' : '同意声明并注册' }}
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

/* +++ 核心修改 4: 添加新样式 +++ */
.disclaimer-box {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background-color: #f7fafc;
  padding: 1rem;
  margin-top: 1rem;
}
.disclaimer-title {
  text-align: center;
  margin: 0;
  font-size: 1.1rem;
  color: #2d3748;
}
.disclaimer-subtitle {
  text-align: center;
  margin: 0.25rem 0 1rem 0;
  font-weight: bold;
  color: #c53030;
  font-size: 0.9rem;
}
.disclaimer-content {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 0.5rem 1rem;
  font-size: 0.8rem;
  color: #4a5568;
}
.disclaimer-content p {
  margin: 0.5rem 0;
}
.terms-check {
  display: flex;
  align-items: flex-start;
  margin-top: 1rem;
  padding: 0.5rem;
}
.terms-check input[type="checkbox"] {
  width: auto;
  height: 1.2em;
  width: 1.2em;
  margin-right: 0.75rem;
  flex-shrink: 0;
  margin-top: 0.15rem; /* 微调对齐 */
}
.terms-check label {
  font-size: 0.9rem;
  font-weight: 500;
  color: #2d3748;
  cursor: pointer;
  line-height: 1.4;
}
/* +++ 样式结束 +++ */

</style>