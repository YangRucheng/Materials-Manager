import { http, HttpResponse } from 'msw'
import type {
  OperationUpdate,
  OperationWrite,
  MovePurchasePlansWrite,
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
  return {
    stock_material_id: material.id,
    name: material.name,
    model_spec: material.model_spec,
    unit_name: material.unit_name,
    decimal_places: unit(material.unit_id)?.decimal_places || 0,
    current_qty: material.current_qty,
    minimum_qty: minimum,
    is_low_stock: low,
    suggested_purchase_qty: String(
      Math.max(Number(minimum || 0) - Number(material.current_qty), 0),
    ),
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
  http.post(`${api}/stock-materials/:id/disable`, ({ params }) => {
    const item = stockMaterials.find((x) => x.id === Number(params.id))
    if (!item) return error(400, 'NOT_FOUND', '物资不存在')
    item.enabled = false
    item.version++
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
      const planDate = new Date().toISOString().slice(0, 10)
      const planIndex = purchaseMaterials.filter((item) => item.plan_date === planDate).length + 1
      const purchase = {
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

  http.get(`${api}/purchase-materials`, ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('keyword') || '').toLowerCase()
    const coded = url.searchParams.get('coded')
    const moved = url.searchParams.get('moved')
    return HttpResponse.json(
      page(
        purchaseMaterials.filter(
          (x) =>
            (!q ||
              `${x.plan_no}${x.material_code || ''}${x.name}${x.model_spec}`
                .toLowerCase()
                .includes(q)) &&
            (coded === null || Boolean(x.material_code) === (coded === 'true')) &&
            (moved === null || x.moved_to_record === (moved === 'true')),
        ),
        url,
      ),
    )
  }),
  http.get(`${api}/purchase-materials/:id`, ({ params }) => {
    const item = purchaseMaterials.find((x) => x.id === Number(params.id))
    return item ? HttpResponse.json(item) : error(400, 'NOT_FOUND', '申购物资不存在')
  }),
  http.post(`${api}/purchase-materials`, async ({ request }) => {
    const body = (await request.json()) as PurchaseMaterialWrite
    const u = unit(body.unit_id)
    if (!u) return error(422, 'VALIDATION_ERROR', '计量单位无效')
    const responsible = body.purchase_responsible || '\\'
    const planDate = body.plan_date || new Date().toISOString().slice(0, 10)
    const planIndex = purchaseMaterials.filter((item) => item.plan_date === planDate).length + 1
    const item = {
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
      salespersons: uniqueOptions(records.map((record) => record.salesperson)),
      statuses: uniqueOptions(records.map((record) => record.status)),
    })
  }),
  http.get(`${api}/purchase-records`, ({ request }) => {
    const url = new URL(request.url)
    const keyword = (url.searchParams.get('keyword') || '').toLowerCase()
    const name = (url.searchParams.get('name') || '').toLowerCase()
    const modelSpec = (url.searchParams.get('model_spec') || '').toLowerCase()
    const actualDemandPerson = (url.searchParams.get('actual_demand_person') || '').toLowerCase()
    const purchaseResponsible = (url.searchParams.get('purchase_responsible') || '').toLowerCase()
    const salesperson = (url.searchParams.get('salesperson') || '').toLowerCase()
    const status = url.searchParams.get('status')
    const emptyStatus = url.searchParams.get('empty_status') === 'true'
    const records = purchaseRequests.flatMap((purchaseRequest) =>
      purchaseRequest.lines.map((line) => purchaseRecord(purchaseRequest, line)),
    )
    return HttpResponse.json(
      page(
        records.filter(
          (record) =>
            (!keyword ||
              `${record.plan_no}${record.trace_no}${record.purchase_order_no || ''}${record.material_code || ''}${record.material_name}${record.salesperson || ''}${record.status}${record.plan_remark || ''}${record.record_remark || ''}`
                .toLowerCase()
                .includes(keyword)) &&
            (!name || record.material_name.toLowerCase().includes(name)) &&
            (!modelSpec || record.model_spec.toLowerCase().includes(modelSpec)) &&
            (!actualDemandPerson ||
              (record.actual_demand_person || '').toLowerCase().includes(actualDemandPerson)) &&
            (!purchaseResponsible ||
              (record.purchase_responsible || '').toLowerCase().includes(purchaseResponsible)) &&
            (!salesperson || (record.salesperson || '').toLowerCase().includes(salesperson)) &&
            (!status || record.status === status) &&
            (!emptyStatus || !record.status?.trim()),
        ),
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
