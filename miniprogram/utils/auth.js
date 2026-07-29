const { request } = require('./request');
const { t } = require('./i18n');

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(result) {
        if (result.code) {
          resolve(result.code);
          return;
        }
        reject(new Error(t('wxLoginFailed')));
      },
      fail(error) {
        reject(new Error(error.errMsg || t('wxLoginFailed')));
      },
    });
  });
}

async function loginSilently() {
  const code = await wxLogin();
  let appId = '';
  try {
    appId = wx.getAccountInfoSync().miniProgram.appId;
  } catch (error) {
    appId = '';
  }
  const session = await request({
    url: '/mini-program/auth/wx-login',
    method: 'POST',
    data: appId && appId !== 'touristappid' ? { code, app_id: appId } : { code },
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
