import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 导入视图组件
import MainLayout from '@/layouts/MainLayout.vue'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import GenesisView from '@/views/GenesisView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // --- 访客路由 ---
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },
    { path: '/genesis', name: 'genesis', component: GenesisView },

    // --- 需要认证的主应用布局 ---
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '', // 默认子路由
          name: 'wallet',
          component: () => import('@/views/WalletView.vue'),
        },
        {
          // 注意：子路由的 path 不应该以 '/' 开头
          path: 'transfer',
          name: 'transfer',
          component: () => import('@/views/TransferView.vue'),
        },
        {
          path: 'invitations',
          name: 'invitations',
          component: () => import('@/views/InvitationView.vue'),
        },
        // +++ 确保这里包含了商店和收藏的路由 +++
        {
          path: 'shop',
          name: 'shop',
          component: () => import('@/views/ShopView.vue'),
        },
        {
          path: 'collection',
          name: 'collection',
          component: () => import('@/views/MyCollectionView.vue'),
        },
      ],
    },

    // --- 404 捕获路由 ---
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// --- 全局路由守卫 (保持不变) ---
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn

  if (to.meta.requiresAuth && !isLoggedIn) {
    return next({ name: 'login' })
  }

  if (!to.meta.requiresAuth && isLoggedIn && to.name !== 'genesis') {
    return next({ name: 'wallet' })
  }
  
  next()
})

export default router