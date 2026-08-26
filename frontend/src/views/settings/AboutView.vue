<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { versionApi } from '@/api/version'
import { buildTime } from '@/config/env'
import { formatShanghaiTime } from '@/utils/time'

const buildTimeLabel = formatShanghaiTime(buildTime)
const backendBuildTimeLabel = ref('—')
onMounted(async () => {
  try {
    const info = await versionApi.get()
    backendBuildTimeLabel.value = formatShanghaiTime(info.build_time ?? undefined)
  } catch {
    backendBuildTimeLabel.value = '—'
  }
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">关于系统</h1>
      </div>
    </div>

    <n-card class="data-card about-card" :bordered="false">
      <section class="product-overview">
        <div class="product-mark">HXNI</div>
        <div class="product-copy">
          <h2>电气车间备件管理系统</h2>
          <p>面向备件库存、申购计划和采购跟踪的一体化管理工具。</p>
        </div>
        <n-tag :bordered="false" round type="success">内部使用</n-tag>
      </section>

      <n-divider />

      <section class="about-section">
        <div class="section-heading">
          <h3>使用小贴士</h3>
          <p>通过以下功能可以更高效地查看和定位数据。</p>
        </div>
        <div class="tips-list">
          <div class="tip-item">
            <span class="tip-index">01</span>
            <div>
              <strong>自定义列表字段</strong>
              <p>使用列表右上角的字段设置，只展示当前工作需要关注的信息。</p>
            </div>
          </div>
          <div class="tip-item">
            <span class="tip-index">02</span>
            <div>
              <strong>组合搜索</strong>
              <p>部分搜索框支持使用竖线分隔多个关键词，快速匹配任意一项。</p>
            </div>
          </div>
        </div>
      </section>

      <n-divider />

      <section class="about-section">
        <div class="section-heading">
          <h3>版权信息</h3>
        </div>
        <div class="copyright-panel">
          <p>本系统为华星镍业检修维护部电气自动化车间设计。</p>
          <p>
            项目仓库：
            <a
              href="https://github.com/YangRucheng/Materials-Manager"
              target="_blank"
              rel="noopener noreferrer"
            >
              github.com/YangRucheng/Materials-Manager
            </a>
          </p>
          <p>
            版权归
            <a href="https://github.com/YangRucheng" target="_blank" rel="noopener noreferrer">
              github.com/YangRucheng
            </a>
            所有。
          </p>
          <p>前端构建时间：{{ buildTimeLabel }}</p>
          <p>后端构建时间：{{ backendBuildTimeLabel }}</p>
        </div>
      </section>
    </n-card>
  </div>
</template>

<style scoped>
.about-card :deep(.n-card__content) {
  padding: 24px 28px;
}

.product-overview {
  display: flex;
  align-items: center;
  gap: 18px;
}

.product-mark {
  display: grid;
  width: 64px;
  height: 64px;
  flex: none;
  place-items: center;
  border: 1px solid #dce5ff;
  border-radius: 14px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.product-copy {
  min-width: 0;
  flex: 1;
}

.product-copy h2,
.section-heading h3 {
  margin: 0;
  color: var(--color-text-strong);
}

.product-copy h2 {
  font-size: 20px;
  font-weight: 650;
}

.product-copy p,
.section-heading p,
.tip-item p,
.copyright-panel p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.product-copy p {
  margin-top: 6px;
}

.section-heading {
  margin-bottom: 14px;
}

.section-heading h3 {
  font-size: 16px;
  font-weight: 600;
}

.section-heading p {
  margin-top: 4px;
  font-size: 13px;
}

.tips-list {
  overflow: hidden;
  border: 1px solid var(--color-border-subtle);
  border-radius: 12px;
  background: var(--color-surface-soft);
}

.tip-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 18px;
}

.tip-item + .tip-item {
  border-top: 1px solid var(--color-border-subtle);
}

.tip-index {
  display: grid;
  width: 30px;
  height: 30px;
  flex: none;
  place-items: center;
  border-radius: 8px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
}

.tip-item strong {
  display: block;
  margin-bottom: 3px;
  color: var(--color-text-strong);
  font-size: 14px;
}

.tip-item p,
.copyright-panel {
  font-size: 13px;
}

.copyright-panel {
  padding: 16px 18px;
  border-left: 3px solid var(--color-primary);
  border-radius: 0 10px 10px 0;
  background: var(--color-surface-soft);
}

.copyright-panel p + p {
  margin-top: 3px;
}

.copyright-panel a {
  color: var(--color-primary);
  font-weight: 600;
}

.copyright-panel a:hover {
  text-decoration: underline;
}
</style>
