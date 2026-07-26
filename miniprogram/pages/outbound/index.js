const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { createClientRequestId, extractMaterialUuid } = require('../../utils/material');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    user: null,
    material: null,
    scanning: false,
    submitting: false,
    personalReasons: [],
    systemReasons: [],
    form: {
      quantity: '1',
      businessReason: '',
      subitemNo: '',
    },
  },

  async onLoad() {
    try {
      const session = await getApp().globalData.authPromise;
      if (session.requires_profile) {
        wx.reLaunch({ url: '/pages/profile/index' });
        return;
      }
      this.setData({ user: session.user });
      await this.loadReasonOptions();
    } catch (error) {
      this.showError(error);
    }
  },

  async loadReasonOptions() {
    try {
      const options = await request({ url: '/mini-program/outbound-reasons' });
      this.setData({
        personalReasons: options.personal_reasons || [],
        systemReasons: options.system_reasons || [],
      });
    } catch (_error) {
      this.setData({ personalReasons: [], systemReasons: [] });
    }
  },

  async scanMaterial() {
    this.setData({ scanning: true });
    try {
      const scanResult = await new Promise((resolve, reject) => {
        wx.scanCode({
          scanType: ['qrCode'],
          success: resolve,
          fail: reject,
        });
      });
      const materialUuid = extractMaterialUuid(scanResult.result);
      if (!materialUuid) {
        throw new Error('二维码中未识别到物资 UUID');
      }
      const material = await request({
        url: `/mini-program/materials/${materialUuid}`,
      });
      this.setData({ material, 'form.quantity': '1' });
    } catch (error) {
      if (!String(error.errMsg || '').includes('cancel')) {
        this.showError(error);
      }
    } finally {
      this.setData({ scanning: false });
    }
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
      return '请先扫描物资二维码';
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
