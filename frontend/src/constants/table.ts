import type { DataTableColumns } from 'naive-ui'

export const tableColumnWidths = {
  unit: 80,
  quantity: 110,
  date: 112,
  datetime: 172,
  status: 104,
  person: 120,
  code: 150,
  identifier: 176,
  name: 220,
  material: 280,
  model: 240,
  text: 200,
  action: 180,
} as const

export function preventTableColumnCompression<T>(
  columns: DataTableColumns<T>,
): DataTableColumns<T> {
  return columns.map((column) => {
    const lockedColumn = { ...column }
    if (lockedColumn.type === 'selection' && lockedColumn.width === undefined) {
      lockedColumn.width = 48
    }
    if (lockedColumn.width !== undefined && lockedColumn.minWidth === undefined) {
      lockedColumn.minWidth = lockedColumn.width
    }
    return lockedColumn
  }) as DataTableColumns<T>
}

export function getTableScrollX<T>(columns: DataTableColumns<T>): number {
  return columns.reduce((total, column) => {
    if ('children' in column && column.children) {
      return total + getTableScrollX(column.children)
    }
    const width = Number(column.minWidth ?? column.width ?? tableColumnWidths.text)
    return total + (Number.isFinite(width) ? width : tableColumnWidths.text)
  }, 0)
}
