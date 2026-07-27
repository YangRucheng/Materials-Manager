const LOCALE_ZH_CN = 'zh-CN';
const LOCALE_ID_ID = 'id-ID';

const dictionaries = {
  [LOCALE_ZH_CN]: {
    appTitle: '备件管理',
    inventoryTitle: '全库库存',
    materialDetailTitle: '物资详情',
    outboundTitle: '扫码出库',
    bindTitle: '绑定账号',
    disabledTitle: '账号待审核',
    registrationClosedTitle: '暂未开放绑定',
    allInventory: '全部库存',
    inventoryDescription: '搜索、筛选并查看全库物资',
    scanMaterialCode: '扫描物资小程序码',
    scanDescription: '识别物资后进入出库确认',
    startScan: '开始扫码',
    personalInfo: '个人信息',
    name: '姓名',
    department: '部门单位',
    registeredAt: '注册时间',
    unknown: '未知',
    materialUuidMissing: '小程序码中未识别到物资 UUID',
    actionFailed: '操作失败，请重试',
    searchPlaceholder: '搜索物资名称或型号规格',
    all: '全部',
    normalStock: '库存正常',
    outOfStock: '无库存',
    lowStock: '低库存',
    resultCount: '共 {count} 项物资',
    loadingInventory: '正在加载库存',
    inventoryEmpty: '没有找到符合条件的物资',
    modelSpec: '型号规格',
    stockQuantity: '库存数量',
    unit: '计量单位',
    loadMore: '加载更多',
    noMore: '已经到底了',
    inventoryLoadFailed: '库存加载失败，请重试',
    loadingMaterialDetail: '正在加载物资详情',
    materialDetailFailed: '物资详情加载失败',
    reload: '重新加载',
    currentStock: '当前库存',
    minimumStock: '最低库存 {quantity} {unit}',
    materialInfo: '物资信息',
    materialName: '物资名称',
    remark: '备注',
    noRemark: '暂无备注',
    imageAttachments: '图片附件',
    imageCount: '{count} 张',
    noImages: '暂无图片附件',
    goOutbound: '去出库',
    invalidMaterial: '物资标识无效',
    loadingMaterial: '正在加载物资',
    outboundInfo: '出库信息',
    outboundQuantity: '出库数量',
    subitemNo: '子项号',
    outboundPurpose: '出库用途',
    inputPlaceholder: '请输入',
    recentReasons: '一键采用近期出库用途',
    rescan: '重新扫码',
    confirmOutbound: '确认出库',
    scanFirst: '请先扫描物资小程序码',
    invalidQuantity: '请输入正确的出库数量',
    quantityExceedsStock: '出库数量不能超过当前库存',
    purposeRequired: '请输入出库用途',
    subitemRequired: '请输入子项号',
    outboundSuccess: '出库成功，剩余 {quantity} {unit}',
    electricalWorkshopParts: '电气车间备件',
    firstUse: '首次使用',
    setUser: '设置使用人',
    identityInfo: '身份信息',
    realNamePlaceholder: '请输入真实姓名',
    departmentPlaceholder: '请输入部门单位',
    enterOutbound: '进入扫码出库',
    bindingWarning: '本小程序仅对车间内部使用，请勿随意绑定！',
    nameRequired: '请输入姓名',
    departmentRequired: '请输入部门单位',
    accountDisabled: '账号待审核',
    accountDisabledDescription: '请联系管理员完成审核，审核通过后重新进入小程序',
    registrationClosed: '暂未开放新用户绑定',
    registrationClosedDescription: '请联系管理员开放后，再重新进入小程序',
    requestFailed: '请求失败，请稍后重试',
    networkFailed: '网络连接失败，请检查网络',
    wxLoginFailed: '微信登录失败，请重试',
    loginRequired: '请先登录',
    invalidToken: '登录凭证无效或已过期',
    forbidden: '没有执行此操作的权限',
  },
  [LOCALE_ID_ID]: {
    appTitle: 'Manajemen Suku Cadang',
    inventoryTitle: 'Stok Gudang',
    materialDetailTitle: 'Detail Material',
    outboundTitle: 'Pengeluaran Barang',
    bindTitle: 'Hubungkan Akun',
    disabledTitle: 'Akun Menunggu Persetujuan',
    registrationClosedTitle: 'Pendaftaran Ditutup',
    allInventory: 'Semua Stok',
    inventoryDescription: 'Cari, filter, dan lihat material di gudang',
    scanMaterialCode: 'Pindai kode mini program material',
    scanDescription: 'Konfirmasikan pengeluaran setelah material dikenali',
    startScan: 'Mulai Pindai',
    personalInfo: 'Informasi Pribadi',
    name: 'Nama',
    department: 'Departemen',
    registeredAt: 'Waktu Pendaftaran',
    unknown: 'Tidak diketahui',
    materialUuidMissing: 'UUID material tidak ditemukan dalam kode',
    actionFailed: 'Operasi gagal. Silakan coba lagi',
    searchPlaceholder: 'Cari nama atau spesifikasi material',
    all: 'Semua',
    normalStock: 'Stok Normal',
    outOfStock: 'Stok Habis',
    lowStock: 'Stok Rendah',
    resultCount: '{count} material',
    loadingInventory: 'Memuat stok',
    inventoryEmpty: 'Tidak ada material yang sesuai',
    modelSpec: 'Spesifikasi',
    stockQuantity: 'Jumlah Stok',
    unit: 'Satuan',
    loadMore: 'Memuat lagi',
    noMore: 'Semua data telah ditampilkan',
    inventoryLoadFailed: 'Gagal memuat stok. Silakan coba lagi',
    loadingMaterialDetail: 'Memuat detail material',
    materialDetailFailed: 'Gagal memuat detail material',
    reload: 'Muat Ulang',
    currentStock: 'Stok Saat Ini',
    minimumStock: 'Stok minimum {quantity} {unit}',
    materialInfo: 'Informasi Material',
    materialName: 'Nama Material',
    remark: 'Catatan',
    noRemark: 'Tidak ada catatan',
    imageAttachments: 'Lampiran Gambar',
    imageCount: '{count} gambar',
    noImages: 'Tidak ada lampiran gambar',
    goOutbound: 'Keluarkan Barang',
    invalidMaterial: 'Identitas material tidak valid',
    loadingMaterial: 'Memuat material',
    outboundInfo: 'Informasi Pengeluaran',
    outboundQuantity: 'Jumlah Keluar',
    subitemNo: 'Nomor Subitem',
    outboundPurpose: 'Tujuan Pengeluaran',
    inputPlaceholder: 'Masukkan',
    recentReasons: 'Gunakan tujuan pengeluaran terbaru',
    rescan: 'Pindai Ulang',
    confirmOutbound: 'Konfirmasi Pengeluaran',
    scanFirst: 'Pindai kode material terlebih dahulu',
    invalidQuantity: 'Masukkan jumlah pengeluaran yang benar',
    quantityExceedsStock: 'Jumlah pengeluaran melebihi stok saat ini',
    purposeRequired: 'Masukkan tujuan pengeluaran',
    subitemRequired: 'Masukkan nomor subitem',
    outboundSuccess: 'Berhasil dikeluarkan. Sisa {quantity} {unit}',
    electricalWorkshopParts: 'Suku Cadang Bengkel Listrik',
    firstUse: 'Penggunaan Pertama',
    setUser: 'Atur Pengguna',
    identityInfo: 'Informasi Identitas',
    realNamePlaceholder: 'Masukkan nama lengkap',
    departmentPlaceholder: 'Masukkan departemen',
    enterOutbound: 'Masuk ke Pengeluaran Barang',
    bindingWarning: 'Mini program ini hanya untuk penggunaan internal bengkel!',
    nameRequired: 'Masukkan nama',
    departmentRequired: 'Masukkan departemen',
    accountDisabled: 'Akun Menunggu Persetujuan',
    accountDisabledDescription: 'Hubungi administrator untuk menyelesaikan persetujuan, lalu buka kembali mini program',
    registrationClosed: 'Pendaftaran pengguna baru belum dibuka',
    registrationClosedDescription: 'Hubungi administrator untuk membuka pendaftaran, lalu buka kembali mini program',
    requestFailed: 'Permintaan gagal. Silakan coba lagi nanti',
    networkFailed: 'Koneksi jaringan gagal. Periksa jaringan Anda',
    wxLoginFailed: 'Login WeChat gagal. Silakan coba lagi',
    loginRequired: 'Silakan login terlebih dahulu',
    invalidToken: 'Sesi login tidak valid atau telah kedaluwarsa',
    forbidden: 'Anda tidak memiliki izin untuk melakukan operasi ini',
  },
};

