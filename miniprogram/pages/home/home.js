const toastModule = require('tdesign-miniprogram/toast/index');
const { extractMaterialUuid } = require('../../utils/material');
const Toast = toastModule.default || toastModule;

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '未知';
  }
  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

Page({
  data: {
    user: null,
    scanning: false,
    userProfileVisible: false,
  },

  async onLoad() {
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
      if (session.requires_profile) {
        wx.reLaunch({ url: '/pages/bind/bind' });
        return;
      }
      this.setData({
        user: {
          ...session.user,
          registered_at: formatDateTime(session.user.created_at),
        },
      });
    } catch (error) {
      this.showError(error);
    }
  },

  openInventory() {
    wx.navigateTo({ url: '/pages/inventory/inventory' });
  },

  showUserProfile() {
    this.setData({ userProfileVisible: true });
  },

  onUserProfileVisibleChange(event) {
    this.setData({ userProfileVisible: event.detail.visible });
  },

  async scanMaterial() {
    this.setData({ scanning: true });
    try {
      const scanResult = await new Promise((resolve, reject) => {
        wx.scanCode({ success: resolve, fail: reject });
      });
      const materialUuid = extractMaterialUuid(scanResult.path || scanResult.result);
      if (!materialUuid) {
        throw new Error('小程序码中未识别到物资 UUID');
      }
      wx.navigateTo({ url: `/pages/outbound/outbound?uuid=${materialUuid}` });
    } catch (error) {
      if (!String(error.errMsg || '').includes('cancel')) {
        this.showError(error);
      }
    } finally {
      this.setData({ scanning: false });
    }
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#home-toast',
      message: error.message || '操作失败，请重试',
      theme: 'error',
      direction: 'column',
    });
  },
});
