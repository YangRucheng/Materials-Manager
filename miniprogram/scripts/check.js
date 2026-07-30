const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const pages = [
  'home/home',
  'outbound/outbound',
  'inventory/inventory',
  'material-detail/material-detail',
  'bind/bind',
  'disabled/disabled',
  'registration-closed/registration-closed',
];
const requiredFiles = ['app.js', 'app.json', 'app.wxss'];
const sharedComponents = ['material-summary-card/material-summary-card'];
for (const page of pages) {
  for (const extension of ['js', 'json', 'wxml', 'wxss']) {
    requiredFiles.push(`pages/${page}.${extension}`);
  }
}
for (const component of sharedComponents) {
  for (const extension of ['js', 'json', 'wxml', 'wxss']) {
    requiredFiles.push(`components/${component}.${extension}`);
  }
}

for (const file of requiredFiles) {
  if (!fs.existsSync(path.join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const appConfig = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'));
JSON.parse(fs.readFileSync(path.join(root, 'project.config.json'), 'utf8'));
const pageConfigs = pages.map((page) =>
  JSON.parse(fs.readFileSync(path.join(root, `pages/${page}.json`), 'utf8')),
);

if (appConfig.pages[0] !== 'pages/home/home') {
  throw new Error('Mini Program home page must be pages/home/home.');
}
if (appConfig.pages.some((page) => page.endsWith('/index'))) {
  throw new Error('Mini Program pages must use semantic file names.');
}
if (appConfig.window.backgroundColor !== '#f4f6fa') {
  throw new Error('Mini Program background color must match the web theme.');
}

const appScript = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
if (!appScript.includes("onPageNotFound()") || !appScript.includes("'/pages/home/home'")) {
  throw new Error('Mini Program must redirect missing pages to home.');
}

const appStyles = fs.readFileSync(path.join(root, 'app.wxss'), 'utf8');
for (const token of ['--td-brand-color: #3f63d8', '--td-text-color-primary: #172033']) {
  if (!appStyles.includes(token)) {
    throw new Error(`Missing shared TDesign theme token: ${token}`);
  }
}

const { extractMaterialUuid } = require(path.join(root, 'utils/material.js'));
const { resolveImageBaseUrl } = require(path.join(root, 'utils/inventory.js'));
const {
  LOCALE_ID_ID,
  LOCALE_ZH_CN,
  dictionaries,
  normalizeLocale,
  t,
} = require(path.join(root, 'utils/i18n.js'));
const expectedUuid = '10000000-0000-4000-8000-000000000001';
if (extractMaterialUuid('10000000000040008000000000000001') !== expectedUuid) {
  throw new Error('Mini Program scene must support compact material UUIDs.');
}
if (
  extractMaterialUuid('pages/outbound/outbound?scene=10000000000040008000000000000001') !==
  expectedUuid
) {
  throw new Error('Mini Program scanner must support unlimited code paths.');
}
if (normalizeLocale('id-ID') !== LOCALE_ID_ID || normalizeLocale('in_ID') !== LOCALE_ID_ID) {
  throw new Error('Mini Program must recognize Indonesian system locales.');
}
if (normalizeLocale('zh_CN') !== LOCALE_ZH_CN || normalizeLocale('en-US') !== LOCALE_ZH_CN) {
  throw new Error('Mini Program must fall back to Simplified Chinese.');
}
const localeKeys = Object.keys(dictionaries[LOCALE_ZH_CN]).sort();
if (
  JSON.stringify(localeKeys) !== JSON.stringify(Object.keys(dictionaries[LOCALE_ID_ID]).sort())
) {
  throw new Error('Mini Program locale dictionaries must contain the same keys.');
}
if (t('resultCount', { count: 3 }, LOCALE_ID_ID) !== '3 material') {
  throw new Error('Mini Program translations must support parameter interpolation.');
}

const requestScript = fs.readFileSync(path.join(root, 'utils/request.js'), 'utf8');
if (!requestScript.includes("'Accept-Language': getLocale()")) {
  throw new Error('Mini Program API requests must declare the selected locale.');
}
if (
  resolveImageBaseUrl('https://images.example.com/') !==
  'https://images.example.com/api/v1/files/images'
) {
  throw new Error('Mini Program image acceleration server URL is invalid.');
}

for (const pageConfig of pageConfigs) {
  const components = Object.values(pageConfig.usingComponents || {});
  if (
    !components.length ||
    components.some(
      (component) =>
        !component.startsWith('tdesign-miniprogram/') && !component.startsWith('/components/'),
    )
  ) {
    throw new Error('Mini Program pages must use TDesign or shared local components.');
  }
}

for (const page of ['material-detail/material-detail', 'outbound/outbound']) {
  const markup = fs.readFileSync(path.join(root, `pages/${page}.wxml`), 'utf8');
  if (!markup.includes('<material-summary-card')) {
    throw new Error(`${page} must reuse the shared material summary card.`);
  }
}

console.log('Mini Program static structure check passed.');
