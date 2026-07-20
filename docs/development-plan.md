# 电气车间备件管理系统——开发方案

系统 Logo 统一使用 `https://cdn.micono.eu.org/icon/logo.png`。

## 1. 项目目标

系统覆盖电气车间二级库库存、申购计划、未编码物资查询、请购以及到货入库的闭环。

本项目只管理数量，不管理单价、金额、供应商、采购订单、合同和财务结算。

核心目标：

1. 库存数量只能通过入库或出库业务改变，所有变化均可追溯。
2. 库存低于安全阈值时及时预警，并能一键新增一条申购计划。
3. 未编码申购计划集中查询并直接补录编码；转入申购记录前必须具备编码。
4. 正式申购后按物资展平跟踪到货进度，并可直接发起二级库入库。
5. 前后端通过固定的 OpenAPI 契约并行开发，避免两个 agent 各自猜测字段和状态。

## 2. 边界与业务原则

### 2.1 本期范围

- 二级库物资档案
- 图片附件
- 入库、出库
- 当前库存和库存流水查询
- 安全库存配置与缺货预警
- 申购计划
- 未编码计划查询与编码补录
- 申购记录、业务员、备注和到货进度跟踪
- 请购到货关联入库
- 用户、简单角色、计量单位等基础数据

### 2.2 明确不做

- 物资成本、金额、税率和预算
- 供应商管理
- 采购订单、合同和付款
- 审批流引擎
- 库位、批次、序列号、保质期
- 盘点差异单和库存直接调整

已确认的入库、出库流水允许修改。修改数量、物资、发生时间或关联请购行时，后端必须在同一事务中重新计算受影响物资的库存余额、后续流水的前后数量，以及请购行的已到货数量，不能只修改流水表而不更新关联数据。系统也保留反向冲销作为可选处理方式。

### 2.3 两种物资必须分开

系统保留两个边界清晰的物资模型：

1. `StockMaterial`（二级库物资）：服务于库存，不要求物料编码。
2. `PurchaseMaterial`（申购计划）：每条记录代表一次申购计划，保存物资、数量、用途、可选子项号和自由文本负责人；物料编码可暂时为空，编码后可转入申购记录。

二者不能合并为一张“万能物资表”。申购物资到货时，可以关联一个已有二级库物资，也可以创建新的二级库物资。同一个二级库物资可以对应多次申购计划，同一个物料编码也可以出现在多条历史计划中。

## 3. 角色与权限

| 角色 | 主要权限 |
| --- | --- |
| 超级管理员 | 用户和基础数据维护，以及全部业务操作 |
| 仓库管理员 | 二级库物资、安全库存、入库、出库、流水修改和库存查询；可查询请购到货信息 |
| 申购管理员 | 申购计划、未编码物资编码补录、请购创建和状态处理；可查询库存信息 |
| 只读角色 | 查询库存、流水、申购计划和请购状态，不允许写入 |

本系统不建设复杂权限模型。`user` 表直接保存一个角色枚举，后端按上述四种角色做简单的读写校验，前端按角色控制菜单和操作按钮即可。

## 4. 端到端业务流程

### 4.1 已有库存物资缺货补库

1. 仓库管理员为二级库物资设置最低库存和目标库存。
2. 当前库存小于或等于最低库存时，物资进入低库存列表。
3. 系统同时计算“在途请购数量”，区分“急需申购”和“已申购待入库”，防止重复请购。
4. 用户点击“发起补库”，系统始终新增一条申购物资（申购计划），复制名称、型号规格、计量单位、备注、图片和二级库关联。
5. 如果该二级库物资过去存在带编码的申购计划，新计划可复用最近一次编码；否则保持未编码并出现在“未编码物资”列表。
6. 申购管理员在计划阶段确认数量、用途和项目并补录编码，再转入正式申购记录。
7. 到货后，仓库管理员从展平的申购记录发起入库；库存和已到货数量同步更新。

发起补库不会创建申购记录。用户确认计划数量、实际需求人和申购负责人后，系统仅新增申购计划；计划编码后可单条或批量转入正式申购记录。

### 4.2 申购全新物资

