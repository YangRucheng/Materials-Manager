<script setup lang="ts">
import { computed } from 'vue'
import type { FileObject } from '@/api/generated'
import { imagePreviewUrl, imageUrl } from '@/utils/image'

const props = defineProps<{ images: FileObject[] }>()
const visible = computed(() => props.images.slice(0, 3))
const extra = computed(() => Math.max(0, props.images.length - 3))
</script>

<template>
  <div class="image-thumbnails">
    <n-image
      v-for="file in visible"
      :key="file.id"
      :src="imagePreviewUrl(file.id, 96)"
      :preview-src="imageUrl(file.id)"
      :alt="file.original_name"
      object-fit="cover"
      width="40"
      height="40"
      class="thumbnail"
    />
    <span v-if="extra" class="extra-count">+{{ extra }}</span>
  </div>
</template>

<style scoped>
.image-thumbnails {
  display: flex;
  align-items: center;
  gap: 6px;
}

.thumbnail {
  flex: none;
  overflow: hidden;
  border-radius: 6px;
}

.extra-count {
  flex: none;
  color: var(--color-text-muted);
  font-size: 12px;
}
</style>
