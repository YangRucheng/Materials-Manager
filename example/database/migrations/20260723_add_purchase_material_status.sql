ALTER TABLE `purchase_material`
  ADD COLUMN `status` ENUM('NORMAL', 'ARCHIVED') NOT NULL DEFAULT 'NORMAL' AFTER `identity_hash`,
  ADD INDEX `ix_purchase_material_status` (`status`);
