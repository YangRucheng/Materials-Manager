const { apiBaseUrl } = require('../config/index');

const stockStatusMeta = {
  normal: { label: '库存正常', theme: 'success' },
  out_of_stock: { label: '无库存', theme: 'danger' },
  low_stock: { label: '低库存', theme: 'warning' },
};

function decorateStock(item) {
  const meta = stockStatusMeta[item.stock_status] || stockStatusMeta.normal;
  return {
    ...item,
    stock_status_label: meta.label,
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
