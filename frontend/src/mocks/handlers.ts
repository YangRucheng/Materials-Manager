import { http, HttpResponse } from 'msw'
import type {
  AiSearchSettingsWrite,
  OperationUpdate,
  OperationWrite,
  MovePurchasePlansWrite,
  PurchaseMaterial,
  PurchaseMaterialBatchUpdate,
  PurchaseMaterialWrite,
  PurchaseRecordWrite,
  ReplenishmentDraftWrite,
  ReplenishmentPolicy,
  StockMaterialWrite,
  StockOperation,
} from '@/api/generated'
import {
  mockFileId,
  nextIds,
  operations,
  purchaseMaterials,
  purchaseRequests,
  stockMaterials,
  units,
  users,
} from './data'

const api = '/api/v1'
let aiSettings = {
  endpoint: 'https://example.test/v1',
  model: 'fast-model',
  enabled: true,
  api_key_configured: true,
  updated_at: new Date().toISOString(),
  version: 1,
}
const now = () => new Date().toISOString()
const mockImage = (id: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240"><rect width="100%" height="100%" fill="#e8f5ee"/><text x="160" y="125" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#456">备件图片 ${id}</text></svg>`
const page = <T>(items: T[], url: URL) => {
  const current = Number(url.searchParams.get('page') || 1)
  const size = Number(url.searchParams.get('page_size') || 20)
  return {
    items: items.slice((current - 1) * size, current * size),
    page: current,
    page_size: size,
    total: items.length,
  }
}
const orSearchTerms = (value: string | null) =>
  (value || '')
    .replace(/｜/g, '|')
    .split('|')
    .map((term) => term.trim().toLowerCase())
    .filter((term, index, terms) => Boolean(term) && terms.indexOf(term) === index)
const aiExpandedSearch = (value: string | null, enabled: boolean) =>
  enabled && value ? value.replace(/(^|[|｜])电机(?=$|[|｜])/g, '$1电机|电动机') : value
const matchesOrSearch = (value: string | number | null | undefined, search: string | null) => {
  const terms = orSearchTerms(search)
  if (!terms.length) return true
  const normalizedValue = String(value ?? '').toLowerCase()
  return terms.some((term) => normalizedValue.includes(term))
}
const error = (status: number, code: string, message: string, details?: Record<string, unknown>) =>
  HttpResponse.json({ code, message, details, request_id: crypto.randomUUID() }, { status })
const actor = (request: Request) => {
  const token = request.headers.get('Authorization')?.replace('Bearer mock-', '')
  return users.find((x) => x.username === token) || users[0]
}
const unit = (id: number | null) => units.find((x) => x.id === id)
const purchaseRecord = (
  request: (typeof purchaseRequests)[number],
  line: (typeof purchaseRequests)[number]['lines'][number],
) => {
  const material = purchaseMaterials.find((item) => item.id === line.purchase_material_id)!
  return {
    line_id: line.id,
    purchase_request_id: request.id,
    purchase_material_id: line.purchase_material_id,
    plan_no: material.plan_no,
    plan_date: material.plan_date,
    purchase_order_no: request.purchase_order_no,
    trace_no: request.trace_no,
    status: line.status,
    material_code: line.material_code_snapshot,
    material_name: line.material_name_snapshot,
    model_spec: line.model_spec_snapshot,
    unit_id: material.unit_id,
    unit_name: line.unit_name_snapshot,
    purchase_qty: line.purchase_qty,
    actual_demand_person: material.actual_demand_person,
    purchase_responsible: material.purchase_responsible,
    salesperson: request.salesperson,
    plan_remark: material.remark,
    record_remark: request.record_remark,
    usage: line.usage,
    subitem_no: line.subitem_no,
    images: material.images,
    stock_material_id: material.stock_material_id,
    purchase_date: request.purchase_date,
    created_at: request.created_at,
    updated_at: material.updated_at,
    version: request.version,
  }
}
const movePlansToRecords = (materials: typeof purchaseMaterials, body: MovePurchasePlansWrite) => {
  const lines = materials.map((material) => ({
    id: nextIds.requestLine++,
    purchase_material_id: material.id,
    material_code_snapshot: material.material_code,
    material_name_snapshot: material.name,
    model_spec_snapshot: material.model_spec,
    unit_name_snapshot: material.unit_name,
    purchase_qty: material.planned_qty,
    status: body.status,
    usage: material.usage,
    subitem_no: material.subitem_no,
  }))
  const purchaseRequest: (typeof purchaseRequests)[number] = {
    id: nextIds.request++,
    purchase_order_no: body.purchase_order_no,
    trace_no: body.trace_no,
    salesperson: body.salesperson,
    record_remark: body.record_remark,
    purchase_date: body.purchase_date,
    created_at: now(),
    version: 1,
    lines,
  }
  materials.forEach((material) => (material.moved_to_record = true))
  purchaseRequests.unshift(purchaseRequest)
  return lines.map((line) => purchaseRecord(purchaseRequest, line))
}
const inventoryBalance = (material: (typeof stockMaterials)[number]) => {
  const minimum = material.replenishment_policy?.minimum_qty
  const low = Boolean(
    material.replenishment_policy?.enabled &&
    minimum !== undefined &&
    Number(material.current_qty) <= Number(minimum),
  )
  const endAt = new Date()
  const startAt = new Date(endAt)
  startAt.setMonth(startAt.getMonth() - 6)
  const reversedIds = new Set(
    operations
      .map((operation) => operation.reversal_of_id)
      .filter((id): id is number => Boolean(id)),
  )
  const recentConsumption = operations
    .filter((operation) => {
      const occurredAt = new Date(operation.occurred_at)
      return (
        operation.operation_type === 'OUTBOUND' &&
        operation.source_type !== 'REVERSAL' &&
        !reversedIds.has(operation.id) &&
        occurredAt >= startAt &&
        occurredAt <= endAt
      )
    })
    .flatMap((operation) => operation.lines)
    .filter((line) => line.stock_material_id === material.id)
    .reduce((sum, line) => sum + Number(line.quantity), 0)
  return {
    stock_material_id: material.id,
    name: material.name,
    model_spec: material.model_spec,
    unit_name: material.unit_name,
    decimal_places: unit(material.unit_id)?.decimal_places || 0,
    current_qty: material.current_qty,
    minimum_qty: minimum,
    is_low_stock: low,
    suggested_purchase_qty: String(recentConsumption),
    updated_at: material.updated_at,
  }
}
const makeOperation = (payload: OperationWrite, type: 'INBOUND' | 'OUTBOUND'): StockOperation => {
  const existing = operations.find((x) => x.client_request_id === payload.client_request_id)
  if (existing) return existing
  const id = nextIds.operation++
  const lines = payload.lines.map((line, index) => {
    const material = stockMaterials.find((x) => x.id === line.stock_material_id)!
    const before = Number(material.current_qty)
    const after =
      type === 'INBOUND' ? before + Number(line.quantity) : before - Number(line.quantity)
    material.current_qty = String(after)
    material.updated_at = now()
    material.version++
    return {
      id: id * 10 + index,
      stock_material_id: material.id,
      material_name: material.name,
      model_spec: material.model_spec,
      unit_name: material.unit_name,
      quantity: line.quantity,
      before_qty: String(before),
      after_qty: String(after),
    }
  })
  const op: StockOperation = {
    id,
    operation_no: `${type === 'INBOUND' ? 'IN' : 'OUT'}20260717${String(id).padStart(4, '0')}`,
    operation_type: type,
    occurred_at: payload.occurred_at,
    business_reason: payload.business_reason,
    receiver_name: payload.receiver_name,
    subitem_no: payload.subitem_no,
    source_type: payload.source_type,
    client_request_id: payload.client_request_id,
    created_at: now(),
    version: 1,
    lines,
  }
  operations.unshift(op)
  return op
}

export const handlers = [
  http.post(`${api}/ai-search/expand`, async ({ request }) => {
    const body = (await request.json()) as { value: string }
    const expanded = body.value
      .split('|')
      .flatMap((value) => (value.trim() === '电机' ? ['电机', '电动机'] : [value.trim()]))
      .filter(Boolean)
      .filter((value, index, values) => values.indexOf(value) === index)
      .join('|')
    return HttpResponse.json({ original: body.value, expanded })
  }),
  http.get(`${api}/ai-search/status`, () =>
    HttpResponse.json({ available: aiSettings.enabled && aiSettings.api_key_configured }),
  ),
  http.get(`${api}/ai-search/settings`, ({ request }) =>
    actor(request).role === 'SUPER_ADMIN'
      ? HttpResponse.json(aiSettings)
      : error(403, 'FORBIDDEN', '没有执行此操作的权限'),
  ),
  http.put(`${api}/ai-search/settings`, async ({ request }) => {
    if (actor(request).role !== 'SUPER_ADMIN')
      return error(403, 'FORBIDDEN', '没有执行此操作的权限')
    const body = (await request.json()) as AiSearchSettingsWrite
    aiSettings = {
      endpoint: body.endpoint.replace(/\/$/, ''),
      model: body.model,
      enabled: body.enabled,
      api_key_configured: body.clear_api_key
        ? false
        : Boolean(body.api_key) || aiSettings.api_key_configured,
      updated_at: now(),
      version: aiSettings.version + 1,
    }
    return HttpResponse.json(aiSettings)
  }),
  http.post(`${api}/ai-search/settings/test`, () =>
    HttpResponse.json({ original: '电机', expanded: '电机|电动机' }),
  ),
  http.post(`${api}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    const user = users.find((x) => x.username === body.username && x.enabled)
    if (!user || body.password !== '123456')
      return error(401, 'INVALID_CREDENTIALS', '用户名或密码错误')
    return HttpResponse.json({ access_token: `mock-${user.username}`, token_type: 'bearer', user })
  }),
  http.get(`${api}/auth/me`, ({ request }) => HttpResponse.json(actor(request))),
  http.get(`${api}/dashboard/summary`, () => {
    const balances = stockMaterials.map(inventoryBalance)
    return HttpResponse.json({
      stock_material_count: stockMaterials.length,
      low_stock_count: balances.filter((x) => x.is_low_stock).length,
      uncoded_purchase_material_count: purchaseMaterials.filter((x) => !x.material_code).length,
      purchase_record_count: purchaseRequests.flatMap((item) => item.lines).length,
    })
  }),
  http.get(`${api}/measurement-units`, ({ request }) =>
    HttpResponse.json(page(units, new URL(request.url))),
  ),
  http.post(`${api}/measurement-units`, async ({ request }) => {
    const body = (await request.json()) as Partial<(typeof units)[number]>
    const item = {
      id: nextIds.unit++,
      code: body.code!,
      name: body.name!,
      decimal_places: body.decimal_places || 0,
      enabled: body.enabled ?? true,
      version: 1,
    } as (typeof units)[number]
    units.push(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.patch(`${api}/measurement-units/:id`, async ({ params, request }) => {
    const item = units.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '计量单位不存在')
    Object.assign(item, await request.json(), { version: item.version + 1 })
    return HttpResponse.json(item)
  }),
  http.get(`${api}/users`, ({ request }) => HttpResponse.json(page(users, new URL(request.url)))),
  http.post(`${api}/users`, async ({ request }) => {
    const body = (await request.json()) as Partial<(typeof users)[number]>
    const item = {
      id: nextIds.user++,
      username: body.username!,
      display_name: body.display_name!,
      role: body.role || 'READ_ONLY',
      enabled: body.enabled ?? true,
      version: 1,
    }
    users.push(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.patch(`${api}/users/:id`, async ({ params, request }) => {
    const item = users.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '用户不存在')
    const body = (await request.json()) as Partial<(typeof users)[number]>
    if (body.username && users.some((x) => x.id !== item.id && x.username === body.username))
      return error(409, 'DUPLICATE_USERNAME', '用户名已存在')
    Object.assign(item, body, { version: item.version + 1 })
    return HttpResponse.json(item)
  }),
  http.delete(`${api}/users/:id`, ({ params, request }) => {
    const item = users.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '用户不存在')
    if (item.id === actor(request).id)
      return error(409, 'CANNOT_DELETE_CURRENT_USER', '不能删除当前登录用户')
    users.splice(users.indexOf(item), 1)
    return new HttpResponse(null, { status: 204 })
  }),

  http.get(`${api}/stock-materials`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    const list = stockMaterials.filter(
      (x) => !q || `${x.name}${x.model_spec}`.toLowerCase().includes(q),
    )
    return HttpResponse.json(page(list, url))
  }),
  http.get(`${api}/stock-materials/:id`, ({ params }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(400, 'NOT_FOUND', '二级库物资不存在')
  }),
  http.post(`${api}/stock-materials`, async ({ request }) => {
    const body = (await request.json()) as StockMaterialWrite
    const u = unit(body.unit_id)
    if (!u) return error(422, 'VALIDATION_ERROR', '计量单位无效')
    if (
      stockMaterials.some(
        (x) =>
          x.name.trim() === body.name.trim() &&
          x.model_spec.trim() === body.model_spec.trim() &&
          x.unit_id === body.unit_id,
      )
    )
      return error(409, 'DUPLICATE_MATERIAL', '名称、规格和单位相同的物资已存在')
    const item = {
      id: nextIds.stock++,
      name: body.name.trim(),
      model_spec: body.model_spec.trim(),
      unit_id: u.id,
      unit_name: u.name,
      remark: body.remark,
      current_qty: '0',
      images: [],
      created_at: now(),
      updated_at: now(),
      version: 1,
    }
    stockMaterials.push(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.patch(`${api}/stock-materials/:id`, async ({ params, request }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '物资不存在')
    const body = (await request.json()) as StockMaterialWrite
    const u = unit(body.unit_id)
    Object.assign(item, body, {
      unit_name: u?.name || item.unit_name,
      updated_at: now(),
      version: item.version + 1,
    })
    return HttpResponse.json(item)
  }),
  http.put(`${api}/stock-materials/:id/replenishment-policy`, async ({ params, request }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '物资不存在')
    item.replenishment_policy = (await request.json()) as ReplenishmentPolicy
    item.version++
    return HttpResponse.json(item)
  }),
  http.get(`${api}/inventory/balances`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    return HttpResponse.json(
      page(
        stockMaterials
          .map(inventoryBalance)
          .filter((x) => !q || `${x.name}${x.model_spec}`.toLowerCase().includes(q)),
        url,
      ),
    )
  }),
  http.get(`${api}/inventory/balances/:id`, ({ params }) => {
    const material = stockMaterials.find((item) => item.id === Number(params.id))
    return material
      ? HttpResponse.json(inventoryBalance(material))
      : error(400, 'NOT_FOUND', '库存物资不存在')
  }),
  http.get(`${api}/inventory/low-stock`, ({ request }) => {
    const url = new URL(request.url)
    return HttpResponse.json(
      page(
        stockMaterials.map(inventoryBalance).filter((x) => x.is_low_stock),
        url,
      ),
    )
  }),
  http.post(`${api}/inventory/inbounds`, async ({ request }) => {
    const body = (await request.json()) as OperationWrite
    return HttpResponse.json(makeOperation(body, 'INBOUND'), {
      status: 201,
    })
  }),
  http.post(`${api}/inventory/outbounds`, async ({ request }) => {
    const body = (await request.json()) as OperationWrite
    if (!body.receiver_name?.trim()) return error(400, 'RECEIVER_REQUIRED', '出库必须填写领用人')
    return HttpResponse.json(makeOperation(body, 'OUTBOUND'), {
      status: 201,
    })
  }),
  http.get(`${api}/inventory/operations`, ({ request }) => {
    const url = new URL(request.url)
    const operationNo = url.searchParams.get('operation_no') || ''
    const type = url.searchParams.get('operation_type')
    const material = url.searchParams.get('material_name') || ''
    const list = operations.filter(
      (x) =>
        (!operationNo || x.operation_no.includes(operationNo)) &&
        (!type || x.operation_type === type) &&
        (!material || x.lines.some((l) => l.material_name.includes(material))),
    )
    return HttpResponse.json(page(list, url))
  }),
  http.get(`${api}/inventory/operations/:id`, ({ params }) => {
    const item = operations.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(400, 'NOT_FOUND', '流水不存在')
  }),
  http.patch(`${api}/inventory/operations/:id`, async ({ params, request }) => {
    const item = operations.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '流水不存在')
    const body = (await request.json()) as OperationUpdate
    for (const line of item.lines) {
      const material = stockMaterials.find((candidate) => candidate.id === line.stock_material_id)
      if (material) {
        const signed =
          item.operation_type === 'INBOUND' ? Number(line.quantity) : -Number(line.quantity)
        material.current_qty = String(Number(material.current_qty) - signed)
      }
    }
    item.lines = body.lines.map((line, index) => {
      const material = stockMaterials.find((candidate) => candidate.id === line.stock_material_id)!
      const before = Number(material.current_qty)
      const signed =
        body.operation_type === 'INBOUND' ? Number(line.quantity) : -Number(line.quantity)
      material.current_qty = String(before + signed)
      return {
        id: item.id * 10 + index,
        stock_material_id: material.id,
        material_name: material.name,
        model_spec: material.model_spec,
        unit_name: material.unit_name,
        quantity: line.quantity,
        before_qty: String(before),
        after_qty: material.current_qty,
      }
    })
    Object.assign(item, {
      operation_type: body.operation_type,
      occurred_at: body.occurred_at,
      source_type: body.source_type,
      business_reason: body.business_reason,
      receiver_name: body.receiver_name,
      subitem_no: body.subitem_no,
      version: item.version + 1,
    })
    return HttpResponse.json(item)
  }),
  http.post(`${api}/inventory/operations/:id/reverse`, async ({ params, request }) => {
    const original = operations.find((x) => x.id === Number(params.id))
    if (!original) return error(400, 'NOT_FOUND', '流水不存在')
    const body = (await request.json()) as { client_request_id: string; reason: string }
    const type = original.operation_type === 'INBOUND' ? 'OUTBOUND' : 'INBOUND'
    const op = makeOperation(
      {
        client_request_id: body.client_request_id,
        occurred_at: now(),
        source_type: 'REVERSAL',
        business_reason: body.reason,
        lines: original.lines.map((x) => ({
          stock_material_id: x.stock_material_id,
          quantity: x.quantity,
        })),
      },
      type,
    )
    op.reversal_of_id = original.id
    return HttpResponse.json(op, { status: 201 })
  }),
  http.get(`${api}/inventory/replenishment-defaults`, () => {
    const latest = [...purchaseMaterials]
      .sort((left, right) => right.id - left.id)
      .find((item) => item.purchase_responsible.trim() && item.purchase_responsible !== '\\')
    return HttpResponse.json({
      purchase_responsible: latest?.purchase_responsible || '',
      demand_date: new Date().toISOString().slice(0, 10),
    })
  }),
  http.post(
    `${api}/inventory/low-stock/:id/create-replenishment-draft`,
    async ({ params, request }) => {
      const stock = stockMaterials.find((x) => x.id === Number(params.id))
      if (!stock) return error(400, 'NOT_FOUND', '物资不存在')
      const body = (await request.json()) as ReplenishmentDraftWrite
      const suggested = inventoryBalance(stock).suggested_purchase_qty
      const previousPlans = purchaseMaterials.filter(
        (item) => item.stock_material_id === stock.id && item.material_code,
      )
      const previous = previousPlans[previousPlans.length - 1]
      const quantityNote = `补库计划：建议申购 ${suggested} ${stock.unit_name}${
        body.planned_qty === suggested ? '' : `，确认计划 ${body.planned_qty} ${stock.unit_name}`
      }`
      const planDate = body.demand_date || new Date().toISOString().slice(0, 10)
      const planIndex = purchaseMaterials.filter((item) => item.plan_date === planDate).length + 1
      const purchase: PurchaseMaterial = {
        id: nextIds.purchase++,
        plan_no: `PLAN-${planDate.replace(/-/g, '')}-${String(planIndex).padStart(3, '0')}`,
        plan_date: planDate,
        material_code: previous?.material_code,
        name: stock.name,
        model_spec: stock.model_spec,
        unit_id: stock.unit_id,
        unit_name: stock.unit_name,
        actual_demand_person: body.actual_demand_person,
        purchase_responsible: body.purchase_responsible,
        planned_qty: body.planned_qty,
        usage: '低库存补库',
        status: '正常',
        moved_to_record: false,
        remark: [stock.remark, quantityNote].filter(Boolean).join('；'),
        stock_material_id: stock.id,
        stock_material_name: stock.name,
        enabled: true,
        images: [...stock.images],
        created_at: now(),
        updated_at: now(),
        version: 1,
      }
      purchaseMaterials.unshift(purchase)
      return HttpResponse.json({ next: 'purchase_material', resource_id: purchase.id })
    },
  ),

  http.get(`${api}/purchase-materials/filter-options`, ({ request }) => {
    const url = new URL(request.url)
    const moved = url.searchParams.get('moved')
    const status = actor(request).role === 'SUPER_ADMIN' ? null : '正常'
    const plans = purchaseMaterials.filter(
      (item) =>
        (moved === null || item.moved_to_record === (moved === 'true')) &&
        (status === null || item.status === status),
    )
    const uniqueOptions = (values: Array<string | null | undefined>) =>
      [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])].sort()
    return HttpResponse.json({
      actual_demand_persons: uniqueOptions(plans.map((item) => item.actual_demand_person)),
      purchase_responsibles: uniqueOptions(plans.map((item) => item.purchase_responsible)),
      subitem_nos: uniqueOptions(plans.map((item) => item.subitem_no)),
    })
  }),
  http.get(`${api}/purchase-materials`, ({ request }) => {
    const url = new URL(request.url)
    const currentUser = actor(request)
    const keyword = url.searchParams.get('keyword')
    const searchField = url.searchParams.get('search_field')
    const searchValue = url.searchParams.get('search_value')
    const name = aiExpandedSearch(
      url.searchParams.get('name'),
      url.searchParams.get('ai_expand') === 'true',
    )
    const modelSpec = url.searchParams.get('model_spec')
    const actualDemandPerson = url.searchParams.get('actual_demand_person')
    const emptyActualDemandPerson = url.searchParams.get('empty_actual_demand_person') === 'true'
    const purchaseResponsible = url.searchParams.get('purchase_responsible')
    const subitemNo = url.searchParams.get('subitem_no')
    const emptySubitemNo = url.searchParams.get('empty_subitem_no') === 'true'
    const coded = url.searchParams.get('coded')
    const moved = url.searchParams.get('moved')
    const status = url.searchParams.get('status')
    if (currentUser.role !== 'SUPER_ADMIN' && status === '已归档')
      return error(403, 'ARCHIVED_PURCHASE_PLAN_FORBIDDEN', '仅超级管理员可查询已归档申购计划')
    const effectiveStatus = currentUser.role === 'SUPER_ADMIN' ? status : '正常'
    return HttpResponse.json(
      page(
        purchaseMaterials.filter((x) => {
          const searchValues: Record<string, string | number | null | undefined> = {
            plan_no: x.plan_no,
            plan_date: x.plan_date,
            material_code: x.material_code,
            name: x.name,
            model_spec: x.model_spec,
            unit_name: x.unit_name,
            planned_qty: x.planned_qty,
            usage: x.usage,
            subitem_no: x.subitem_no,
            remark: x.remark,
          }
          return (
            matchesOrSearch(
              `${x.plan_no}${x.plan_date}${x.material_code || ''}${x.name}${x.model_spec}${x.unit_name}${x.planned_qty}${x.actual_demand_person || ''}${x.purchase_responsible || ''}${x.usage}${x.subitem_no || ''}${x.remark || ''}`,
              keyword,
            ) &&
            (!searchField || matchesOrSearch(searchValues[searchField], searchValue)) &&
            matchesOrSearch(x.name, name) &&
            matchesOrSearch(x.model_spec, modelSpec) &&
            (emptyActualDemandPerson
              ? !x.actual_demand_person?.trim() ||
                ['\\', '/', '—', '-'].includes(x.actual_demand_person)
              : matchesOrSearch(x.actual_demand_person, actualDemandPerson)) &&
            matchesOrSearch(x.purchase_responsible, purchaseResponsible) &&
            (emptySubitemNo ? !x.subitem_no?.trim() : !subitemNo || x.subitem_no === subitemNo) &&
            (coded === null || Boolean(x.material_code) === (coded === 'true')) &&
            (moved === null || x.moved_to_record === (moved === 'true')) &&
            (effectiveStatus === null || x.status === effectiveStatus)
          )
        }),
        url,
      ),
    )
  }),
  http.get(`${api}/purchase-materials/:id`, ({ params, request }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    if (item?.status === '已归档' && actor(request).role !== 'SUPER_ADMIN')
      return error(403, 'ARCHIVED_PURCHASE_PLAN_FORBIDDEN', '仅超级管理员可查询已归档申购计划')
    return item ? HttpResponse.json(item) : error(400, 'NOT_FOUND', '申购物资不存在')
  }),
  http.post(`${api}/purchase-materials`, async ({ request }) => {
    const body = (await request.json()) as PurchaseMaterialWrite
    const u = unit(body.unit_id)
    if (!u) return error(422, 'VALIDATION_ERROR', '计量单位无效')
    const responsible = body.purchase_responsible || '\\'
    const planDate = body.plan_date || new Date().toISOString().slice(0, 10)
    const planIndex = purchaseMaterials.filter((item) => item.plan_date === planDate).length + 1
    const item: PurchaseMaterial = {
      id: nextIds.purchase++,
      plan_no: `PLAN-${planDate.replace(/-/g, '')}-${String(planIndex).padStart(3, '0')}`,
      plan_date: planDate,
      material_code: body.material_code || undefined,
      name: body.name,
      model_spec: body.model_spec,
      unit_id: u.id,
      unit_name: u.name,
      actual_demand_person: body.actual_demand_person || responsible,
      purchase_responsible: responsible,
      planned_qty: body.planned_qty,
      usage: body.usage,
      subitem_no: body.subitem_no,
      remark: body.remark,
      stock_material_id: body.stock_material_id,
      stock_material_name: stockMaterials.find((stock) => stock.id === body.stock_material_id)
        ?.name,
      status: body.status || '正常',
      moved_to_record: false,
      enabled: true,
      images: [],
      created_at: now(),
      updated_at: now(),
      version: 1,
    }
    purchaseMaterials.push(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.patch(`${api}/purchase-materials/batch`, async ({ request }) => {
    const body = (await request.json()) as PurchaseMaterialBatchUpdate
    const materials = body.materials.map((reference) =>
      purchaseMaterials.find((item) => item.id === reference.id),
    )
    if (materials.some((material) => !material)) return error(400, 'NOT_FOUND', '申购计划不存在')
    const plans = materials.filter((material) => material !== undefined)
    if (plans.some((item, index) => item.version !== body.materials[index].version))
      return error(409, 'VERSION_CONFLICT', '数据已被其他用户修改')
    for (const item of plans) {
      if (body.plan_date !== undefined) item.plan_date = body.plan_date
      if (body.actual_demand_person !== undefined)
        item.actual_demand_person = body.actual_demand_person
      if ('subitem_no' in body) item.subitem_no = body.subitem_no || undefined
      if (body.usage !== undefined) item.usage = body.usage
      if (body.status !== undefined) item.status = body.status
      item.version++
      item.updated_at = now()
    }
    return HttpResponse.json(plans)
  }),
  http.patch(`${api}/purchase-materials/:id`, async ({ params, request }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '申购物资不存在')
    const body = (await request.json()) as PurchaseMaterialWrite
    const selectedUnit = unit(body.unit_id)
    Object.assign(item, body, {
      unit_name: selectedUnit?.name || item.unit_name,
      stock_material_name: stockMaterials.find((stock) => stock.id === body.stock_material_id)
        ?.name,
      version: item.version + 1,
      updated_at: now(),
    })
    return HttpResponse.json(item)
  }),
  http.delete(`${api}/purchase-materials/:id`, ({ params, request }) => {
    const index = purchaseMaterials.findIndex((x) => x.id === Number(params.id))
    if (index < 0) return error(400, 'NOT_FOUND', '申购物资不存在')
    const item = purchaseMaterials[index]
    const version = Number(new URL(request.url).searchParams.get('version'))
    if (version !== item.version) return error(409, 'VERSION_CONFLICT', '数据已被其他用户修改')
    if (item.moved_to_record)
      return error(409, 'PURCHASE_PLAN_IN_USE', '已转入申购记录的计划不能删除')
    purchaseMaterials.splice(index, 1)
    return new HttpResponse(null, { status: 204 })
  }),
  http.post(`${api}/purchase-materials/:id/link-stock-material`, async ({ params, request }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    const body = (await request.json()) as { stock_material_id: number }
    const stock = stockMaterials.find((x) => x.id === body.stock_material_id)
    if (!item || !stock) return error(400, 'NOT_FOUND', '物资不存在')
    item.stock_material_id = stock.id
    item.stock_material_name = stock.name
    item.version++
    return HttpResponse.json(item)
  }),
  http.post(`${api}/purchase-materials/batch-move-to-record`, async ({ request }) => {
    const body = (await request.json()) as MovePurchasePlansWrite & { material_ids: number[] }
    const materials = body.material_ids.map((id) =>
      purchaseMaterials.find((item) => item.id === id),
    )
    if (materials.some((material) => !material)) return error(400, 'NOT_FOUND', '申购计划不存在')
    const plans = materials.filter((material) => material !== undefined)
    const uncoded = plans.filter((material) => !material.material_code)
    if (uncoded.length) return error(409, 'MATERIAL_CODE_REQUIRED', '未编码物资不能转入申购记录')
    if (plans.some((material) => material.moved_to_record))
      return error(409, 'PLAN_ALREADY_MOVED', '部分申购计划已转入申购记录')
    return HttpResponse.json(movePlansToRecords(plans, body))
  }),
  http.post(`${api}/purchase-materials/:id/move-to-record`, async ({ params, request }) => {
    const material = purchaseMaterials.find((item) => item.id === Number(params.id))
    if (!material) return error(400, 'NOT_FOUND', '申购计划不存在')
    if (!material.material_code)
      return error(409, 'MATERIAL_CODE_REQUIRED', '物资编码完成后才能转入申购记录')
    if (material.moved_to_record)
      return error(409, 'PLAN_ALREADY_MOVED', '该申购计划已转入申购记录')
    const body = (await request.json()) as MovePurchasePlansWrite
    return HttpResponse.json(movePlansToRecords([material], body)[0])
  }),
  http.get(`${api}/purchase-records/filter-options`, () => {
    const records = purchaseRequests.flatMap((purchaseRequest) =>
      purchaseRequest.lines.map((line) => purchaseRecord(purchaseRequest, line)),
    )
    const uniqueOptions = (values: Array<string | null | undefined>) =>
      [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])].sort()
    return HttpResponse.json({
      actual_demand_persons: uniqueOptions(records.map((record) => record.actual_demand_person)),
      purchase_responsibles: uniqueOptions(records.map((record) => record.purchase_responsible)),
      subitem_nos: uniqueOptions(records.map((record) => record.subitem_no)),
      salespersons: uniqueOptions(records.map((record) => record.salesperson)),
      statuses: uniqueOptions(records.map((record) => record.status)),
    })
  }),
  http.get(`${api}/purchase-records`, ({ request }) => {
    const url = new URL(request.url)
    const keyword = url.searchParams.get('keyword')
    const searchField = url.searchParams.get('search_field')
    const searchValue = url.searchParams.get('search_value')
    const purchaseOrderNo = url.searchParams.get('purchase_order_no')
    const traceNo = url.searchParams.get('trace_no')
    const name = aiExpandedSearch(
      url.searchParams.get('name'),
      url.searchParams.get('ai_expand') === 'true',
    )
    const modelSpec = url.searchParams.get('model_spec')
    const actualDemandPerson = url.searchParams.get('actual_demand_person')
    const purchaseResponsible = url.searchParams.get('purchase_responsible')
    const salesperson = url.searchParams.get('salesperson')
    const status = url.searchParams.get('status')
    const emptyStatus = url.searchParams.get('empty_status') === 'true'
    const records = purchaseRequests.flatMap((purchaseRequest) =>
      purchaseRequest.lines.map((line) => purchaseRecord(purchaseRequest, line)),
    )
    return HttpResponse.json(
      page(
        records.filter((record) => {
          const searchValues: Record<string, string | number | null | undefined> = {
            plan_no: record.plan_no,
            plan_date: record.plan_date,
            purchase_order_no: record.purchase_order_no,
            trace_no: record.trace_no,
            material_code: record.material_code,
            material_name: record.material_name,
            model_spec: record.model_spec,
            unit_name: record.unit_name,
            purchase_qty: record.purchase_qty,
            salesperson: record.salesperson,
            status: record.status,
            purchase_date: record.purchase_date,
            usage: record.usage,
            subitem_no: record.subitem_no,
            plan_remark: record.plan_remark,
            record_remark: record.record_remark,
          }
          return (
            matchesOrSearch(
              `${record.plan_no}${record.plan_date}${record.trace_no || ''}${record.purchase_order_no || ''}${record.material_code || ''}${record.material_name}${record.model_spec}${record.unit_name}${record.purchase_qty}${record.actual_demand_person || ''}${record.purchase_responsible || ''}${record.salesperson || ''}${record.status}${record.purchase_date}${record.usage || ''}${record.subitem_no || ''}${record.plan_remark || ''}${record.record_remark || ''}`,
              keyword,
            ) &&
            (!searchField || matchesOrSearch(searchValues[searchField], searchValue)) &&
            matchesOrSearch(record.purchase_order_no, purchaseOrderNo) &&
            matchesOrSearch(record.trace_no, traceNo) &&
            matchesOrSearch(record.material_name, name) &&
            matchesOrSearch(record.model_spec, modelSpec) &&
            matchesOrSearch(record.actual_demand_person, actualDemandPerson) &&
            matchesOrSearch(record.purchase_responsible, purchaseResponsible) &&
            matchesOrSearch(record.salesperson, salesperson) &&
            (!status || record.status === status) &&
            (!emptyStatus || !record.status?.trim())
          )
        }),
        url,
      ),
    )
  }),
  http.get(`${api}/purchase-records/:id`, ({ params }) => {
    for (const purchaseRequest of purchaseRequests) {
      const line = purchaseRequest.lines.find((item) => item.id === Number(params.id))
      if (line) return HttpResponse.json(purchaseRecord(purchaseRequest, line))
    }
    return error(400, 'NOT_FOUND', '申购记录不存在')
  }),
  http.patch(`${api}/purchase-records/:id`, async ({ params, request }) => {
    for (const purchaseRequest of purchaseRequests) {
      const line = purchaseRequest.lines.find((item) => item.id === Number(params.id))
      if (!line) continue
      const body = (await request.json()) as PurchaseRecordWrite
      const material = purchaseMaterials.find((item) => item.id === line.purchase_material_id)!
      const selectedUnit = unit(body.unit_id)
      if (!selectedUnit) return error(422, 'VALIDATION_ERROR', '计量单位无效')
      Object.assign(material, {
        plan_date: body.plan_date,
        material_code: body.material_code,
        name: body.material_name,
        model_spec: body.model_spec,
        unit_id: selectedUnit.id,
        unit_name: selectedUnit.name,
        actual_demand_person: body.actual_demand_person,
        purchase_responsible: body.purchase_responsible,
        planned_qty: body.purchase_qty,
        usage: body.usage,
        subitem_no: body.subitem_no,
        remark: body.plan_remark,
        stock_material_id: body.stock_material_id,
        images: body.image_ids.map(
          (id) =>
            material.images.find((image) => image.id === id) || {
              id,
              original_name: '申购附件.png',
              mime_type: 'image/png' as const,
              size_bytes: 0,
              width: 800,
              height: 600,
            },
        ),
        updated_at: now(),
        version: material.version + 1,
      })
      Object.assign(line, {
        material_code_snapshot: material.material_code,
        material_name_snapshot: material.name,
        model_spec_snapshot: material.model_spec,
        unit_name_snapshot: material.unit_name,
        purchase_qty: body.purchase_qty,
        status: body.status,
        usage: body.usage,
        subitem_no: body.subitem_no,
      })
      Object.assign(purchaseRequest, {
        purchase_order_no: body.purchase_order_no,
        trace_no: body.trace_no,
        purchase_date: body.purchase_date,
        salesperson: body.salesperson,
        record_remark: body.record_remark,
        version: purchaseRequest.version + 1,
      })
      return HttpResponse.json(purchaseRecord(purchaseRequest, line))
    }
    return error(400, 'NOT_FOUND', '申购记录不存在')
  }),
  http.get(
    `${api}/files/images/:id`,
    ({ params }) =>
      new HttpResponse(mockImage(String(params.id)), {
        headers: { 'Content-Type': 'image/svg+xml' },
      }),
  ),
  http.post(`${api}/files/images`, async ({ request }) => {
    const form = await request.formData()
    const file = form.get('file') as File
    const id = mockFileId(nextIds.file++)
    return HttpResponse.json(
      {
        id,
        original_name: file.name,
        mime_type: 'image/png',
        size_bytes: file.size,
        width: 800,
        height: 600,
      },
      { status: 201 },
    )
  }),
  http.delete(`${api}/files/images/:id`, () => new HttpResponse(null, { status: 204 })),
]
