const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { imageUrl } = require('../../utils/inventory');
const { buildRedirectQuery } = require('../../utils/navigation');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

function present(value, fallback) {
  const text = String(value ?? '').trim();
  return text && !['\\', '/', '-', '—'].includes(text) ? text : fallback;
}

Page({
  data: {
    record: null,
    loading: true,
    failed: false,
    i18n: getMessages(),
  },

  async onLoad(options) {
    setNavigationBarTitle('purchaseRecordDetailTitle');
    this.recordId = Number(options.line_id || 0);
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) return;
      if (session.registration_disabled) return;
      if (session.requires_profile) {
        const redirect = buildRedirectQuery(
          `/pages/purchase-record-detail/purchase-record-detail?line_id=${this.recordId}`,
        );
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      await getApp().globalData.imageSettingsPromise;
      await this.loadRecord(this.recordId);
    } catch (error) {
      this.setData({ loading: false, failed: true });
      this.showError(error);
    }
  },

  async loadRecord(id) {
    if (!Number.isInteger(id) || id <= 0) {
      this.setData({ loading: false, failed: true });
      this.showError(new Error(t('invalidPurchaseRecord')));
      return;
    }
    this.setData({ loading: true, failed: false });
    try {
      const result = await request({ url: `/mini-program/purchase-records/${id}` });
      const record = {
        ...result,
        plan_date_label: String(result.plan_date || '').replace(/-/g, '/'),
        purchase_date_label: String(result.purchase_date || '').replace(/-/g, '/'),
        quantity_label: `${result.purchase_qty} ${result.unit_name}`,
        purchase_order_no_label: result.purchase_order_no || t('notSet'),
        material_code_label: present(result.material_code, t('notSet')),
        material_code_copyable: Boolean(present(result.material_code, '')),
        demand_department_label: present(result.demand_department, t('notSet')),
        actual_demand_person_label: present(result.actual_demand_person, t('notSet')),
        usage_label: present(result.usage, t('notSet')),
        salesperson_label: present(result.salesperson, t('notSet')),
        remark_label: present(result.remark, t('noRemark')),
        trace_no_label: present(result.trace_no, t('notSet')),
        subitem_no_label: present(result.subitem_no, t('notSet')),
        image_count_label: t('imageCount', { count: (result.images || []).length }),
        status_theme:
          result.status === '已入库'
            ? 'success'
            : result.status === '部分入库'
              ? 'warning'
              : result.status === '已采购'
                ? 'primary'
                : 'default',
        images: (result.images || []).map((image) => ({
          ...image,
          preview_url: imageUrl(image.id, 192),
          original_url: imageUrl(image.id),
        })),
      };
      this.recordId = id;
      this.setData({ record });
      wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    } catch (error) {
      this.setData({ failed: true });
      this.showError(error);
    } finally {
      this.setData({ loading: false });
    }
  },

  previewImage(event) {
    const urls = this.data.record.images.map((image) => image.original_url);
    wx.previewImage({ current: urls[event.currentTarget.dataset.index], urls });
  },

  copyMaterialCode(event) {
    const code = String(event.currentTarget.dataset.code || '').trim();
    if (!code) return;
    wx.setClipboardData({
      data: code,
      success: () => {
        Toast({
          context: this,
          selector: '#purchase-record-detail-toast',
          message: t('copied'),
          theme: 'success',
          direction: 'column',
        });
      },
    });
  },

  onShareAppMessage() {
    const record = this.data.record;
    return {
      title: record ? `${t('sharePurchaseRecord')} · ${record.material_name}` : t('sharePurchaseRecord'),
      path: `/pages/purchase-record-detail/purchase-record-detail?line_id=${this.recordId}`,
    };
  },

  retry() {
    void this.loadRecord(this.recordId);
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#purchase-record-detail-toast',
      message: error.message || t('purchaseRecordDetailFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
