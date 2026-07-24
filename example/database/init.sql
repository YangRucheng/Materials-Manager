-- 电气车间备件管理系统 MySQL 8.0 初始化脚本
-- 使用方式：先在 1Panel 中创建空数据库，再选择该数据库导入本文件。
-- 本脚本不创建数据库或数据库账号，也不会由业务容器自动执行。

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET @OLD_FOREIGN_KEY_CHECKS = @@FOREIGN_KEY_CHECKS;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `user` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `display_name` VARCHAR(128) NOT NULL,
  `role` ENUM('SUPER_ADMIN', 'WAREHOUSE_ADMIN', 'PURCHASE_ADMIN', 'READ_ONLY') NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_user` PRIMARY KEY (`id`),
  CONSTRAINT `uq_user_username` UNIQUE (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `business_event_log` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `business_type` VARCHAR(64) NOT NULL,
  `business_id` BIGINT UNSIGNED NOT NULL,
  `action` VARCHAR(64) NOT NULL,
  `old_status` VARCHAR(32) NULL,
  `new_status` VARCHAR(32) NULL,
  `occurred_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `remark` VARCHAR(1000) NULL,
  `before_data` JSON NULL,
  `after_data` JSON NULL,
  CONSTRAINT `pk_business_event_log` PRIMARY KEY (`id`),
  INDEX `ix_business_event_entity` (`business_type`, `business_id`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `file_object` (
  `id` VARCHAR(36) NOT NULL,
  `original_name` VARCHAR(255) NOT NULL,
  `mime_type` VARCHAR(32) NOT NULL,
  `size_bytes` BIGINT UNSIGNED NOT NULL,
  `width` INT NOT NULL,
  `height` INT NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_file_object` PRIMARY KEY (`id`),
  INDEX `ix_file_object_sha256` (`sha256`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `measurement_unit` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(32) NOT NULL,
  `name` VARCHAR(32) NOT NULL,
  `decimal_places` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_measurement_unit` PRIMARY KEY (`id`),
  CONSTRAINT `ck_measurement_unit_decimal_places_range`
    CHECK (`decimal_places` >= 0 AND `decimal_places` <= 1),
  CONSTRAINT `uq_measurement_unit_code` UNIQUE (`code`),
  CONSTRAINT `uq_measurement_unit_name` UNIQUE (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_request` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `purchase_order_no` VARCHAR(128) NULL,
  `trace_no` VARCHAR(128) NULL,
  `salesperson` VARCHAR(128) NULL,
  `remark` VARCHAR(1000) NULL,
  `purchase_date` DATE NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_request` PRIMARY KEY (`id`),
  INDEX `ix_purchase_request_trace_no` (`trace_no`),
  INDEX `ix_purchase_request_purchase_order_no` (`purchase_order_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_material` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(128) NOT NULL,
  `model_spec` VARCHAR(255) NOT NULL,
  `unit_id` BIGINT UNSIGNED NOT NULL,
  `remark` VARCHAR(1000) NULL,
  `identity_hash` VARCHAR(64) NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_stock_material` PRIMARY KEY (`id`),
  CONSTRAINT `fk_stock_material_unit_id_measurement_unit`
    FOREIGN KEY (`unit_id`) REFERENCES `measurement_unit` (`id`),
  CONSTRAINT `uq_stock_material_identity_hash` UNIQUE (`identity_hash`),
  INDEX `ix_stock_material_model_spec` (`model_spec`),
  INDEX `ix_stock_material_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_operation` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `operation_no` VARCHAR(32) NOT NULL,
  `operation_type` ENUM('INBOUND', 'OUTBOUND') NOT NULL,
  `occurred_at` DATETIME(6) NOT NULL,
  `business_reason` VARCHAR(500) NOT NULL,
  `receiver_unit` VARCHAR(128) NULL,
  `receiver_name` VARCHAR(64) NULL,
  `subitem_no` VARCHAR(64) NULL,
  `source_type` ENUM('MANUAL', 'REVERSAL', 'INITIALIZATION') NOT NULL,
  `reversal_of_id` BIGINT UNSIGNED NULL,
  `client_request_id` VARCHAR(64) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_stock_operation` PRIMARY KEY (`id`),
  CONSTRAINT `uq_stock_operation_operation_no` UNIQUE (`operation_no`),
  CONSTRAINT `uq_stock_operation_reversal_of_id` UNIQUE (`reversal_of_id`),
  CONSTRAINT `fk_stock_operation_reversal_of_id_stock_operation`
    FOREIGN KEY (`reversal_of_id`) REFERENCES `stock_operation` (`id`),
  CONSTRAINT `uq_stock_operation_client_request_id` UNIQUE (`client_request_id`),
  INDEX `ix_stock_operation_occurred_at` (`occurred_at`),
  INDEX `ix_stock_operation_source_occurred` (`source_type`, `occurred_at`),
  INDEX `ix_stock_operation_type_occurred` (`operation_type`, `occurred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_material` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `plan_no` VARCHAR(32) NOT NULL,
  `plan_date` DATE NOT NULL,
  `material_code` VARCHAR(64) NULL,
  `name` VARCHAR(128) NOT NULL,
  `model_spec` VARCHAR(255) NOT NULL,
  `unit_id` BIGINT UNSIGNED NOT NULL,
  `actual_demand_person` VARCHAR(128) NOT NULL,
  `purchase_responsible` VARCHAR(128) NOT NULL,
  `planned_qty` DECIMAL(18, 1) NOT NULL,
  `usage` VARCHAR(500) NOT NULL,
  `subitem_no` VARCHAR(64) NULL,
  `remark` VARCHAR(1000) NULL,
  `stock_material_id` BIGINT UNSIGNED NULL,
  `identity_hash` VARCHAR(64) NOT NULL,
  `status` ENUM('NORMAL', 'ARCHIVED') NOT NULL DEFAULT 'NORMAL',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_material` PRIMARY KEY (`id`),
  CONSTRAINT `uq_purchase_material_plan_no` UNIQUE (`plan_no`),
  CONSTRAINT `fk_purchase_material_unit_id_measurement_unit`
    FOREIGN KEY (`unit_id`) REFERENCES `measurement_unit` (`id`),
  CONSTRAINT `fk_purchase_material_stock_material_id_stock_material`
    FOREIGN KEY (`stock_material_id`) REFERENCES `stock_material` (`id`),
  INDEX `ix_purchase_material_identity_hash` (`identity_hash`),
  INDEX `ix_purchase_material_plan_date` (`plan_date`),
  INDEX `ix_purchase_material_material_code` (`material_code`),
  INDEX `ix_purchase_material_model_spec` (`model_spec`),
  INDEX `ix_purchase_material_name` (`name`),
  INDEX `ix_purchase_material_purchase_responsible` (`purchase_responsible`),
  INDEX `ix_purchase_material_status` (`status`),
  INDEX `ix_purchase_material_stock_material_id` (`stock_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_balance` (
  `stock_material_id` BIGINT UNSIGNED NOT NULL,
  `quantity` DECIMAL(18, 1) NOT NULL DEFAULT 0,
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_stock_balance` PRIMARY KEY (`stock_material_id`),
  CONSTRAINT `fk_stock_balance_stock_material_id_stock_material`
    FOREIGN KEY (`stock_material_id`) REFERENCES `stock_material` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_material_image` (
  `material_id` BIGINT UNSIGNED NOT NULL,
  `file_id` VARCHAR(36) NOT NULL,
  `sort_order` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  CONSTRAINT `pk_stock_material_image` PRIMARY KEY (`material_id`, `file_id`),
  CONSTRAINT `fk_stock_material_image_material_id_stock_material`
    FOREIGN KEY (`material_id`) REFERENCES `stock_material` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_stock_material_image_file_id_file_object`
    FOREIGN KEY (`file_id`) REFERENCES `file_object` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_replenishment_policy` (
  `stock_material_id` BIGINT UNSIGNED NOT NULL,
  `minimum_qty` DECIMAL(18, 1) NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_stock_replenishment_policy` PRIMARY KEY (`stock_material_id`),
  CONSTRAINT `ck_stock_replenishment_policy_minimum_nonnegative`
    CHECK (`minimum_qty` >= 0),
  CONSTRAINT `fk_stock_replenishment_policy_stock_material_id_stock_material`
    FOREIGN KEY (`stock_material_id`) REFERENCES `stock_material` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_material_image` (
  `material_id` BIGINT UNSIGNED NOT NULL,
  `file_id` VARCHAR(36) NOT NULL,
  `sort_order` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  CONSTRAINT `pk_purchase_material_image` PRIMARY KEY (`material_id`, `file_id`),
  CONSTRAINT `fk_purchase_material_image_material_id_purchase_material`
    FOREIGN KEY (`material_id`) REFERENCES `purchase_material` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_purchase_material_image_file_id_file_object`
    FOREIGN KEY (`file_id`) REFERENCES `file_object` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_request_line` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `purchase_request_id` BIGINT UNSIGNED NOT NULL,
  `purchase_material_id` BIGINT UNSIGNED NOT NULL,
  `material_code_snapshot` VARCHAR(64) NULL,
  `material_name_snapshot` VARCHAR(128) NOT NULL,
  `model_spec_snapshot` VARCHAR(255) NOT NULL,
  `unit_name_snapshot` VARCHAR(32) NOT NULL,
  `purchase_qty` DECIMAL(18, 1) NOT NULL,
  `status` VARCHAR(128) NOT NULL DEFAULT '已申购',
  `usage` VARCHAR(500) NOT NULL,
  `subitem_no` VARCHAR(64) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_request_line` PRIMARY KEY (`id`),
  CONSTRAINT `ck_purchase_request_line_purchase_positive` CHECK (`purchase_qty` > 0),
  CONSTRAINT `uq_purchase_request_line_purchase_request_id`
    UNIQUE (`purchase_request_id`, `purchase_material_id`, `subitem_no`, `usage`),
  CONSTRAINT `fk_purchase_request_line_purchase_request_id_purchase_request`
    FOREIGN KEY (`purchase_request_id`) REFERENCES `purchase_request` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_purchase_request_line_purchase_material_id_purchase_material`
    FOREIGN KEY (`purchase_material_id`) REFERENCES `purchase_material` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_operation_line` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `operation_id` BIGINT UNSIGNED NOT NULL,
  `stock_material_id` BIGINT UNSIGNED NOT NULL,
  `quantity` DECIMAL(18, 1) NOT NULL,
  `before_qty` DECIMAL(18, 1) NOT NULL,
  `after_qty` DECIMAL(18, 1) NOT NULL,
  `material_name_snapshot` VARCHAR(128) NOT NULL,
  `model_spec_snapshot` VARCHAR(255) NOT NULL,
  `unit_name_snapshot` VARCHAR(32) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_stock_operation_line` PRIMARY KEY (`id`),
  CONSTRAINT `ck_stock_operation_line_operation_quantity_positive` CHECK (`quantity` > 0),
  CONSTRAINT `uq_stock_operation_line_operation_id` UNIQUE (`operation_id`, `stock_material_id`),
  CONSTRAINT `fk_stock_operation_line_operation_id_stock_operation`
    FOREIGN KEY (`operation_id`) REFERENCES `stock_operation` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_stock_operation_line_stock_material_id_stock_material`
    FOREIGN KEY (`stock_material_id`) REFERENCES `stock_material` (`id`),
  INDEX `ix_operation_line_material_operation` (`stock_material_id`, `operation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 首次登录账号，默认密码均为 123456。重复导入不会重置已有账号密码。
INSERT INTO `user` (`username`, `password_hash`, `display_name`, `role`, `enabled`)
VALUES
  ('admin', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', '系统管理员', 'SUPER_ADMIN', 1),
  ('warehouse', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', '仓库管理员', 'WAREHOUSE_ADMIN', 1),
  ('purchase', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', '申购管理员', 'PURCHASE_ADMIN', 1),
  ('readonly', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', '只读用户', 'READ_ONLY', 1)
ON DUPLICATE KEY UPDATE
  `display_name` = VALUES(`display_name`),
  `role` = VALUES(`role`),
  `enabled` = VALUES(`enabled`);

INSERT INTO `measurement_unit` (
  `code`,
  `name`,
  `decimal_places`,
  `enabled`
)
VALUES
  ('PCS', '个', 0, 1),
  ('SET', '套', 0, 1),
  ('M', '米', 1, 1),
  ('KG', '千克', 1, 1)
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `decimal_places` = VALUES(`decimal_places`),
  `enabled` = VALUES(`enabled`);

SET FOREIGN_KEY_CHECKS = @OLD_FOREIGN_KEY_CHECKS;
