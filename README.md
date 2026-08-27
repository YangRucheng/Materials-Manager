# 电气车间备件管理系统

面向电气车间二级库的库存与申购协同系统，不涉及物资价格和成本核算。

## 特色

- 库存流水可修正、冲销并自动重算后续余额，完整保留业务轨迹。
- 申购计划可暂缺编码，到货时可关联或新建二级库物资。
- 前后端契约统一维护在 [docs/openapi.yaml](docs/openapi.yaml)，Excel 模板随后端代码版本管理，初始化数据集中在 [example](example)。
- FastAPI + SQLAlchemy 异步后端、Vue 3 + TypeScript 前端，支持 Docker 镜像部署。

## 小程序功能开关

小程序首页各功能（二级库库存 / 华星总库存 / 申购计划 / 申购记录 / 物料编码）支持开关控制，
开关值在管理后台「高级设置」配置，小程序启动时拉取：

- 二级库库存：`禁用` / `仅查询` / `可读写`（仅 `可读写` 允许扫码出库）。
- 其余四项：`禁用` / `仅查询`（本身只读）。

这些开关**仅在小程序前端做展示与跳转拦截**（属体验层控制），后端数据接口不做对应鉴权，不是安全边界。

## 二级库模式（高级设置）

「高级设置」提供二级库**完整模式 / 精简模式**切换（默认完整模式）：

- **完整模式**：二级库支持物资档案、库存、出入库与操作记录，数据存完整模式表
  （`stock_material` / `stock_balance` / `stock_operation` 等）。
- **精简模式**（独立数据库表 `lite_inventory`，与完整模式数据完全隔离，可随时切回）：
  - 小程序端二级库库存**仅可查看**，不支持扫码出库/出入库（按模式调用
    `/mini-program/lite-inventory` 等精简接口；后端出库接口同样拦截）。
  - 后台「二级库」tab 变为单一一级 tab，与「华星总库存」一致：仅 Excel 一次性全量导入
    + 只读查询；完整模式写接口（入库/出库/物资档案/操作记录/补库）返回 403。
  - 工作台「二级库物资」统计改读精简表。

与「小程序功能开关」不同，二级库模式是**系统级行为**（后台写接口与小程序出库在后端一并拦截），
属于功能边界而非仅体验层控制。

## 部署

前端由独立 CI/CD 构建并与后端分离部署时，参见 [前后端分离部署](docs/frontend-separated-deployment.md)，通过构建变量注入后端和图片 CDN 地址。

Docker Compose 方案依赖外部 MySQL 8.0+ 和外部网络 `1panel-network`。配置示例、初始化
SQL 位于 `example/`；Excel 模板位于 `backend/app/templates/`，随代码一同构建和发布。

```bash
cp example/.env.example .env
mysql -h <host> -u <user> -p <database> < example/database/init.sql
docker compose pull
docker compose up -d
```

至少设置 `APP_DATABASE_URL` 和 `APP_JWT_SECRET`；启用扫码出库小程序时还需设置
`APP_WECHAT_MINI_PROGRAM_APP_ID` 和 `APP_WECHAT_MINI_PROGRAM_APP_SECRET`。多个小程序分别在
这两个变量中按相同顺序用英文逗号分隔，可追加任意数量；管理后台会按 AppID 分开记录微信
身份，并可人工合并属于同一人员的账号。
`example/database/init.sql` 仅用于初始化
新数据库；已有数据库升级前先备份，再执行
对应的 `example/database/migrations/` 脚本。接口令牌功能需要执行
`20260804_add_user_api_token.sql`；令牌哈希化升级执行 `20260820_hash_user_api_token.sql`；
多小程序升级使用 `upgrade-multi-miniprogram.sql`，并将脚本中的
原小程序 AppID 替换为真实值。20260820 批次还包含
`20260820_add_system_setting.sql`（AI 搜索配置迁移到独立表）、
`20260820_narrow_purchase_request_line_unique.sql`（申购记录唯一索引收窄为 usage 哈希）与
`20260820_drop_redundant_indexes.sql`（删除仅被前导通配 LIKE 查询的无效索引）。
链接分享功能需要执行 `20260821_add_share_link.sql`（新增匿名分享链接表）。
