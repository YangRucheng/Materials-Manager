-- 周期性计划（申购计划模板）：新增模板表与镜像表
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：CREATE TABLE IF NOT EXISTS，可重复执行。
CREATE TABLE IF NOT EXISTS `purchase_plan_template` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `material_code` VARCHAR(64) NULL,
  `category` VARCHAR(64) NULL,
  `urgency` VARCHAR(32) NOT NULL DEFAULT '正常',
  `demand_department` VARCHAR(128) NOT NULL DEFAULT 'HXNI 检修维护部',
  `name` VARCHAR(128) NOT NULL,
  `model_spec` VARCHAR(255) NOT NULL,
  `unit_name` VARCHAR(32) NOT NULL,
  `actual_demand_person` VARCHAR(128) NOT NULL,
  `purchase_responsible` VARCHAR(128) NOT NULL,
  `planned_qty` DECIMAL(18, 1) NOT NULL,
  `usage` VARCHAR(500) NOT NULL,
  `subitem_no` VARCHAR(64) NULL,
  `remark` VARCHAR(1000) NULL,
  `stock_material_id` BIGINT UNSIGNED NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_plan_template` PRIMARY KEY (`id`),
  CONSTRAINT `fk_purchase_plan_template_stock_material_id_stock_material`
    FOREIGN KEY (`stock_material_id`) REFERENCES `stock_material` (`id`),
  INDEX `ix_purchase_plan_template_stock_material_id` (`stock_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_plan_template_image` (
  `plan_id` BIGINT UNSIGNED NOT NULL,
  `file_id` VARCHAR(36) NOT NULL,
  `sort_order` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  CONSTRAINT `pk_purchase_plan_template_image` PRIMARY KEY (`plan_id`, `file_id`),
  CONSTRAINT `fk_purchase_plan_template_image_plan_id_purchase_plan_template`
    FOREIGN KEY (`plan_id`) REFERENCES `purchase_plan_template` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_purchase_plan_template_image_file_id_file_object`
    FOREIGN KEY (`file_id`) REFERENCES `file_object` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
