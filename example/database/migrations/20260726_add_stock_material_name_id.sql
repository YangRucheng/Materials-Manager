ALTER TABLE `stock_material`
  ADD COLUMN `name_id` VARCHAR(128) NULL AFTER `name`,
  ADD COLUMN `alias` VARCHAR(128) NULL AFTER `name_id`,
  ADD INDEX `ix_stock_material_name_id` (`name_id`),
  ADD INDEX `ix_stock_material_alias` (`alias`);
