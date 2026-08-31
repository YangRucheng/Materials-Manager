# internal/excel/testdata —— .xls 回归夹具

均为 xlwt（Python，BIFF8）生成的最小华星库存表，锁定 extrame/xls v0.0.1 在
华星导入（job #14）中暴露的解析缺陷及 vendored 补丁后的正确行为：

| 文件 | 覆盖场景 | 期望读取结果 |
|---|---|---|
| `huaxing_rk_formatted.xls` | RK 存储的数量、自定义数字格式 `0_);(0)`；日期单元格 `M/D/YY` | 数量 `"1"`/`"2"`；日期 `"2026-08-30"` |
| `huaxing_formula_cached.xls` | 数量与日期为 FORMULA、带 8 字节数值缓存结果（对 xlwt 产物做字节级注入，语义同 Excel 保存） | 数量 `"2"`；日期 `"2026-08-30"` |
| `huaxing_merged_title.xls` | 第 1 行为合并单元格标题、第 2 行才是表头 | 表头定位跳过标题行；数量 `"3"` |
| `huaxing_text_quantity.xls` | 数量以文本存储且带千分位 `"1,234"` | reader 原样输出 `"1,234"`，service 层 `normalizeNumberText` 清洗为 1234 |

重新生成（需 `pip install xlwt`；formula 夹具还需按 README-同级测试中注释的偏移做字节注入，
或直接复用 `git log` 中的二进制）：核心记录特征——
数量单元格走 `MULRK/RK`（XF→用户自定义 FORMAT），FORMULA 记录结果字节
`result[6:8] != FF FF` 时为小端 double 缓存值。

消费方：`reader_test.go`（reader 层）、`internal/service/huaxing_service_test.go`（端到端解析）。
