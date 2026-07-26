const { apiBaseUrl } = require('../config/index');
const { t } = require('./i18n');

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
