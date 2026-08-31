# third_party/extrame-xls —— 带补丁的 extrame/xls v0.0.1

本目录是 [github.com/extrame/xls](https://github.com/extrame/xls) `v0.0.1`（Apache-2.0，
LICENSE 随附于本目录）的 **修改副本**，通过 `server/go.mod` 的
`replace github.com/extrame/xls => ./third_party/extrame-xls` 生效。
按 Apache-2.0 §4(b) 要求声明修改如下。

## 为什么要打补丁（背景）

Go 重构（#233）把 xls 读取从 Python xlrd 换成了 extrame/xls。xlrd 返回**原生值**
（数字就是数字、日期按 XF 格式给出 datetime），而 extrame/xls v0.0.1 返回**格式化显示串**，
且格式化实现有缺陷，导致华星库存导入回归（job #14：`HUAXING_IMPORT_INVALID_QUANTITY`
"第 2 行数量不是有效数值"，实际单元格是数字 1）：

1. `XfRk.String`：把所有 XF 用户自定义格式（fNo≥164，含导出工具注册的 "General"）
   的 RK/MULRK **数字**一律按日期渲染成 `"1899-12-31T00:00:00Z"` 串；内置日期格式又渲染成
   `"2006.01"`（丢天）。→ 数量解析失败、日期静默丢失。
2. `NumberCol.String`：完全忽略数字格式，日期格式的 NUMBER 单元格输出序列值（如 `"46264"`）。
3. `FormulaCol`：把 `Col` 嵌在命名结构体字段 `Header` 里，`FirstCol/LastCol/Row`
   方法没有提升到 `FormulaCol` 上，`worksheet.add` 的类型断言永远失败 → **公式单元格被静默丢弃**；
   即便可达也只返回字面量 `"FormulaCol"`，不读 8 字节缓存结果。
4. `RK.number`：整数分支把无符号右移结果直接当有符号数（**负数解码成巨大正数**），
   且漏掉「整数 ×1/100」组合。
5. `WorkSheet.Row`：对不存在的行做 `row.wb = ...`，稀疏工作表（无 ROW 记录的行）**panic**。

## 修改清单

- `cell_format.go`（新增）：按格式串本身判别 数字/日期/时间（思路等价 xlrd），
  数字一律输出原始值；日期输出 `2006-01-02`（带时间则附 ` 15:04:05`，纯时间输出 `15:04:05`）。
- `col.go`：
  - `XfRk.String` / `NumberCol.String` 接入上述格式判别；
  - `RK.number` 修正有符号解码与 整数×1/100；
  - `FormulaCol` 补齐 `Row/FirstCol/LastCol`（修复被静默丢弃的问题），并按 xlrd 语义
    解码 8 字节缓存结果（数值 double / 布尔 / 错误 / 字符串；字符串值来自后续 STRING 记录）。
- `worksheet.go`：FORMULA 后接的 `STRING(0x0207)` 记录解析（`parseBiff8String`，兼容
  Excel 实际布局与 OOo 文档布局）；`WorkSheet.Row` nil 守卫。
- `patch_test.go`（新增）：锁定以上补丁行为的单元测试。

数量/日期的进一步容错（千分位、全角数字等文本清洗）在
`internal/service/huaxing_service.go` 的 `normalizeNumberText` 中完成，不在本库内。

## 测试

本目录是独立 Go module，不在主模块 `./...` 范围内：

```bash
cd server/third_party/extrame-xls && go test ./...
```

端到端回归见 `server/internal/excel/reader_test.go` 与
`server/internal/service/huaxing_service_test.go`（fixture：`internal/excel/testdata/`）。
