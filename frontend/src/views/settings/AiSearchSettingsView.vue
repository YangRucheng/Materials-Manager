<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { aiSearchApi } from '@/api/aiSearch'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const form = reactive({
  endpoint: '',
  api_key: '',
  model: '',
  enabled: true,
  version: 0,
})

async function load() {
  loading.value = true
  try {
    const data = await aiSearchApi.settings()
    Object.assign(form, {
      endpoint: data.endpoint,
      api_key: data.api_key,
      model: data.model,
      enabled: data.enabled,
      version: data.version,
    })
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.endpoint.trim() || !form.model.trim() || !form.api_key.trim()) {
    message.error('请填写端点、模型和 API Key')
    return
  }
  saving.value = true
  try {
    const data = await aiSearchApi.updateSettings({
      endpoint: form.endpoint.trim(),
      api_key: form.api_key.trim(),
      model: form.model.trim(),
      enabled: form.enabled,
      version: form.version,
    })
    form.api_key = data.api_key
    form.version = data.version
    message.success('大模型配置已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  try {
    const data = await aiSearchApi.testSettings()
    message.success(`测试成功：${data.original} → ${data.expanded}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '测试失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">大模型设置</h1>
      </div>
    </div>
    <n-card :loading="loading" title="模型连接">
      <n-alert type="info" :bordered="false" style="margin-bottom: 20px">
        端点可填写 API 基础地址（如 https://api.openai.com/v1）或完整的 /chat/completions 地址。API
        Key 在数据库中加密保存，仅超级管理员可在此页面查看。
      </n-alert>
      <n-form label-placement="left" label-width="120" style="max-width: 760px">
        <n-form-item label="启用服务">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
        <n-form-item label="兼容端点" required>
          <n-input v-model:value="form.endpoint" placeholder="https://api.openai.com/v1" />
        </n-form-item>
        <n-form-item label="模型" required>
          <n-input v-model:value="form.model" placeholder="gpt-4.1-mini" />
        </n-form-item>
        <n-form-item label="API Key" required>
          <n-input v-model:value="form.api_key" placeholder="请输入 API Key" autocomplete="off" />
        </n-form-item>
        <n-form-item :show-label="false">
          <div class="settings-actions">
            <n-space>
              <n-button :loading="testing" :disabled="!form.api_key.trim()" @click="testConnection">
                测试“电机”扩展
              </n-button>
              <n-button type="primary" :loading="saving" @click="save">保存配置</n-button>
            </n-space>
          </div>
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<style scoped>
.settings-actions {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}
</style>