let currentLocale = LOCALE_ZH_CN;

function normalizeLocale(language) {
  const languageCode = String(language || '')
    .trim()
    .replace('_', '-')
    .toLowerCase()
    .split('-', 1)[0];
  return ['id', 'in'].includes(languageCode) ? LOCALE_ID_ID : LOCALE_ZH_CN;
}

function detectSystemLocale() {
  try {
    if (typeof wx.getAppBaseInfo === 'function') {
      return normalizeLocale(wx.getAppBaseInfo().language);
    }
  } catch (_error) {
    // Continue with the compatibility API for older WeChat clients.
  }
  try {
    return normalizeLocale(wx.getSystemInfoSync().language);
  } catch (_error) {
    return LOCALE_ZH_CN;
  }
}

function initializeI18n() {
  currentLocale = detectSystemLocale();
  return currentLocale;
}

function getLocale() {
  return currentLocale;
}

function getMessages(locale = currentLocale) {
  return dictionaries[locale] || dictionaries[LOCALE_ZH_CN];
}

function t(key, params = {}, locale = currentLocale) {
  const template = getMessages(locale)[key] || dictionaries[LOCALE_ZH_CN][key] || key;
  return Object.keys(params).reduce(
    (value, name) => value.replace(new RegExp(`\\{${name}\\}`, 'g'), String(params[name])),
    template,
  );
}

function setNavigationBarTitle(key) {
  wx.setNavigationBarTitle({ title: t(key) });
}

module.exports = {
  LOCALE_ID_ID,
  LOCALE_ZH_CN,
  dictionaries,
  getLocale,
  getMessages,
  initializeI18n,
  normalizeLocale,
  setNavigationBarTitle,
  t,
};
