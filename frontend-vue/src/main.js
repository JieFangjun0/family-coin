import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// 1. 启用 Pinia 状态管理
app.use(createPinia())
// 2. 启用 Vue Router
app.use(router)

// 3. 挂载应用
app.mount('#app')