const { getMessages, setNavigationBarTitle } = require('../../utils/i18n');

Page({
  data: { i18n: getMessages() },
  onLoad() {
    setNavigationBarTitle('disabledTitle');
  },
  onShow() {
    if (typeof wx.hideHomeButton === 'function') {
      wx.hideHomeButton();
    }
  },
});
