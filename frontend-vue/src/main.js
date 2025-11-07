import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useEconomicsStore } from '@/stores/economics'
const app = createApp(App)

// 1. 启用 Pinia 状态管理
app.use(createPinia())

const economicsStore = useEconomicsStore()
// 立即触发 API 请求，无需等待组件挂载
economicsStore.fetchEconomics()

// 2. 启用 Vue Router
app.use(router)

// 3. 挂载应用
app.mount('#app')