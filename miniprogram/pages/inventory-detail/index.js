const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { decorateStock, imageUrl } = require('../../utils/inventory');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    material: null,
    loading: true,
    failed: false,
  },

  async onLoad(options) {
    this.materialUuid = options.uuid || '';
    try {
      const session = await getApp().globalData.authPromise;
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
      await this.loadMaterial();
    } catch (error) {
      this.setData({ loading: false, failed: true });
      this.showError(error);
    }
  },

  async loadMaterial() {
    if (!this.materialUuid) {
      this.setData({ loading: false, failed: true });
      this.showError(new Error('物资标识无效'));
      return;
    }
    this.setData({ loading: true, failed: false });
    try {
      const result = await request({
        url: `/mini-program/materials/${this.materialUuid}`,
      });
      const material = decorateStock({
        ...result,
        images: (result.images || []).map((image) => ({
          ...image,
          preview_url: imageUrl(image.id, 720),
          original_url: imageUrl(image.id),
        })),
      });
      this.setData({ material });
    } catch (error) {
      this.setData({ failed: true });
      this.showError(error);
    } finally {
      this.setData({ loading: false });
    }
  },

  previewImage(event) {
    const urls = this.data.material.images.map((image) => image.original_url);
    wx.previewImage({
      current: urls[event.currentTarget.dataset.index],
      urls,
    });
  },

  retry() {
    void this.loadMaterial();
  },

  goOutbound() {
    getApp().globalData.pendingMaterialUuid = this.materialUuid;
    wx.reLaunch({ url: '/pages/outbound/index' });
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#detail-toast',
      message: error.message || '物资详情加载失败',
      theme: 'error',
      direction: 'column',
    });
  },
});
