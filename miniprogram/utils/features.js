const MODE_DISABLED = 'disabled';
const MODE_QUERY_ONLY = 'query_only';
const MODE_READ_WRITE = 'read_write';
const SECONDARY_WAREHOUSE_FULL = 'full';
const SECONDARY_WAREHOUSE_LITE = 'lite';

// 拉取失败或尚未加载时的兜底：等价于现状全开放（库存可出库、其余只读可进）。
const DEFAULT_MODES = {
  inventory_mode: MODE_READ_WRITE,
  huaxing_inventory_mode: MODE_QUERY_ONLY,
  purchase_plans_mode: MODE_QUERY_ONLY,
  purchase_records_mode: MODE_QUERY_ONLY,
  material_codes_mode: MODE_QUERY_ONLY,
  secondary_warehouse_mode: SECONDARY_WAREHOUSE_FULL,
};

function getModes() {
  const app = getApp();
  return (app && app.globalData && app.globalData.featureModes) || DEFAULT_MODES;
}

function isFeatureDisabled(key) {
  return getModes()[key] === MODE_DISABLED;
}

// 二级库精简模式：独立表 + 只读，不支持出入库。
function isLiteMode() {
  return getModes().secondary_warehouse_mode === SECONDARY_WAREHOUSE_LITE;
}

function canOutbound() {
  return !isLiteMode() && getModes().inventory_mode === MODE_READ_WRITE;
}

module.exports = {
  MODE_DISABLED,
  MODE_QUERY_ONLY,
  MODE_READ_WRITE,
  SECONDARY_WAREHOUSE_FULL,
  SECONDARY_WAREHOUSE_LITE,
  DEFAULT_MODES,
  getModes,
  isFeatureDisabled,
  isLiteMode,
  canOutbound,
};
