-- 系统设置独立表：把 AI 搜索配置从 business_event_log 迁出到 system_setting（键值表）。
-- 即使本迁移失败，业务也照常运行（旧读取路径仍读事件日志）——见服务端 get_setting 的兼容读。

CREATE TABLE IF NOT EXISTS `system_setting` (
  `setting_key` VARCHAR(64) NOT NULL,
  `setting_value` JSON NOT NULL,
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `pk_system_setting` PRIMARY KEY (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 迁移存量 AI 配置：取最新一条 AI_SEARCH_CONFIG_UPDATED 事件的 after_data 作为当前值。
-- version 沿用事件 id，保证前端已缓存的 version 与乐观锁语义一致。
INSERT INTO `system_setting` (`setting_key`, `setting_value`, `version`, `updated_at`)
SELECT 'ai_search_config', `after_data`, `id`, `occurred_at`
FROM `business_event_log`
WHERE `business_type` = 'SYSTEM_SETTING'
  AND `business_id` = 1
  AND `action` = 'AI_SEARCH_CONFIG_UPDATED'
  AND `after_data` IS NOT NULL
ORDER BY `id` DESC
LIMIT 1
ON DUPLICATE KEY UPDATE
  `setting_value` = VALUES(`setting_value`),
  `version` = VALUES(`version`),
  `updated_at` = VALUES(`updated_at`);