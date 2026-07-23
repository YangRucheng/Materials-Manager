<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { fileApi } from '@/api/files'
import type { FileObject } from '@/api/generated'
import { imagePreviewUrl, imageUrl, validateImageSelection } from '@/utils/image'

const props = withDefaults(
  defineProps<{ files: FileObject[]; disabled?: boolean; max?: number }>(),
  { max: 9 },
)
const emit = defineEmits<{ 'update:files': [files: FileObject[]] }>()
const input = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const message = useMessage()

async function uploadSelected(selected: File[]) {
  if (!selected.length || uploading.value) return
  const validationError = validateImageSelection(props.files.length, selected, props.max)
  if (validationError) {
    message.error(validationError)
    return
  }
  uploading.value = true
  try {
    const uploaded = await Promise.all(selected.map((file) => fileApi.uploadImage(file)))
    const merged = [...props.files, ...uploaded]
    const unique = Array.from(new Map(merged.map((file) => [file.id, file])).values())
    if (unique.length < merged.length) {
      message.info('已自动忽略重复图片')
    }
    emit('update:files', unique)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '图片上传失败')
  } finally {
    uploading.value = false
  }
}

async function choose(event: Event) {
  const selected = Array.from((event.target as HTMLInputElement).files || [])
  try {
    await uploadSelected(selected)
  } finally {
    if (input.value) input.value.value = ''
  }
}

async function pasteImages(event: ClipboardEvent) {
  if (props.disabled || uploading.value) return
  const selected = Array.from(event.clipboardData?.items || [])
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null)
  if (!selected.length) {
    message.warning('剪贴板中没有可粘贴的图片')
    return
  }
  event.preventDefault()
  await uploadSelected(selected)
}

async function remove(file: FileObject) {
  try {
    await fileApi.removeImage(file.id)
  } catch {
    /* 已被草稿引用时由保存接口统一处理 */
  }
  emit(
    'update:files',
    props.files.filter((x) => x.id !== file.id),
  )
}
</script>

<template>
  <div
    class="image-uploader"
    tabindex="0"
    aria-label="图片上传区域，支持 Ctrl+V 粘贴图片"
    @paste="pasteImages"
  >
    <div v-for="file in files" :key="file.id" class="image-item">
      <n-image
        :src="imagePreviewUrl(file.id, 192)"
        :preview-src="imageUrl(file.id)"
        :alt="file.original_name"
        object-fit="cover"
        width="96"
        height="96"
      />
      <n-button
        v-if="!disabled"
        class="remove"
        size="tiny"
        circle
        type="error"
        @click="remove(file)"
        >×</n-button
      >
    </div>
    <button
      v-if="!disabled && files.length < max"
      type="button"
      class="upload-trigger"
      :disabled="uploading"
      @click="input?.click()"
    >
      <span class="plus">+</span><span>{{ uploading ? '上传中' : '上传' }}</span>
    </button>
    <input
      ref="input"
      hidden
      type="file"
      multiple
      accept="image/jpeg,image/png,image/webp"
      @change="choose"
    />
  </div>
  <p class="image-hint">JPG/PNG/WebP，单图 ≤10 MB，最多 {{ max }} 张；支持 Ctrl+V 粘贴。</p>
</template>

<style scoped>
.image-uploader {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.image-uploader:focus-visible {
  outline: 2px solid rgba(24, 160, 88, 0.35);
  outline-offset: 4px;
  border-radius: 4px;
}
.image-item {
  position: relative;
  width: 98px;
  height: 98px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}
.remove {
  position: absolute;
  top: 4px;
  right: 4px;
}
.upload-trigger {
  width: 98px;
  height: 98px;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  background: #fafafa;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.upload-trigger:hover {
  border-color: #18a058;
  color: #18a058;
}
.plus {
  font-size: 28px;
  line-height: 1;
}
.image-hint {
  margin: 8px 0 0;
  color: #9ca3af;
  font-size: 12px;
}
</style>
