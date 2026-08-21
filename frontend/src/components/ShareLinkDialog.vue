<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import type { ShareExpiryOption, ShareRead, ShareType } from '@/api/generated'
import { shareApi } from '@/api/share'

const props = withDefaults(
  defineProps<{
    show: boolean
    shareType: ShareType
    /** 勾选项 id（申购计划 id / 申购记录 line_id），与 shareType 对应 */
    itemIds?: number[]
    /** 页面展示用名称，如「申购计划」「申购记录」 */
    title: string
  }>(),
  { itemIds: () => [] },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

const message = useMessage()

const expiryOptions: Array<{ value: ShareExpiryOption; label: string }> = [
  { value: '24h', label: '24小时' },
  { value: '3d', label: '3天' },
  { value: '7d', label: '7天' },
  { value: '30d', label: '30天' },
  { value: 'permanent', label: '永久' },
]
const expiryLabels = Object.fromEntries(expiryOptions.map((item) => [item.value, item.label]))

// step: confirm（确认信息 + 选择失效时间）→ final（再次确认）→ done（生成链接）
const step = ref<'confirm' | 'final' | 'done'>('confirm')
const expiry = ref<ShareExpiryOption>('7d')
const creating = ref(false)
const shareResult = ref<ShareRead | null>(null)

const shareUrl = computed(() => {
  if (!shareResult.value) return ''
  return `${window.location.origin}/share/${shareResult.value.token}`
})

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      step.value = 'confirm'
      expiry.value = '7d'
      creating.value = false
      shareResult.value = null
    }
  },
)

function close() {
  if (creating.value) return
  emit('update:show', false)
}

function toFinal() {
  if (!props.itemIds.length) {
    message.warning('请先勾选要分享的条目')
    return
  }
  step.value = 'final'
}

async function confirmShare() {
  if (creating.value) return
  creating.value = true
  try {
    shareResult.value = await shareApi.createShare({
      share_type: props.shareType,
      item_ids: props.itemIds,
      expires_in: expiry.value,
    })
    step.value = 'done'
  } catch (error) {
    message.error(error instanceof Error ? error.message : '分享失败')
  } finally {
    creating.value = false
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    message.success('分享链接已复制')
  } catch {
    message.warning('复制失败，请手动复制')
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="`链接分享 · ${title}`"
    style="width: 560px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    :closable="!creating"
    @update:show="close"
  >
    <!-- 第一步：确认信息 + 选择失效时间 -->
    <template v-if="step === 'confirm'">
      <n-alert type="warning" :bordered="false" style="margin-bottom: 16px">
        你将把勾选的 <b>{{ itemIds.length }} 条{{ title }}</b> 分享为
        <b>无需登录即可访问的公开页面</b
        >。任何获得链接的人都能查看这些数据，请确认内容不涉及敏感信息。
      </n-alert>
      <n-form label-placement="top">
        <n-form-item label="链接失效时间">
          <n-radio-group v-model:value="expiry" name="share-expiry">
            <n-space wrap>
              <n-radio-button
                v-for="option in expiryOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </n-radio-button>
            </n-space>
          </n-radio-group>
        </n-form-item>
      </n-form>
    </template>

    <!-- 第二步：再次确认 -->
    <template v-else-if="step === 'final'">
      <n-alert type="warning" :bordered="false" style="margin-bottom: 16px">
        再次确认：将分享 <b>{{ itemIds.length }} 条{{ title }}</b
        >，失效时间为 <b>{{ expiryLabels[expiry] }}</b
        >。分享后任何获得链接的人 <b>无需登录</b>即可查看，此操作将立即生效。
      </n-alert>
      <n-descriptions :column="1" label-placement="left" size="small">
        <n-descriptions-item label="分享内容">
          {{ itemIds.length }} 条{{ title }}
        </n-descriptions-item>
        <n-descriptions-item label="失效时间">{{ expiryLabels[expiry] }}</n-descriptions-item>
        <n-descriptions-item label="访问方式">公开链接，无需登录</n-descriptions-item>
      </n-descriptions>
    </template>

    <!-- 第三步：分享成功，展示链接 -->
    <template v-else>
      <n-result status="success" title="分享成功" :description="`已生成 ${title} 分享链接`" />
      <n-input-group style="margin-top: 8px">
        <n-input :value="shareUrl" readonly class="share-url-input" />
        <n-button type="primary" @click="copyLink">复制链接</n-button>
      </n-input-group>
      <n-alert type="info" :bordered="false" style="margin-top: 16px">
        链接失效时间为 {{ expiryLabels[expiry] }}。可在链接有效期内随时撤回，撤回后链接立即失效。
      </n-alert>
    </template>

    <template #footer>
      <template v-if="step === 'confirm'">
        <n-space justify="end">
          <n-button @click="close">取消</n-button>
          <n-button type="primary" @click="toFinal">下一步</n-button>
        </n-space>
      </template>
      <template v-else-if="step === 'final'">
        <n-space justify="end">
          <n-button :disabled="creating" @click="step = 'confirm'">上一步</n-button>
          <n-button type="primary" :loading="creating" @click="confirmShare">确认分享</n-button>
        </n-space>
      </template>
      <template v-else>
        <n-space justify="end">
          <n-button @click="close">完成</n-button>
        </n-space>
      </template>
    </template>
  </n-modal>
</template>

<style scoped>
.share-url-input :deep(input) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}
</style>
