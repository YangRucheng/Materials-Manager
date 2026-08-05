const toastModule = require('tdesign-miniprogram/toast/index');
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

Page({
  data: {
    result: null,
    i18n: getMessages(),
  },

  async onLoad() {
    setNavigationBarTitle('outboundSuccessTitle');
    const app = getApp();
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
        wx.reLaunch({ url: '/pages/bind/bind' });
        return;
      }
    } catch (_error) {
      wx.reLaunch({ url: '/pages/home/home' });
      return;
    }
    const result = app.globalData.lastOutbound;
    app.globalData.lastOutbound = null;
    if (!result || !result.operation_no) {
      wx.reLaunch({ url: '/pages/home/home' });
      return;
    }
    this.setData({
      result: {
        ...result,
        subitem_no_label: result.subitem_no || t('notSet'),
        receiver_name_label: result.receiver_name || t('notSet'),
        occurred_at_label: formatDateTime(result.occurred_at),
      },
    });
  },

  goHome() {
    wx.reLaunch({ url: '/pages/home/home' });
  },
});
