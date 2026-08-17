-- 20260816 新增 Excel 导出任务表（申购记录/申购计划结果导出异步化共用）
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：CREATE TABLE IF NOT EXISTS。
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