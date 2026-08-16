-- 接口令牌哈希化：user.api_token 明文 → api_token_hash (SHA-256 十六进制)。
-- 一次性迁移转换：把存量明文哈希后写入新列，老令牌继续有效（客户端仍发明文，
-- 服务端 SHA-256 后比对）；此后新建/重新生成令牌时库中只存哈希，明文仅返回一次。

ALTER TABLE `user` ADD COLUMN `api_token_hash` VARCHAR(64) NULL AFTER `password_hash`;

UPDATE `user` SET `api_token_hash` = SHA2(`api_token`, 256) WHERE `api_token` IS NOT NULL;

ALTER TABLE `user`
  MODIFY COLUMN `api_token_hash` VARCHAR(64) NOT NULL,
  DROP INDEX `uq_user_api_token`,
  DROP COLUMN `api_token`,
  ADD CONSTRAINT `uq_user_api_token_hash` UNIQUE (`api_token_hash`);