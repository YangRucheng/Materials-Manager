-- 接口令牌可逆加密回显：新增 api_token_enc 列（Fernet 密文）。
-- 目的：令牌可能用于多处（如 MCP 客户端），不应每次读取都重新生成。
-- 每次读取时后端解密该列并回显给前端；api_token_hash 仍用于认证快速查找。
-- 既有数据只有哈希（不可逆），新建于本列之后的令牌会自动写入密文；
-- 旧令牌在下次成功用于接口调用时由后端自动加密回写，此后持续回显，无需重新生成。
ALTER TABLE `user` ADD COLUMN `api_token_enc` VARCHAR(512) NOT NULL DEFAULT '' AFTER `api_token_hash`;
