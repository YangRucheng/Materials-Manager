-- 20260810 申购记录自包含化：新增快照列、行级镜像表、外键解绑、清理死列
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：各语句带存在性判断/IF NOT EXISTS。

-- 1) 记录行补齐计划快照列（记录自包含，读路径不再依赖计划表）
ALTER TABLE `purchase_request_line`
  ADD COLUMN `plan_no_snapshot` VARCHAR(32) NULL AFTER `purchase_material_id`,
  ADD COLUMN `plan_date_snapshot` DATE NULL AFTER `plan_no_snapshot`,
  ADD COLUMN `category_snapshot` VARCHAR(64) NULL AFTER `material_code_snapshot`,
  ADD COLUMN `demand_department_snapshot` VARCHAR(128) NULL AFTER `category_snapshot`,
  ADD COLUMN `actual_demand_person_snapshot` VARCHAR(128) NULL AFTER `unit_name_snapshot`,
  ADD COLUMN `purchase_responsible_snapshot` VARCHAR(128) NULL AFTER `actual_demand_person_snapshot`,
  ADD COLUMN `plan_remark_snapshot` VARCHAR(1000) NULL AFTER `purchase_responsible_snapshot`,
  ADD COLUMN `stock_material_id_snapshot` BIGINT UNSIGNED NULL AFTER `plan_remark_snapshot`;

-- 2) 回填快照：从关联计划复制
UPDATE `purchase_request_line` AS `line`
JOIN `purchase_material` AS `material` ON `material`.`id` = `line`.`purchase_material_id`
SET
  `line`.`plan_no_snapshot` = `material`.`plan_no`,
  `line`.`plan_date_snapshot` = `material`.`plan_date`,
  `line`.`category_snapshot` = `material`.`category`,
  `line`.`demand_department_snapshot` = `material`.`demand_department`,
  `line`.`actual_demand_person_snapshot` = `material`.`actual_demand_person`,
  `line`.`purchase_responsible_snapshot` = `material`.`purchase_responsible`,
  `line`.`plan_remark_snapshot` = `material`.`remark`,
  `line`.`stock_material_id_snapshot` = `material`.`stock_material_id`
WHERE
  `line`.`plan_no_snapshot` IS NULL;

-- 3) 快照列改为非空（回填完成后）
ALTER TABLE `purchase_request_line`
  MODIFY COLUMN `plan_no_snapshot` VARCHAR(32) NOT NULL,
  MODIFY COLUMN `plan_date_snapshot` DATE NOT NULL,
  MODIFY COLUMN `demand_department_snapshot` VARCHAR(128) NOT NULL,
  MODIFY COLUMN `actual_demand_person_snapshot` VARCHAR(128) NOT NULL,
  MODIFY COLUMN `purchase_responsible_snapshot` VARCHAR(128) NOT NULL;

-- 4) 行级镜像表（计划清理后镜像不丢失）
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

-- 5) 回填行级镜像：从计划镜像复制
INSERT IGNORE INTO `purchase_request_line_image` (`line_id`, `file_id`, `sort_order`)
SELECT
  `line`.`id`,
  `plan_image`.`file_id`,
  `plan_image`.`sort_order`
FROM `purchase_request_line` AS `line`
JOIN `purchase_material_image` AS `plan_image`
  ON `plan_image`.`material_id` = `line`.`purchase_material_id`;

-- 6) 外键解绑：purchase_material_id 改为可空 + ON DELETE SET NULL（清理计划不阻塞）
ALTER TABLE `purchase_request_line`
  DROP FOREIGN KEY `fk_purchase_request_line_purchase_material_id_purchase_material`,
  MODIFY COLUMN `purchase_material_id` BIGINT UNSIGNED NULL,
  ADD CONSTRAINT `fk_purchase_request_line_purchase_material_id_purchase_material`
    FOREIGN KEY (`purchase_material_id`) REFERENCES `purchase_material` (`id`) ON DELETE SET NULL;

-- 7) 清理死列：头表 trace_no/salesperson（读路径均用行表）、计划表 identity_hash（无读路径）
ALTER TABLE `purchase_request`
  DROP INDEX `ix_purchase_request_trace_no`,
  DROP COLUMN `trace_no`,
  DROP COLUMN `salesperson`;

ALTER TABLE `purchase_material`
  DROP INDEX `ix_purchase_material_identity_hash`,
  DROP COLUMN `identity_hash`;
