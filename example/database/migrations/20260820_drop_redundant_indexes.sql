-- 清理冗余/无效索引：下列列全部经 contains_any(`LIKE '%term%'`) 查询，
-- B-tree 索引无法被前导通配 LIKE 使用，纯属写放大；数据量小，全表扫足够。
-- （保留 plan_no 唯一、status 等值过滤、stock_material_id 外键索引。）

ALTER TABLE `material_code_library` DROP INDEX `ix_material_code_library_name`;
ALTER TABLE `material_code_library` DROP INDEX `ix_material_code_library_model_spec`;

ALTER TABLE `huaxing_inventory` DROP INDEX `ix_huaxing_inventory_name`;
ALTER TABLE `huaxing_inventory` DROP INDEX `ix_huaxing_inventory_model_spec`;

ALTER TABLE `stock_material` DROP INDEX `ix_stock_material_name`;
ALTER TABLE `stock_material` DROP INDEX `ix_stock_material_name_id`;
ALTER TABLE `stock_material` DROP INDEX `ix_stock_material_alias`;
ALTER TABLE `stock_material` DROP INDEX `ix_stock_material_model_spec`;

ALTER TABLE `purchase_material` DROP INDEX `ix_purchase_material_plan_date`;
ALTER TABLE `purchase_material` DROP INDEX `ix_purchase_material_material_code`;
ALTER TABLE `purchase_material` DROP INDEX `ix_purchase_material_category`;
ALTER TABLE `purchase_material` DROP INDEX `ix_purchase_material_model_spec`;
ALTER TABLE `purchase_material` DROP INDEX `ix_purchase_material_name`;
ALTER TABLE `purchase_material` DROP INDEX `ix_purchase_material_purchase_responsible`;

ALTER TABLE `purchase_request` DROP INDEX `ix_purchase_request_contract_no`;
ALTER TABLE `purchase_request` DROP INDEX `ix_purchase_request_vessel_no`;
ALTER TABLE `purchase_request` DROP INDEX `ix_purchase_request_consolidation_date`;
ALTER TABLE `purchase_request` DROP INDEX `ix_purchase_request_consolidation_port`;
ALTER TABLE `purchase_request` DROP INDEX `ix_purchase_request_sailing_date`;
ALTER TABLE `purchase_request` DROP INDEX `ix_purchase_request_purchase_order_no`;