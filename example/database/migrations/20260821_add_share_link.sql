-- 20260821 新增匿名分享链接表（申购计划/申购记录分享为无鉴权页面）
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- 幂等：CREATE TABLE IF NOT EXISTS。
-- token 为 UUIDv7（不可猜解），expires_at 为 NULL 表示永久有效；
-- 匿名读取端点 GET /shares/{token} 不鉴权，仅凭 token 返回该分享的数据快照。
CREATE TABLE IF NOT EXISTS `share_link` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `token` VARCHAR(36) NOT NULL,
  `share_type` ENUM('PURCHASE_PLAN', 'PURCHASE_RECORD') NOT NULL,
  `item_ids` JSON NOT NULL,
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
