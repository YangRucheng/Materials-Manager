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
  storeSession(session);
  return session;
}

function storeSession(session) {
  if (session.access_token) {
    wx.setStorageSync('miniProgramAccessToken', session.access_token);
  } else {
    wx.removeStorageSync('miniProgramAccessToken');
  }
  if (session.registration_token) {
    wx.setStorageSync('miniProgramRegistrationToken', session.registration_token);
  } else {
    wx.removeStorageSync('miniProgramRegistrationToken');
  }
  if (session.user) {
    wx.setStorageSync('miniProgramUser', session.user);
  } else {
    wx.removeStorageSync('miniProgramUser');
  }
  const app = getApp();
  app.globalData.user = session.user || null;
  app.globalData.authPromise = Promise.resolve(session);
}

module.exports = {
  loginSilently,
  storeSession,
};
