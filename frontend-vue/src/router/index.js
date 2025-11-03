import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
          path: '',
          name: 'wallet',
          component: () => import('@/views/WalletView.vue'),
        },
        {
          path: 'transfer',
          name: 'transfer',
          component: () => import('@/views/TransferView.vue'),
        },
        {
          path: 'invitations',
          name: 'invitations',
          component: () => import('@/views/InvitationView.vue'),
        },
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
        {
          // 核心修正：路径中添加了 :uid 参数
          path: 'community/:uid?',
          name: 'community',
          component: () => import('@/views/CommunityView.vue'),
        },
        {
          path: 'friends',
          name: 'friends',
          component: () => import('@/views/FriendsView.vue'),
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
        },
        {
          path: 'admin',
          name: 'admin',
          component: () => import('@/views/AdminView.vue'),
          meta: { requiresAdmin: true },
        },
      ],
    },

    // --- 404 捕获路由 ---
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// --- 全局路由守卫 ---
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn

  if (to.meta.requiresAuth && !isLoggedIn) {
    return next({ name: 'login' })
  }

  if (!to.meta.requiresAuth && isLoggedIn && to.name !== 'genesis') {
    return next({ name: 'wallet' })
  }
  
  if (to.meta.requiresAdmin) {
    // 创世用户的 UID 是 '000'
    if (authStore.userInfo.uid !== '000') {
      return next({ name: 'wallet' });
    }
  }
  
  next()
})

export default router