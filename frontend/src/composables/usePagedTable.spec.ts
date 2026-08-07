import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { usePagedTable, type PagedFetchParams } from './usePagedTable'
import type { Page } from '@/api/generated'

type Item = { id: number }
type Filters = { keyword: string }

function pageOf(items: Item[], page: number, pageSize: number, total: number): Page<Item> {
  return { items, page, page_size: pageSize, total }
}

function routeWith(query: Record<string, string | undefined>): RouteLocationNormalizedLoaded {
  return { query } as unknown as RouteLocationNormalizedLoaded
}

// vue-router mock：仅在 urlSync 场景被 usePagedTable 调用
const mocks = vi.hoisted(() => ({
  routeQuery: {} as Record<string, string | undefined>,
  replace: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeWith(mocks.routeQuery),
  useRouter: () => ({ replace: mocks.replace }),
}))

beforeEach(() => {
  mocks.routeQuery = {}
  mocks.replace.mockClear()
})

describe('usePagedTable', () => {
  it('loads the first page on load() and exposes items/total/loading', async () => {
    const fetchMock = vi.fn().mockResolvedValue(pageOf([{ id: 1 }], 1, 20, 1))
    const { items, total, loading, filters, load } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      immediate: false,
    })
    await load()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: '' }),
      expect.objectContaining({ page: 1, page_size: 20 }),
    )
    expect(items.value).toEqual([{ id: 1 }])
    expect(total.value).toBe(1)
    expect(loading.value).toBe(false)
    filters.keyword = 'x'
    expect(filters.keyword).toBe('x')
  })

  it('query() resets page to 1 and reloads; beforeQuery runs first', async () => {
    const fetchMock = vi.fn().mockResolvedValue(pageOf([], 1, 20, 0))
    const beforeQuery = vi.fn()
    const { page, query } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      beforeQuery,
    })
    fetchMock.mockClear()
    page.value = 3
    await query()

    expect(beforeQuery).toHaveBeenCalled()
    expect(page.value).toBe(1)
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.anything(),
      expect.objectContaining({ page: 1 }),
    )
  })

  it('changePage/changePageSize update pager and reload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(pageOf([], 1, 20, 0))
    const { page, pageSize, changePage, changePageSize } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
    })
    fetchMock.mockClear()

    await changePage(2)
    expect(page.value).toBe(2)
    expect(fetchMock).toHaveBeenLastCalledWith(expect.anything(), { page: 2, page_size: 20 })

    fetchMock.mockClear()
    await changePageSize(50)
    expect(pageSize.value).toBe(50)
    expect(page.value).toBe(1)
    expect(fetchMock).toHaveBeenLastCalledWith(expect.anything(), { page: 1, page_size: 50 })
  })

  it('resetFilters restores initial filters and queries', async () => {
    const fetchMock = vi.fn().mockResolvedValue(pageOf([], 1, 20, 0))
    const { filters, resetFilters } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
    })
    filters.keyword = 'hello'
    await resetFilters()
    expect(filters.keyword).toBe('')
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ keyword: '' }),
      expect.anything(),
    )
  })

  it('rollbackEmptyPage: page 2 empty rolls back to page 1 and reloads', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(pageOf([], 2, 20, 20))
      .mockResolvedValueOnce(pageOf([{ id: 99 }], 1, 20, 20))
    const { page, items, changePage } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      rollbackEmptyPage: true,
    })
    await changePage(2)

    expect(page.value).toBe(1)
    expect(items.value).toEqual([{ id: 99 }])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('rollbackEmptyPage: page 1 empty does not loop forever', async () => {
    const fetchMock = vi.fn().mockResolvedValue(pageOf([], 1, 20, 0))
    const { items, load } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      rollbackEmptyPage: true,
    })
    await load()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(items.value).toEqual([])
  })

  it('paginated:false uses fixed page_size and no page param', async () => {
    const fetchMock = vi.fn().mockResolvedValue(pageOf([{ id: 1 }], 1, 200, 1))
    const { items, load } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      paginated: false,
      defaultPageSize: 200,
      immediate: false,
    })
    await load()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ page: 1, page_size: 200 }),
    )
    expect(items.value).toEqual([{ id: 1 }])
  })

  it('silently swallows errors when no onError is provided', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('boom'))
    const { loading, load } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      immediate: false,
    })
    await load()
    expect(loading.value).toBe(false)
  })

  it('calls onError when provided', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('boom'))
    const onError = vi.fn()
    const { load } = usePagedTable<Item, Filters>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ keyword: '' }),
      onError,
      immediate: false,
    })
    await load()
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('urlSync: page/pageSize/filters restored from URL, syncRoute writes URL', async () => {
    type F = { name: string; status: string[] }
    mocks.routeQuery = { page: '3', page_size: '50', name: '电机', status: '正常,紧急' }
    const urlSync = {
      routeName: 'purchase-materials',
      fromQuery: (route: RouteLocationNormalizedLoaded) => ({
        name: String(route.query.name || ''),
        status: String(route.query.status || '')
          .split(',')
          .filter(Boolean),
      }),
      toQuery: (f: F) => ({ name: f.name || undefined, status: f.status.join(',') || undefined }),
    }
    const fetchMock = vi.fn().mockResolvedValue(pageOf([], 1, 20, 0))
    const { filters, page, pageSize, syncRoute } = usePagedTable<Item, F>({
      fetch: (f, p) => fetchMock(f, p),
      initialFilters: () => ({ name: '', status: [] }),
      urlSync,
      immediate: false,
    })

    // 从 URL 恢复
    expect(page.value).toBe(3)
    expect(pageSize.value).toBe(50)
    expect(filters.name).toBe('电机')
    expect(filters.status).toEqual(['正常', '紧急'])

    // 写回 URL：非默认 page/page_size 保留，toQuery 字段合并
    filters.name = '水泵'
    filters.status = ['正常']
    await syncRoute()
    expect(mocks.replace).toHaveBeenCalledWith({
      name: 'purchase-materials',
      query: { page: '3', page_size: '50', name: '水泵', status: '正常' },
    })
  })

  it('fetch receives typed filters object for typed Query construction', async () => {
    type TypedF = { keyword?: string; min_qty?: string }
    const seen: Array<{ f: TypedF; p: PagedFetchParams }> = []
    const { filters, load } = usePagedTable<Item, TypedF>({
      fetch: (f, p) => {
        seen.push({ f, p })
        return Promise.resolve(pageOf([], 1, 20, 0))
      },
      initialFilters: () => ({ keyword: '' }),
      immediate: false,
    })
    filters.keyword = 'abc'
    await load()
    expect(seen[0].f.keyword).toBe('abc')
    expect(seen[0].p.page).toBe(1)
  })
})
