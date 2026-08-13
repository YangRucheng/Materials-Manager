const REDIRECT_KEY = 'bindRedirect';

/**
 * 把当前页面 url（含 query）编码为回跳参数。
 * @param {string} url 形如 "/pages/outbound/outbound?uuid=..."
 */
function buildRedirectQuery(url) {
  return encodeURIComponent(url);
}

/**
 * 从 bind 页读取暂存的回跳目标并清除。
 * 校验以 /pages/ 开头，防止篡改跳转到任意路径。
 * @returns {string} 合法回跳 url，否则返回空字符串。
 */
function takeRedirect() {
  const target = wx.getStorageSync(REDIRECT_KEY);
  wx.removeStorageSync(REDIRECT_KEY);
  return typeof target === 'string' && target.startsWith('/pages/') ? target : '';
}

/**
 * 从页面 onLoad options 读取 redirect 参数并解码。
 * @param {Record<string, string>} options 页面 onLoad(options) 的 options
 * @returns {string} 合法回跳 url，否则返回空字符串。
 */
function extractRedirect(options = {}) {
  const raw = options.redirect || '';
  if (!raw) return '';
  try {
    const target = decodeURIComponent(raw);
    return target.startsWith('/pages/') ? target : '';
  } catch (_error) {
    return '';
  }
}

/**
 * 获取当前页面完整路径（含 query），用于 401 重登发现未绑定时回跳原页面。
 * @returns {string} 形如 "/pages/material-detail/material-detail?uuid=..."；无页面时返回空串。
 */
function getCurrentPageUrl() {
  const pages = getCurrentPages();
  const page = pages.length ? pages[pages.length - 1] : null;
  if (!page || !page.route) return '';
  const options = page.options || {};
  const query = Object.keys(options)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(String(options[key]))}`)
    .join('&');
  return `/${page.route}${query ? `?${query}` : ''}`;
}

module.exports = {
  REDIRECT_KEY,
  buildRedirectQuery,
  extractRedirect,
  takeRedirect,
  getCurrentPageUrl,
};
