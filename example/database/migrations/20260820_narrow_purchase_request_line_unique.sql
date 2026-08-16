-- 收窄 purchase_request_line 唯一索引：原唯一键含 `usage` VARCHAR(500)，
-- 索引过宽；改用归一化 usage_hash（SHA-256 前 32 位十六进制）保持等值语义。

ALTER TABLE `purchase_request_line` ADD COLUMN `usage_hash` VARCHAR(32) NULL AFTER `usage`;

UPDATE `purchase_request_line` SET `usage_hash` = LEFT(SHA2(`usage`, 256), 32);

ALTER TABLE `purchase_request_line`
  MODIFY COLUMN `usage_hash` VARCHAR(32) NOT NULL,
  DROP INDEX `uq_purchase_request_line_purchase_request_id`,
  ADD CONSTRAINT `uq_purchase_request_line_purchase_request_id`
    UNIQUE (`purchase_request_id`, `purchase_material_id`, `subitem_no`, `usage_hash`);