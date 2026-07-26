const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { createClientRequestId, extractMaterialUuid } = require('../../utils/material');
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
    material: null,
    scanning: false,
    submitting: false,
    recentReasons: [],
    userProfileVisible: false,
    form: {
      quantity: '1',
      businessReason: '',
      subitemNo: '',
    },
  },

  async onLoad(options = {}) {
    const app = getApp();
    const sceneMaterialUuid = extractMaterialUuid(options.scene);
    if (sceneMaterialUuid) {
      app.globalData.pendingMaterialUuid = sceneMaterialUuid;
    }
    try {
      const session = await app.globalData.authPromise;
      if (session.account_disabled) {
        wx.reLaunch({ url: '/pages/disabled/index' });
        return;
      }
      if (session.registration_disabled) {
        wx.reLaunch({ url: '/pages/registration-closed/index' });
        return;
      }
      if (session.requires_profile) {
        wx.reLaunch({ url: '/pages/profile/index' });
        return;
      }
      this.setData({
        user: {
          ...session.user,
          registered_at: formatDateTime(session.user.created_at),
        },
      });
      const pendingMaterialUuid = app.globalData.pendingMaterialUuid;
      app.globalData.pendingMaterialUuid = '';
      await this.loadReasonOptions();
      if (pendingMaterialUuid) {
        this.setData({ scanning: true });
        try {
          await this.loadMaterial(pendingMaterialUuid);
        } finally {
          this.setData({ scanning: false });
        }
      }
    } catch (error) {
      this.showError(error);
    }
  },

  async loadReasonOptions() {
    try {
      const options = await request({ url: '/mini-program/outbound-reasons' });
      const personalReasons = options.personal_reasons || [];
      const systemReasons = options.system_reasons || [];
      this.setData({
        recentReasons: [...new Set([...personalReasons, ...systemReasons])],
      });
    } catch (_error) {
      this.setData({ recentReasons: [] });
    }
  },

  openInventory() {
    wx.navigateTo({ url: '/pages/inventory/index' });
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
        wx.scanCode({
          success: resolve,
          fail: reject,
        });
      });
      const materialUuid = extractMaterialUuid(scanResult.path || scanResult.result);
      if (!materialUuid) {
        throw new Error('小程序码中未识别到物资 UUID');
      }
      await this.loadMaterial(materialUuid);
    } catch (error) {
      if (!String(error.errMsg || '').includes('cancel')) {
        this.showError(error);
      }
    } finally {
      this.setData({ scanning: false });
    }
  },

  async loadMaterial(materialUuid) {
    const material = await request({
      url: `/mini-program/materials/${materialUuid}`,
    });
    this.setData({ material, 'form.quantity': '1' });
  },

  onFieldChange(event) {
    const { field } = event.currentTarget.dataset;
    this.setData({ [`form.${field}`]: event.detail.value });
  },

  selectReason(event) {
    this.setData({ 'form.businessReason': event.currentTarget.dataset.reason });
  },

  validateForm() {
    if (!this.data.material) {
      return '请先扫描物资小程序码';
    }
    const { quantity, businessReason, subitemNo } = this.data.form;
    const numericQuantity = Number(quantity);
    if (!quantity || !Number.isFinite(numericQuantity) || numericQuantity <= 0) {
      return '请输入正确的出库数量';
    }
    if (numericQuantity > Number(this.data.material.current_qty)) {
      return '出库数量不能超过当前库存';
    }
    if (!businessReason.trim()) {
      return '请输入出库用途';
    }
    if (!subitemNo.trim()) {
      return '请输入子项号';
    }
    return '';
  },

  async submitOutbound() {
    const validationMessage = this.validateForm();
    if (validationMessage) {
      this.showError(new Error(validationMessage));
      return;
    }
    const { quantity, businessReason, subitemNo } = this.data.form;
    this.setData({ submitting: true });
    try {
      const result = await request({
        url: '/mini-program/outbound',
        method: 'POST',
        data: {
          client_request_id: createClientRequestId(),
          material_uuid: this.data.material.uuid,
          occurred_at: new Date().toISOString(),
          quantity,
          business_reason: businessReason.trim(),
          subitem_no: subitemNo.trim(),
          receiver_unit: '',
        },
      });
      Toast({
        context: this,
        selector: '#outbound-toast',
        message: `出库成功，剩余 ${result.after_qty} ${result.unit_name}`,
        theme: 'success',
        direction: 'column',
      });
      this.setData({
        material: null,
        form: {
          quantity: '1',
          businessReason: '',
          subitemNo: '',
        },
      });
      void this.loadReasonOptions();
    } catch (error) {
      this.showError(error);
    } finally {
      this.setData({ submitting: false });
    }
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#outbound-toast',
      message: error.message || '操作失败，请重试',
      theme: 'error',
      direction: 'column',
    });
  },
});
