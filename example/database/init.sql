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
  `api_token_hash` VARCHAR(64) NOT NULL,
  `api_token_enc` VARCHAR(512) NOT NULL DEFAULT '',
  `display_name` VARCHAR(128) NOT NULL,
  `role` ENUM('SUPER_ADMIN', 'WAREHOUSE_ADMIN', 'PURCHASE_ADMIN', 'READ_ONLY') NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_user` PRIMARY KEY (`id`),
  CONSTRAINT `uq_user_username` UNIQUE (`username`),
  CONSTRAINT `uq_user_api_token_hash` UNIQUE (`api_token_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `mini_program_user` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `display_name` VARCHAR(128) NOT NULL,
  `department_name` VARCHAR(128) NOT NULL DEFAULT '华星检修维护部电气车间',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_mini_program_user` PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `mini_program_identity` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `mini_program_user_id` BIGINT UNSIGNED NOT NULL,
  `app_id` VARCHAR(64) NOT NULL,
  `wechat_openid` VARCHAR(128) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_mini_program_identity` PRIMARY KEY (`id`),
  CONSTRAINT `uq_mini_program_identity_app_id` UNIQUE (`app_id`, `wechat_openid`),
  CONSTRAINT `uq_mini_program_identity_mini_program_user_id`
    UNIQUE (`mini_program_user_id`, `app_id`),
  CONSTRAINT `fk_mini_program_identity_mini_program_user_id_mini_program_user`
    FOREIGN KEY (`mini_program_user_id`) REFERENCES `mini_program_user` (`id`) ON DELETE CASCADE
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

