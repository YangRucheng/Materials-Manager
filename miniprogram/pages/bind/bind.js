const toastModule = require('tdesign-miniprogram/toast/index');
const { request } = require('../../utils/request');
const { storeSession } = require('../../utils/auth');
const { REDIRECT_KEY, extractRedirect, takeRedirect } = require('../../utils/navigation');
const { getMessages, setNavigationBarTitle, t } = require('../../utils/i18n');
const Toast = toastModule.default || toastModule;

Page({
  data: {
    displayName: '',
    departmentName: '华星检修维护部电气车间',
    loading: false,
    buttonLabel: 'enterHome',
    i18n: getMessages(),
  },

  async onLoad(options = {}) {
    setNavigationBarTitle('bindTitle');
    const redirect = extractRedirect(options);
    if (redirect) {
      wx.setStorageSync(REDIRECT_KEY, redirect);
    } else {
      wx.removeStorageSync(REDIRECT_KEY);
    }
    // 按钮文案随回跳目标变化：扫码出库 / 继续原页面 / 进入首页。
    this.setData({ buttonLabel: this.resolveButtonLabel(redirect) });
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
      if (!session.requires_profile) {
        wx.reLaunch({ url: '/pages/home/home' });
      }
    } catch (error) {
      this.showError(error);
    }
  },

  resolveButtonLabel(redirect) {
    if (getApp().globalData.pendingMaterialUuid) {
      return 'enterOutbound';
    }
    if (redirect) {
      return 'continueAfterBind';
    }
    return 'enterHome';
  },

  onNameChange(event) {
    this.setData({ displayName: event.detail.value });
  },

  onDepartmentChange(event) {
    this.setData({ departmentName: event.detail.value });
  },

  async submitProfile() {
    const displayName = this.data.displayName.trim();
    const departmentName = this.data.departmentName.trim();
    if (!displayName) {
      this.showError(new Error(t('nameRequired')));
      return;
    }
    if (!departmentName) {
      this.showError(new Error(t('departmentRequired')));
      return;
    }
    this.setData({ loading: true });
    try {
      const session = await request({
        url: '/mini-program/profile',
        method: 'POST',
        data: {
          display_name: displayName,
          department_name: departmentName,
        },
        token: wx.getStorageSync('miniProgramRegistrationToken'),
      });
      storeSession(session);
      // 只有拿到 access_token 才算账号可用（待审核用户后端不会签发 token）。
      // 无 token 时必须落在禁用页，不能带着空 token 进首页，否则后续请求都会提示"请先登录"。
      const hasAccessToken = Boolean(session.access_token);
      const userDisabled = session.user && !session.user.enabled;
      if (!hasAccessToken || userDisabled) {
        getApp().globalData.accountDisabled = true;
        wx.reLaunch({ url: '/pages/disabled/disabled' });
        return;
      }
      const materialUuid = getApp().globalData.pendingMaterialUuid;
      // 回跳优先级：扫码场景（pendingMaterialUuid）→ 分享/直达场景（redirect）→ 首页。
      const redirect = takeRedirect();
      wx.reLaunch({
        url: materialUuid
          ? `/pages/outbound/outbound?uuid=${materialUuid}`
          : redirect || '/pages/home/home',
      });
    } catch (error) {
      this.showError(error);
    } finally {
      this.setData({ loading: false });
    }
  },

  showError(error) {
    Toast({
      context: this,
      selector: '#profile-toast',
      message: error.message || t('actionFailed'),
      theme: 'error',
      direction: 'column',
    });
  },
});
