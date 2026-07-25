const { request } = require('./request');

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(result) {
        if (result.code) {
          resolve(result.code);
          return;
        }
        reject(new Error('微信登录失败，请重试'));
      },
      fail(error) {
        reject(new Error(error.errMsg || '微信登录失败，请重试'));
      },
    });
  });
}

async function loginSilently() {
  const code = await wxLogin();
  const session = await request({
    url: '/mini-program/auth/wx-login',
    method: 'POST',
    data: { code },
    auth: false,
  });
  wx.setStorageSync('miniProgramAccessToken', session.access_token);
  wx.setStorageSync('miniProgramUser', session.user);
  return session;
}

function updateStoredUser(user) {
  wx.setStorageSync('miniProgramUser', user);
  const app = getApp();
  app.globalData.user = user;
  app.globalData.authPromise = Promise.resolve({
    access_token: wx.getStorageSync('miniProgramAccessToken'),
    token_type: 'bearer',
    user,
    requires_profile: false,
  });
}

module.exports = {
  loginSilently,
  updateStoredUser,
};
