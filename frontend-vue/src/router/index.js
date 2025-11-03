import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

import MainLayout from '@/layouts/MainLayout.vue'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import GenesisView from '@/views/GenesisView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },
    { path: '/genesis', name: 'genesis', component: GenesisView },
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'wallet',
          component: () => import('@/views/WalletView.vue'),
        },
        // --- 新增代码 ---
        {
          path: '/transfer',
          name: 'transfer',
          component: () => import('@/views/TransferView.vue'),
        },
        // --- 新增代码结束 ---
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // 守卫现在只处理与“登录状态”相关的逻辑
  const isLoggedIn = authStore.isLoggedIn

  // 1. 路由需要认证，但用户未登录
  if (to.meta.requiresAuth && !isLoggedIn) {
    return next({ name: 'login' })
  }

  // 2. 用户已登录，但想访问访客页面 (登录/注册/创世)
  if (isLoggedIn && ['login', 'register', 'genesis'].includes(to.name)) {
    return next({ name: 'wallet' })
  }

  // 其他所有情况都放行
  next()
})

export default router