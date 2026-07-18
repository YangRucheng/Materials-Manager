<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const message = useMessage()
const formRef = ref<FormInst | null>(null)
const loading = ref(false)
const model = reactive({ username: '', password: '' })
const rules: FormRules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

async function submit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await auth.login(model)
    await router.replace(String(route.query.redirect || '/dashboard'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro">
      <div class="intro-content">
        <span class="eyebrow">ELECTRICAL WORKSHOP</span>
        <h1>电气车间<br />备件管理系统</h1>
        <p>库存、申购计划与请购到货闭环管理</p>
      </div>
    </section>
    <section class="login-panel">
      <n-card class="login-card" :bordered="false">
        <h2>欢迎登录</h2>
        <p class="muted">请输入系统账号</p>
        <n-form ref="formRef" :model="model" :rules="rules" size="large" @submit.prevent="submit">
          <n-form-item label="用户名" path="username"
            ><n-input v-model:value="model.username" placeholder="用户名"
          /></n-form-item>
          <n-form-item label="密码" path="password"
            ><n-input
              v-model:value="model.password"
              type="password"
              show-password-on="click"
              placeholder="密码"
              @keyup.enter="submit"
          /></n-form-item>
          <n-button type="primary" block size="large" :loading="loading" @click="submit"
            >登录</n-button
          >
        </n-form>
      </n-card>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  background: white;
}
.login-intro {
  background: linear-gradient(145deg, #0a6847, #18a058);
  color: white;
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
}
.login-intro::after {
  content: '';
  position: absolute;
  width: 480px;
  height: 480px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 50%;
  right: -120px;
  bottom: -160px;
  box-shadow:
    0 0 0 80px rgba(255, 255, 255, 0.04),
    0 0 0 160px rgba(255, 255, 255, 0.03);
}
.intro-content {
  z-index: 1;
  max-width: 500px;
  padding: 48px;
}
.eyebrow {
  letter-spacing: 3px;
  opacity: 0.75;
}
h1 {
  font-size: 48px;
  line-height: 1.25;
  margin: 20px 0;
}
.intro-content p {
  font-size: 18px;
  opacity: 0.85;
}
.login-panel {
  display: grid;
  place-items: center;
  padding: 48px;
}
.login-card {
  width: 420px;
}
h2 {
  font-size: 28px;
  margin: 0 0 6px;
}
</style>
