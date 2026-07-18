import type { Role } from '@/api/generated'

export type Permission = 'warehouse:write' | 'purchase:write' | 'settings:write' | 'read'

export const rolePermissions: Record<Role, Permission[]> = {
  SUPER_ADMIN: ['warehouse:write', 'purchase:write', 'settings:write', 'read'],
  WAREHOUSE_ADMIN: ['warehouse:write', 'read'],
  PURCHASE_ADMIN: ['purchase:write', 'read'],
  READ_ONLY: ['read'],
}

export const roleLabels: Record<Role, string> = {
  SUPER_ADMIN: '超级管理员',
  WAREHOUSE_ADMIN: '仓库管理员',
  PURCHASE_ADMIN: '申购管理员',
  READ_ONLY: '只读角色',
}