1. 申购管理员创建申购计划，填写名称、型号规格、计量单位、备注和图片。
2. 已有物料编码时直接填写；没有编码时保持为空。
3. 所有编码为空的计划统一出现在“未编码物资”页面，不生成申请号、状态或申请人数据。
4. 取得公司物料编码后，直接编辑申购计划补录编码。
5. 申购管理员创建请购草稿，填写请购单号、申请数量、用途，并按需填写子项号后提交。
6. 到货时，从请购行创建入库；首次入库需要选择已有二级库物资或创建新二级库物资，并建立关联。

### 4.3 已有编码、但二级库尚无该物资

申购管理员直接创建带编码的申购计划并加入请购单；首次到货入库时再创建二级库物资。

### 4.4 出库

仓库管理员选择物资、数量，必填领用人，可选填写子项号，确认后出库。系统允许负库存，出库数量可以超过当前库存。

## 5. 状态机

编码维护没有状态机。`material_code IS NULL` 即未编码，非空即已编码。

### 5.1 请购单

```text
DRAFT -> SUBMITTED -> PROCESSING -> PARTIALLY_RECEIVED -> COMPLETED
          |              |                 |
          v              v                 v
       RETURNED       CANCELED           CLOSED
          |
          v
       SUBMITTED
```

- `DRAFT`：草稿，可编辑表头和明细。
- `SUBMITTED`：已提请购，内容冻结。
- `PROCESSING`：申购管理员已受理。
- `RETURNED`：退回修改，可再次提交。
- `PARTIALLY_RECEIVED`：已有部分数量关联入库。
- `COMPLETED`：所有明细已全部到货入库。
- `CLOSED`：业务人工关闭，允许存在未到货数量，必须填写关闭原因。
- `CANCELED`：无到货记录时取消。

系统本期不实现通用审批流。`SUBMITTED` 表示已正式提请购，`PROCESSING` 表示相关人员已受理。

## 6. 数据库设计

技术约束：MySQL 8.0、InnoDB、`utf8mb4`。数量统一使用 `DECIMAL(18,3)`，禁止用浮点数。时间存 UTC 的 `DATETIME(6)`，API 使用带时区的 ISO 8601；前端按 `Asia/Shanghai` 展示。

所有业务表默认含：

- `id BIGINT UNSIGNED` 主键
- `created_at DATETIME(6)`
- `updated_at DATETIME(6)`
- `created_by BIGINT UNSIGNED`
- `updated_by BIGINT UNSIGNED`
- `version INT UNSIGNED`，用于乐观锁

### 6.1 基础表

#### `user`

`username`、`password_hash`、`display_name`、`role`、`enabled`。`role` 取值为 `SUPER_ADMIN`、`WAREHOUSE_ADMIN`、`PURCHASE_ADMIN`、`READ_ONLY`，一个用户只配置一个角色。生产环境可以以后替换为企业 SSO。

#### `measurement_unit`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `code` | VARCHAR(32) | 唯一、必填 |
| `name` | VARCHAR(32) | 唯一、必填 |
| `decimal_places` | TINYINT UNSIGNED | 0~3，默认 0 |
| `enabled` | BOOLEAN | 默认 true |

### 6.2 图片附件

#### `file_object`

图片统一保存在后端 `data/uploads/` 目录，不在 MySQL 中保存二进制。上传后使用 Pillow 解码并转换为 PNG，移除原图片元数据，再以可按字符串排序的 UUIDv7 作为主键和文件名。不能只修改扩展名而保留原编码格式。

数据库保存：文件 `id`、`original_name`、`mime_type`、`size_bytes`、`width`、`height`、`sha256`。业务附件表只保存 `file_id`；图片接口地址及磁盘文件名均由 `file_id` 推导，不持久化域名或路径，`mime_type` 固定为 `image/png`。

上传入口可接受 `image/jpeg`、`image/png`、`image/webp`；单图建议不超过 10 MB，每个物资最多 9 张。应用启动时自动确保 `backend/data/uploads/` 存在。图片读取无需鉴权，并可通过 `size` 指定最大边长，按比例生成 WebP 预览以降低传输量。

