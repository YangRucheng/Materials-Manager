import { onActivated, onMounted, reactive, ref, type Ref } from 'vue'
import { useRoute, useRouter, type RouteLocationNormalizedLoaded } from 'vue-router'
import { compactRouteQuery, routeQueryPositiveInteger } from '@/utils/routeQuery'
import type { Page } from '@/api/generated'

/** 传给 fetch 的分页状态（由 composable 合成，调用方据此构造 typed query） */
export interface PagedFetchParams {
  page: number
  page_size: number
}

/** URL 同步配置：分页与筛选写入 URL，可从 URL 恢复（KeepAlive 页用） */
export interface UsePagedTableUrlSync<F extends object> {
  /** router.replace 的目标路由 name */
  routeName: string
  /** 把筛选状态序列化为 URL query；空值交给 compactRouteQuery 压缩 */
  toQuery: (filters: F) => Record<string, string | number | null | undefined>
  /** 首次挂载时从路由 query 恢复筛选状态 */
  fromQuery: (route: RouteLocationNormalizedLoaded) => F
}

/** usePagedTable 选项 */
export interface UsePagedTableOptions<T, F extends object> {
  /**
   * 分页查询函数，由调用方提供（不同页面调不同 API）。
   * 第一个参数是 reactive 的筛选状态，第二个是合成好的 page/page_size。
   * 调用方在此构造 typed 查询对象并调 typed API 方法。
   */
  fetch: (filters: F, pager: PagedFetchParams) => Promise<Page<T>>
  /** 初始筛选状态工厂：reactive 化；resetFilters 时再次调用以恢复空值（返回全新对象） */
  initialFilters: () => F
  /** 加载失败回调；缺省时静默（对应组 B / 组 D 的 load 无 catch） */
  onError?: (error: unknown) => void
  /** 每次成功加载后回调（清空已选行等） */
  onLoaded?: (data: Page<T>) => void
  /** query() 最前执行的回调（组 B 用于 clearExpandedName） */
  beforeQuery?: () => void
  /** 防空页回退：加载后 items 为空且 page>1 时自动退一页重载 */
  rollbackEmptyPage?: boolean
  /** 是否分页模式；false 时固定 page_size 全量拉取（组 D），默认 true */
  paginated?: boolean
  /** 默认每页条数，默认 20 */
  defaultPageSize?: number
  /** URL 同步；开启后 page/pageSize 从 URL 恢复、用户操作后写回 URL、onActivated 时重写 */
  urlSync?: UsePagedTableUrlSync<F>
  /** 是否挂载后立即加载，默认 true */
  immediate?: boolean
  /** 分页器可选每页条数，默认 [10, 20, 50, 100, 200] */
  pageSizeOptions?: number[]
}

/** usePagedTable 返回值 */
export interface UsePagedTable<T, F extends object> {
  items: Ref<T[]>
  total: Ref<number>
  page: Ref<number>
  pageSize: Ref<number>
  loading: Ref<boolean>
  /** reactive 代理，直接用于模板 v-model 与 fetch 读取 */
  filters: F
  pageSizeOptions: number[]
  load: () => Promise<void>
  query: () => Promise<void>
  changePage: (nextPage?: number) => Promise<void>
  changePageSize: (nextPageSize?: number) => Promise<void>
  resetFilters: () => Promise<void>
  /** 无 urlSync 时为空操作；供 AI 查询等自定义路径复用 */
  syncRoute: () => Promise<void>
}

/**
 * 统一列表分页/加载/筛选/URL 同步逻辑，消除各列表页的重复代码。
 *
 * 设计约定：
 * - fetch 接收 (filters, pager)，由调用方在闭包内构造 typed query（见各 api 模块 XxxListQuery）。
 * - urlSync 开启时，page/pageSize/filters 从 URL 恢复，操作后写回 URL，onActivated 重写（KeepAlive）。
 * - 不传 onError 时错误静默，与现有组 B/D 页面行为一致。
 */
export function usePagedTable<T, F extends object>(
  options: UsePagedTableOptions<T, F>,
): UsePagedTable<T, F> {
  const {
    fetch,
    initialFilters,
    onError,
    onLoaded,
    beforeQuery,
    rollbackEmptyPage = false,
    paginated = true,
    defaultPageSize = 20,
    urlSync,
    immediate = true,
    pageSizeOptions = [10, 20, 50, 100, 200],
  } = options

  // 仅 urlSync 页面才需要路由上下文（useRoute/useRouter 必须在 setup 期调用）
  const route = urlSync ? useRoute() : null
  const router = urlSync ? useRouter() : null

  const page = ref(urlSync ? routeQueryPositiveInteger(route!.query.page, 1) : 1)
  const pageSize = ref(
    urlSync ? routeQueryPositiveInteger(route!.query.page_size, defaultPageSize) : defaultPageSize,
  )
  // reactive() 返回 UnwrapNestedRefs<F>，与 F 不完全同构；这里保持外部类型为 F，
  // 内部按 F 语义使用（filters 各字段仍是响应式的，reactive 代理透传读写）。
  const filters = reactive<F>(urlSync ? (urlSync.fromQuery(route!) as F) : initialFilters()) as F

  const items = ref<T[]>([]) as Ref<T[]>
  const total = ref(0)
  const loading = ref(false)

  async function syncRoute() {
    if (!urlSync || !router || !route) return
    await router.replace({
      name: urlSync.routeName,
      query: compactRouteQuery({
        page: page.value === 1 ? undefined : page.value,
        page_size: pageSize.value === defaultPageSize ? undefined : pageSize.value,
        ...urlSync.toQuery(filters),
      }),
    })
  }

  async function load() {
    loading.value = true
    try {
      const data = await fetch(
        filters,
        paginated
          ? { page: page.value, page_size: pageSize.value }
          : { page: 1, page_size: pageSize.value },
      )
      items.value = data.items
      total.value = data.total
      onLoaded?.(data)
      // 防空页回退：退页后重载，page 收敛到 1 时递归必然终止
      if (rollbackEmptyPage && paginated && data.items.length === 0 && page.value > 1) {
        page.value -= 1
        await load()
      }
    } catch (error) {
      onError?.(error)
    } finally {
      loading.value = false
    }
  }

  async function query() {
    beforeQuery?.()
    page.value = 1
    if (urlSync) await syncRoute()
    await load()
  }

  async function changePage(nextPage?: number) {
    if (nextPage !== undefined) page.value = nextPage
    if (urlSync) await syncRoute()
    await load()
  }

  async function changePageSize(nextPageSize?: number) {
    if (nextPageSize !== undefined) pageSize.value = nextPageSize
    page.value = 1
    if (urlSync) await syncRoute()
    await load()
  }

  async function resetFilters() {
    Object.assign(filters, initialFilters())
    await query()
  }

  if (urlSync) onActivated(() => void syncRoute())
  if (immediate) onMounted(() => void load())

  return {
    items,
    total,
    page,
    pageSize,
    loading,
    filters,
    pageSizeOptions,
    load,
    query,
    changePage,
    changePageSize,
    resetFilters,
    syncRoute,
  }
}
