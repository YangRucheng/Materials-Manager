const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { storeSession } = require('../../utils/auth');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    displayName: '',
    loading: false,
  },

  async onLoad() {
    try {
      const session = await getApp().globalData.authPromise;
      if (!session.requires_profile) {
        wx.reLaunch({ url: '/pages/outbound/index' });
      }
    } catch (error) {
      this.showError(error);
    }
  },

  onNameChange(event) {
    this.setData({ displayName: event.detail.value });
  },

  async submitProfile() {
    const displayName = this.data.displayName.trim();
    if (!displayName) {
      this.showError(new Error('请输入姓名'));
      return;
    }
    this.setData({ loading: true });
    try {
      const session = await request({
        url: '/mini-program/profile',
        method: 'POST',
        data: { display_name: displayName },
        token: wx.getStorageSync('miniProgramRegistrationToken'),
      });
      storeSession(session);
      wx.reLaunch({ url: '/pages/outbound/index' });
    } catch (error) {
      this.showError(error);
    } finally {
      this.setData({ loading: false });
    }
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#profile-toast',
      message: error.message || '操作失败，请重试',
      theme: 'error',
      direction: 'column',
    });
  },
});
