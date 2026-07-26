const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const requiredFiles = [
  'app.js',
  'app.json',
  'app.wxss',
  'pages/profile/index.js',
  'pages/profile/index.json',
  'pages/profile/index.wxml',
  'pages/outbound/index.js',
  'pages/outbound/index.json',
  'pages/outbound/index.wxml',
  'pages/disabled/index.js',
  'pages/disabled/index.json',
  'pages/disabled/index.wxml',
];

for (const file of requiredFiles) {
  if (!fs.existsSync(path.join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const appConfig = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'));
JSON.parse(fs.readFileSync(path.join(root, 'project.config.json'), 'utf8'));
const pageConfigs = [
  JSON.parse(fs.readFileSync(path.join(root, 'pages/profile/index.json'), 'utf8')),
  JSON.parse(fs.readFileSync(path.join(root, 'pages/outbound/index.json'), 'utf8')),
  JSON.parse(fs.readFileSync(path.join(root, 'pages/disabled/index.json'), 'utf8')),
];

if (appConfig.window.backgroundColor !== '#f4f6fa') {
  throw new Error('Mini Program background color must match the web theme.');
}

const appStyles = fs.readFileSync(path.join(root, 'app.wxss'), 'utf8');
for (const token of ['--td-brand-color: #3f63d8', '--td-text-color-primary: #172033']) {
  if (!appStyles.includes(token)) {
    throw new Error(`Missing shared TDesign theme token: ${token}`);
  }
}

const { extractMaterialUuid } = require(path.join(root, 'utils/material.js'));
const expectedUuid = '10000000-0000-4000-8000-000000000001';
if (extractMaterialUuid('10000000000040008000000000000001') !== expectedUuid) {
  throw new Error('Mini Program scene must support compact material UUIDs.');
}
if (
  extractMaterialUuid('pages/outbound/index?scene=10000000000040008000000000000001') !==
  expectedUuid
) {
  throw new Error('Mini Program scanner must support unlimited code paths.');
}

for (const pageConfig of pageConfigs) {
  const components = Object.values(pageConfig.usingComponents || {});
  if (!components.length || components.some((component) => !component.startsWith('tdesign-miniprogram/'))) {
    throw new Error('Mini Program pages must use TDesign components.');
  }
}

console.log('Mini Program static structure check passed.');
