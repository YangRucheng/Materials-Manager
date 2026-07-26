<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import { inventoryApi } from '@/api/inventory'
import type {
  FileObject,
  InventoryBalance,
  StockMaterial,
  StockMaterialWrite,
} from '@/api/generated'
import ImageUploader from '@/components/ImageUploader.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import { isDecimalString } from '@/utils/decimal'
import { formatShanghaiTime } from '@/utils/time'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const material = ref<StockMaterial | null>(null)
const balance = ref<InventoryBalance | null>(null)
const images = ref<FileObject[]>([])
const miniProgramCodeUrl = ref('')
const formRef = ref<FormInst | null>(null)
const loading = ref(true)
const saving = ref(false)
const canWrite = computed(() => auth.can('warehouse:write'))
const miniProgramCodeFilename = computed(
  () => `物资-${material.value?.uuid ?? '出库'}-小程序码.png`,
)
const form = reactive<StockMaterialWrite>({
  name: '',
  model_spec: '',
  unit_id: null,
  remark: '',
  image_ids: [],
})
const policy = reactive({
  minimum_qty: '0',
  enabled: true,
  version: undefined as number | undefined,
})
const rules: FormRules = {
  name: { required: true, message: '请输入物资名称' },
  model_spec: { required: true, message: '请输入型号规格；无型号时填写“无”' },
  unit_id: { type: 'number', required: true, message: '请选择计量单位' },
}

function syncForm(value: StockMaterial) {
  Object.assign(form, {
    name: value.name,
    model_spec: value.model_spec,
    unit_id: value.unit_id,
    remark: value.remark || '',
    image_ids: value.images.map((image) => image.id),
    version: value.version,
  })
  Object.assign(policy, {
    minimum_qty: value.replenishment_policy?.minimum_qty ?? '0',
    enabled: value.replenishment_policy?.enabled ?? true,
    version: value.replenishment_policy?.version,
  })
  images.value = [...value.images]
}

function replaceMiniProgramCodeUrl(nextUrl = '') {
  if (miniProgramCodeUrl.value) URL.revokeObjectURL(miniProgramCodeUrl.value)
  miniProgramCodeUrl.value = nextUrl
}

async function loadMiniProgramCode(materialId: number) {
  try {
    const code = await inventoryApi.materialMiniProgramCode(materialId)
    replaceMiniProgramCodeUrl(URL.createObjectURL(code))
  } catch (error) {
    replaceMiniProgramCodeUrl()
    message.warning(error instanceof Error ? error.message : '出库小程序码加载失败')
  }
}