通过 `stock_material_image` 和 `purchase_material_image` 两张关联表绑定图片，字段为 `material_id`、`file_id`、`sort_order`，从而保留外键完整性。

### 6.3 二级库域

#### `stock_material`

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| `name` | VARCHAR(128) | 必填，去除首尾空格 |
| `model_spec` | VARCHAR(255) | 必填；无型号时明确填写“无” |
| `unit_id` | BIGINT UNSIGNED | 必填，外键 |
| `remark` | VARCHAR(1000) | 可空 |
| `identity_hash` | CHAR(64) | 名称、规格、单位规范化后生成，唯一 |
| `enabled` | BOOLEAN | 默认 true；有流水后只能停用，不能删除 |

此模型按要求不包含物料编码。API 返回 `images` 和当前库存等聚合字段，但这些不是本表字段。

#### `stock_replenishment_policy`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `stock_material_id` | BIGINT UNSIGNED | 主键、外键 |
| `minimum_qty` | DECIMAL(18,3) | >= 0 |
| `target_qty` | DECIMAL(18,3) | >= minimum_qty |
| `enabled` | BOOLEAN | 默认 true |

安全库存独立于物资基础信息，满足“关注缺货及时申购”，又不改变用户指定的二级库物资核心模型。

#### `stock_balance`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `stock_material_id` | BIGINT UNSIGNED | 主键、外键 |
| `quantity` | DECIMAL(18,3) | 可为负数 |
| `version` | INT UNSIGNED | 并发控制 |
| `updated_at` | DATETIME(6) | 必填 |

余额是查询加速数据，库存流水是审计依据。禁止提供直接更新余额的接口。

#### `stock_operation`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `operation_no` | VARCHAR(32) | 唯一业务号，如 `IN202607170001` |
| `operation_type` | ENUM | 仅 `INBOUND`、`OUTBOUND` |
| `occurred_at` | DATETIME(6) | 实际发生时间 |
| `operator_id` | BIGINT UNSIGNED | 操作人 |
| `business_reason` | VARCHAR(500) | 必填 |
| `receiver_name` | VARCHAR(64) | 出库时必填 |
| `subitem_no` | VARCHAR(64) | 出库时可选、直接填写 |
| `source_type` | ENUM | `MANUAL`、`PURCHASE_RECEIPT`、`REVERSAL`、`INITIALIZATION` |
| `reversal_of_id` | BIGINT UNSIGNED | 冲销时关联原流水 |
| `client_request_id` | VARCHAR(64) | 唯一，防止重复提交 |

`INITIALIZATION` 仍然是一笔入库，不允许绕过流水直接设置初始库存。

#### `stock_operation_line`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `operation_id` | BIGINT UNSIGNED | 外键 |
| `stock_material_id` | BIGINT UNSIGNED | 外键 |
| `quantity` | DECIMAL(18,3) | 必须 > 0 |
| `before_qty` | DECIMAL(18,3) | 操作前数量快照 |
| `after_qty` | DECIMAL(18,3) | 操作后数量快照 |
| `material_name_snapshot` | VARCHAR(128) | 历史快照 |
| `model_spec_snapshot` | VARCHAR(255) | 历史快照 |
| `unit_name_snapshot` | VARCHAR(32) | 历史快照 |
| `purchase_request_line_id` | BIGINT UNSIGNED | 到货入库时可关联 |

唯一约束：`(operation_id, stock_material_id)`，同一单据中同一物资只能出现一次。

### 6.4 申购域

#### `purchase_material`

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| `plan_no` | VARCHAR(32) | 唯一业务 ID，格式 `PLAN-YYYYMMDD-001`，序号按计划日期递增 |
| `plan_date` | DATE | 必填；转入申购记录后仍通过原计划保留 |
| `material_code` | VARCHAR(64) | 可空；同一编码可出现在多次申购计划中 |
| `name` | VARCHAR(128) | 必填 |
| `model_spec` | VARCHAR(255) | 必填 |
| `unit_id` | BIGINT UNSIGNED | 必填，外键 |
| `subitem_no` | VARCHAR(64) | 可空、直接填写 |
| `remark` | VARCHAR(1000) | 可空 |
| `stock_material_id` | BIGINT UNSIGNED | 可空，关联二级库物资；允许多个计划关联同一物资 |
| `identity_hash` | CHAR(64) | 用于重复物资提示，不强制阻止不同编码 |
| `enabled` | BOOLEAN | 默认 true |

