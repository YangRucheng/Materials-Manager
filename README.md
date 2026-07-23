# 电气车间备件管理系统

面向电气车间二级库的库存与申购协同系统，不涉及物资价格和成本核算。

## 功能

- 维护物资档案、图片、库存余额以及入库、出库和历史流水。
- 按安全库存生成申购计划，维护物料编码并导出编码申请表和采购申请表。
- 跟踪申购、分批到货和入库进度，形成库存—申购—到货闭环。
- 提供超级管理员、仓库管理员、申购管理员和只读用户四类权限。

## 特色

- 库存流水可修正、冲销并自动重算后续余额，完整保留业务轨迹。
- 申购计划可暂缺编码，到货时可关联或新建二级库物资。
- 前后端契约统一维护在 [docs/openapi.yaml](docs/openapi.yaml)，Excel 模板和初始化数据集中在 [example](example)。
- FastAPI + SQLAlchemy 异步后端、Vue 3 + TypeScript 前端，支持 Docker 镜像部署。

## 部署

依赖 Docker Compose、外部 MySQL 8.0+ 和外部网络 `1panel-network`。配置示例、初始化
SQL 和 Excel 模板位于 `example/`；发布镜像会将模板复制到后端运行目录
`/app/data/template`。

```bash
cp example/.env.example .env
mysql -h <host> -u <user> -p <database> < example/database/init.sql
docker compose pull
docker compose up -d
```

至少设置 `APP_DATABASE_URL` 和 `APP_JWT_SECRET`。数据库结构以
`example/database/init.sql` 为准；后端只校验结构，不会在运行时创建、修改或迁移数据库表。
已有数据库的结构升级必须在部署新版本前由运维流程独立完成，并提前备份。
