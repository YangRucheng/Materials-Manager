<script setup lang="ts">
defineProps<{ show: boolean }>()
</script>

<template>
  <div v-if="show" class="export-loading-overlay">
    <div class="export-loading-card">
      <n-spin size="large" />
      <p class="export-loading-text">正在生成 Excel，请稍候…</p>
    </div>
  </div>
</template>

<style scoped>
.export-loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(23, 32, 51, 0.45);
}

.export-loading-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 28px 40px;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 16px 48px rgba(15, 23, 42, 0.18);
}

.export-loading-text {
  margin: 0;
  color: #4b5565;
  font-size: 14px;
}
</style>
