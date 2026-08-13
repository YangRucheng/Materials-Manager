const { apiBaseUrl } = require('../config/index');
const { getLocale, t } = require('./i18n');
const { buildRedirectQuery, getCurrentPageUrl } = require('./navigation');

const errorMessageKeys = {
  ACCOUNT_DISABLED: 'accountDisabled',
  FORBIDDEN: 'forbidden',
  INVALID_TOKEN: 'invalidToken',
  MINI_PROGRAM_REGISTRATION_DISABLED: 'registrationClosed',
  UNAUTHORIZED: 'loginRequired',
  USER_DISABLED: 'invalidToken',
};

// 模块级单例：并发的 401 只触发一次静默重登。
let refreshPromise = null;

function clearAuthStorage() {
  wx.removeStorageSync('miniProgramAccessToken');
  wx.removeStorageSync('miniProgramRegistrationToken');
  wx.removeStorageSync('miniProgramUser');
}

function request(options) {
  // 可恢复的鉴权失败仅发生在：需要鉴权且未显式传入 token。
  // auth:false（登录/设置接口）与显式 options.token（绑定页注册 token）不参与重登重试。
  const canRetry = options.auth !== false && !options.token;

  return new Promise((resolve, reject) => {
    function refreshSessionAndRetry() {
      if (!refreshPromise) {
        // 懒加载以打破 auth.js <-> request.js 顶层循环依赖（CommonJS 按调用时机求值）。
        const { loginSilently } = require('./auth');
        refreshPromise = loginSilently()
          .then((session) => {
            refreshPromise = null;
            // 静默重登后发现账号未绑定：跳绑定页，绑定后回跳原页面。
            if (session && session.requires_profile) {
              const currentPageUrl = getCurrentPageUrl();
              const redirect = currentPageUrl ? buildRedirectQuery(currentPageUrl) : '';
              wx.reLaunch({
                url: redirect ? `/pages/bind/bind?redirect=${redirect}` : '/pages/bind/bind',
              });
            }
            return session;
          })
          .catch((error) => {
            refreshPromise = null;
            if (
              error.code === 'ACCOUNT_DISABLED' ||
              error.code === 'MINI_PROGRAM_REGISTRATION_DISABLED'
            ) {
              clearAuthStorage();
              wx.reLaunch({
                url:
                  error.code === 'ACCOUNT_DISABLED'
                    ? '/pages/disabled/disabled'
                    : '/pages/registration-closed/registration-closed',
              });
            }
            throw error;
          });
      }
      return refreshPromise;
    }

    function doRequest() {
      // 每次重试都重新读取 token，重登后自动带上新 token。
      const token = options.token || wx.getStorageSync('miniProgramAccessToken');
      const headers = {
        'content-type': 'application/json',
        'Accept-Language': getLocale(),
        ...(options.header || {}),
      };
      if (token && options.auth !== false) {
        headers.Authorization = `Bearer ${token}`;
      }

      wx.request({
        url: `${apiBaseUrl}${options.url}`,
        method: options.method || 'GET',
        data: options.data,
        header: headers,
        success(response) {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            resolve(response.data);
            return;
          }

          const code = response.data?.code;

          // 账号禁用 / 注册关闭：全局处理，清空凭证并跳转。
          if (code === 'ACCOUNT_DISABLED') {
            clearAuthStorage();
            wx.reLaunch({ url: '/pages/disabled/disabled' });
          } else if (code === 'MINI_PROGRAM_REGISTRATION_DISABLED') {
            clearAuthStorage();
            wx.reLaunch({ url: '/pages/registration-closed/registration-closed' });
          }

          // 静默重登 + 单次重试：token 缺失或过期（UNAUTHORIZED / INVALID_TOKEN）。
          if (
            response.statusCode === 401 &&
            canRetry &&
            !options._retried &&
            (code === 'UNAUTHORIZED' || code === 'INVALID_TOKEN')
          ) {
            options._retried = true;
            refreshSessionAndRetry()
              .then((session) => {
                // 重登发现未绑定：已跳绑定页，不再重试，避免弹「请先登录」干扰跳转。
                if (session && session.requires_profile) {
                  const error = new Error(t('loginRequired'));
                  error.code = 'UNAUTHORIZED';
                  error.statusCode = 401;
                  reject(error);
                  return;
                }
                doRequest();
              })
              .catch(reject);
            return;
          }

          // 不可恢复的 401（重试后仍失败等）：仅丢弃已失效的 access token，不循环。
          if (response.statusCode === 401 && canRetry) {
            wx.removeStorageSync('miniProgramAccessToken');
          }

          const messageKey = errorMessageKeys[code];
          const error = new Error(
            messageKey ? t(messageKey) : response.data?.message || t('requestFailed'),
          );
          error.code = code;
          error.statusCode = response.statusCode;
          reject(error);
        },
        fail(error) {
          reject(new Error(error.errMsg || t('networkFailed')));
        },
      });
    }

    doRequest();
  });
}

module.exports = {
  request,
};
