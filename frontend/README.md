# 电气车间备件管理系统前端

按 `docs/development-plan.md` 实现的 Vue 3 + TypeScript 前端。默认启用 MSW 契约模拟数据，可在后端尚未启动时演示完整业务。

## 启动

```bash
npm install
npm run dev
```

演示账号密码均为 `123456`：`admin`、`warehouse`、`purchase`、`readonly`，分别对应四种角色。

## 接入后端

复制 `../example/frontend.env.example` 为 `.env.local`。本地联调可将 `VITE_API_BASE_URL` 设置为 `http://localhost:8000/api/v1`；使用 Vite 同源代理时则设置为 `/api/v1`，并通过 `VITE_API_PROXY` 指定后端。

生产环境由 CI/CD 在 `npm run build` 前注入：

```dotenv
VITE_USE_MOCK=false
VITE_API_BASE_URL=https://api.example.com
VITE_IMAGE_BASE_URL=https://img.example.com
```

`VITE_API_BASE_URL` 和 `VITE_IMAGE_BASE_URL` 只填写服务器域名时会自动补全接口路径；`VITE_IMAGE_BASE_URL` 可省略，省略后图片从后端 API 读取。完整的前后端分离、跨域和 CDN 配置见 `../docs/frontend-separated-deployment.md`。

运行 `npm run generate:api` 可依据 `../docs/openapi.yaml` 更新 `src/api/generated.ts`；页面和组件没有另建 DTO。

## 校验

```bash
npm run build
npm run test
npm run lint
```

数量在表单、状态和请求体中始终保存为字符串；时区按 `Asia/Shanghai` 展示，写接口发送带 `+08:00` 的 ISO 8601 时间。入出库提交使用 UUID `client_request_id`，确认和请求期间锁定按钮。
