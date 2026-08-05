const { apiBaseUrl } = require('../config/index');
const { t } = require('./i18n');

// 库存状态 → t-tag 主题色。全局已统一为蓝色分级（见 app.wxss 语义变量）：
// success=中浅蓝（正常）、warning=主蓝（低库存）、danger=深蓝（无库存）。
const stockStatusMeta = {
  normal: { labelKey: 'normalStock', theme: 'success' },
  out_of_stock: { labelKey: 'outOfStock', theme: 'danger' },
  low_stock: { labelKey: 'lowStock', theme: 'warning' },
};

function decorateStock(item) {
  const meta = stockStatusMeta[item.stock_status] || stockStatusMeta.normal;
  return {
    ...item,
    stock_status_label: t(meta.labelKey),
    stock_status_theme: meta.theme,
  };
}

function resolveImageBaseUrl(serverUrl) {
  const normalized = String(serverUrl || '').trim().replace(/\/+$/, '');
  if (!normalized) {
    return `${apiBaseUrl}/files/images`;
  }
  if (/^https?:\/\/[^/]+$/i.test(normalized)) {
    return `${normalized}/api/v1/files/images`;
  }
  return normalized;
}

function imageUrl(fileId, size) {
  const appImageBaseUrl =
    typeof getApp === 'function' ? getApp().globalData.imageBaseUrl : '';
  const url = `${appImageBaseUrl || resolveImageBaseUrl('')}/${fileId}`;
  return size ? `${url}?size=${size}` : url;
}

module.exports = {
  decorateStock,
  imageUrl,
  resolveImageBaseUrl,
};
