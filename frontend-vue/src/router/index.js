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
        {
          path: '/transfer',
          name: 'transfer',
          component: () => import('@/views/TransferView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to, from, next) => {
  // 在路由守卫中，Pinia store 已经可以安全使用
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn

  // 场景1: 目标路由需要认证，但用户未登录 -> 跳转到登录页
  if (to.meta.requiresAuth && !isLoggedIn) {
    // 保存用户想去的页面，登录后可以重定向回去（可选的优化）
    // to.fullPath
    return next({ name: 'login' })
  }

  // 场景2: 用户已登录，但想访问访客页面 (如登录页) -> 跳转到钱包主页
  if (!to.meta.requiresAuth && isLoggedIn) {
    return next({ name: 'wallet' })
  }
  
  // 其他所有情况 (已登录访问需认证页，未登录访问访客页) -> 放行
  next()
})

export default router