ALTER TABLE `stock_operation`
  ADD COLUMN `receiver_unit` VARCHAR(128) NULL AFTER `business_reason`;
