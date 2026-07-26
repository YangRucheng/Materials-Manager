const { getMessages, setNavigationBarTitle } = require('../../utils/i18n');

Page({
  data: { i18n: getMessages() },
  onLoad() {
    setNavigationBarTitle('registrationClosedTitle');
  },
});
