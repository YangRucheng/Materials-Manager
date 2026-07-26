const { loginSilently } = require('./utils/auth');

App({
  globalData: {
    authPromise: null,
    pendingMaterialUuid: '',
    user: null,
  },

  onLaunch() {
    this.globalData.authPromise = loginSilently().then((session) => {
      this.globalData.user = session.user;
      return session;
    });
  },
});
