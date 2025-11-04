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
  server: {
    host: true, 
    port: 5173,
    
    // +++ 关键修改：添加这里 +++
    // 允许来自 Nginx 反向代理的域名访问
    allowedHosts: [
      'jiefangjun.xyz',
      'www.jiefangjun.xyz',
    ],
    // +++ 修改结束 +++

    proxy: {
      // 代理配置保持不变，这部分是正确的
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    }
  }
})