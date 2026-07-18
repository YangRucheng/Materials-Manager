import { http, HttpResponse } from 'msw'
import type {
  OperationUpdate,
  OperationWrite,
  PurchaseMaterialWrite,
  PurchaseRequestStatus,
  PurchaseRequestWrite,
  ReplenishmentPolicy,
  StockMaterialWrite,
  StockOperation,
} from '@/api/generated'
import { defaultPurchaseRequestNo } from '@/utils/purchase'
import {
  mockImageUrl,
  nextIds,
  operations,
  projects,
  purchaseMaterials,
  purchaseRequests,
  stockMaterials,
  units,
  users,
} from './data'

const api = '/api/v1'
const now = () => new Date().toISOString()
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
const error = (status: number, code: string, message: string, details?: Record<string, unknown>) =>
  HttpResponse.json({ code, message, details, request_id: crypto.randomUUID() }, { status })
const actor = (request: Request) => {
  const token = request.headers.get('Authorization')?.replace('Bearer mock-', '')
  return users.find((x) => x.username === token) || users[0]
}
const event = (action: string, old_status?: string, new_status?: string, remark?: string) => ({
  id: nextIds.event++,
  action,
  old_status,
  new_status,
  operator_name: '当前用户',
  occurred_at: now(),
  remark,
})
const unit = (id: number | null) => units.find((x) => x.id === id)
const project = (id: number | null) => projects.find((x) => x.id === id)
const recalcRequest = (lineId: number) => {
  const request = purchaseRequests.find((x) => x.lines.some((line) => line.id === lineId))
  if (!request) return
  if (request.lines.every((line) => Number(line.received_qty) >= Number(line.requested_qty)))
    request.status = 'COMPLETED'
  else if (request.lines.some((line) => Number(line.received_qty) > 0))
    request.status = 'PARTIALLY_RECEIVED'
  else request.status = request.handler_name ? 'PROCESSING' : 'SUBMITTED'
}
const inventoryBalance = (material: (typeof stockMaterials)[number]) => {
  const purchaseIds = new Set(
    purchaseMaterials.filter((x) => x.stock_material_id === material.id).map((x) => x.id),
  )
  const onOrder = purchaseRequests
    .filter((r) => ['SUBMITTED', 'PROCESSING', 'PARTIALLY_RECEIVED'].includes(r.status))
    .flatMap((r) => r.lines)
    .filter((line) => purchaseIds.has(line.purchase_material_id))
    .reduce((sum, line) => sum + Number(line.requested_qty) - Number(line.received_qty), 0)
  const minimum = material.replenishment_policy?.minimum_qty
  const target = material.replenishment_policy?.target_qty
  const low = Boolean(
    material.replenishment_policy?.enabled &&
    minimum !== undefined &&
    Number(material.current_qty) <= Number(minimum),
  )
  return {
    stock_material_id: material.id,
    name: material.name,
    model_spec: material.model_spec,
    unit_name: material.unit_name,
    decimal_places: unit(material.unit_id)?.decimal_places || 0,
    current_qty: material.current_qty,
    minimum_qty: minimum,
    target_qty: target,
    on_order_qty: String(onOrder),
    is_low_stock: low,
    warning_state: low
      ? onOrder > 0
        ? ('ON_ORDER' as const)
        : ('PENDING_PURCHASE' as const)
      : undefined,
    suggested_purchase_qty: String(
      Math.max(Number(target || 0) - Number(material.current_qty) - onOrder, 0),
    ),
    updated_at: material.updated_at,
  }
}
const makeOperation = (
  payload: OperationWrite,
  type: 'INBOUND' | 'OUTBOUND',
  username: string,
): StockOperation => {
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
    if (line.purchase_request_line_id && type === 'INBOUND') {
      const requestLine = purchaseRequests
        .flatMap((x) => x.lines)
        .find((x) => x.id === line.purchase_request_line_id)
      if (requestLine)
        requestLine.received_qty = String(Number(requestLine.received_qty) + Number(line.quantity))
      recalcRequest(line.purchase_request_line_id)
    }
    return {
      id: id * 10 + index,
      stock_material_id: material.id,
      material_name: material.name,
      model_spec: material.model_spec,
      unit_name: material.unit_name,
      quantity: line.quantity,
      before_qty: String(before),
      after_qty: String(after),
      purchase_request_line_id: line.purchase_request_line_id,
    }
  })
  const purchaseRequest = purchaseRequests.find((r) =>
    r.lines.some((l) => payload.lines.some((x) => x.purchase_request_line_id === l.id)),
  )
  const op: StockOperation = {
    id,
    operation_no: `${type === 'INBOUND' ? 'IN' : 'OUT'}20260717${String(id).padStart(4, '0')}`,
    operation_type: type,
    occurred_at: payload.occurred_at,
    operator_name: username,
    business_reason: payload.business_reason,
    receiver_name: payload.receiver_name,
    project_subitem_id: payload.project_subitem_id,
    source_type: payload.source_type,
    purchase_request_no: purchaseRequest?.request_no,
    client_request_id: payload.client_request_id,
    created_at: now(),
    version: 1,
    lines,
  }
  operations.unshift(op)
  return op
}

