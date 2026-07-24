ALTER TABLE `purchase_material`
  ADD COLUMN `category` VARCHAR(64) NULL AFTER `material_code`,
  ADD COLUMN `urgency` VARCHAR(32) NOT NULL DEFAULT '正常' AFTER `category`,
  ADD COLUMN `demand_department` VARCHAR(128) NOT NULL DEFAULT 'HXNI 检修维护部' AFTER `urgency`,
  MODIFY COLUMN `status` ENUM('NORMAL', 'DEFERRED', 'ARCHIVED') NOT NULL DEFAULT 'NORMAL',
  ADD INDEX `ix_purchase_material_category` (`category`);

ALTER TABLE `purchase_request`
  ADD COLUMN `contract_no` VARCHAR(128) NULL AFTER `trace_no`,
  ADD COLUMN `vessel_no` VARCHAR(128) NULL AFTER `contract_no`,
  ADD COLUMN `consolidation_date` DATE NULL AFTER `vessel_no`,
  ADD COLUMN `consolidation_port` VARCHAR(128) NULL AFTER `consolidation_date`,
  ADD COLUMN `sailing_date` DATE NULL AFTER `consolidation_port`,
  ADD INDEX `ix_purchase_request_contract_no` (`contract_no`),
  ADD INDEX `ix_purchase_request_vessel_no` (`vessel_no`),
  ADD INDEX `ix_purchase_request_consolidation_date` (`consolidation_date`),
  ADD INDEX `ix_purchase_request_consolidation_port` (`consolidation_port`),
  ADD INDEX `ix_purchase_request_sailing_date` (`sailing_date`);
