import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles.css'

async function bootstrap() {
  if (import.meta.env.VITE_USE_MOCK !== 'false') {
    const { worker } = await import('./mocks/browser')
    await worker.start({
      onUnhandledRequest: 'bypass',
      serviceWorker: { url: '/mockServiceWorker.js' },
    })
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