export const handlers = [
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
      pending_purchase_count: balances.filter((x) => x.warning_state === 'PENDING_PURCHASE').length,
      on_order_count: balances.filter((x) => x.warning_state === 'ON_ORDER').length,
      uncoded_purchase_material_count: purchaseMaterials.filter((x) => !x.material_code).length,
      pending_purchase_request_count: purchaseRequests.filter((x) =>
        ['SUBMITTED', 'PROCESSING'].includes(x.status),
      ).length,
      partially_received_count: purchaseRequests.filter((x) => x.status === 'PARTIALLY_RECEIVED')
        .length,
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
    if (!item) return error(404, 'NOT_FOUND', '计量单位不存在')
    Object.assign(item, await request.json(), { version: item.version + 1 })
    return HttpResponse.json(item)
  }),
  http.get(`${api}/project-subitems`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    return HttpResponse.json(
      page(
        projects.filter(
          (x) => !q || Object.values(x).some((v) => String(v).toLowerCase().includes(q)),
        ),
        url,
      ),
    )
  }),
  http.post(`${api}/project-subitems`, async ({ request }) => {
    const body = (await request.json()) as Partial<(typeof projects)[number]>
    const item = {
      id: nextIds.project++,
      project_code: body.project_code!,
      project_name: body.project_name!,
      subitem_no: body.subitem_no!,
      subitem_name: body.subitem_name!,
      enabled: body.enabled ?? true,
      version: 1,
    }
    projects.push(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.patch(`${api}/project-subitems/:id`, async ({ params, request }) => {
    const item = projects.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '项目子项不存在')
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
    if (!item) return error(404, 'NOT_FOUND', '用户不存在')
    const body = (await request.json()) as Partial<(typeof users)[number]>
    if (body.username && users.some((x) => x.id !== item.id && x.username === body.username))
      return error(409, 'DUPLICATE_USERNAME', '用户名已存在')
    Object.assign(item, body, { version: item.version + 1 })
    return HttpResponse.json(item)
  }),
  http.delete(`${api}/users/:id`, ({ params, request }) => {
    const item = users.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '用户不存在')
    if (item.id === actor(request).id)
      return error(409, 'CANNOT_DELETE_CURRENT_USER', '不能删除当前登录用户')
    const referenced =
      operations.some((operation) => operation.operator_name === item.display_name) ||
      purchaseMaterials.some((material) => material.purchase_responsible_id === item.id)
    if (referenced) return error(409, 'USER_IN_USE', '该用户已有操作记录或业务数据关联，不能删除')
    users.splice(users.indexOf(item), 1)
    return new HttpResponse(null, { status: 204 })
  }),

  http.get(`${api}/stock-materials`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    const enabled = url.searchParams.get('enabled')
    const list = stockMaterials.filter(
      (x) =>
        (!q || `${x.name}${x.model_spec}`.toLowerCase().includes(q)) &&
        (enabled === null || String(x.enabled) === enabled),
    )
    return HttpResponse.json(page(list, url))
  }),
  http.get(`${api}/stock-materials/:id`, ({ params }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(404, 'NOT_FOUND', '二级库物资不存在')
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
      enabled: true,
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
    if (!item) return error(404, 'NOT_FOUND', '物资不存在')
    const body = (await request.json()) as StockMaterialWrite
    const u = unit(body.unit_id)
    Object.assign(item, body, {
      unit_name: u?.name || item.unit_name,
      updated_at: now(),
      version: item.version + 1,
    })
    return HttpResponse.json(item)
  }),
  http.post(`${api}/stock-materials/:id/disable`, ({ params }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '物资不存在')
    item.enabled = false
    item.version++
    return HttpResponse.json(item)
  }),
  http.put(`${api}/stock-materials/:id/replenishment-policy`, async ({ params, request }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '物资不存在')
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
    return HttpResponse.json(makeOperation(body, 'INBOUND', actor(request).display_name), {
      status: 201,
    })
  }),
  http.post(`${api}/inventory/outbounds`, async ({ request }) => {
    const body = (await request.json()) as OperationWrite
    return HttpResponse.json(makeOperation(body, 'OUTBOUND', actor(request).display_name), {
      status: 201,
    })
  }),
  http.get(`${api}/inventory/operations`, ({ request }) => {
    const url = new URL(request.url)
    const operationNo = url.searchParams.get('operation_no') || ''
    const type = url.searchParams.get('operation_type')
    const material = url.searchParams.get('material_name') || ''
    const requestNo = url.searchParams.get('purchase_request_no') || ''
    const list = operations.filter(
      (x) =>
        (!operationNo || x.operation_no.includes(operationNo)) &&
        (!type || x.operation_type === type) &&
        (!material || x.lines.some((l) => l.material_name.includes(material))) &&
        (!requestNo || x.purchase_request_no?.includes(requestNo)),
    )
    return HttpResponse.json(page(list, url))
  }),
  http.get(`${api}/inventory/operations/:id`, ({ params }) => {
    const item = operations.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(404, 'NOT_FOUND', '流水不存在')
  }),
  http.patch(`${api}/inventory/operations/:id`, async ({ params, request }) => {
    const item = operations.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '流水不存在')
    const body = (await request.json()) as OperationUpdate
    const affectedRequestLines = new Set<number>()
    for (const line of item.lines) {
      const material = stockMaterials.find((candidate) => candidate.id === line.stock_material_id)
      if (material) {
        const signed =
          item.operation_type === 'INBOUND' ? Number(line.quantity) : -Number(line.quantity)
        material.current_qty = String(Number(material.current_qty) - signed)
      }
      if (line.purchase_request_line_id) {
        const requestLine = purchaseRequests
          .flatMap((candidate) => candidate.lines)
          .find((candidate) => candidate.id === line.purchase_request_line_id)
        if (requestLine) {
          const signed =
            item.operation_type === 'INBOUND' ? Number(line.quantity) : -Number(line.quantity)
          requestLine.received_qty = String(Number(requestLine.received_qty) - signed)
          affectedRequestLines.add(requestLine.id)
        }
      }
    }
    item.lines = body.lines.map((line, index) => {
      const material = stockMaterials.find((candidate) => candidate.id === line.stock_material_id)!
      const before = Number(material.current_qty)
      const signed =
        body.operation_type === 'INBOUND' ? Number(line.quantity) : -Number(line.quantity)
      material.current_qty = String(before + signed)
      if (line.purchase_request_line_id) {
        const requestLine = purchaseRequests
          .flatMap((candidate) => candidate.lines)
          .find((candidate) => candidate.id === line.purchase_request_line_id)
        if (requestLine) {
          requestLine.received_qty = String(Number(requestLine.received_qty) + signed)
          affectedRequestLines.add(requestLine.id)
        }
      }
      return {
        id: item.id * 10 + index,
        stock_material_id: material.id,
        material_name: material.name,
        model_spec: material.model_spec,
        unit_name: material.unit_name,
        quantity: line.quantity,
        before_qty: String(before),
        after_qty: material.current_qty,
        purchase_request_line_id: line.purchase_request_line_id,
      }
    })
    Object.assign(item, {
      operation_type: body.operation_type,
      occurred_at: body.occurred_at,
      source_type: body.source_type,
      business_reason: body.business_reason,
      receiver_name: body.receiver_name,
      project_subitem_id: body.project_subitem_id,
      version: item.version + 1,
    })
    affectedRequestLines.forEach(recalcRequest)
    return HttpResponse.json(item)
  }),
  http.post(`${api}/inventory/operations/:id/reverse`, async ({ params, request }) => {
    const original = operations.find((x) => x.id === Number(params.id))
    if (!original) return error(404, 'NOT_FOUND', '流水不存在')
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
      actor(request).display_name,
    )
    op.reversal_of_id = original.id
    return HttpResponse.json(op, { status: 201 })
  }),
  http.post(`${api}/inventory/low-stock/:id/create-replenishment-draft`, ({ params }) => {
    const stock = stockMaterials.find((x) => x.id === Number(params.id))
    if (!stock) return error(404, 'NOT_FOUND', '物资不存在')
    const suggested = inventoryBalance(stock).suggested_purchase_qty
    const previousPlans = purchaseMaterials.filter(
      (item) => item.stock_material_id === stock.id && item.material_code,
    )
    const previous = previousPlans[previousPlans.length - 1]
    const purchase = {
      id: nextIds.purchase++,
      material_code: previous?.material_code,
      name: stock.name,
      model_spec: stock.model_spec,
      unit_id: stock.unit_id,
      unit_name: stock.unit_name,
      actual_demand_person: '仓库管理员',
      purchase_responsible_id: 2,
      purchase_responsible_name: '仓库管理员',
      remark: [stock.remark, `补库计划：建议申购 ${suggested} ${stock.unit_name}`]
        .filter(Boolean)
        .join('；'),
      stock_material_id: stock.id,
      stock_material_name: stock.name,
      code_state: previous?.material_code ? ('CODED' as const) : ('UNCODED' as const),
      enabled: true,
      images: [...stock.images],
      created_at: now(),
      updated_at: now(),
      version: 1,
    }
    purchaseMaterials.unshift(purchase)
    return HttpResponse.json({ next: 'purchase_material', resource_id: purchase.id })
  }),

  http.get(`${api}/purchase-materials`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    const coded = url.searchParams.get('coded')
    return HttpResponse.json(
      page(
        purchaseMaterials.filter(
          (x) =>
            (!q || `${x.material_code || ''}${x.name}${x.model_spec}`.toLowerCase().includes(q)) &&
            (coded === null || Boolean(x.material_code) === (coded === 'true')),
        ),
        url,
      ),
    )
  }),
  http.get(`${api}/purchase-materials/:id`, ({ params }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(404, 'NOT_FOUND', '申购物资不存在')
  }),
  http.post(`${api}/purchase-materials`, async ({ request }) => {
    const body = (await request.json()) as PurchaseMaterialWrite
    const u = unit(body.unit_id)
    if (!u) return error(422, 'VALIDATION_ERROR', '计量单位无效')
    const responsible =
      users.find((user) => user.id === body.purchase_responsible_id) || actor(request)
    const item = {
      id: nextIds.purchase++,
      material_code: body.material_code || undefined,
      name: body.name,
      model_spec: body.model_spec,
      unit_id: u.id,
      unit_name: u.name,
      actual_demand_person: body.actual_demand_person || responsible.display_name,
      purchase_responsible_id: responsible.id,
      purchase_responsible_name: responsible.display_name,
      remark: body.remark,
      stock_material_id: body.stock_material_id,
      code_state: body.material_code ? ('CODED' as const) : ('UNCODED' as const),
      enabled: true,
      images: [],
      created_at: now(),
      updated_at: now(),
      version: 1,
    }
    purchaseMaterials.push(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.patch(`${api}/purchase-materials/:id`, async ({ params, request }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '申购物资不存在')
    const body = (await request.json()) as PurchaseMaterialWrite
    const selectedUnit = unit(body.unit_id)
    const responsible = users.find((user) => user.id === body.purchase_responsible_id)
    Object.assign(item, body, {
      unit_name: selectedUnit?.name || item.unit_name,
      purchase_responsible_name: responsible?.display_name || item.purchase_responsible_name,
      code_state: body.material_code ? 'CODED' : 'UNCODED',
      version: item.version + 1,
      updated_at: now(),
    })
    return HttpResponse.json(item)
  }),
  http.post(`${api}/purchase-materials/:id/link-stock-material`, async ({ params, request }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    const body = (await request.json()) as { stock_material_id: number }
    const stock = stockMaterials.find((x) => x.id === body.stock_material_id)
    if (!item || !stock) return error(404, 'NOT_FOUND', '物资不存在')
    item.stock_material_id = stock.id
    item.stock_material_name = stock.name
    item.version++
    return HttpResponse.json(item)
  }),
  http.get(`${api}/purchase-requests`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    const status = url.searchParams.get('status')
    return HttpResponse.json(
      page(
        purchaseRequests.filter(
          (x) =>
            (!q ||
              `${x.request_no}${x.lines.map((l) => l.material_name_snapshot).join('')}`
                .toLowerCase()
                .includes(q)) &&
            (!status || x.status === status),
        ),
        url,
      ),
    )
  }),
  http.post(`${api}/purchase-requests`, async ({ request }) => {
    const body = (await request.json()) as PurchaseRequestWrite
    const id = nextIds.request++
    const selectedMaterials = body.lines.map((line) =>
      purchaseMaterials.find((item) => item.id === line.purchase_material_id),
    )
    const responsibleIds = new Set(selectedMaterials.map((item) => item?.purchase_responsible_id))
    if (responsibleIds.size > 1)
      return error(409, 'MULTIPLE_PURCHASE_RESPONSIBLES', '同一请购单只能包含同一申购负责人的计划')
    const lines = body.lines.map((line) => {
      const m = purchaseMaterials.find((x) => x.id === line.purchase_material_id)!
      const p = project(line.project_subitem_id)!
      return {
        id: nextIds.requestLine++,
        purchase_material_id: m.id,
        material_code_snapshot: m.material_code,
        material_name_snapshot: m.name,
        model_spec_snapshot: m.model_spec,
        unit_name_snapshot: m.unit_name,
        requested_qty: line.requested_qty,
        received_qty: '0',
        usage: line.usage,
        project_subitem_id: p.id,
        project_code_snapshot: p.project_code,
        subitem_no_snapshot: p.subitem_no,
        subitem_name_snapshot: p.subitem_name,
      }
    })
    const item = {
      id,
      request_no: body.request_no || defaultPurchaseRequestNo(),
      status: 'DRAFT' as const,
      applicant_name:
        selectedMaterials[0]?.purchase_responsible_name || actor(request).display_name,
      remark: body.remark,
      created_at: now(),
      version: 1,
      lines,
      events: [event('创建请购草稿', undefined, 'DRAFT')],
    }
    purchaseRequests.unshift(item)
    return HttpResponse.json(item, { status: 201 })
  }),
  http.get(`${api}/purchase-requests/:id`, ({ params }) => {
    const item = purchaseRequests.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(404, 'NOT_FOUND', '请购单不存在')
  }),
  http.patch(`${api}/purchase-requests/:id`, async ({ params, request }) => {
    const item = purchaseRequests.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '请购单不存在')
    if (!['DRAFT', 'RETURNED'].includes(item.status))
      return error(409, 'INVALID_STATUS_TRANSITION', '当前状态不可编辑')
    const body = (await request.json()) as PurchaseRequestWrite
    const selectedMaterials = body.lines.map((line) =>
      purchaseMaterials.find((material) => material.id === line.purchase_material_id),
    )
    const responsibleIds = new Set(
      selectedMaterials.map((material) => material?.purchase_responsible_id),
    )
    if (responsibleIds.size > 1)
      return error(409, 'MULTIPLE_PURCHASE_RESPONSIBLES', '同一请购单只能包含同一申购负责人的计划')
    item.request_no = body.request_no || item.request_no
    item.remark = body.remark
    item.applicant_name = selectedMaterials[0]?.purchase_responsible_name || item.applicant_name
    item.lines = body.lines.map((line) => {
      const m = purchaseMaterials.find((x) => x.id === line.purchase_material_id)!
      const p = project(line.project_subitem_id)!
      return {
        id: line.id || nextIds.requestLine++,
        purchase_material_id: m.id,
        material_code_snapshot: m.material_code,
        material_name_snapshot: m.name,
        model_spec_snapshot: m.model_spec,
        unit_name_snapshot: m.unit_name,
        requested_qty: line.requested_qty,
        received_qty: '0',
        usage: line.usage,
        project_subitem_id: p.id,
        project_code_snapshot: p.project_code,
        subitem_no_snapshot: p.subitem_no,
        subitem_name_snapshot: p.subitem_name,
      }
    })
    item.version++
    return HttpResponse.json(item)
  }),
  http.post(`${api}/purchase-requests/:id/:action`, async ({ params, request }) => {
    const item = purchaseRequests.find((x) => x.id === Number(params.id))
    if (!item) return error(404, 'NOT_FOUND', '请购单不存在')
    const action = String(params.action)
    const body = (await request.json().catch(() => ({}))) as Record<string, string>
    const transitions: Record<string, PurchaseRequestStatus> = {
      submit: 'SUBMITTED',
      accept: 'PROCESSING',
      return: 'RETURNED',
      cancel: 'CANCELED',
      close: 'CLOSED',
    }
    const next = transitions[action]
    const allowed: Record<string, string[]> = {
      submit: ['DRAFT', 'RETURNED'],
      accept: ['SUBMITTED'],
      return: ['SUBMITTED', 'PROCESSING'],
      cancel: ['DRAFT', 'RETURNED', 'SUBMITTED'],
      close: ['PROCESSING', 'PARTIALLY_RECEIVED'],
    }
    if (!next || !allowed[action].includes(item.status))
      return error(409, 'INVALID_STATUS_TRANSITION', '当前状态不允许此操作')
    if (action === 'submit') {
      const missing = item.lines.filter(
        (x) => !purchaseMaterials.find((m) => m.id === x.purchase_material_id)?.material_code,
      )
      if (missing.length)
        return error(409, 'MATERIAL_CODE_REQUIRED', '请购明细存在无编码物资', {
          line_ids: missing.map((x) => x.id),
        })
      item.lines.forEach((line) => {
        line.material_code_snapshot = purchaseMaterials.find(
          (m) => m.id === line.purchase_material_id,
        )?.material_code
      })
      item.submitted_at = now()
    }
    if (action === 'accept') item.handler_name = actor(request).display_name
    if (action === 'return') item.return_reason = body.reason
    if (action === 'close') item.close_reason = body.reason
    const old = item.status
    item.status = next
    item.events.push(event(action, old, next, body.reason))
    item.version++
    return HttpResponse.json(item)
  }),
  http.get(`${api}/purchase-requests/:id/receipts`, ({ params }) => {
    const item = purchaseRequests.find((x) => x.id === Number(params.id))
    const ids = new Set(item?.lines.map((x) => x.id) || [])
    return HttpResponse.json(
      operations.filter((x) =>
        x.lines.some((l) => l.purchase_request_line_id && ids.has(l.purchase_request_line_id)),
      ),
    )
  }),
  http.post(`${api}/purchase-request-lines/:id/prepare-inbound`, ({ params }) => {
    const line = purchaseRequests.flatMap((x) => x.lines).find((x) => x.id === Number(params.id))
    const request = purchaseRequests.find((x) => x.lines.some((l) => l.id === line?.id))
    const material = purchaseMaterials.find((x) => x.id === line?.purchase_material_id)
    if (!line || !request || !material) return error(404, 'NOT_FOUND', '请购行不存在')
    return HttpResponse.json({
      purchase_request_no: request.request_no,
      line_id: line.id,
      purchase_material_id: material.id,
      material_name: material.name,
      model_spec: material.model_spec,
      unit_name: material.unit_name,
      remaining_qty: String(Number(line.requested_qty) - Number(line.received_qty)),
      stock_material_id: material.stock_material_id,
    })
  }),
  http.post(`${api}/files/images`, async ({ request }) => {
    const form = await request.formData()
    const file = form.get('file') as File
    const id = nextIds.file++
    return HttpResponse.json(
      {
        id,
        original_name: file.name,
        url: mockImageUrl(id),
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
