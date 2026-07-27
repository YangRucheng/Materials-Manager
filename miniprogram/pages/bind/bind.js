const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { storeSession } = require('../../utils/auth');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    displayName: '',
    departmentName: '华星检修维护部电气车间',
    loading: false,
    i18n: getMessages(),
  },

  async onLoad() {
    setNavigationBarTitle('bindTitle');
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) {
        wx.reLaunch({ url: '/pages/disabled/disabled' });
        return;
      }
      if (session.registration_disabled) {
        wx.reLaunch({ url: '/pages/registration-closed/registration-closed' });
        return;
      }
      if (!session.requires_profile) {
        wx.reLaunch({ url: '/pages/home/home' });
      }
    } catch (error) {
      this.showError(error);
    }
  },

  onNameChange(event) {
    this.setData({ displayName: event.detail.value });
  },

  onDepartmentChange(event) {
    this.setData({ departmentName: event.detail.value });
  },

  async submitProfile() {
    const displayName = this.data.displayName.trim();
    const departmentName = this.data.departmentName.trim();
    if (!displayName) {
      this.showError(new Error(t('nameRequired')));
      return;
    }
    if (!departmentName) {
      this.showError(new Error(t('departmentRequired')));
      return;
    }
    this.setData({ loading: true });
    try {
      const session = await request({
        url: '/mini-program/profile',
        method: 'POST',
        data: {
          display_name: displayName,
          department_name: departmentName,
        },
        token: wx.getStorageSync('miniProgramRegistrationToken'),
      });
      storeSession(session);
      if (session.user && !session.user.enabled) {
        getApp().globalData.accountDisabled = true;
        wx.reLaunch({ url: '/pages/disabled/disabled' });
        return;
      }
      const materialUuid = getApp().globalData.pendingMaterialUuid;
      wx.reLaunch({
        url: materialUuid
          ? `/pages/outbound/outbound?uuid=${materialUuid}`
          : '/pages/home/home',
      });
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
      message: error.message || t('actionFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
