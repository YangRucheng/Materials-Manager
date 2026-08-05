const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { imageUrl } = require('../../utils/inventory');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

function present(value, fallback) {
  const text = String(value ?? '').trim();
  return text && !['\\', '/', '-', '—'].includes(text) ? text : fallback;
}

Page({
  data: {
    plan: null,
    loading: true,
    failed: false,
    i18n: getMessages(),
  },

  async onLoad(options) {
    setNavigationBarTitle('purchasePlanDetailTitle');
    this.planId = Number(options.id || 0);
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) return;
      if (session.registration_disabled) return;
      if (session.requires_profile) {
        wx.reLaunch({ url: '/pages/bind/bind' });
        return;
      }
      await getApp().globalData.imageSettingsPromise;
      await this.loadPlan(this.planId);
    } catch (error) {
      this.setData({ loading: false, failed: true });
      this.showError(error);
    }
  },

  async loadPlan(id) {
    if (!Number.isInteger(id) || id <= 0) {
      this.setData({ loading: false, failed: true });
      this.showError(new Error(t('invalidPurchasePlan')));
      return;
    }
    this.setData({ loading: true, failed: false });
    try {
      const result = await request({ url: `/mini-program/purchase-plans/${id}` });
      const plan = {
        ...result,
        plan_date_label: String(result.plan_date || '').replace(/-/g, '/'),
        quantity_label: `${result.planned_qty} ${result.unit_name}`,
        urgency_theme: result.urgency === '紧急' ? 'warning' : 'default',
        material_code_label: present(result.material_code, t('notSet')),
        category_label: present(result.category, t('notSet')),
        subitem_no_label: present(result.subitem_no, t('notSet')),
        remark_label: present(result.remark, t('noRemark')),
        image_count_label: t('imageCount', { count: (result.images || []).length }),
        images: (result.images || []).map((image) => ({
          ...image,
          preview_url: imageUrl(image.id, 192),
          original_url: imageUrl(image.id),
        })),
      };
      this.planId = id;
      this.setData({ plan });
      wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    } catch (error) {
      this.setData({ failed: true });
      this.showError(error);
    } finally {
      this.setData({ loading: false });
    }
  },

  previewImage(event) {
    const urls = this.data.plan.images.map((image) => image.original_url);
    wx.previewImage({ current: urls[event.currentTarget.dataset.index], urls });
  },

  retry() {
    void this.loadPlan(this.planId);
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#purchase-plan-detail-toast',
      message: error.message || t('purchasePlanDetailFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
