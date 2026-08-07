# 前后端分离部署

前端使用 Vite 构建，后端地址和图片加速地址均在 **构建阶段** 注入。变量会被写入静态 JavaScript 产物，因此部署后修改服务器环境变量不会生效，需要重新构建前端。

## 构建变量

| 变量                  | 必填             | 示例                      | 说明                                                                         |
| --------------------- | ---------------- | ------------------------- | ---------------------------------------------------------------------------- |
| `VITE_USE_MOCK`       | 建议             | `false`                   | 生产环境应为 `false`。未设置时开发模式默认启用，生产模式默认关闭。           |
| `VITE_API_BASE_URL`   | 前后端分离时必填 | `https://api.example.com` | 后端服务器地址；只有域名时自动补 `/api/v1`，也可直接填写完整 API 根地址。    |
| `VITE_IMAGE_BASE_URL` | 否               | `https://img.example.com` | 图床/CDN 地址；只有域名时自动补 `/api/v1/files/images`，未设置时从后端读取。 |
| `VITE_API_PROXY`      | 否               | `http://localhost:8000`   | 仅供 `npm run dev` 的本地代理使用，不影响生产产物。                          |

所有 `VITE_*` 变量都会暴露给浏览器，禁止放入密钥、Token 或其他敏感信息。地址末尾可以带斜杠，构建配置会自动清理。

## CI/CD 构建

Linux Runner 示例：

```bash
cd frontend
npm ci
VITE_USE_MOCK=false \
VITE_API_BASE_URL=https://api.example.com \
VITE_IMAGE_BASE_URL=https://img.example.com \
npm run build
```

PowerShell Runner 示例：

```powershell
Set-Location frontend
npm ci
$env:VITE_USE_MOCK = 'false'
$env:VITE_API_BASE_URL = 'https://api.example.com'
$env:VITE_IMAGE_BASE_URL = 'https://img.example.com'
npm run build
```

构建产物位于 `frontend/dist/`，CD 阶段只需把该目录发布到静态站点、对象存储或 CDN。该方案不依赖 Docker 构建参数，也不需要修改现有 Docker 镜像。

## 后端跨域

后端使用独立的 `RefererCORSMiddleware` 处理跨域。它优先从 `Referer` 解析前端页面的协议和域名；没有 `Referer` 或其格式无效时，再使用 `Origin`：

```text
Referer: https://spares.example.com/login?redirect=/
Origin: https://spares.example.com
Access-Control-Allow-Origin: https://spares.example.com
Vary: Origin, Referer
```

该逻辑覆盖 OPTIONS 预检和正常响应，并为所有响应（含结构化错误响应）补齐 CORS Header。预检会回显浏览器请求的 Header，并允许常用 HTTP 方法；响应同时暴露 `X-Request-ID` 和 `Content-Disposition`。本项目不使用 HTTP 404 状态码，错误响应统一为结构化业务错误体，详见 `../docs/api-error-conventions.md`。

可配置项：

```dotenv
APP_CORS_ALLOW_CREDENTIALS=true
APP_CORS_MAX_AGE=86400
```

浏览器要求 `Access-Control-Allow-Origin` 与页面 Origin 一致，因此正常部署时 `Referer` 所属站点应与 `Origin` 相同。若浏览器的 Referrer Policy 不发送 `Referer`，中间件会自动回退到 `Origin`。

## 图片 CDN / 图床加速

`VITE_IMAGE_BASE_URL` 只影响图片展示和预览请求。图片上传、删除仍通过 `VITE_API_BASE_URL` 访问后端，因此 CDN 只需代理公开的 GET 图片接口：

```text
客户端请求: https://img.example.com/api/v1/files/images/<file_id>?size=320
回源地址:   https://api.example.com/api/v1/files/images/<file_id>?size=320
```

建议的 CDN 规则：

- 仅代理 `GET /api/v1/files/images/*`，不要把上传和删除接口切到 CDN。
- 保留 `size` 查询参数，并将其纳入缓存键，否则不同尺寸预览会互相覆盖。
- 遵循后端返回的 `Cache-Control`；文件 ID 不变时内容不可变，适合长时间缓存。
- 转发原始路径和查询字符串，不要重写文件 ID。
- 图床域名与前端都使用 HTTPS。

如果暂时不使用图片 CDN，删除或留空 `VITE_IMAGE_BASE_URL` 即可，前端会自动从后端读取图片。

## 推荐环境划分

不同环境分别保存 CI/CD 变量，不提交真实域名配置文件：

| 环境 | `VITE_API_BASE_URL`            | `VITE_IMAGE_BASE_URL`          |
| ---- | ------------------------------ | ------------------------------ |
| 测试 | `https://api-test.example.com` | `https://img-test.example.com` |
| 生产 | `https://api.example.com`      | `https://img.example.com`      |

每套环境生成独立的 `dist` 产物，避免同一个静态包跨环境复用导致请求到错误的后端。
