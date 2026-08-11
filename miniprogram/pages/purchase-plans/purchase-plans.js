const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { buildRedirectQuery } = require('../../utils/navigation');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

function decoratePlan(item) {
  return {
    ...item,
    plan_date_label: String(item.plan_date || '').replace(/-/g, '/'),
    quantity_label: `${item.planned_qty} ${item.unit_name}`,
    urgency_theme: item.urgency === '紧急' ? 'warning' : 'default',
  };
}

Page({
  data: {
    items: [],
    keyword: '',
    actualDemandPerson: '',
    subitemNo: '',
    actualDemandPersonOptions: [],
    subitemNoOptions: [],
    page: 1,
    pageSize: 15,
    total: 0,
    hasMore: false,
    loading: true,
    loadingMore: false,
    resultCount: '',
    i18n: getMessages(),
  },

  async onLoad() {
    setNavigationBarTitle('purchasePlansTitle');
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) return;
      if (session.registration_disabled) return;
      if (session.requires_profile) {
        const redirect = buildRedirectQuery('/pages/purchase-plans/purchase-plans');
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      const displayName = session.user?.display_name || '';
      this.setData({ actualDemandPerson: displayName });
      await this.loadFilterOptions(displayName);
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

  onSearchChange(event) {
    this.setData({ keyword: event.detail.value });
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => void this.loadPlans(true), 350);
  },

  onActualDemandPersonChange(event) {
    const value = event.detail.value || '';
    this.setData({ actualDemandPerson: value });
    void this.loadPlans(true);
  },

  onSubitemNoChange(event) {
    const value = event.detail.value || '';
    this.setData({ subitemNo: value });
    void this.loadPlans(true);
  },

  async loadFilterOptions(displayName) {
    try {
      const result = await request({ url: '/mini-program/purchase-plans/filter-options' });
      const persons = (result.actual_demand_persons || []).filter(Boolean);
      if (displayName && !persons.includes(displayName)) {
        persons.unshift(displayName);
      }
      this.setData({
        actualDemandPersonOptions: [
          { label: t('allActualDemandPersons'), value: '' },
          ...persons.map((value) => ({ label: value, value })),
        ],
        subitemNoOptions: [
          { label: t('allSubitemNos'), value: '' },
          ...(result.subitem_nos || []).map((value) => ({ label: value, value })),
        ],
      });
    } catch (error) {
      /* 筛选选项加载失败不阻塞列表 */
    }
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
      const actualDemandPerson = this.data.actualDemandPerson.trim();
      if (actualDemandPerson) data.actual_demand_person = actualDemandPerson;
      const subitemNo = this.data.subitemNo.trim();
      if (subitemNo) data.subitem_no = subitemNo;
      const result = await request({ url: '/mini-program/purchase-plans', data });
      if (requestId !== this.requestId) return;
      const incoming = (result.items || []).map(decoratePlan);
      const items = reset ? incoming : [...this.data.items, ...incoming];
      this.setData({
        items,
        page,
        total: result.total || 0,
        resultCount: t('purchasePlanResultCount', { count: result.total || 0 }),
        hasMore: items.length < (result.total || 0),
      });
    } catch (error) {
      if (requestId === this.requestId) this.showError(error);
    } finally {
      if (requestId === this.requestId) this.setData({ loading: false, loadingMore: false });
    }
  },

  openDetail(event) {
    wx.navigateTo({
      url: `/pages/purchase-plan-detail/purchase-plan-detail?id=${event.currentTarget.dataset.id}`,
    });
  },

  onShareAppMessage() {
    return {
      title: t('sharePurchasePlans'),
      path: '/pages/purchase-plans/purchase-plans',
    };
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#purchase-plans-toast',
      message: error.message || t('purchasePlansLoadFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