是否已有编码直接判断 `material_code` 是否为空，不设置重复的编码状态字段。未编码查询条件就是 `material_code IS NULL`。

#### `purchase_request`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `purchase_order_no` | VARCHAR(128) | 申购单号，可空、可编辑；界面默认“申购 年/月/日” |
| `trace_no` | VARCHAR(128) | 追溯号，可空、可编辑 |
| `status` | ENUM | 见状态机 |
| `applicant_id` | BIGINT UNSIGNED | 申请人 |
| `handler_id` | BIGINT UNSIGNED | 受理人，可空 |
| `remark` | VARCHAR(1000) | 可空 |
| `return_reason` | VARCHAR(500) | 退回时必填 |
| `close_reason` | VARCHAR(500) | 关闭时必填 |
| `purchase_date` | DATE | 申购日期，可空、可编辑 |
| `completed_at` | DATETIME(6) | 可空 |

#### `purchase_request_line`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `purchase_request_id` | BIGINT UNSIGNED | 外键 |
| `purchase_material_id` | BIGINT UNSIGNED | 外键 |
| `material_code_snapshot` | VARCHAR(64) | 提交时必填 |
| `material_name_snapshot` | VARCHAR(128) | 必填 |
| `model_spec_snapshot` | VARCHAR(255) | 必填 |
| `unit_name_snapshot` | VARCHAR(32) | 必填 |
| `requested_qty` | DECIMAL(18,3) | 必须 > 0 |
| `received_qty` | DECIMAL(18,3) | 默认 0、不得小于 0；允许大于 `requested_qty` |
| `usage` | VARCHAR(500) | 必填 |
| `subitem_no` | VARCHAR(64) | 可空、直接填写 |

同一请购单中相同“申购物资 + 子项号 + 用途”应合并为一行。

### 6.5 缺货计算

不额外保存预警表，查询时计算：

```text
on_order_qty = 已提交、处理中、部分到货的请购行之和(requested_qty - received_qty)
is_low_stock = current_qty <= minimum_qty
suggested_purchase_qty = max(target_qty - current_qty - on_order_qty, 0)
```

展示状态：

- 当前库存低且 `on_order_qty = 0`：`急需申购`
- 当前库存低且 `on_order_qty > 0`：`已申购待入库`
- 建议数量为 0：不再提示重复发起，但仍显示库存低和在途数量

## 7. 后端技术方案

### 7.1 技术栈

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x async ORM
- `asyncmy` MySQL 驱动
- `example/database/init.sql` 空库初始化
- JWT access token；密码使用 Argon2
- Pillow，用于校验图片并统一转换为 PNG
- pytest、pytest-asyncio、httpx
- Ruff、mypy

### 7.2 目录建议

```text
backend/
  app/
    main.py
    api/v1/
      auth.py
      stock_materials.py
      inventory.py
      purchase_materials.py
      purchase_requests.py
      dictionaries.py
      files.py
    core/
      config.py
      database.py
      security.py
      errors.py
      permissions.py
    domain/
      enums.py
    models/
    schemas/
    repositories/
    services/
      inventory_service.py
      replenishment_service.py
      purchase_request_service.py
      file_service.py
    migrations/
  tests/
    unit/
    integration/
  pyproject.toml
  alembic.ini
```

路由只做参数解析、鉴权和响应转换；业务状态转换、库存锁定、入库回写请购等逻辑必须放在 service 层。repository 负责查询，不承载业务规则。

### 7.3 Pydantic 模型规范

- `Create`、`Update`、`Read`、`ListItem` 分离，禁止一个 Schema 同时用于创建和响应。
- 请求模型使用 `extra='forbid'`，拒绝未知字段。
- 数量使用 `Decimal`，并校验大于 0、最多 3 位小数。
- 枚举在后端集中定义，OpenAPI 输出字符串枚举。
- 更新接口携带 `version`，版本冲突返回 HTTP 409。
- 提交、受理、完成、退回等动作使用显式 action endpoint，不允许通过通用 PATCH 任意修改状态。

