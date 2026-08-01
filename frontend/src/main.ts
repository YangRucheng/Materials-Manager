import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { systemSettingsApi } from './api/systemSettings'
import { configureImageBaseUrl } from './utils/image'
import { loadSiteScale } from './utils/siteScale'
import './styles.css'

async function bootstrap() {
  loadSiteScale()
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
  app.use(createPinia()).use(router).mount('#app')
}

void bootstrap()