CREATE TABLE IF NOT EXISTS `system_setting` (
  `setting_key` VARCHAR(64) NOT NULL,
  `setting_value` JSON NOT NULL,
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_system_setting` PRIMARY KEY (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `webhook_channel` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `platform` ENUM('FEISHU', 'DINGTALK') NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 0,
  `webhook_url_encrypted` VARCHAR(2000) NOT NULL DEFAULT '',
  `secret_encrypted` VARCHAR(2000) NOT NULL DEFAULT '',
  `subscribed_events` JSON NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_webhook_channel` PRIMARY KEY (`id`),
  CONSTRAINT `uq_webhook_channel_platform` UNIQUE (`platform`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `webhook_delivery` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `event_id` VARCHAR(36) NOT NULL,
  `event_type` ENUM('STOCK_OUTBOUND_CREATED', 'STOCK_INBOUND_CREATED', 'MINI_PROGRAM_USER_BOUND') NOT NULL,
  `channel_id` BIGINT UNSIGNED NOT NULL,
  `payload` JSON NOT NULL,
  `status` ENUM('PENDING', 'SENDING', 'SUCCEEDED', 'FAILED') NOT NULL DEFAULT 'PENDING',
  `attempts` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `next_retry_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `response_status` INT NULL,
  `response_excerpt` VARCHAR(1000) NULL,
  `last_error` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `delivered_at` DATETIME(6) NULL,
  CONSTRAINT `pk_webhook_delivery` PRIMARY KEY (`id`),
  CONSTRAINT `uq_webhook_delivery_event_id` UNIQUE (`event_id`, `channel_id`),
  CONSTRAINT `fk_webhook_delivery_channel_id_webhook_channel`
    FOREIGN KEY (`channel_id`) REFERENCES `webhook_channel` (`id`),
  INDEX `ix_webhook_delivery_pending` (`status`, `next_retry_at`, `id`)
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

CREATE TABLE IF NOT EXISTS `material_code_library` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `material_code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NULL,
  `model_spec` VARCHAR(255) NULL,
  `unit_name` VARCHAR(32) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_material_code_library` PRIMARY KEY (`id`),
  CONSTRAINT `uq_material_code_library_material_code` UNIQUE (`material_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `excel_import_job` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `import_type` VARCHAR(32) NOT NULL,
  `status` ENUM('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED') NOT NULL DEFAULT 'PENDING',
  `original_filename` VARCHAR(255) NOT NULL,
  `file_path` VARCHAR(500) NOT NULL,
  `result` JSON NULL,
  `error_code` VARCHAR(64) NULL,
  `error_message` VARCHAR(1000) NULL,
  `created_by` BIGINT UNSIGNED NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `started_at` DATETIME(6) NULL,
  `finished_at` DATETIME(6) NULL,
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_excel_import_job` PRIMARY KEY (`id`),
  CONSTRAINT `fk_excel_import_job_created_by_user`
    FOREIGN KEY (`created_by`) REFERENCES `user` (`id`),
  INDEX `ix_excel_import_job_type_status` (`import_type`, `status`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `excel_export_job` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `export_type` VARCHAR(32) NOT NULL,
  `status` ENUM('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED') NOT NULL DEFAULT 'PENDING',
  `download_filename` VARCHAR(255) NULL,
  `file_path` VARCHAR(500) NULL,
  `params` JSON NULL,
  `result` JSON NULL,
  `error_code` VARCHAR(64) NULL,
  `error_message` VARCHAR(1000) NULL,
  `created_by` BIGINT UNSIGNED NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `started_at` DATETIME(6) NULL,
  `finished_at` DATETIME(6) NULL,
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_excel_export_job` PRIMARY KEY (`id`),
  CONSTRAINT `fk_excel_export_job_created_by_user`
    FOREIGN KEY (`created_by`) REFERENCES `user` (`id`),
  INDEX `ix_excel_export_job_type_status` (`export_type`, `status`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `share_link` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `token` VARCHAR(36) NOT NULL,
  `share_type` ENUM('PURCHASE_PLAN', 'PURCHASE_RECORD') NOT NULL,
  `item_ids` JSON NOT NULL,
  `columns` JSON NULL,
  `expires_at` DATETIME(6) NULL,
  `created_by` BIGINT UNSIGNED NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_share_link` PRIMARY KEY (`id`),
  CONSTRAINT `uq_share_link_token` UNIQUE (`token`),
  CONSTRAINT `fk_share_link_created_by_user`
    FOREIGN KEY (`created_by`) REFERENCES `user` (`id`),
  INDEX `ix_share_link_expires_at` (`expires_at`),
  INDEX `ix_share_link_share_type` (`share_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
  CONSTRAINT `pk_huaxing_inventory` PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `lite_inventory` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(128) NOT NULL,
  `model_spec` VARCHAR(255) NULL,
  `unit_name` VARCHAR(32) NULL,
  `quantity` DECIMAL(18, 2) NULL,
  `remark` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_lite_inventory` PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_request` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `purchase_order_no` VARCHAR(128) NULL,
  `contract_no` VARCHAR(128) NULL,
  `vessel_no` VARCHAR(128) NULL,
  `consolidation_date` DATE NULL,
  `consolidation_port` VARCHAR(128) NULL,
  `sailing_date` DATE NULL,
  `remark` VARCHAR(1000) NULL,
  `purchase_date` DATE NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_request` PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_material` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `uuid` VARCHAR(36) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `name_id` VARCHAR(128) NULL,
  `alias` VARCHAR(128) NULL,
  `model_spec` VARCHAR(255) NOT NULL,
  `unit_name` VARCHAR(32) NOT NULL,
  `remark` VARCHAR(1000) NULL,
  `identity_hash` VARCHAR(64) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_stock_material` PRIMARY KEY (`id`),
  CONSTRAINT `uq_stock_material_uuid` UNIQUE (`uuid`),
  CONSTRAINT `uq_stock_material_identity_hash` UNIQUE (`identity_hash`)
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
  `source_type` ENUM('MANUAL', 'MINI_PROGRAM', 'REVERSAL', 'INITIALIZATION') NOT NULL,
  `reversal_of_id` BIGINT UNSIGNED NULL,
  `client_request_id` VARCHAR(64) NOT NULL,
  `mini_program_user_name_snapshot` VARCHAR(128) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_stock_operation` PRIMARY KEY (`id`),
  CONSTRAINT `uq_stock_operation_operation_no` UNIQUE (`operation_no`),
  CONSTRAINT `fk_stock_operation_reversal_of_id_stock_operation`
    FOREIGN KEY (`reversal_of_id`) REFERENCES `stock_operation` (`id`),
  CONSTRAINT `uq_stock_operation_client_request_id` UNIQUE (`client_request_id`),
  INDEX `ix_stock_operation_occurred_at` (`occurred_at`),
  INDEX `ix_stock_operation_source_occurred` (`source_type`, `occurred_at`),
  INDEX `ix_stock_operation_type_occurred` (`operation_type`, `occurred_at`),
  INDEX `ix_stock_operation_reversal_of_id` (`reversal_of_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_material` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `plan_no` VARCHAR(32) NOT NULL,
  `plan_date` DATE NOT NULL,
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
  `status` ENUM('NORMAL', 'DEFERRED', 'ARCHIVED') NOT NULL DEFAULT 'NORMAL',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_material` PRIMARY KEY (`id`),
  CONSTRAINT `uq_purchase_material_plan_no` UNIQUE (`plan_no`),
  CONSTRAINT `fk_purchase_material_stock_material_id_stock_material`
    FOREIGN KEY (`stock_material_id`) REFERENCES `stock_material` (`id`),
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

CREATE TABLE IF NOT EXISTS `purchase_request_line` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `purchase_request_id` BIGINT UNSIGNED NOT NULL,
  `purchase_material_id` BIGINT UNSIGNED NULL,
  `plan_no_snapshot` VARCHAR(32) NOT NULL,
  `plan_date_snapshot` DATE NOT NULL,
  `material_code_snapshot` VARCHAR(64) NULL,
  `category_snapshot` VARCHAR(64) NULL,
  `demand_department_snapshot` VARCHAR(128) NOT NULL,
  `material_name_snapshot` VARCHAR(128) NOT NULL,
  `model_spec_snapshot` VARCHAR(255) NOT NULL,
  `unit_name_snapshot` VARCHAR(32) NOT NULL,
  `actual_demand_person_snapshot` VARCHAR(128) NOT NULL,
  `purchase_responsible_snapshot` VARCHAR(128) NOT NULL,
  `plan_remark_snapshot` VARCHAR(1000) NULL,
  `stock_material_id_snapshot` BIGINT UNSIGNED NULL,
  `purchase_qty` DECIMAL(18, 1) NOT NULL,
  `status` VARCHAR(128) NOT NULL DEFAULT '已申购',
  `usage` VARCHAR(500) NOT NULL,
  `usage_hash` VARCHAR(32) NOT NULL,
  `subitem_no` VARCHAR(64) NULL,
  `trace_no` VARCHAR(128) NULL,
  `salesperson` VARCHAR(128) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT `pk_purchase_request_line` PRIMARY KEY (`id`),
  CONSTRAINT `ck_purchase_request_line_purchase_positive` CHECK (`purchase_qty` > 0),
  CONSTRAINT `uq_purchase_request_line_purchase_request_id`
    UNIQUE (`purchase_request_id`, `purchase_material_id`, `subitem_no`, `usage_hash`),
  CONSTRAINT `fk_purchase_request_line_purchase_request_id_purchase_request`
    FOREIGN KEY (`purchase_request_id`) REFERENCES `purchase_request` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_purchase_request_line_purchase_material_id_purchase_material`
    FOREIGN KEY (`purchase_material_id`) REFERENCES `purchase_material` (`id`) ON DELETE SET NULL,
  INDEX `ix_purchase_request_line_trace_no` (`trace_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `purchase_request_line_image` (
  `line_id` BIGINT UNSIGNED NOT NULL,
  `file_id` VARCHAR(36) NOT NULL,
  `sort_order` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  CONSTRAINT `pk_purchase_request_line_image` PRIMARY KEY (`line_id`, `file_id`),
  CONSTRAINT `fk_purchase_request_line_image_line_id_purchase_request_line`
    FOREIGN KEY (`line_id`) REFERENCES `purchase_request_line` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_purchase_request_line_image_file_id_file_object`
    FOREIGN KEY (`file_id`) REFERENCES `file_object` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `stock_operation_line` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `operation_id` BIGINT UNSIGNED NOT NULL,
  `stock_material_id` BIGINT UNSIGNED NOT NULL,
  `quantity` DECIMAL(18, 1) NOT NULL,
  `remaining_qty` DECIMAL(18, 1) NOT NULL,
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
SET @admin_api_token = LOWER(CONCAT(HEX(RANDOM_BYTES(4)), '-', HEX(RANDOM_BYTES(2)),
  '-4', SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3), '-',
  SUBSTRING('89ab', 1 + FLOOR(RAND() * 4), 1), SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3),
  '-', HEX(RANDOM_BYTES(6))));
SET @warehouse_api_token = LOWER(CONCAT(HEX(RANDOM_BYTES(4)), '-', HEX(RANDOM_BYTES(2)),
  '-4', SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3), '-',
  SUBSTRING('89ab', 1 + FLOOR(RAND() * 4), 1), SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3),
  '-', HEX(RANDOM_BYTES(6))));
SET @purchase_api_token = LOWER(CONCAT(HEX(RANDOM_BYTES(4)), '-', HEX(RANDOM_BYTES(2)),
  '-4', SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3), '-',
  SUBSTRING('89ab', 1 + FLOOR(RAND() * 4), 1), SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3),
  '-', HEX(RANDOM_BYTES(6))));
SET @readonly_api_token = LOWER(CONCAT(HEX(RANDOM_BYTES(4)), '-', HEX(RANDOM_BYTES(2)),
  '-4', SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3), '-',
  SUBSTRING('89ab', 1 + FLOOR(RAND() * 4), 1), SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3),
  '-', HEX(RANDOM_BYTES(6))));

INSERT INTO `user` (`username`, `password_hash`, `api_token_hash`, `display_name`, `role`, `enabled`)
VALUES
  ('admin', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', SHA2(@admin_api_token, 256), '系统管理员', 'SUPER_ADMIN', 1),
  ('warehouse', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', SHA2(@warehouse_api_token, 256), '仓库管理员', 'WAREHOUSE_ADMIN', 1),
  ('purchase', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', SHA2(@purchase_api_token, 256), '申购管理员', 'PURCHASE_ADMIN', 1),
  ('readonly', '$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg', SHA2(@readonly_api_token, 256), '只读用户', 'READ_ONLY', 1)
ON DUPLICATE KEY UPDATE
  `display_name` = VALUES(`display_name`),
  `role` = VALUES(`role`),
  `enabled` = VALUES(`enabled`);

SET FOREIGN_KEY_CHECKS = @OLD_FOREIGN_KEY_CHECKS;
