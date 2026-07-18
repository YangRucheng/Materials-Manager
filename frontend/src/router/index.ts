import { createRouter, createWebHistory } from 'vue-router'
import type { Permission } from '@/types/navigation'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    permission?: Permission
    public?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/dashboard/DashboardView.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'warehouse/materials',
          name: 'stock-materials',
          component: () => import('@/views/warehouse/StockMaterialsView.vue'),
          meta: { title: '二级库物资' },
        },
        {
          path: 'warehouse/materials/:id',
          name: 'stock-material-detail',
          component: () => import('@/views/warehouse/StockMaterialDetailView.vue'),
          meta: { title: '二级库物资详情' },
        },
        {
          path: 'warehouse/inbound',
          name: 'inbound',
          component: () => import('@/views/warehouse/OperationEditorView.vue'),
          props: { operationType: 'INBOUND' },
          meta: { title: '入库', permission: 'warehouse:write' },
        },
        {
          path: 'warehouse/outbound',
          name: 'outbound',
          component: () => import('@/views/warehouse/OperationEditorView.vue'),
          props: { operationType: 'OUTBOUND' },
          meta: { title: '出库', permission: 'warehouse:write' },
        },
        {
          path: 'warehouse/stock',
          name: 'stock',
          component: () => import('@/views/warehouse/StockView.vue'),
          meta: { title: '库存查询' },
        },
        {
          path: 'warehouse/operations',
          name: 'operations',
          component: () => import('@/views/warehouse/OperationsView.vue'),
          meta: { title: '操作记录' },
        },
        {
          path: 'warehouse/operations/:id',
          name: 'operation-detail',
          component: () => import('@/views/warehouse/OperationDetailView.vue'),
          meta: { title: '流水详情' },
        },
        {
          path: 'procurement/materials',
          name: 'purchase-materials',
          component: () => import('@/views/procurement/PurchaseMaterialsView.vue'),
          meta: { title: '申购计划' },
        },
        {
          path: 'procurement/materials/:id',
          name: 'purchase-material-detail',
          component: () => import('@/views/procurement/PurchaseMaterialDetailView.vue'),
          meta: { title: '申购计划详情' },
        },
        {
          path: 'procurement/uncoded-materials',
          name: 'uncoded-materials',
          component: () => import('@/views/procurement/UncodedMaterialsView.vue'),
          meta: { title: '未编码物资' },
        },
        {
          path: 'procurement/records',
          name: 'purchase-records',
          component: () => import('@/views/procurement/PurchaseRequestsView.vue'),
          meta: { title: '申购记录' },
        },
        {
          path: 'procurement/records/:id',
          name: 'purchase-record-detail',
          component: () => import('@/views/procurement/PurchaseRequestDetailView.vue'),
          meta: { title: '申购记录详情' },
        },
        {
          path: 'settings/units',
          name: 'units',
          component: () => import('@/views/settings/UnitsView.vue'),
          meta: { title: '计量单位', permission: 'settings:write' },
        },
        {
          path: 'settings/users',
          name: 'users',
          component: () => import('@/views/settings/UsersView.vue'),
          meta: { title: '用户管理', permission: 'settings:write' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true, title: '页面不存在' },
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  document.title = `${to.meta.title || '系统'} - 电气车间备件管理系统`
  if (!to.meta.public && !auth.isAuthenticated)
    return { name: 'login', query: { redirect: to.fullPath } }
  if (to.name === 'login' && auth.isAuthenticated) return { name: 'dashboard' }
  if (to.meta.permission && !auth.can(to.meta.permission)) return { name: 'dashboard' }
})

export default router
