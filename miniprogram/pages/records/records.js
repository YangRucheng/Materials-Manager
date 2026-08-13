const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { buildRedirectQuery } = require('../../utils/navigation');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return t('unknown');
  }
  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function decorateRecord(item) {
  return {
    ...item,
    operation_type_label: item.operation_type === 'INBOUND' ? t('operationInbound') : t('operationOutbound'),
    operation_type_theme: item.operation_type === 'INBOUND' ? 'success' : 'warning',
    occurred_at_label: formatDateTime(item.occurred_at),
    receiver_name_label: item.receiver_name || t('notSet'),
    subitem_no_label: item.subitem_no || t('notSet'),
    quantity_label: `${item.quantity} ${item.unit_name}`,
    stock_change_label: `${item.before_qty} → ${item.after_qty} ${item.unit_name}`,
  };
}

Page({
  data: {
    items: [],
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
    setNavigationBarTitle('recordsTitle');
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
        const redirect = buildRedirectQuery('/pages/records/records');
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
      await this.loadRecords(true);
    } catch (error) {
      this.setData({ loading: false });
      this.showError(error);
    }
  },

  async onPullDownRefresh() {
    await this.loadRecords(true);
    wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingMore) {
      void this.loadRecords(false);
    }
  },

  async loadRecords(reset) {
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) {
      return;
    }
    const requestId = (this.requestId || 0) + 1;
    this.requestId = requestId;
    const page = reset ? 1 : this.data.page + 1;
    this.setData(reset ? { loading: true } : { loadingMore: true });
    try {
      const result = await request({
        url: '/mini-program/operations',
        data: { page, page_size: this.data.pageSize },
      });
      if (requestId !== this.requestId) {
        return;
      }
      const incoming = (result.items || []).map(decorateRecord);
      const items = reset ? incoming : [...this.data.items, ...incoming];
      this.setData({
        items,
        page,
        total: result.total || 0,
        resultCount: t('recordCount', { count: result.total || 0 }),
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

  showError(error) {
    Toast({
      context: this,
      selector: '#records-toast',
      message: error.message || t('actionFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
