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

async function choose(event: Event) {
  const selected = Array.from((event.target as HTMLInputElement).files || [])
  const validationError = validateImageSelection(props.files.length, selected, props.max)
  if (validationError) {
    message.error(validationError)
    return
  }
  uploading.value = true
  try {
    const uploaded = await Promise.all(selected.map(fileApi.uploadImage))
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
    if (input.value) input.value.value = ''
  }
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
  <div class="image-uploader">
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
      <span class="plus">+</span><span>{{ uploading ? '上传中' : '上传图片' }}</span>
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
  <p class="image-hint">
    支持 JPG、PNG、WebP，单图不超过 10 MB，最多 {{ max }} 张；服务端统一转换为
    PNG，相同图片自动复用。
  </p>
</template>

<style scoped>
.image-uploader {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
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