### 7.4 事务与并发

入库或出库必须在单个数据库事务中完成：

1. 按 `stock_material_id` 升序锁定所有 `stock_balance` 行（`SELECT ... FOR UPDATE`），避免死锁。
2. 校验物资启用和单位数量精度；允许出库后为负库存。
3. 写入操作单和明细，记录操作前后数量。
4. 更新余额。
5. 若为请购到货，锁定请购行并更新 `received_qty`，再重算请购单状态。
6. 提交事务。

每个入出库请求必须带 `client_request_id`。重复请求返回第一次创建的结果，不能再次扣加库存。

#### 已确认流水修改规则

仓库管理员和超级管理员可以修改已确认流水。可修改字段包括：入/出库类型、发生时间、业务原因、领用人、可选子项号、物资明细、数量、来源类型和关联请购行；流水号、首次创建人、首次创建时间和 `client_request_id` 为系统字段，不允许修改。

修改必须作为一个完整事务执行：

1. 根据旧明细和新明细收集全部受影响的二级库物资、请购行并按 ID 升序加锁。
2. 撤销旧流水对关联请购行 `received_qty` 的影响。
3. 保存新内容，然后按 `occurred_at, operation_id` 顺序重新计算受影响物资全部流水的 `before_qty`、`after_qty` 和最终 `stock_balance.quantity`。
4. 允许重算结果为负库存，也允许累计到货量超过请购数量；到货达到或超过申请数量时请购状态为 `COMPLETED`。
5. 重新累计受影响请购行的到货数量，并更新请购单的部分到货/完成状态。
6. 在 `business_event_log` 保存修改前后 JSON、修改人和修改时间，然后提交事务。

二级库规模较小，本期优先采用“对受影响物资重放全部流水”的清晰实现，避免增量修补导致历史前后数量不一致。后续只有在实际数据量证明存在性能问题时再优化。

### 7.5 API 返回约定

成功响应直接返回资源；列表统一为：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

错误统一为：

```json
{
  "code": "MATERIAL_CODE_REQUIRED",
  "message": "请购明细存在无编码物资",
  "details": {"lines": [{"line_no": 1, "purchase_material_id": 12}]},
  "request_id": "..."
}
```

重点错误码：`VERSION_CONFLICT`、`DUPLICATE_MATERIAL`、`MATERIAL_CODE_REQUIRED`、`INVALID_STATUS_TRANSITION`、`NEGATIVE_RECEIPT`、`IDEMPOTENCY_CONFLICT`。

## 8. API 契约

统一前缀 `/api/v1`。

