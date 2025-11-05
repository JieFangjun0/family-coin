<script setup>
import { useAuthStore } from '@/stores/auth';
// 从新的 client.js 导入
import { setLogoutHandler } from '@/api/client';

// 获取 auth store 实例
const authStore = useAuthStore();

// 将 auth store 的 logout 方法设置为 API 模块的全局登出处理器。
// 这是一个健壮的设计，确保任何导致认证失败的 API 请求都会自动触发登出。
setLogoutHandler(authStore.logout);
</script>

<template>
  <router-view />

  <footer class="site-footer">
    <div class="footer-content">
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
        浙ICP备2025207932号-1
      </a>
      <a href="http://www.beian.gov.cn/portal/registerSystemInfo?recordcode=33019202002747" target="_blank" rel="noopener noreferrer" class="police-link">
        <img src="/gongan.png" alt="公网安备" />
        浙公网安备33019202002747号
      </a>
    </div>
  </footer>
  </template>

<style>
/* 全局样式保持不变 */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  background-color: #f0f2f5;

  /* +++ 为 footer 腾出空间 +++ */
  padding-bottom: 60px; /* 页脚高度的两倍，防止内容遮挡 */
}

/* +++ 添加页脚样式 +++ */
.site-footer {
  position: fixed; /* 固定在底部 */
  bottom: 0;
  left: 0;
  width: 100%;
  background-color: #f0f2f5; /* 与 body 背景色一致 */
  padding: 1rem 0;
  border-top: 1px solid #e2e8f0;
  z-index: 1000;
  height: 40px; /* 固定高度 */
  box-sizing: border-box;
}

.footer-content {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px; /* 两个链接之间的间距 */
  font-size: 0.85rem;
  color: #718096;
}

.footer-content a {
  color: #718096;
  text-decoration: none;
  display: flex;
  align-items: center;
}

.footer-content a:hover {
  color: #42b883;
}

.police-link img {
  width: 16px;
  height: 16px;
  margin-right: 5px;
}
</style>