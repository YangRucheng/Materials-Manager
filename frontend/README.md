# 电气车间备件管理系统前端

按 `docs/development-plan.md` 实现的 Vue 3 + TypeScript 前端。默认启用 MSW 契约模拟数据，可在后端尚未启动时演示完整业务。

## 启动

```bash
npm install
npm run dev
```

演示账号密码均为 `123456`：`admin`、`warehouse`、`purchase`、`readonly`，分别对应四种角色。

## 接入后端

复制 `.env.example` 为 `.env.local`，设置：

```dotenv
VITE_USE_MOCK=false
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY=http://localhost:8000
```

仓库加入 `contracts/openapi.yaml` 后运行 `npm run generate:api`，由 OpenAPI 覆盖 `src/api/generated.ts`。当前文件是根据开发方案第 8 节建立的临时契约类型快照；页面和组件没有另建 DTO。

## 校验

```bash
npm run build
npm run test
npm run lint
```

数量在表单、状态和请求体中始终保存为字符串；时区按 `Asia/Shanghai` 展示，写接口发送带 `+08:00` 的 ISO 8601 时间。入出库提交使用 UUID `client_request_id`，确认和请求期间锁定按钮。
