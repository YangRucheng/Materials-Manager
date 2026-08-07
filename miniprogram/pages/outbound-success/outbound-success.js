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

function decorate(result) {
  return {
    ...result,
    subitem_no_label: result.subitem_no || t('notSet'),
    receiver_name_label: result.receiver_name || t('notSet'),
    occurred_at_label: formatDateTime(result.occurred_at),
  };
}

Page({
  data: {
    result: null,
    loading: false,
    i18n: getMessages(),
  },

  async onLoad(options = {}) {
    setNavigationBarTitle('outboundSuccessTitle');
    const app = getApp();
    const operationNo = String(options.operation_no || '').trim();
    try {
      const session = await app.globalData.authPromise;
      if (session.account_disabled) {
        wx.reLaunch({ url: '/pages/disabled/disabled' });
        return;
      }
      if (session.registration_disabled) {
        wx.reLaunch({ url: '/pages/registration-closed/registration-closed' });
        return;
      }
      if (session.requires_profile) {
        // 分享/直达场景：绑定后回跳到同一结果页（带流水号）。
        const redirect = buildRedirectQuery(
          operationNo
            ? `/pages/outbound-success/outbound-success?operation_no=${operationNo}`
            : '/pages/outbound-success/outbound-success',
        );
        wx.reLaunch({ url: `/pages/bind/bind?redirect=${redirect}` });
        return;
      }
    } catch (_error) {
      wx.reLaunch({ url: '/pages/home/home' });
      return;
    }

    // 从分享进入：按流水号恢复出库明细
    if (operationNo) {
      this.setData({ loading: true });
      try {
        const result = await request({
          url: `/mini-program/outbound/${operationNo}`,
        });
        this.setData({ result: decorate(result) });
      } catch (error) {
        this.showError(error);
      } finally {
        this.setData({ loading: false });
      }
      return;
    }

    // 出库流程内跳转：用内存中的结果
    const result = app.globalData.lastOutbound;
    app.globalData.lastOutbound = null;
    if (!result || !result.operation_no) {
      wx.reLaunch({ url: '/pages/home/home' });
      return;
    }
    this.setData({ result: decorate(result) });
  },

  onShareAppMessage() {
    const result = this.data.result;
    return {
      title: t('shareOutboundSuccess'),
      path: result
        ? `/pages/outbound-success/outbound-success?operation_no=${result.operation_no}`
        : '/pages/outbound-success/outbound-success',
    };
  },

  goHome() {
    wx.reLaunch({ url: '/pages/home/home' });
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#outbound-success-toast',
      message: error.message || t('actionFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
