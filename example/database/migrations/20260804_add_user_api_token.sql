ALTER TABLE `user` ADD COLUMN `api_token` VARCHAR(36) NULL AFTER `password_hash`;

UPDATE `user`
SET `api_token` = LOWER(CONCAT(
  HEX(RANDOM_BYTES(4)), '-',
  HEX(RANDOM_BYTES(2)), '-',
  '4', SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3), '-',
  SUBSTRING('89ab', 1 + FLOOR(RAND() * 4), 1),
  SUBSTRING(HEX(RANDOM_BYTES(2)), 2, 3), '-',
  HEX(RANDOM_BYTES(6))
))
WHERE `api_token` IS NULL;

ALTER TABLE `user`
  MODIFY COLUMN `api_token` VARCHAR(36) NOT NULL,
  ADD CONSTRAINT `uq_user_api_token` UNIQUE (`api_token`);
