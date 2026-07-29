ALTER TABLE `stock_operation`
  DROP FOREIGN KEY `fk_stock_operation_mini_program_user_id_mini_program_user`,
  DROP INDEX `ix_stock_operation_mini_program_user_id`,
  DROP COLUMN `mini_program_user_id`;
