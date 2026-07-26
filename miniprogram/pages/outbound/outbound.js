const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { createClientRequestId, extractMaterialUuid } = require('../../utils/material');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
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
    i18n: getMessages(),
  },

  async onLoad(options = {}) {
    setNavigationBarTitle('outboundTitle');
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
        throw new Error(t('materialUuidMissing'));
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
      return t('scanFirst');
    }
    const { quantity, businessReason, subitemNo } = this.data.form;
    const numericQuantity = Number(quantity);
    if (!quantity || !Number.isFinite(numericQuantity) || numericQuantity <= 0) {
      return t('invalidQuantity');
    }
    if (numericQuantity > Number(this.data.material.current_qty)) {
      return t('quantityExceedsStock');
    }
    if (!businessReason.trim()) {
      return t('purposeRequired');
    }
    if (!subitemNo.trim()) {
      return t('subitemRequired');
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
        message: t('outboundSuccess', {
          quantity: result.after_qty,
          unit: result.unit_name,
        }),
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
      message: error.message || t('actionFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
