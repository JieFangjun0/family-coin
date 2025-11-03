
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
          path: 'transfer', // 注意这里我移除了开头的 '/'
          name: 'transfer',
          component: () => import('@/views/TransferView.vue'),
        },
        {
          path: 'invitations', // 注意这里我移除了开头的 '/'
          name: 'invitations',
          component: () => import('@/views/InvitationView.vue'),
        },
        // --- 在这里添加缺失的路由 ---
        {
          path: 'shop', // 定义 URL 路径 (作为 /shop)
          name: 'shop',  // 路由名称，与 TheSidebar.vue 中对应
          component: () => import('@/views/ShopView.vue'), // 指向你的 ShopView 组件
        },
        {
          path: 'collection', // 定义 URL 路径 (作为 /collection)
          name: 'collection', // 路由名称，与 TheSidebar.vue 中对应
          component: () => import('@/views/MyCollectionView.vue'), // 指向你的 MyCollectionView 组件
        },
        // -------------------------
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

  // 场景1: 目标路由需要认证，但用户未登录 -> 跳转到登录页
  if (to.meta.requiresAuth && !isLoggedIn) {
    return next({ name: 'login' })
  }

  // 场景2: 用户已登录，但想访问访客页面 (如登录页) -> 跳转到钱包主页
  if (!to.meta.requiresAuth && isLoggedIn && to.name !== 'genesis') { // 允许已登录用户访问 genesis (虽然一般不会)
    return next({ name: 'wallet' })
  }
  
  // 其他所有情况 -> 放行
  next()
})

export default router