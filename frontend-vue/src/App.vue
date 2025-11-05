<script setup>
import { useAuthStore } from '@/stores/auth';
import { setLogoutHandler } from '@/api/client';

const authStore = useAuthStore();
setLogoutHandler(authStore.logout);
</script>

<template>
  <div class="app-wrapper">
    
    <div class="content-wrapper">
      <router-view />
    </div>

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
  </div>
</template>

<style>
/* +++ 全局和粘性页脚样式 +++ */

/* 1. 确保 html, body 和根元素占满高度 */
html, body, #app {
  height: 100%;
  margin: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  background-color: #f0f2f5;
}

/* 2. app-wrapper 负责粘性页脚布局 */
.app-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100%; /* 关键：占满视窗高度 */
}

/* 3. content-wrapper 负责推开页脚 */
.content-wrapper {
  flex-grow: 1; /* 关键：让内容区“推开”页脚 */
  display: flex; 
  flex-direction: column;
}

/* 4. 页脚样式 (非 fixed) */
.site-footer {
  flex-shrink: 0; /* 确保页脚不会缩小 */
  width: 100%;
  background-color: #f0f2f5;
  padding: 0.75rem 0; 
  border-top: 1px solid #e2e8f0;
  box-sizing: border-box;
}

.footer-content {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap; 
  gap: 10px 20px; 
  font-size: 0.85rem;
  color: #718096;
  padding: 0 1rem; 
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

/* * (重要)
 * 移除了之前在这里的 .app-layout 全局样式。
 * .app-layout 的样式完全交给 MainLayout.vue 自己去(scoped)定义。
 */
</style>