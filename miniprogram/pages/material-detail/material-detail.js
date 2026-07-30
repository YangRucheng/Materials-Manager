const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { imageUrl } = require('../../utils/inventory');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    material: null,
    loading: true,
    failed: false,
    i18n: getMessages(),
  },

  async onLoad(options) {
    setNavigationBarTitle('materialDetailTitle');
    this.materialUuid = options.uuid || '';
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
      await getApp().globalData.imageSettingsPromise;
      await this.loadMaterial();
    } catch (error) {
      this.setData({ loading: false, failed: true });
      this.showError(error);
    }
  },

  async loadMaterial() {
    if (!this.materialUuid) {
      this.setData({ loading: false, failed: true });
      this.showError(new Error(t('invalidMaterial')));
      return;
    }
    this.setData({ loading: true, failed: false });
    try {
      const result = await request({
        url: `/mini-program/materials/${this.materialUuid}`,
      });
      const material = {
        ...result,
        image_count_label: t('imageCount', { count: (result.images || []).length }),
        images: (result.images || []).map((image) => ({
          ...image,
          preview_url: imageUrl(image.id, 720),
          original_url: imageUrl(image.id),
        })),
      };
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
    wx.navigateTo({ url: `/pages/outbound/outbound?uuid=${this.materialUuid}` });
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#detail-toast',
      message: error.message || t('materialDetailFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
