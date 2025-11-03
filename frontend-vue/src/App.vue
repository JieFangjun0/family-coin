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
}
</style>