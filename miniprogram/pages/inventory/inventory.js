const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { decorateStock } = require('../../utils/inventory');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    items: [],
    keyword: '',
    stockStatus: 'all',
    page: 1,
    pageSize: 15,
    total: 0,
    hasMore: false,
    loading: true,
    loadingMore: false,
  },

  async onLoad() {
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
    if (this.data.hasMore && !this.data.loadingMore) {
      void this.loadInventory(false);
    }
  },

  onSearchChange(event) {
    const keyword = event.detail.value;
    this.setData({ keyword });
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      void this.loadInventory(true);
    }, 350);
  },

  onStatusChange(event) {
    const stockStatus = event.detail.value;
    if (stockStatus === this.data.stockStatus) {
      return;
    }
    this.setData({ stockStatus });
    void this.loadInventory(true);
  },

  async loadInventory(reset) {
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) {
      return;
    }
    const requestId = (this.requestId || 0) + 1;
    this.requestId = requestId;
    const page = reset ? 1 : this.data.page + 1;
    this.setData(reset ? { loading: true } : { loadingMore: true });
    try {
      const query = {
        page,
        page_size: this.data.pageSize,
      };
      const keyword = this.data.keyword.trim();
      if (keyword) {
        query.keyword = keyword;
      }
      if (this.data.stockStatus !== 'all') {
        query.stock_status = this.data.stockStatus;
      }
      const result = await request({ url: '/mini-program/inventory', data: query });
      if (requestId !== this.requestId) {
        return;
      }
      const incoming = (result.items || []).map(decorateStock);
      const items = reset ? incoming : [...this.data.items, ...incoming];
      this.setData({
        items,
        page,
        total: result.total || 0,
        hasMore: items.length < (result.total || 0),
      });
    } catch (error) {
      if (requestId === this.requestId) {
        this.showError(error);
      }
    } finally {
      if (requestId === this.requestId) {
        this.setData({ loading: false, loadingMore: false });
      }
    }
  },

  openDetail(event) {
    wx.navigateTo({
      url: `/pages/material-detail/material-detail?uuid=${event.currentTarget.dataset.uuid}`,
    });
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#inventory-toast',
      message: error.message || '库存加载失败，请重试',
      theme: 'error',
      direction: 'column',
    });
  },
});
