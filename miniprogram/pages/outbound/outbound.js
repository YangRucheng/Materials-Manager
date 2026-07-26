const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { createClientRequestId, extractMaterialUuid } = require('../../utils/material');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    material: null,
    loading: true,
    scanning: false,
    submitting: false,
    recentReasons: [],
    form: {
      quantity: '1',
      businessReason: '',
      subitemNo: '',
    },
  },

  async onLoad(options = {}) {
    const app = getApp();
    const materialUuid =
      extractMaterialUuid(options.uuid) ||
      extractMaterialUuid(options.scene) ||
      extractMaterialUuid(app.globalData.pendingMaterialUuid);
    if (materialUuid) {
      app.globalData.pendingMaterialUuid = materialUuid;
    }
    try {
      const session = await app.globalData.authPromise;
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
      app.globalData.pendingMaterialUuid = '';
      if (!materialUuid) {
        wx.reLaunch({ url: '/pages/home/home' });
        return;
      }
      await Promise.all([this.loadReasonOptions(), this.loadMaterial(materialUuid)]);
    } catch (error) {
      this.showError(error);
    } finally {
      this.setData({ loading: false });
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
      setTimeout(() => {
        if (getCurrentPages().length > 1) {
          wx.navigateBack();
          return;
        }
        wx.reLaunch({ url: '/pages/home/home' });
      }, 800);
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
