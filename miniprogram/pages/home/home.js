const toastModule = require('tdesign-miniprogram/toast/index');
const { extractMaterialUuid } = require('../../utils/material');
const { canOutbound, isFeatureDisabled, SECONDARY_WAREHOUSE_LITE } = require('../../utils/features');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const { apiBaseUrl } = require('../../config/index');
const { uploadTime: buildUploadTime } = require('../../config/build-info');
const Toast = toastModule.default || toastModule;

const SHARE_IMAGE_URL = `${apiBaseUrl.replace(/\/api\/v1\/?$/, '')}/logo.png`;

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return t('unknown');
  }
  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

Page({
  data: {
    user: null,
    scanning: false,
    liteMode: false,
    userProfileVisible: false,
    miniProgramUpdatedAt: buildUploadTime || t('unknown'),
    i18n: getMessages(),
  },

  async onLoad() {
    setNavigationBarTitle('appTitle');
    try {
      const [session, featureModes] = await Promise.all([
        getApp().globalData.authPromise,
        getApp().globalData.featureSettingsPromise,
      ]);
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
        liteMode: featureModes.secondary_warehouse_mode === SECONDARY_WAREHOUSE_LITE,
      });
    } catch (error) {
      this.showError(error);
    }
  },

  openInventory() {
    if (!this.ensureFeatureEnabled('inventory_mode')) return;
    wx.navigateTo({ url: '/pages/inventory/inventory' });
  },

  openHuaXingInventory() {
    if (!this.ensureFeatureEnabled('huaxing_inventory_mode')) return;
    wx.navigateTo({ url: '/pages/huaxing-inventory/huaxing-inventory' });
  },

  openPurchasePlans() {
    if (!this.ensureFeatureEnabled('purchase_plans_mode')) return;
    wx.navigateTo({ url: '/pages/purchase-plans/purchase-plans' });
  },

  openPurchaseRecords() {
    if (!this.ensureFeatureEnabled('purchase_records_mode')) return;
    wx.navigateTo({ url: '/pages/purchase-records/purchase-records' });
  },

  openMaterialCodes() {
    if (!this.ensureFeatureEnabled('material_codes_mode')) return;
    wx.navigateTo({ url: '/pages/material-codes/material-codes' });
  },

  ensureFeatureEnabled(modeKey) {
    if (isFeatureDisabled(modeKey)) {
      this.showError(new Error(t('featureNotOpen')));
      return false;
    }
    return true;
  },

  onShareAppMessage() {
    return {
      title: t('shareHome'),
      path: '/pages/home/home',
      imageUrl: SHARE_IMAGE_URL,
    };
  },

  showUserProfile() {
    this.setData({ userProfileVisible: true });
  },

  onUserProfileVisibleChange(event) {
    this.setData({ userProfileVisible: event.detail.visible });
  },

  openRecords() {
    this.setData({ userProfileVisible: false });
    wx.navigateTo({ url: '/pages/records/records' });
  },

  async scanMaterial() {
    if (!canOutbound()) {
      this.showError(new Error(t('outboundNotOpen')));
      return;
    }
    this.setData({ scanning: true });
    try {
      const scanResult = await new Promise((resolve, reject) => {
        wx.scanCode({ success: resolve, fail: reject });
      });
      const materialUuid = extractMaterialUuid(scanResult.path || scanResult.result);
      if (!materialUuid) {
        throw new Error(t('materialUuidMissing'));
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
      message: error.message || t('actionFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
