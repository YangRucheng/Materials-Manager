const { apiBaseUrl } = require('../config/index');
const { getLocale, t } = require('./i18n');

const errorMessageKeys = {
  ACCOUNT_DISABLED: 'accountDisabled',
  FORBIDDEN: 'forbidden',
  INVALID_TOKEN: 'invalidToken',
  MINI_PROGRAM_REGISTRATION_DISABLED: 'registrationClosed',
  UNAUTHORIZED: 'loginRequired',
  USER_DISABLED: 'invalidToken',
};

function request(options) {
  const token = options.token || wx.getStorageSync('miniProgramAccessToken');
  const headers = {
    'content-type': 'application/json',
    'Accept-Language': getLocale(),
    ...(options.header || {}),
  };
  if (token && options.auth !== false) {
    headers.Authorization = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
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
        if (response.statusCode === 401 && options.auth !== false && !options.token) {
          wx.removeStorageSync('miniProgramAccessToken');
        }
        if (response.data?.code === 'ACCOUNT_DISABLED') {
          wx.removeStorageSync('miniProgramAccessToken');
          wx.removeStorageSync('miniProgramRegistrationToken');
          wx.removeStorageSync('miniProgramUser');
          wx.reLaunch({ url: '/pages/disabled/disabled' });
        }
        if (response.data?.code === 'MINI_PROGRAM_REGISTRATION_DISABLED') {
          wx.removeStorageSync('miniProgramAccessToken');
          wx.removeStorageSync('miniProgramRegistrationToken');
          wx.removeStorageSync('miniProgramUser');
          wx.reLaunch({ url: '/pages/registration-closed/registration-closed' });
        }
        const messageKey = errorMessageKeys[response.data?.code];
        const error = new Error(messageKey ? t(messageKey) : response.data?.message || t('requestFailed'));
        error.code = response.data?.code;
        error.statusCode = response.statusCode;
        reject(error);
      },
      fail(error) {
        reject(new Error(error.errMsg || t('networkFailed')));
      },
    });
  });
}

module.exports = {
  request,
};
