-- 20260813 新增华星库存表（二级库菜单，华星平台库存报表全量导入、只读）
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：CREATE TABLE IF NOT EXISTS。
CREATE TABLE IF NOT EXISTS `huaxing_inventory` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `first_inbound_date` DATE NULL,
  `warehouse` VARCHAR(128) NULL,
  `material_code` VARCHAR(64) NULL,
  `name` VARCHAR(255) NULL,
  `model_spec` VARCHAR(255) NULL,
  `quantity` DECIMAL(18, 2) NULL,
  `unit_name` VARCHAR(32) NULL,
  `purchaser` VARCHAR(128) NULL,
  `purchase_department` VARCHAR(128) NULL,
  `subitem_no_name` VARCHAR(255) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_huaxing_inventory` PRIMARY KEY (`id`),
  INDEX `ix_huaxing_inventory_name` (`name`),
  INDEX `ix_huaxing_inventory_model_spec` (`model_spec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
