const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { buildRedirectQuery } = require('../../utils/navigation');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

function decorateItem(item) {
  const quantity = item.quantity != null ? String(item.quantity) : '';
  return {
    ...item,
    qtyDisplay: quantity
      ? `${quantity}${item.unit_name ? ' ' + item.unit_name : ''}`
      : '',
  };
}

Page({
  data: {
    items: [],
    keyword: '',
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
    setNavigationBarTitle('huaxingInventoryTitle');
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) return;
      if (session.registration_disabled) return;
      if (session.requires_profile) {
        const redirect = buildRedirectQuery('/pages/huaxing-inventory/huaxing-inventory');
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      await this.loadInventory(true);
    } catch (error) {
      this.setData({ loading: false });
      this.showError(error);
    }
  },

  onUnload() {
    clearTimeout(this.searchTimer);
  },

  async onPullDownRefresh() {
    await this.loadInventory(true);
    wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingMore) void this.loadInventory(false);
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
    this.searchTimer = setTimeout(() => void this.loadInventory(true), 350);
  },

  async loadInventory(reset) {
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) return;
    const requestId = (this.requestId || 0) + 1;
    this.requestId = requestId;
    const page = reset ? 1 : this.data.page + 1;
    this.setData(reset ? { loading: true } : { loadingMore: true });
    try {
      const data = { page, page_size: this.data.pageSize };
      const keyword = this.data.keyword.trim();
      if (keyword) data.keyword = keyword;
      const result = await request({ url: '/mini-program/huaxing-inventory', data });
      if (requestId !== this.requestId) return;
      const incoming = (result.items || []).map(decorateItem);
      const items = reset ? incoming : [...this.data.items, ...incoming];
      this.setData({
        items,
        page,
        total: result.total || 0,
        resultCount: t('huaxingInventoryResultCount', { count: result.total || 0 }),
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
      title: t('shareHuaxingInventory'),
      path: '/pages/huaxing-inventory/huaxing-inventory',
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

  copyNameAndCode() {
    const item = this.data.detailItem;
    if (!item) return;
    wx.setClipboardData({
      data: `${item.name || ''} ${item.material_code || ''}`.trim(),
      success: () => {
        Toast({
          context: this,
          selector: '#huaxing-inventory-toast',
          message: t('copied'),
          theme: 'success',
          direction: 'column',
        });
      },
    });
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#huaxing-inventory-toast',
      message: error.message || t('huaxingInventoryLoadFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
