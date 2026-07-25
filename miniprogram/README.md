# 备件扫码出库小程序

原生微信小程序，使用 TDesign Mini Program 组件库。启动后通过 `wx.login` 无感登录；未注册用户只有在提交姓名后才会创建 OpenID 与姓名映射，管理端不支持手工新增。之后可直接扫描二级库物资 UUID 二维码完成出库。

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

## 二维码内容

支持直接存储物资 UUID，也支持在任意 URL 或文本中包含标准 UUID。小程序只会使用识别到的 UUID 查询二级库物资。
