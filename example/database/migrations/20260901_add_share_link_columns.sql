-- 20260901 分享链接新增展示列配置：share_link.columns（JSON NULL）
-- 适用已有库（新装直接使用 init.sql，无需执行本脚本）。
-- columns 为 NULL 表示分享页展示该类型全部默认列；否则仅展示列出的列（键名）。
-- 请在执行前备份数据库。
ALTER TABLE `share_link`
  ADD COLUMN `columns` JSON NULL AFTER `item_ids`;
