const fs = require('fs');
const path = require('path');
const ci = require('miniprogram-ci');

const projectPath = path.resolve(__dirname, '..');
const appid = process.env.MINIPROGRAM_APPID;
const privateKeyPath = process.env.MINIPROGRAM_PRIVATE_KEY_PATH;
const version = process.env.MINIPROGRAM_VERSION;
const desc = process.env.MINIPROGRAM_DESC || 'GitHub Actions 自动上传';

if (!appid) {
  throw new Error('缺少环境变量 MINIPROGRAM_APPID');
}

if (!privateKeyPath || !fs.existsSync(privateKeyPath)) {
  throw new Error('缺少有效的环境变量 MINIPROGRAM_PRIVATE_KEY_PATH');
}

if (!version) {
  throw new Error('缺少环境变量 MINIPROGRAM_VERSION');
}

async function main() {
  const project = new ci.Project({
    appid,
    type: 'miniProgram',
    projectPath,
    privateKeyPath,
    ignores: ['node_modules/**/*'],
  });

  console.log('正在构建小程序 npm 依赖...');
  await ci.packNpm(project, { ignores: [] });
  project.updateFileAndDirs();

  console.log(`正在上传微信小程序，版本号：${version}`);
  await ci.upload({
    project,
    version,
    desc,
    robot: 1,
    onProgressUpdate: console.log,
  });

  console.log('微信小程序代码上传完成。');
}

main().catch((error) => {
  console.error('微信小程序代码上传失败：', error);
  process.exit(1);
});
