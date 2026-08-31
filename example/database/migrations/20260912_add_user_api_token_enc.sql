-- 接口令牌可逆加密回显：新增 api_token_enc 列（Fernet 密文）。
-- 目的：令牌可能用于多处（如 MCP 客户端），不应每次读取都重新生成。
-- 每次读取时后端解密该列并回显给前端；api_token_hash 仍用于认证快速查找。
-- 既有数据只有哈希（不可逆），升级后需对相关用户执行一次“重新生成”，
-- 以便写入密文，此后即可持续回显。
ALTER TABLE `user` ADD COLUMN `api_token_enc` VARCHAR(512) NOT NULL DEFAULT '' AFTER `api_token_hash`;
