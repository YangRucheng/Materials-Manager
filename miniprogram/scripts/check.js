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
for (const page of pages) {
  for (const extension of ['js', 'json', 'wxml', 'wxss']) {
    requiredFiles.push(`pages/${page}.${extension}`);
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
    components.some((component) => !component.startsWith('tdesign-miniprogram/'))
  ) {
    throw new Error('Mini Program pages must use TDesign components.');
  }
}

console.log('Mini Program static structure check passed.');
