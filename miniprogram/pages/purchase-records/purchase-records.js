const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { buildRedirectQuery } = require('../../utils/navigation');
const { imageUrl } = require('../../utils/inventory');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

function present(value, fallback) {
  const text = String(value ?? '').trim();
  return text && !['\\', '/', '-', '—'].includes(text) ? text : fallback;
}

function decorateRecord(item) {
  return {
    ...item,
    plan_date_label: String(item.plan_date || '').replace(/-/g, '/'),
    purchase_date_label: String(item.purchase_date || '').replace(/-/g, '/'),
    quantity_label: `${item.purchase_qty} ${item.unit_name}`,
    purchase_order_no_label: item.purchase_order_no || t('notSet'),
    material_code_label: present(item.material_code, t('notSet')),
    demand_department_label: present(item.demand_department, t('notSet')),
    actual_demand_person_label: present(item.actual_demand_person, t('notSet')),
    usage_label: present(item.usage, t('notSet')),
    salesperson_label: present(item.salesperson, t('notSet')),
    remark_label: present(item.remark, t('noRemark')),
    trace_no_label: present(item.trace_no, t('notSet')),
    subitem_no_label: present(item.subitem_no, t('notSet')),
    image_count_label: t('imageCount', { count: (item.images || []).length }),
    images: (item.images || []).map((image) => ({
      ...image,
      preview_url: imageUrl(image.id, 192),
      original_url: imageUrl(image.id),
    })),
    status_theme:
      item.status === '已入库'
        ? 'success'
        : item.status === '部分入库'
          ? 'warning'
          : item.status === '已采购'
            ? 'primary'
            : 'default',
  };
}

Page({
  data: {
    items: [],
    keyword: '',
    status: '',
    statusOptions: [],
    subitemNo: '',
    subitemNoOptions: [],
    page: 1,
    pageSize: 15,
    total: 0,
    hasMore: false,
    loading: true,
    loadingMore: false,
    resultCount: '',
    backTopVisible: false,
    detailVisible: false,
    detailItem: null,
    i18n: getMessages(),
  },

  async onLoad() {
    setNavigationBarTitle('purchaseRecordsTitle');
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) return;
      if (session.registration_disabled) return;
      if (session.requires_profile) {
        const redirect = buildRedirectQuery('/pages/purchase-records/purchase-records');
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      await getApp().globalData.imageSettingsPromise;
      await this.loadFilterOptions();
      await this.loadPlans(true);
    } catch (error) {
      this.setData({ loading: false });
      this.showError(error);
    }
  },

  onUnload() {
    clearTimeout(this.searchTimer);
  },

  async onPullDownRefresh() {
    await this.loadPlans(true);
    wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingMore) void this.loadPlans(false);
  },

  onPageScroll(event) {
    const scrollTop = event.scrollTop || 0;
    if (scrollTop > 400 && !this.data.backTopVisible) {
      this.setData({ backTopVisible: true });
    } else if (scrollTop <= 400 && this.data.backTopVisible) {
      this.setData({ backTopVisible: false });
    }
  },

  scrollToTop() {
    wx.pageScrollTo({ scrollTop: 0, duration: 300 });
  },

  onSearchChange(event) {
    this.setData({ keyword: event.detail.value });
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => void this.loadPlans(true), 350);
  },

  onStatusChange(event) {
    const value = event.detail.value || '';
    this.setData({ status: value });
    void this.loadPlans(true);
  },

  onSubitemNoChange(event) {
    const value = event.detail.value || '';
    this.setData({ subitemNo: value });
    void this.loadPlans(true);
  },

  async loadFilterOptions() {
    let statuses = [];
    let subitemNos = [];
    try {
      const result = await request({ url: '/mini-program/purchase-records/filter-options' });
      statuses = (result.statuses || []).filter(Boolean);
      subitemNos = (result.subitem_nos || []).filter(Boolean);
    } catch (error) {
      // 选项加载失败不阻塞列表，但提示用户，并至少保留「全部状态」选项
      Toast({
        context: this,
        selector: '#purchase-records-toast',
        message: t('purchaseRecordFilterOptionsLoadFailed'),
        theme: 'warning',
      });
    }
    this.setData({
      statusOptions: [
        { label: t('allPurchaseStatuses'), value: '' },
        ...statuses.map((value) => ({ label: value, value })),
      ],
      subitemNoOptions: [
        { label: t('allSubitemNos'), value: '' },
        ...subitemNos.map((value) => ({ label: value, value })),
      ],
    });
  },

  async loadPlans(reset) {
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) return;
    const requestId = (this.requestId || 0) + 1;
    this.requestId = requestId;
    const page = reset ? 1 : this.data.page + 1;
    this.setData(reset ? { loading: true } : { loadingMore: true });
    try {
      const data = { page, page_size: this.data.pageSize };
      const keyword = this.data.keyword.trim();
      if (keyword) data.keyword = keyword;
      const status = this.data.status.trim();
      if (status) data.status = status;
      const subitemNo = this.data.subitemNo.trim();
      if (subitemNo) data.subitem_no = subitemNo;
      const result = await request({ url: '/mini-program/purchase-records', data });
      if (requestId !== this.requestId) return;
      const incoming = (result.items || []).map(decorateRecord);
      const items = reset ? incoming : [...this.data.items, ...incoming];
      this.setData({
        items,
        page,
        total: result.total || 0,
        resultCount: t('purchaseRecordResultCount', { count: result.total || 0 }),
        hasMore: items.length < (result.total || 0),
      });
    } catch (error) {
      if (requestId === this.requestId) this.showError(error);
    } finally {
      if (requestId === this.requestId) this.setData({ loading: false, loadingMore: false });
    }
  },

  onShareAppMessage() {
    return {
      title: t('sharePurchaseRecords'),
      path: '/pages/purchase-records/purchase-records',
    };
  },

  openDetail(event) {
    const item = this.data.items[event.currentTarget.dataset.index];
    if (!item) return;
    this.setData({ detailItem: item, detailVisible: true });
  },

  onDetailVisibleChange(event) {
    this.setData({ detailVisible: event.detail.visible });
  },

  previewImage(event) {
    const urls = this.data.detailItem.images.map((image) => image.original_url);
    wx.previewImage({ current: urls[event.currentTarget.dataset.index], urls });
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#purchase-records-toast',
      message: error.message || t('purchaseRecordsLoadFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
