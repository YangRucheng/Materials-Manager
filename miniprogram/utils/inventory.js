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

function imageUrl(fileId, size) {
  const baseUrl = `${apiBaseUrl}/files/images/${fileId}`;
  return size ? `${baseUrl}?size=${size}` : baseUrl;
}

module.exports = {
  decorateStock,
  imageUrl,
};
