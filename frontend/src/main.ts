import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { systemSettingsApi } from './api/systemSettings'
import { useSettingsStore } from './stores/settings'
import { configureImageBaseUrl } from './utils/image'
import './styles.css'

async function bootstrap() {
  if (
    import.meta.env.VITE_USE_MOCK === 'true' ||
    (import.meta.env.VITE_USE_MOCK !== 'false' && import.meta.env.DEV)
  ) {
    const { worker } = await import('./mocks/browser')
    await worker.start({
      onUnhandledRequest: 'bypass',
      serviceWorker: { url: '/mockServiceWorker.js' },
    })
  }
  try {
    const imageSettings = await systemSettingsApi.imageAcceleration()
    configureImageBaseUrl(imageSettings.image_acceleration_server_url)
  } catch {
    configureImageBaseUrl('')
  }
  const app = createApp(App)
  app.directive('loading', {
    mounted: (element: HTMLElement, binding) => {
      element.style.opacity = binding.value ? '0.65' : ''
    },
    updated: (element: HTMLElement, binding) => {
      element.style.opacity = binding.value ? '0.65' : ''
    },
  })
  const pinia = createPinia()
  app.use(pinia).use(router)
  // 二级库模式等系统配置在 mount 前加载，保证菜单/路由守卫首次导航即可读到。
  await useSettingsStore(pinia).load()
  app.mount('#app')
}

void bootstrap()
