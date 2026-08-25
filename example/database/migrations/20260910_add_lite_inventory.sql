-- 20260910 精简二级库独立表：二级库处于「精简模式」时的 Excel 一次性导入 + 只读查询。
-- 与完整模式（stock_material / stock_balance / stock_operation 等）完全隔离。
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：CREATE TABLE IF NOT EXISTS。
CREATE TABLE IF NOT EXISTS `lite_inventory` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(128) NOT NULL,
  `model_spec` VARCHAR(255) NULL,
  `unit_name` VARCHAR(32) NULL,
  `quantity` DECIMAL(18, 2) NULL,
  `remark` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_lite_inventory` PRIMARY KEY (`id`),
  INDEX `ix_lite_inventory_name` (`name`),
  INDEX `ix_lite_inventory_model_spec` (`model_spec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
