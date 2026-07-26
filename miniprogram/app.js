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
        if (!['ACCOUNT_DISABLED', 'MINI_PROGRAM_REGISTRATION_DISABLED'].includes(error.code)) {
          throw error;
        }
        wx.removeStorageSync('miniProgramAccessToken');
        wx.removeStorageSync('miniProgramRegistrationToken');
        wx.removeStorageSync('miniProgramUser');
        if (error.code === 'ACCOUNT_DISABLED') {
          this.globalData.accountDisabled = true;
          wx.reLaunch({ url: '/pages/disabled/index' });
          return { account_disabled: true, user: null, requires_profile: false };
        }
        wx.reLaunch({ url: '/pages/registration-closed/index' });
        return { registration_disabled: true, user: null, requires_profile: false };
      });
  },
});
