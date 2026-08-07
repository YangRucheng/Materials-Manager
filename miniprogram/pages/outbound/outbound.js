const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { createClientRequestId, extractMaterialUuid } = require('../../utils/material');
const { buildRedirectQuery } = require('../../utils/navigation');
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
    // 幂等 id：进入出库页生成一次，提交重试复用，成功或彻底失败后作废
    clientRequestId: '',
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
        // 记录待回跳目标（扫码场景用 pendingMaterialUuid，其余用 redirect）。
        // 保留 pendingMaterialUuid 兼容既有扫码→绑定→出库回跳流程。
        const redirect = buildRedirectQuery(
          materialUuid
            ? `/pages/outbound/outbound?uuid=${materialUuid}`
            : '/pages/outbound/outbound',
        );
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      app.globalData.pendingMaterialUuid = '';
      if (!materialUuid) {
        wx.reLaunch({ url: '/pages/home/home' });
        return;
      }
      await Promise.all([this.loadReasonOptions(), this.loadMaterial(materialUuid)]);
      this.setData({ clientRequestId: createClientRequestId() });
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

  onShareAppMessage() {
    const material = this.data.material;
    const materialUuid = (material && material.uuid) || '';
    return {
      title: material ? `${t('shareOutbound')} · ${material.name}` : t('shareOutbound'),
      path: materialUuid
        ? `/pages/outbound/outbound?uuid=${materialUuid}`
        : '/pages/outbound/outbound',
    };
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
          client_request_id:
            this.data.clientRequestId || createClientRequestId(),
          material_uuid: this.data.material.uuid,
          occurred_at: new Date().toISOString(),
          quantity,
          business_reason: businessReason.trim(),
          subitem_no: subitemNo.trim(),
          receiver_unit: '',
        },
      });
      getApp().globalData.lastOutbound = result;
      // 成功后作废幂等 id
      this.setData({ clientRequestId: '' });
      wx.redirectTo({ url: '/pages/outbound-success/outbound-success' });
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
