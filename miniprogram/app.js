const { loginSilently } = require('./utils/auth');
const { request } = require('./utils/request');
const { resolveImageBaseUrl } = require('./utils/inventory');
const { getMessages, initializeI18n } = require('./utils/i18n');

App({
  globalData: {
    authPromise: null,
    pendingMaterialUuid: '',
    user: null,
    accountDisabled: false,
    imageBaseUrl: '',
    imageSettingsPromise: null,
    locale: 'zh-CN',
    messages: getMessages(),
  },

  onLaunch() {
    this.globalData.locale = initializeI18n();
    this.globalData.messages = getMessages();
    this.globalData.imageSettingsPromise = request({
      url: '/system-settings/image-acceleration',
      auth: false,
    })
      .then((settings) => {
        this.globalData.imageBaseUrl = resolveImageBaseUrl(
          settings.image_acceleration_server_url,
        );
        return this.globalData.imageBaseUrl;
      })
      .catch(() => '');
    this.globalData.authPromise = loginSilently()
      .then((session) => {
        this.globalData.user = session.user;
        return session;
      })
      .catch((error) => {
        if (!['ACCOUNT_DISABLED', 'MINI_PROGRAM_REGISTRATION_DISABLED'].includes(error.code)) {
          throw error;
        }
        wx.removeStorageSync('miniProgramAccessToken');
        wx.removeStorageSync('miniProgramRegistrationToken');
        wx.removeStorageSync('miniProgramUser');
        if (error.code === 'ACCOUNT_DISABLED') {
          this.globalData.accountDisabled = true;
          wx.reLaunch({ url: '/pages/disabled/disabled' });
          return { account_disabled: true, user: null, requires_profile: false };
        }
        wx.reLaunch({ url: '/pages/registration-closed/registration-closed' });
        return { registration_disabled: true, user: null, requires_profile: false };
      });
  },

  onPageNotFound() {
    wx.reLaunch({ url: '/pages/home/home' });
  },
});
