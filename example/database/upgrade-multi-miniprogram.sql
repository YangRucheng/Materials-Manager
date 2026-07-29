-- 已有数据库升级脚本：单小程序用户改为“人员主账号 + 小程序身份”。
-- 执行前必须把下面的 NULL 替换为原有小程序的真实 AppID，并先完成数据库备份。
-- 保持 NULL 会让身份数据迁移因 NOT NULL 约束失败，不会继续删除原 OpenID 列。
SET @PRIMARY_MINI_PROGRAM_APP_ID = NULL;

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

INSERT INTO `mini_program_identity` (
  `mini_program_user_id`,
  `app_id`,
  `wechat_openid`,
  `created_at`,
  `updated_at`,
  `version`
)
SELECT
  `id`,
  @PRIMARY_MINI_PROGRAM_APP_ID,
  `wechat_openid`,
  `created_at`,
  `updated_at`,
  1
FROM `mini_program_user`;

ALTER TABLE `mini_program_user`
  DROP INDEX `uq_mini_program_user_wechat_openid`,
  DROP COLUMN `wechat_openid`;
