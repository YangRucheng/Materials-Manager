# 备件扫码出库小程序

原生微信小程序，使用 TDesign Mini Program 组件库。启动后通过 `wx.login` 无感登录；未注册用户只有在提交姓名后才会创建 OpenID 与姓名映射，管理端不支持手工新增。之后可扫描物资小程序码直接进入对应物资的出库页面。

## 本地运行

1. 在本目录执行 `npm install`。
2. 使用微信开发者工具导入本目录。
3. 将 `project.config.json` 的 `appid` 替换为正式小程序 AppID。
4. 在微信开发者工具中执行“工具 → 构建 npm”。
5. 在小程序后台将 `https://materials-manager.qcloud.19890605.xyz` 配置为 request 合法域名。

后端需要配置：

```env
APP_WECHAT_MINI_PROGRAM_APP_ID=正式小程序AppID
APP_WECHAT_MINI_PROGRAM_APP_SECRET=正式小程序AppSecret
```

AppSecret 仅配置在后端，不得写入小程序代码。

## GitHub Actions 自动上传

推送 `miniprogram/` 下的改动到 `main` 分支后，工作流“自动上传微信小程序代码”会检查并上传开发版本，也可以在 GitHub Actions 页面手动运行。版本号统一使用北京时间日期，例如 `v2026.07.26`；上传备注统一使用 `CI 自动上传于 2026/07/26 09:37:12` 格式。

请在仓库的 `Settings → Secrets and variables → Actions` 中添加：

- `WECHAT_MINIPROGRAM_APPID`：正式小程序 AppID。
- `WECHAT_MINIPROGRAM_PRIVATE_KEY`：微信公众平台“小程序代码上传”中生成的上传私钥完整内容。

如果微信公众平台启用了上传 IP 白名单，GitHub 托管运行器的动态出口 IP 可能导致上传失败。此时需要关闭上传 IP 白名单，或改用具有固定出口 IP 的自托管运行器。

## 小程序码内容

网页端通过微信 `getUnlimitedQRCode` 接口生成物资小程序码，`scene` 使用物资 UUID 的 32 位无连字符形式。扫码进入后会自动载入对应物资；小程序内扫码同样兼容该小程序码。
