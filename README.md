# 电气车间备件管理系统

面向电气车间二级库的库存与申购协同系统，不涉及物资价格和成本核算。

## 特色

- 库存流水可修正、冲销并自动重算后续余额，完整保留业务轨迹。
- 申购计划可暂缺编码，到货时可关联或新建二级库物资。
- 前后端契约统一维护在 [docs/openapi.yaml](docs/openapi.yaml)，Excel 模板随后端代码版本管理，初始化数据集中在 [example](example)。
- FastAPI + SQLAlchemy 异步后端、Vue 3 + TypeScript 前端，支持 Docker 镜像部署。

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
