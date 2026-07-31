-- 添加飞书/钉钉 Webhook 渠道配置和事务投递队列。

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
