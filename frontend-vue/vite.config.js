import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 【新增部分】
  server: {
    host: true, // 允许从容器外部访问
    port: 5173, // Vite 默认端口
    proxy: {
      // 将所有 /api 开头的请求代理到后端服务
      '/api': {
        target: 'http://backend:8000', // Docker Compose 中的后端服务名
        changeOrigin: true,
        // 重写路径，去掉 /api 前缀
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    }
  }
})