const { apiBaseUrl } = require('../config/index');

function request(options) {
  const token = options.token || wx.getStorageSync('miniProgramAccessToken');
  const headers = {
    'content-type': 'application/json',
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
        const error = new Error(response.data?.message || '请求失败，请稍后重试');
        error.code = response.data?.code;
        error.statusCode = response.statusCode;
        reject(error);
      },
      fail(error) {
        reject(new Error(error.errMsg || '网络连接失败，请检查网络'));
      },
    });
  });
}

module.exports = {
  request,
};
