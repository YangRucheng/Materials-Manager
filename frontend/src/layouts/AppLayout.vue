<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import type { MenuOption } from 'naive-ui'
import { useMediaQuery } from '@vueuse/core'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { roleLabels } from '@/types/navigation'
import { LOGO_URL } from '@/constants/branding'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const settings = useSettingsStore()
const collapsed = ref(false)
// 移动端断点：≤768px 时侧边栏切换为抽屉导航
const isMobile = useMediaQuery('(max-width: 768px)')
const drawerOpen = ref(false)
const closeDrawer = () => {
  drawerOpen.value = false
}
const link = (label: string, name: string) => ({
  label: () => h(RouterLink, { to: { name }, onClick: closeDrawer }, { default: () => label }),
  key: name,
})

const menuOptions = computed<MenuOption[]>(() => {
  const items: MenuOption[] = [link('工作台', 'dashboard')]
  if (settings.isLiteMode) {
    // 精简模式：二级库只有一级 tab（Excel 导入 + 只读查询），与华星总库存同层级。
    items.push(link('二级库', 'warehouse-lite'))
  } else {
    items.push({
      label: '二级库',
      key: 'warehouse-group',
      children: [
        link('库存查询', 'stock'),
        link('物资档案', 'stock-materials'),
        link('操作记录', 'operations'),
        ...(auth.can('warehouse:write') ? [link('入库', 'inbound'), link('出库', 'outbound')] : []),
      ],
    })
  }
  items.push(link('华星总库存', 'hua-xing-stock'))
  items.push({
    label: '申购管理',
    key: 'procurement-group',
    children: [
      link('申购计划', 'purchase-materials'),
      link('周期性计划', 'purchase-plan-templates'),
      link('未编码物资', 'uncoded-materials'),
      link('物料编码库', 'material-code-library'),
      link('申购记录', 'purchase-records'),
    ],
  })
  if (auth.can('settings:write'))
    items.push({
      label: '系统管理',
      key: 'settings-group',
      children: [
        link('管理端用户', 'users'),
        link('小程序用户', 'mini-program-users'),
        link('高级设置', 'advanced-settings'),
        link('分享链接', 'share-links'),
        link('关于', 'about'),
      ],
    })
  return items
})

function logout() {
  auth.logout()
  void router.push({ name: 'login' })
}
</script>

<template>
  <n-layout :has-sider="!isMobile" class="app-shell">
    <n-layout-sider
      v-if="!isMobile"
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
        <div class="topbar-left">
          <button
            v-if="isMobile"
            type="button"
            class="menu-toggle"
            aria-label="打开导航菜单"
            @click="drawerOpen = true"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              aria-hidden="true"
            >
              <path d="M3 6h18M3 12h18M3 18h18" />
            </svg>
          </button>
          <n-breadcrumb>
            <n-breadcrumb-item v-if="!isMobile">备件管理</n-breadcrumb-item>
            <n-breadcrumb-item>{{ route.meta.title }}</n-breadcrumb-item>
          </n-breadcrumb>
        </div>
        <n-dropdown :options="[{ label: '退出登录', key: 'logout' }]" @select="logout">
          <button type="button" class="user-menu-trigger" aria-label="打开用户菜单">
            <span class="user-summary">
              <span class="user-name">{{ auth.user?.display_name || auth.user?.username }}</span>
              <span v-if="!isMobile" class="user-role">{{
                auth.user ? roleLabels[auth.user.role] : ''
              }}</span>
            </span>
            <span class="user-menu-caret" aria-hidden="true" />
          </button>
        </n-dropdown>
      </n-layout-header>
      <n-layout-content class="app-content" :native-scrollbar="false">
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

  <!-- 移动端抽屉导航 -->
  <n-drawer v-model:show="drawerOpen" placement="left" :width="250" aria-label="导航菜单">
    <div class="drawer-brand">
      <img class="brand-mark" :src="LOGO_URL" alt="系统 Logo" />
      <span>电气车间备件</span>
    </div>
    <n-menu
      class="drawer-menu"
      :options="menuOptions"
      :value="String(route.name || '')"
      @update:value="closeDrawer"
    />
  </n-drawer>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  background: var(--color-bg);
}
.brand {
  height: 68px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid var(--color-border-subtle);
  color: var(--color-text-strong);
  font-size: 17px;
  font-weight: 650;
  white-space: nowrap;
}
.brand.compact {
  justify-content: center;
  padding: 0;
}
.brand-mark {
  width: 34px;
  height: 34px;
  object-fit: contain;
  flex: none;
}
.topbar {
  height: 68px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgb(255 255 255 / 92%);
  backdrop-filter: blur(12px);
}
.topbar-left {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}
.menu-toggle {
  display: grid;
  flex: none;
  width: 40px;
  height: 40px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 10px;
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}
.menu-toggle:hover,
.menu-toggle:focus-visible {
  border-color: #dce5ff;
  background: var(--color-primary-soft);
  outline: none;
}
.user-menu-trigger {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 13px 6px 15px;
  border: 1px solid transparent;
  border-radius: 12px;
  color: inherit;
  background: transparent;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}
.user-menu-trigger:hover,
.user-menu-trigger:focus-visible {
  border-color: #dce5ff;
  background: var(--color-primary-soft);
  outline: none;
}
.user-summary {
  display: grid;
  gap: 2px;
  min-width: 96px;
  text-align: left;
}
.user-name {
  color: var(--color-text-strong);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.25;
}
.user-role {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.25;
}
.user-menu-caret {
  width: 7px;
  height: 7px;
  margin-top: -3px;
  border-right: 1.5px solid var(--color-text-muted);
  border-bottom: 1.5px solid var(--color-text-muted);
  transform: rotate(45deg);
}
.app-content {
  padding: 24px 28px 32px;
  background:
    radial-gradient(circle at 100% 0%, rgb(63 99 216 / 4%), transparent 28%), var(--color-bg);
}
/* 抽屉内导航 */
.drawer-brand {
  display: flex;
  height: 68px;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--color-border-subtle);
  color: var(--color-text-strong);
  font-size: 17px;
  font-weight: 650;
  white-space: nowrap;
}
.drawer-menu {
  padding-top: 8px;
}
/* 移动端（≤768px）顶栏与内容区适配 */
@media (max-width: 768px) {
  .topbar {
    height: 56px;
    padding: 0 12px;
  }
  .user-summary {
    min-width: 0;
  }
  .app-content {
    padding: 16px 14px 24px;
  }
}
</style>
