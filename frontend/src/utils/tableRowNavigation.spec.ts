import { afterEach, describe, expect, it } from 'vitest'
import { createTableRowClickGuard } from './tableRowNavigation'

function mouseEvent(
  target: EventTarget,
  currentTarget: EventTarget,
  clientX = 0,
  clientY = 0,
): MouseEvent {
  return {
    button: 0,
    target,
    currentTarget,
    clientX,
    clientY,
  } as unknown as MouseEvent
}

afterEach(() => {
  window.getSelection()?.removeAllRanges()
  document.body.replaceChildren()
})

describe('表格行点击保护', () => {
  it('普通单击允许进入详情', () => {
    const row = document.createElement('div')
    const cell = document.createElement('span')
    row.append(cell)
    const guard = createTableRowClickGuard()

    guard.onMouseDown(mouseEvent(cell, row))

    expect(guard.shouldIgnore(mouseEvent(cell, row))).toBe(false)
  })

  it('点击交互元素时忽略整行跳转', () => {
    const row = document.createElement('div')
    const button = document.createElement('button')
    row.append(button)
    const guard = createTableRowClickGuard()

    guard.onMouseDown(mouseEvent(button, row))

    expect(guard.shouldIgnore(mouseEvent(button, row))).toBe(true)
  })

  it('拖动鼠标时忽略整行跳转', () => {
    const row = document.createElement('div')
    const cell = document.createElement('span')
    row.append(cell)
    const guard = createTableRowClickGuard()

    guard.onMouseDown(mouseEvent(cell, row, 10, 10))

    expect(guard.shouldIgnore(mouseEvent(cell, row, 16, 10))).toBe(true)
  })

  it('选中当前行文本时忽略整行跳转', () => {
    const row = document.createElement('div')
    const cell = document.createElement('span')
    cell.textContent = '可复制文本'
    row.append(cell)
    document.body.append(row)
    const range = document.createRange()
    range.selectNodeContents(cell)
    window.getSelection()?.addRange(range)
    const guard = createTableRowClickGuard()

    expect(guard.shouldIgnore(mouseEvent(cell, row))).toBe(true)
  })

  it('其他区域的文本选区不影响当前行跳转', () => {
    const row = document.createElement('div')
    const cell = document.createElement('span')
    row.append(cell)
    const outside = document.createElement('span')
    outside.textContent = '其他文本'
    document.body.append(row, outside)
    const range = document.createRange()
    range.selectNodeContents(outside)
    window.getSelection()?.addRange(range)
    const guard = createTableRowClickGuard()

    expect(guard.shouldIgnore(mouseEvent(cell, row))).toBe(false)
  })
})
