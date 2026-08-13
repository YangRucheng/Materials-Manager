const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { buildRedirectQuery } = require('../../utils/navigation');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

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
    setNavigationBarTitle('materialCodesTitle');
    try {
      const session = await getApp().globalData.authPromise;
      if (session.account_disabled) return;
      if (session.registration_disabled) return;
      if (session.requires_profile) {
        const redirect = buildRedirectQuery('/pages/material-codes/material-codes');
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      await this.loadCodes(true);
    } catch (error) {
      this.setData({ loading: false });
      this.showError(error);
    }
  },

  onUnload() {
    clearTimeout(this.searchTimer);
  },

  async onPullDownRefresh() {
    await this.loadCodes(true);
    wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingMore) void this.loadCodes(false);
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
    this.searchTimer = setTimeout(() => void this.loadCodes(true), 350);
  },

  async loadCodes(reset) {
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) return;
    const requestId = (this.requestId || 0) + 1;
    this.requestId = requestId;
    const page = reset ? 1 : this.data.page + 1;
    this.setData(reset ? { loading: true } : { loadingMore: true });
    try {
      const data = { page, page_size: this.data.pageSize };
      const keyword = this.data.keyword.trim();
      if (keyword) data.keyword = keyword;
      const result = await request({ url: '/mini-program/material-codes', data });
      if (requestId !== this.requestId) return;
      const incoming = result.items || [];
      const items = reset ? incoming : [...this.data.items, ...incoming];
      this.setData({
        items,
        page,
        total: result.total || 0,
        resultCount: t('materialCodeResultCount', { count: result.total || 0 }),
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
      title: t('shareMaterialCodes'),
      path: '/pages/material-codes/material-codes',
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

  copyMaterialCode() {
    const item = this.data.detailItem;
    if (!item) return;
    wx.setClipboardData({
      data: item.material_code || '',
      success: () => {
        Toast({
          context: this,
          selector: '#material-codes-toast',
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
      selector: '#material-codes-toast',
      message: error.message || t('materialCodesLoadFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
