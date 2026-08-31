-- 20260831 扩展 material_code 列长度：64→128，适配华星库存导入中较长的货品编码
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：ALTER TABLE MODIFY COLUMN 可重复执行。

ALTER TABLE `material_code_library`
  MODIFY COLUMN `material_code` VARCHAR(128) NOT NULL;

ALTER TABLE `huaxing_inventory`
  MODIFY COLUMN `material_code` VARCHAR(128) NULL;

ALTER TABLE `purchase_material`
  MODIFY COLUMN `material_code` VARCHAR(128) NULL;

ALTER TABLE `purchase_plan_template`
  MODIFY COLUMN `material_code` VARCHAR(128) NULL;

ALTER TABLE `purchase_request_line`
  MODIFY COLUMN `material_code_snapshot` VARCHAR(128) NULL;