<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import type { MenuOption } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { roleLabels } from '@/types/navigation'
import { LOGO_URL } from '@/constants/branding'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)
const link = (label: string, name: string) => ({
  label: () => h(RouterLink, { to: { name } }, { default: () => label }),
  key: name,
})

const menuOptions = computed<MenuOption[]>(() => {
  const items: MenuOption[] = [link('工作台', 'dashboard')]
  items.push({
    label: '二级库',
    key: 'warehouse-group',
    children: [
      link('物资档案', 'stock-materials'),
      link('库存查询', 'stock'),
      link('操作记录', 'operations'),
      ...(auth.can('warehouse:write') ? [link('入库', 'inbound'), link('出库', 'outbound')] : []),
    ],
  })
  items.push({
    label: '申购管理',
    key: 'procurement-group',
    children: [
      link('申购计划', 'purchase-materials'),
      link('未编码物资', 'uncoded-materials'),
      link('申购记录', 'purchase-records'),
    ],
  })
  if (auth.can('settings:write'))
    items.push({
      label: '系统设置',
      key: 'settings-group',
      children: [link('计量单位', 'units'), link('用户管理', 'users')],
    })
  return items
})

function logout() {
  auth.logout()
  void router.push({ name: 'login' })
}
</script>

<template>
  <n-layout has-sider class="app-shell">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :collapsed="collapsed"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="brand" :class="{ compact: collapsed }">
        <img class="brand-mark" :src="LOGO_URL" alt="系统 Logo" />
        <span v-if="!collapsed">电气车间备件</span>
      </div>
      <n-menu
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="22"
        :options="menuOptions"
        :value="String(route.name || '')"
      />
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="topbar">
        <n-breadcrumb>
          <n-breadcrumb-item>备件管理</n-breadcrumb-item>
          <n-breadcrumb-item>{{ route.meta.title }}</n-breadcrumb-item>
        </n-breadcrumb>
        <n-dropdown :options="[{ label: '退出登录', key: 'logout' }]" @select="logout">
          <n-button text>
            <n-space align="center"
              ><n-avatar round size="small">{{ auth.user?.display_name.slice(0, 1) }}</n-avatar
              ><span>{{ auth.user?.display_name }}</span
              ><n-tag size="small">{{
                auth.user ? roleLabels[auth.user.role] : ''
              }}</n-tag></n-space
            >
          </n-button>
        </n-dropdown>
      </n-layout-header>
      <n-layout-content content-style="padding: 20px;" :native-scrollbar="false">
        <router-view v-slot="{ Component, route: currentRoute }">
          <keep-alive>
            <component
              :is="Component"
              v-if="currentRoute.meta.keepAlive"
              :key="String(currentRoute.name)"
            />
          </keep-alive>
          <component :is="Component" v-if="!currentRoute.meta.keepAlive" />
        </router-view>
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<style scoped>
.app-shell {
  height: 100vh;
}
.brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}
.brand.compact {
  justify-content: center;
  padding: 0;
}
.brand-mark {
  width: 32px;
  height: 32px;
  object-fit: contain;
  flex: none;
}
.topbar {
  height: 64px;
  padding: 0 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
}
</style>
