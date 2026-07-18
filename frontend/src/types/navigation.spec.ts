import { describe, expect, it } from 'vitest'
import { rolePermissions } from './navigation'

describe('四角色权限', () => {
  it('超级管理员拥有全部写权限', () => {
    expect(rolePermissions.SUPER_ADMIN).toEqual(
      expect.arrayContaining(['warehouse:write', 'purchase:write', 'settings:write']),
    )
  })
  it('仓库管理员仅能写仓库域', () => {
    expect(rolePermissions.WAREHOUSE_ADMIN).toContain('warehouse:write')
    expect(rolePermissions.WAREHOUSE_ADMIN).not.toContain('purchase:write')
  })
  it('申购管理员仅能写申购域', () => {
    expect(rolePermissions.PURCHASE_ADMIN).toContain('purchase:write')
    expect(rolePermissions.PURCHASE_ADMIN).not.toContain('warehouse:write')
  })
  it('只读角色没有写权限', () => {
    expect(rolePermissions.READ_ONLY).toEqual(['read'])
  })
})
