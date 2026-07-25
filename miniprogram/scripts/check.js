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
];

for (const file of requiredFiles) {
  if (!fs.existsSync(path.join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'));
JSON.parse(fs.readFileSync(path.join(root, 'project.config.json'), 'utf8'));
JSON.parse(fs.readFileSync(path.join(root, 'pages/profile/index.json'), 'utf8'));
JSON.parse(fs.readFileSync(path.join(root, 'pages/outbound/index.json'), 'utf8'));

console.log('Mini Program static structure check passed.');
