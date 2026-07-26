<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { aiSearchApi } from '@/api/aiSearch'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const codeEnvOptions = [
  { label: '体验版', value: 'trial' },
  { label: '正式版', value: 'release' },
]
const form = reactive({
  endpoint: '',
  api_key: '',
  model: '',
  enabled: true,
  mini_program_code_env: 'release' as 'trial' | 'release',
  mini_program_registration_enabled: true,
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
      mini_program_code_env: data.mini_program_code_env,
      mini_program_registration_enabled: data.mini_program_registration_enabled,
      version: data.version,
    })
  } finally {
    loading.value = false
  }
}

async function save() {
  if (form.enabled && (!form.endpoint.trim() || !form.model.trim() || !form.api_key.trim())) {
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
      mini_program_code_env: form.mini_program_code_env,
      mini_program_registration_enabled: form.mini_program_registration_enabled,
      version: form.version,
    })
    form.api_key = data.api_key
    form.version = data.version
    if (!data.enabled) {
      message.success('高级设置已保存，模型服务未启用')
      return
    }
    try {
      const testResult = await aiSearchApi.testSettings()
      message.success(
        `高级设置已保存，模型测试成功：${testResult.original} → ${testResult.expanded}`,
      )
    } catch (error) {
      message.warning(
        `高级设置已保存，但模型自动测试失败：${error instanceof Error ? error.message : '请检查模型配置'}`,
      )
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">高级设置</h1>
      </div>
    </div>
    <div class="settings-stack">
      <n-card :loading="loading" title="模型连接">
        <n-alert type="info" :bordered="false" style="margin-bottom: 20px">
          端点可填写 API 基础地址（如 https://api.openai.com/v1）或完整的 /chat/completions
          地址。API Key 在数据库中加密保存，仅超级管理员可在此页面查看。
        </n-alert>
        <n-form label-placement="left" label-width="120" style="max-width: 760px">
          <n-form-item label="启用服务">
            <n-switch v-model:value="form.enabled" />
          </n-form-item>
          <n-form-item label="兼容端点" :required="form.enabled">
            <n-input v-model:value="form.endpoint" placeholder="https://api.openai.com/v1" />
          </n-form-item>
          <n-form-item label="模型" :required="form.enabled">
            <n-input v-model:value="form.model" placeholder="gpt-4.1-mini" />
          </n-form-item>
          <n-form-item label="API Key" :required="form.enabled">
            <n-input v-model:value="form.api_key" placeholder="请输入 API Key" autocomplete="off" />
          </n-form-item>
        </n-form>
      </n-card>

      <n-card :loading="loading" title="小程序码">
        <n-alert type="info" :bordered="false" style="margin-bottom: 20px">
          物资详情页将按照这里选择的版本生成出库小程序码。
        </n-alert>
        <n-form label-placement="left" label-width="120">
          <n-form-item label="环境版本">
            <n-select
              v-model:value="form.mini_program_code_env"
              :options="codeEnvOptions"
              style="max-width: 240px"
            />
          </n-form-item>
        </n-form>
      </n-card>

      <n-card :loading="loading" title="小程序用户">
        <n-alert type="info" :bordered="false" style="margin-bottom: 20px">
          关闭后，新微信用户不能填写资料完成绑定；已经绑定的用户不受影响。
        </n-alert>
        <n-form label-placement="left" label-width="140">
          <n-form-item label="允许新用户绑定">
            <n-switch v-model:value="form.mini_program_registration_enabled" />
          </n-form-item>
        </n-form>
      </n-card>

      <div class="settings-actions">
        <n-button type="primary" :loading="saving" @click="save">保存配置</n-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-actions {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}

.settings-stack {
  display: grid;
  gap: 16px;
}
</style>
