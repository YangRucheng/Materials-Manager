<template>
  <div class="about-page">
    <n-card class="about-card" :bordered="false">
      <div class="about-heading">
        <div class="about-mark">HXNI</div>
        <div>
          <h1>电气车间备件管理系统</h1>
          <p>面向备件库存、申购计划和采购跟踪的一体化管理工具。</p>
        </div>
      </div>

      <n-divider />

      <section class="about-section">
        <h2>小贴士</h2>
        <div class="tips-grid">
          <div class="tip-item">
            <strong>快速横向浏览</strong>
            <span>在较宽的表格中，按住 Shift 并滚动鼠标滚轮即可横向移动。</span>
          </div>
          <div class="tip-item">
            <strong>自定义列表字段</strong>
            <span>使用列表右上角的字段设置，只展示当前工作需要关注的信息。</span>
          </div>
          <div class="tip-item">
            <strong>组合搜索</strong>
            <span>部分搜索框支持使用竖线分隔多个关键词，快速匹配任意一项。</span>
          </div>
        </div>
      </section>

      <n-divider />

      <footer class="copyright">
        <p>本系统为华星镍业检修维护部电气自动化车间设计。</p>
        <p>
          版权归
          <a href="https://github.com/YangRucheng" target="_blank" rel="noopener noreferrer">
            github.com/YangRucheng
          </a>
          所有。
        </p>
      </footer>
    </n-card>
  </div>
</template>

<style scoped>
.about-page {
  display: flex;
  justify-content: center;
}

.about-card {
  width: min(880px, 100%);
}

.about-heading {
  display: flex;
  align-items: center;
  gap: 20px;
}

.about-mark {
  display: grid;
  width: 72px;
  height: 72px;
  flex: none;
  place-items: center;
  border-radius: 18px;
  background: linear-gradient(135deg, #1d6f5f, #2e9b7f);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
  box-shadow: 0 10px 24px rgb(29 111 95 / 20%);
}

.about-heading h1,
.about-section h2 {
  margin: 0;
  color: #1f2937;
}

.about-heading p {
  margin: 8px 0 0;
  color: var(--muted);
}

.about-section h2 {
  margin-bottom: 16px;
  font-size: 18px;
}

.tips-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.tip-item {
  display: flex;
  min-height: 112px;
  flex-direction: column;
  gap: 9px;
  padding: 18px;
  border: 1px solid #e6ecea;
  border-radius: 12px;
  background: #f8fbfa;
}

.tip-item strong {
  color: #1d6f5f;
  font-size: 15px;
}

.tip-item span,
.copyright {
  color: #5f6b76;
  line-height: 1.7;
}

.copyright p {
  margin: 4px 0;
}

.copyright a {
  color: #1d6f5f;
  font-weight: 600;
  text-decoration: none;
}

.copyright a:hover {
  text-decoration: underline;
}

@media (max-width: 760px) {
  .about-heading {
    align-items: flex-start;
  }

  .tips-grid {
    grid-template-columns: 1fr;
  }
}
</style>
