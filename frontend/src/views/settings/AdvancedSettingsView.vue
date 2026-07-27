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
  mini_program_new_user_enabled: true,
  image_acceleration_server_url: '',
  version: 0,
})

async function load() {
  loading.value = true
  try {
    const data = await aiSearchApi.settings()
    Object.assign(form, data)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载配置失败')
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
      mini_program_new_user_enabled: form.mini_program_new_user_enabled,
      image_acceleration_server_url: form.image_acceleration_server_url.trim(),
      version: form.version,
    })
    Object.assign(form, data)
    if (!data.enabled) {
      message.success('高级设置已保存')
      return
    }
    try {
      const testResult = await aiSearchApi.testSettings()
      message.success(`配置已保存，模型连接正常：${testResult.original} → ${testResult.expanded}`)
    } catch (error) {
      message.warning(
        `配置已保存，模型连接失败：${error instanceof Error ? error.message : '请检查模型配置'}`,
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
  <div class="page advanced-settings-page">
    <div class="page-header settings-header">
      <h1 class="page-title">高级设置</h1>
      <n-button type="primary" :loading="saving" :disabled="loading" @click="save">
        保存配置
      </n-button>
    </div>

    <div v-loading="loading" class="settings-grid">
      <n-card class="settings-card model-card" title="模型服务" :bordered="false">
        <template #header-extra>
          <div class="switch-control">
            <span>{{ form.enabled ? '已启用' : '已停用' }}</span>
            <n-switch v-model:value="form.enabled" />
          </div>
        </template>
        <n-form label-placement="top">
          <div class="model-fields">
            <n-form-item label="兼容端点" :required="form.enabled">
              <n-input
                v-model:value="form.endpoint"
                placeholder="https://api.openai.com/v1"
                :disabled="!form.enabled"
              />
            </n-form-item>
            <n-form-item label="模型" :required="form.enabled">
              <n-input
                v-model:value="form.model"
                placeholder="gpt-4.1-mini"
                :disabled="!form.enabled"
              />
            </n-form-item>
            <n-form-item class="api-key-field" label="API Key" :required="form.enabled">
              <n-input
                v-model:value="form.api_key"
                type="password"
                show-password-on="mousedown"
                placeholder="请输入 API Key"
                autocomplete="off"
                :disabled="!form.enabled"
              />
            </n-form-item>
          </div>
        </n-form>
      </n-card>

      <n-card class="settings-card" title="小程序" :bordered="false">
        <n-form label-placement="left" label-width="132">
          <n-form-item label="小程序码版本">
            <n-select v-model:value="form.mini_program_code_env" :options="codeEnvOptions" />
          </n-form-item>
          <n-form-item label="新用户绑定">
            <div class="switch-control">
              <n-switch v-model:value="form.mini_program_registration_enabled" />
              <span>{{ form.mini_program_registration_enabled ? '允许' : '关闭' }}</span>
            </div>
          </n-form-item>
          <n-form-item label="新用户默认状态">
            <div class="switch-control">
              <n-switch v-model:value="form.mini_program_new_user_enabled" />
              <span>{{ form.mini_program_new_user_enabled ? '启用' : '待审核' }}</span>
            </div>
          </n-form-item>
        </n-form>
      </n-card>

      <n-card class="settings-card image-card" title="图片加速" :bordered="false">
        <n-form label-placement="top">
          <n-form-item label="加速服务器地址">
            <n-input
              v-model:value="form.image_acceleration_server_url"
              placeholder="http://192.168.1.10"
              clearable
            />
          </n-form-item>
        </n-form>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.advanced-settings-page {
  max-width: 1180px;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(300px, 1fr);
  gap: 18px;
}

.settings-card {
  border: 1px solid #e8edf5;
  border-radius: 14px;
  box-shadow: 0 10px 28px rgb(30 64 175 / 5%);
}

.model-card {
  grid-row: span 2;
}

.model-fields {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(180px, 0.8fr);
  gap: 4px 18px;
}

.api-key-field {
  grid-column: 1 / -1;
}

.switch-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
}

:deep(.n-card-header) {
  padding: 20px 22px 14px;
}

:deep(.n-card__content) {
  padding: 12px 22px 20px;
}

:deep(.n-form-item:last-child) {
  margin-bottom: 0;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .model-card {
    grid-row: auto;
  }
}

@media (max-width: 640px) {
  .model-fields {
    grid-template-columns: 1fr;
  }

  .api-key-field {
    grid-column: auto;
  }
}
</style>
