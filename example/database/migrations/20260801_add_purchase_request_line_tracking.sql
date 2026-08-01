ALTER TABLE `purchase_request_line` ADD COLUMN `trace_no` VARCHAR(128) NULL;
ALTER TABLE `purchase_request_line` ADD COLUMN `salesperson` VARCHAR(128) NULL;
UPDATE `purchase_request_line` AS `line`
JOIN `purchase_request` AS `request` ON `request`.`id` = `line`.`purchase_request_id`
SET
  `line`.`trace_no` = `request`.`trace_no`,
  `line`.`salesperson` = `request`.`salesperson`
WHERE
  `line`.`trace_no` IS NULL
  AND `line`.`salesperson` IS NULL;
CREATE INDEX `ix_purchase_request_line_trace_no` ON `purchase_request_line` (`trace_no`);