### 8.1 二级库物资与库存

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/stock-materials` | 按名称、型号、启用状态查询物资 |
| POST | `/stock-materials` | 创建物资 |
| GET | `/stock-materials/{id}` | 详情，含图片、余额和补库策略 |
| PATCH | `/stock-materials/{id}` | 修改基础信息，不允许改库存 |
| POST | `/stock-materials/{id}/disable` | 停用 |
| PUT | `/stock-materials/{id}/replenishment-policy` | 设置最低/目标库存 |
| GET | `/inventory/balances` | 库存查询，支持名称、型号、库存范围、低库存筛选 |
| GET | `/inventory/low-stock` | 低库存与在途数量列表 |
| POST | `/inventory/inbounds` | 入库 |
| POST | `/inventory/outbounds` | 出库 |
| POST | `/inventory/operations/{id}/reverse` | 以反向流水冲销 |
| GET | `/inventory/operations` | 查询操作记录 |
| GET | `/inventory/operations/{id}` | 流水详情 |
| PATCH | `/inventory/operations/{id}` | 修改已确认流水并重算余额、后续快照和关联请购到货数量 |
| POST | `/inventory/low-stock/{material_id}/create-replenishment-draft` | 新增一条申购物资（申购计划），不创建请购单 |

入库请求示例：

```json
{
  "client_request_id": "2b7f1b69-2bcc-45da-8d72-2e1f8d889ec8",
  "occurred_at": "2026-07-17T10:30:00+08:00",
  "source_type": "PURCHASE_RECEIPT",
  "business_reason": "请购物资到货",
  "lines": [
    {
      "stock_material_id": 10,
      "quantity": "5",
      "purchase_request_line_id": 31
    }
  ]
}
```

### 8.2 申购计划与编码维护

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET/POST | `/purchase-materials` | 查询/创建申购计划；`coded=false` 查询未编码数据 |
| GET/PATCH | `/purchase-materials/{id}` | 详情/修改 |
| DELETE | `/purchase-materials/{id}` | 删除尚未转入申购记录的计划 |
| POST | `/purchase-materials/{id}/link-stock-material` | 关联二级库物资 |
| GET | `/purchase-materials/export-uncoded` | 按当前关键词导出未编码物资的物料编码申请表 |
| POST | `/purchase-materials/export-purchase-application` | 按所选计划导出采购申请表 |
| POST | `/purchase-materials/batch-move-to-record` | 将多条已编码计划批量转为同一批申购记录 |

Excel 布局示例位于 `example/template/*.json`，部署时复制到运行目录的
`data/template/`，运行时生成工作簿；仓库不保存原始 XLSX 模板。

补录编码直接修改申购计划：

```json
{
  "material_code": "DQ-000123",
  "name": "交流接触器",
  "model_spec": "CJX2-2510 220V",
  "unit_id": 1,
  "image_ids": [],
  "version": 2
}
```

### 8.3 请购

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET/POST | `/purchase-requests` | 查询/创建请购草稿 |
| GET/PATCH | `/purchase-requests/{id}` | 详情/修改草稿或退回单 |
| POST | `/purchase-requests/{id}/submit` | 提交，逐行校验物料编码 |
| POST | `/purchase-requests/{id}/accept` | 受理 |
| POST | `/purchase-requests/{id}/return` | 退回 |
| POST | `/purchase-requests/{id}/cancel` | 取消无到货单据 |
| POST | `/purchase-requests/{id}/close` | 关闭，必须填写原因 |
| GET | `/purchase-requests/{id}/receipts` | 查询关联入库记录 |
| POST | `/purchase-request-lines/{id}/prepare-inbound` | 返回入库预填数据，首次到货提示关联/创建二级库物资 |

创建请购草稿：

```json
{
  "purchase_order_no": "申购 2026/7/17",
  "trace_no": null,
  "purchase_date": "2026-07-17",
  "remark": "7 月检修备件",
  "lines": [
    {
      "purchase_material_id": 21,
      "requested_qty": "10",
      "usage": "1# 机组控制柜检修备用",
      "subitem_no": "01-01"
    }
  ]
}
```

草稿允许暂时没有编码，但 `/submit` 必须拒绝任何无编码明细，并返回具体行号和申购物资 ID。

### 8.4 文件与字典

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/files/images` | 上传并转换为 `data/uploads/{uuid7}.png`，数据库提交后返回文件元数据（不返回持久化 URL） |
| GET | `/files/images/orphans` | 超级管理员排查超过保护期的未引用记录、无记录磁盘文件和磁盘缺失记录 |
| DELETE | `/files/images/orphans` | 超级管理员清理超过保护期的未引用记录和无记录磁盘文件 |
| GET | `/files/images/{id}` | 公开读取图片；可传 `size=16..2048` 获取等比例 WebP 预览 |
| DELETE | `/files/images/{id}` | 删除尚未被业务引用的图片 |
| GET | `/measurement-units` | 计量单位下拉选项 |
| GET | `/dashboard/summary` | 库存总项数、低库存、待编码、待处理请购统计 |

## 9. 前端方案

### 9.1 技术栈

- Vue 3 + TypeScript + Vite
- Vue Router
- Naive UI
- Pinia
- Axios
- `@vueuse/core`
- Vitest + Vue Test Utils
- ESLint + Prettier

前端数量字段始终按字符串传给后端，避免 JavaScript 浮点误差。后端 OpenAPI 定稿后，用 `openapi-typescript` 生成接口类型；页面不得私自复制一套不一致的 DTO。

### 9.2 路由与页面

```text
/login
/dashboard
/warehouse/materials
/warehouse/materials/:id
/warehouse/inbound
/warehouse/outbound
/warehouse/stock
/warehouse/operations
/warehouse/operations/:id
/procurement/materials
/procurement/materials/:id
/procurement/uncoded-materials
/procurement/requests
/procurement/requests/new
/procurement/requests/:id
/settings/units
/settings/users
```

### 9.3 页面要点

#### 工作台

- 低库存数量、急需申购数量、已申购待入库数量
- 未编码申购计划数量
- 待处理请购、部分到货请购
- 快捷入口：入库、出库、新物资申购、低库存补库

#### 库存查询

表格列：物资名称、型号规格、单位、当前库存、最低库存、目标库存、在途数量、预警状态、更新时间、操作。

行操作：查看详情、入库、出库、发起补库。发起补库成功后跳转到新建的申购计划详情，不跳转请购单。

#### 入库/出库

- 支持一张单多行物资。
- 数量输入根据计量单位限制小数位数。
- 出库即时显示当前库存和出库后库存，允许显示负数并正常提交。
- 从请购进入入库时预填物资、剩余未到数量、来源单号。
- 首次到货若未关联二级库物资，弹窗提供“关联已有物资”和“新建二级库物资”两条路径。
- 提交按钮在请求期间禁用，并使用 UUID 作为 `client_request_id`。

#### 操作记录

可按流水号、入/出库类型、物资名称、操作人、日期范围、来源请购单筛选。详情展示前后库存、原因、来源和冲销关系；仓库管理员和超级管理员可进入编辑模式。保存前提示“修改流水将重新计算库存及关联请购到货数量”，保存成功后刷新受影响的库存和后续流水。

#### 申购物资

列表显示物料编码、名称、规格、单位和关联二级库物资。每次补库都新增一条计划，同一编码和二级库物资可以重复出现。

#### 未编码物资

页面调用 `/purchase-materials?coded=false`，只展示物料编码为空的申购计划。没有申请号、申请人、状态或单独的编辑按钮；点击物资名称进入可直接编辑保存的申购计划详情页。

#### 请购编辑页

请购单号默认按上海日期生成 `申购单-{y}年{m}月{d}日`（例如 `申购单-2026年7月17日`），可由用户改成公司系统单号。每行选择申购物资、数量、用途，并可直接填写子项号；无编码计划允许保存草稿，但提交前统一校验。

#### 请购详情

展示申请数量、已到数量、未到数量、用途、可选子项号、物料快照和关联入库记录。允许从未到货行发起入库。

### 9.4 前端目录建议

```text
frontend/
  src/
    api/
      client.ts
      generated.ts
      inventory.ts
      procurement.ts
    router/
    stores/
      auth.ts
      dictionaries.ts
    layouts/
    views/
      dashboard/
      warehouse/
      procurement/
      settings/
    components/
      ImageUploader.vue
      MaterialSelector.vue
      QuantityInput.vue
      StatusSteps.vue
      OperationLinesEditor.vue
    composables/
    types/
    utils/
```

## 10. 审计、安全和可运维性

- 所有状态变化写入 `business_event_log`：业务类型、业务 ID、动作、原状态、新状态、操作者、时间、备注。
- 已确认库存流水允许修改，修改前后的内容写入 `business_event_log`，便于排查库存变化。
- 图片统一转换为 PNG 并以服务端生成的 UUID 命名；文件名、扩展名和 MIME 类型不能直接信任客户端。
- 记录 `request_id`，应用日志中包含用户、接口、耗时和错误码，但不记录密码/token。
- 查询接口强制分页，默认 20，最大 200。
- 模糊搜索字段建立合适索引；业务号、物料编码、状态和时间建立组合索引。
- 每日备份 MySQL 和 `backend/data/uploads/`，两者保持同一保留周期。

## 11. 两个 agent 的并行开发边界

### 11.1 开工前共同冻结

第一天先固定以下内容并提交到仓库：

1. 枚举值和状态流转表。
2. 本文第 8 节的 URL、请求体、响应体和错误体。
3. OpenAPI 文件 `docs/openapi.yaml`。
4. 统一的分页、时间、Decimal 字符串、错误码规则。
5. 10~20 条用于前后端联调的种子数据。

### 11.2 后端 agent

负责 `backend/`、`docs/openapi.yaml` 和 `docker-compose.yml`：

1. 项目脚手架、认证和四角色简单校验。
2. SQLAlchemy 模型、`example/database/init.sql` 和种子数据。
3. 二级库物资、库存余额和流水事务。
4. 安全库存与缺货计算。
5. 申购计划、未编码查询和编码直接补录。
6. 请购状态机和到货入库闭环。
7. `data/uploads/{uuid}.png` 图片转换、保存和读取。
8. 单元测试、集成测试、OpenAPI 更新。

### 11.3 前端 agent

负责 `frontend/`：

1. Vue3/Vite/Router/Naive UI/Pinia 脚手架。
2. 登录、布局和四角色菜单。
3. 依据 `docs/openapi.yaml` 生成类型。
4. 二级库物资、库存、入出库和流水页面。
5. 低库存工作台与补库入口。
6. 申购计划、未编码物资、请购页面。
7. 图片上传和预览。
8. 先使用 Mock Service Worker 基于契约开发，后切换真实 API。

前端 agent 不修改后端业务枚举；后端 agent 如果变更契约，必须同时更新 OpenAPI 并明确通知前端。

## 12. 测试重点

### 12.1 后端必须覆盖

- 同一物资并发出库不会丢失扣减，允许最终库存为负。
- 重复 `client_request_id` 不会重复入库或出库。
- 入库、出库、修改流水、冲销后的余额和流水一致。
- 修改历史流水后，受影响的后续 `before_qty`、`after_qty` 和当前余额正确重算。
- 修改请购到货入库流水后，请购行 `received_qty` 和请购状态正确重算。
- 无编码明细可以保存请购草稿，但不能提交。
- `coded=false` 只返回物料编码为空的申购计划，补录后立即移出该列表。
- 同一物料编码和同一二级库物资允许出现在多条申购计划中。
- 请购部分到货、全部到货和人工关闭状态正确。
- 到货数量可以超过请购数量，累计到货达到或超过申请数量时状态为已完成。
- 停用物资不能新增入出库业务。
- 只读角色写入返回 403；其余角色按仓库域和申购域做简单校验。

### 12.2 前端必须覆盖

- 四种角色对应的菜单和动作按钮。
- Decimal 字符串不会被错误转成浮点数。
- 出库后库存为负数时允许提交，并清晰显示负数结果。
- 无编码请购行的提交拦截和跳转编辑。
- 图片类型、大小、数量限制。
- 退回单可编辑，已提交单只读。
- 重复点击提交不会生成重复流水。

## 13. MVP 验收标准

1. 能维护两种独立物资和各自图片，字段符合需求。
2. 二级库没有“直接输入库存余额”的入口；库存由入库、出库流水计算，已确认流水允许编辑并自动重算余额。
3. 任意库存变化都能查到操作人、时间、原因、前后数量。
4. 系统允许负库存；并发出库不会丢失任何一笔扣减。
5. 低库存页能显示当前库存、最低/目标库存、在途数量和建议申购数量。
6. 未编码计划可直接查询和补录编码，不存在编码申请号、状态和申请人；请购提交时仍校验编码非空。
7. 请购每行都具备物料编码、申请数量和用途，子项号可选并直接填写。
8. 请购到货可直接创建入库，并正确更新库存和到货状态。
9. 前端所有主要页面可在 1366×768 下正常使用，表格支持分页和筛选。
10. `docker compose up` 可启动后端和前端；重建数据库及导入初始化脚本有明确命令。

## 14. 推荐实施顺序

1. 冻结枚举、OpenAPI 和数据库初始化脚本。
2. 完成登录、基础字典和两种物资档案。
3. 完成库存余额、入库、出库、流水编辑和并发测试。
4. 完成安全库存和低库存预警。
5. 完成申购计划、未编码查询和编码补录。
6. 完成请购状态机。
7. 完成请购到货入库闭环。
8. 补充修改日志、四角色校验、异常场景、端到端测试和部署说明。

这个顺序能尽早锁定最有风险的库存一致性，同时让两个 agent 从第一天起就能依靠同一份接口契约并行工作。
