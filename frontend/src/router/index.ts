import { createRouter, createWebHistory } from 'vue-router'
import type { Permission } from '@/types/navigation'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    permission?: Permission
    public?: boolean
    keepAlive?: boolean
  }
}

/** 完整模式二级库的路由：精简模式下统一重定向到精简视图 */
const FULL_WAREHOUSE_ROUTES = new Set([
  'stock-materials',
  'stock-material-detail',
  'inbound',
  'outbound',
  'stock',
  'operations',
  'operation-detail',
])

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
          path: 'warehouse/hua-xing-stock',
          name: 'hua-xing-stock',
          component: () => import('@/views/warehouse/HuaXingStockView.vue'),
          meta: { title: '华星总库存' },
        },
        {
          path: 'warehouse/lite',
          name: 'warehouse-lite',
          component: () => import('@/views/warehouse/SecondaryWarehouseLiteView.vue'),
          meta: { title: '二级库' },
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
          meta: { title: '申购计划', keepAlive: true },
        },
        {
          path: 'procurement/materials/:id',
          name: 'purchase-material-detail',
          component: () => import('@/views/procurement/PurchaseMaterialDetailView.vue'),
          meta: { title: '申购计划详情' },
        },
        {
          path: 'procurement/purchase-plan-templates',
          name: 'purchase-plan-templates',
          component: () => import('@/views/procurement/PurchasePlanTemplatesView.vue'),
          meta: { title: '周期性计划', keepAlive: true },
        },
        {
          path: 'procurement/uncoded-materials',
          name: 'uncoded-materials',
          component: () => import('@/views/procurement/UncodedMaterialsView.vue'),
          meta: { title: '未编码物资' },
        },
        {
          path: 'procurement/material-code-library',
          name: 'material-code-library',
          component: () => import('@/views/procurement/MaterialCodeLibraryView.vue'),
          meta: { title: '物料编码库' },
        },
        {
          path: 'procurement/records',
          name: 'purchase-records',
          component: () => import('@/views/procurement/PurchaseRequestsView.vue'),
          meta: { title: '申购记录', keepAlive: true },
        },
        {
          path: 'procurement/records/:id',
          name: 'purchase-record-detail',
          component: () => import('@/views/procurement/PurchaseRequestDetailView.vue'),
          meta: { title: '申购记录详情' },
        },
        {
          path: 'settings/advanced',
          name: 'advanced-settings',
          component: () => import('@/views/settings/AdvancedSettingsView.vue'),
          meta: { title: '高级设置', permission: 'settings:write' },
        },
        {
          path: 'settings/ai-search',
          redirect: { name: 'advanced-settings' },
        },
        {
          path: 'settings/users',
          name: 'users',
          component: () => import('@/views/settings/UsersView.vue'),
          meta: { title: '管理端用户', permission: 'settings:write' },
        },
        {
          path: 'settings/mini-program-users',
          name: 'mini-program-users',
          component: () => import('@/views/settings/MiniProgramUsersView.vue'),
          meta: { title: '小程序用户', permission: 'settings:write' },
        },
        {
          path: 'settings/about',
          name: 'about',
          component: () => import('@/views/settings/AboutView.vue'),
          meta: { title: '关于', permission: 'settings:write' },
        },
        {
          path: 'settings/share-links',
          name: 'share-links',
          component: () => import('@/views/settings/ShareLinksView.vue'),
          meta: { title: '分享链接', permission: 'settings:write' },
        },
      ],
    },
    {
      path: '/share/:token',
      name: 'share',
      component: () => import('@/views/public/ShareView.vue'),
      meta: { public: true, title: '分享预览' },
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
  // 二级库精简模式下，完整模式仓库路由不可访问，统一重定向到精简视图。
  if (useSettingsStore().isLiteMode && to.name && FULL_WAREHOUSE_ROUTES.has(String(to.name))) {
    return { name: 'warehouse-lite' }
  }
})

export default router
