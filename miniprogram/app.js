const { loginSilently } = require('./utils/auth');

App({
  globalData: {
    authPromise: null,
    pendingMaterialUuid: '',
    user: null,
    accountDisabled: false,
  },

  onLaunch() {
    this.globalData.authPromise = loginSilently()
      .then((session) => {
        this.globalData.user = session.user;
        return session;
      })
      .catch((error) => {
        if (error.code !== 'ACCOUNT_DISABLED') {
          throw error;
        }
        wx.removeStorageSync('miniProgramAccessToken');
        wx.removeStorageSync('miniProgramRegistrationToken');
        wx.removeStorageSync('miniProgramUser');
        this.globalData.accountDisabled = true;
        wx.reLaunch({ url: '/pages/disabled/index' });
        return { account_disabled: true, user: null, requires_profile: false };
      });
  },
});