async function load() {
  loading.value = true
  try {
    const materialId = Number(route.params.id)
    const [nextMaterial, nextBalance] = await Promise.all([
      inventoryApi.material(materialId),
      inventoryApi.balance(materialId),
    ])
    material.value = nextMaterial
    balance.value = nextBalance
    syncForm(nextMaterial)
    await loadMiniProgramCode(materialId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '物资档案加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!material.value) return
  await formRef.value?.validate()
  if (!isDecimalString(policy.minimum_qty, 1, true)) {
    message.error('最低库存必须为非负数，且最多 1 位小数')
    return
  }

  saving.value = true
  try {
    const materialId = material.value.id
    await inventoryApi.updateMaterial(materialId, {
      ...form,
      name: form.name.trim(),
      model_spec: form.model_spec.trim(),
      remark: form.remark?.trim() || undefined,
      image_ids: images.value.map((image) => image.id),
      version: material.value.version,
    })
    material.value = await inventoryApi.savePolicy(materialId, {
      minimum_qty: policy.minimum_qty,
      enabled: policy.enabled,
      version: policy.version,
    })
    balance.value = await inventoryApi.balance(materialId)
    syncForm(material.value)
    message.success('物资档案已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void dictionaries.load()
  void load()
})

onBeforeUnmount(() => {
  replaceMiniProgramCodeUrl()
})
</script>

<template>
  <div v-if="material" v-loading="loading" class="page">
    <div class="detail-toolbar">
      <n-button secondary @click="router.push({ name: 'stock-materials' })">
        ← 返回物资档案
      </n-button>
      <n-space v-if="canWrite">
        <n-button
          secondary
          @click="router.push({ name: 'inbound', query: { material_id: material.id } })"
        >
          入库
        </n-button>
        <n-button
          type="primary"
          @click="router.push({ name: 'outbound', query: { material_id: material.id } })"
        >
          出库
        </n-button>
      </n-space>
    </div>

    <n-card title="物资档案信息">
      <n-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-placement="top"
        :disabled="!canWrite"
      >
        <div class="form-grid">
          <n-form-item label="物资名称" path="name" required>
            <n-input v-model:value="form.name" maxlength="128" />
          </n-form-item>
          <n-form-item label="型号规格" path="model_spec" required>
            <n-input
              v-model:value="form.model_spec"
              maxlength="255"
              placeholder="无型号时填写“无”"
            />
          </n-form-item>
          <n-form-item label="计量单位" path="unit_id" required>
            <n-select v-model:value="form.unit_id" :options="dictionaries.unitOptions" />
          </n-form-item>
          <n-form-item label="当前库存">
            <n-input :value="material.current_qty" disabled>
              <template #suffix>{{ material.unit_name }}</template>
            </n-input>
          </n-form-item>
          <n-form-item label="最低库存">
            <QuantityInput v-model:value="policy.minimum_qty" :disabled="!canWrite">
              <template #suffix>{{ material.unit_name }}</template>
            </QuantityInput>
          </n-form-item>
          <n-form-item label="建议申购数量">
            <n-input :value="balance?.suggested_purchase_qty ?? '0'" disabled>
              <template #suffix>{{ material.unit_name }}</template>
            </n-input>
          </n-form-item>
          <n-form-item label="低库存预警" class="wide-form-item">
            <div class="switch-field">
              <n-switch v-model:value="policy.enabled" :disabled="!canWrite" />
              <span>{{ policy.enabled ? '已启用' : '已停用' }}</span>
              <span class="muted">库存低于最低库存时进入低库存清单</span>
            </div>
          </n-form-item>
          <n-form-item label="备注" class="wide-form-item">
            <n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count />
          </n-form-item>
          <n-form-item label="出库小程序码" class="wide-form-item mini-program-code-form-item">
            <div class="mini-program-code-field">
              <img
                v-if="miniProgramCodeUrl"
                class="mini-program-code-image"
                :src="miniProgramCodeUrl"
                :alt="`${material.name}出库小程序码`"
              />
              <div class="mini-program-code-details">
                <strong>微信扫码直达出库</strong>
                <span class="muted">扫码后自动进入小程序并载入当前物资，无需再次扫描</span>
                <code>{{ material.uuid }}</code>
                <n-button
                  tag="a"
                  secondary
                  size="small"
                  :href="miniProgramCodeUrl"
                  :download="miniProgramCodeFilename"
                >
                  下载小程序码
                </n-button>
              </div>
            </div>
          </n-form-item>
          <n-form-item label="图片附件" class="wide-form-item attachment-form-item">
            <ImageUploader v-model:files="images" :disabled="!canWrite" />
          </n-form-item>
        </div>
      </n-form>
      <template #footer>
        <n-space justify="space-between" align="center">
          <n-space align="center">
            <span class="muted">最后更新：{{ formatShanghaiTime(material.updated_at) }}</span>
            <n-tag size="small" :type="material.has_operation_records ? 'default' : 'success'">
              {{ material.has_operation_records ? '已有操作记录' : '暂无操作记录' }}
            </n-tag>
          </n-space>
          <n-button v-if="canWrite" type="primary" :loading="saving" @click="save">
            保存修改
          </n-button>
        </n-space>
      </template>
    </n-card>
  </div>
</template>

<style scoped>
.wide-form-item {
  grid-column: 1 / -1;
}

.switch-field {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 10px;
}

.attachment-form-item {
  margin-bottom: 0;
}

.mini-program-code-field {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 24px;
  padding: 20px;
  border: 1px solid #e3e8f2;
  border-radius: 10px;
  background: #f8faff;
  box-sizing: border-box;
}

.mini-program-code-image {
  width: 168px;
  height: 168px;
  flex: none;
  padding: 8px;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(31, 52, 118, 0.1);
  box-sizing: border-box;
}

.mini-program-code-details {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  flex-direction: column;
  gap: 10px;
}

.mini-program-code-details strong {
  color: #172033;
  font-size: 16px;
}

.mini-program-code-details code {
  max-width: 100%;
  padding: 6px 10px;
  overflow: hidden;
  border-radius: 6px;
  background: #edf2ff;
  color: #3658c7;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .mini-program-code-field {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
