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
        // +++ 新增管理员路由 +++
        {
          path: 'admin',
          name: 'admin',
          component: () => import('@/views/AdminView.vue'),
          meta: { requiresAdmin: true }, // 添加一个 meta 字段用于权限判断
        },
      ],
    },

    // --- 404 捕获路由 ---
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// --- 全局路由守卫 (修改) ---
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn

  if (to.meta.requiresAuth && !isLoggedIn) {
    return next({ name: 'login' })
  }

  // 如果已登录，但尝试访问公共页面（如登录页），则重定向到钱包页
  if (!to.meta.requiresAuth && isLoggedIn && to.name !== 'genesis') {
    return next({ name: 'wallet' })
  }
  
  // +++ 新增管理员权限检查 +++
  if (to.meta.requiresAdmin) {
    // 确保在检查 isAdmin 之前用户信息已加载
    if (!authStore.userInfo.uid) {
      // 这是一个边缘情况，如果直接访问/admin页面，可能需要等待用户信息加载
      // 但在我们的应用流中，用户总是先登录，所以通常不会发生
      await authStore.fetchUserDetails(); // 假设 authStore 有这个方法
    }
    
    // 创世用户的 UID 是 '000'
    if (authStore.userInfo.uid !== '000') {
      // 如果不是管理员，重定向到钱包首页
      return next({ name: 'wallet' });
    }
  }
  
  next()
})

export default router