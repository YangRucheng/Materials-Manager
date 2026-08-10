// ==UserScript==
// @name         备件管理系统 - 华兴物料申购跟踪同步
// @namespace    https://materials-manager.qcloud.19890605.xyz/
// @version      1.0.0
// @description  从华兴帆软“物料申购跟踪”同步采购人、状态、合同号和船名。
// @match        https://materials-manager.qcloud.19890605.xyz/*
// @match        http://43.154.152.157:8080/webroot/decision/*
// @updateURL    https://github.com/YangRucheng/Materials-Manager/raw/refs/heads/main/example/script/huayou-new-sync.user.js
// @downloadURL  https://github.com/YangRucheng/Materials-Manager/raw/refs/heads/main/example/script/huayou-new-sync.user.js
// @connect      materials-manager.qcloud.19890605.xyz
// @connect      43.154.152.157
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_openInTab
// @grant        GM_cookie
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  const PLATFORM_ORIGIN = "http://43.154.152.157:8080";
  const PLATFORM_BASE = `${PLATFORM_ORIGIN}/webroot/decision`;
  const MATERIALS_API = "https://materials-manager.qcloud.19890605.xyz/api/v1";
  const VIEWLET =
    "%252F%25E6%2595%25B0%25E6%258D%25AE%25E5%2588%2586%25E6%259E%2590" +
    "%252F%25E4%25BB%2593%25E5%2582%25A8%25E7%25AE%25A1%25E7%2590%2586" +
    "%252F%25E7%2589%25A9%25E6%2596%2599%25E7%2594%25B3%25E8%25B4%25AD" +
    "%252F%25E7%2589%25A9%25E6%2596%2599%25E7%2594%25B3%25E8%25B4%25AD%25E8%25B7%259F%25E8%25B8%25AA.cpt";
  const PREFIX = "huaxing_tracking_sync_";
  const TASK_KEY = `${PREFIX}task`;
  const RESPONSE_PREFIX = `${PREFIX}response_`;
  const WORKER_PARAM = "huaxingSyncTask";
  const defaults = {
    platformUsername: "huaxing_jianxiu",
    platformPassword: "",
    adminUsername: "admin",
    adminPassword: "",
    intervalMinutes: 10,
    batchSize: 50,
    autoEnabled: false,
    dryRun: true,
    minimized: false,
    panelRight: 20,
    panelBottom: 20,
  };

  function key(name) {
    return `${PREFIX}${name}`;
  }
  function loadConfig() {
    return Object.fromEntries(
      Object.entries(defaults).map(([name, value]) => [
        name,
        GM_getValue(key(name), value),
      ]),
    );
  }
  function saveConfig(values) {
    config = { ...config, ...values };
    Object.entries(config).forEach(([name, value]) =>
      GM_setValue(key(name), value),
    );
  }
  function int(value, fallback, min, max) {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed)
      ? Math.min(max, Math.max(min, parsed))
      : fallback;
  }
  function clean(value) {
    return String(value ?? "")
      .replace(/\s+/g, " ")
      .trim();
  }
  function form(data) {
    return Object.entries(data)
      .map(
        ([name, value]) =>
          `${encodeURIComponent(name)}=${encodeURIComponent(value ?? "")}`,
      )
      .join("&");
  }
  function joined(values) {
    const value = [...new Set(values.map(clean).filter(Boolean))].join(" / ");
    return value.length <= 128 ? value : `${value.slice(0, 127)}…`;
  }
  function request({
    method = "GET",
    url,
    headers = {},
    data,
    responseType,
    timeout = 45000,
  }) {
    return new Promise((resolve, reject) =>
      GM_xmlhttpRequest({
        method,
        url,
        headers,
        data,
        responseType,
        timeout,
        anonymous: false,
        onload(response) {
          if (response.status >= 200 && response.status < 300) resolve(response);
          else {
            const detail = String(response.responseText || response.response || "");
            reject(new Error(`HTTP ${response.status}：${detail.slice(0, 300)}`));
          }
        },
        ontimeout: () => reject(new Error(`请求超时：${url}`)),
        onerror: (error) =>
          reject(new Error(error?.error || error?.message || `网络请求失败：${url}`)),
      }),
    );
  }
  async function json(options) {
    const response = await request(options);
    const text = String(response.responseText || response.response || "");
    try {
      return JSON.parse(text);
    } catch {
      throw new Error(`接口返回的不是有效 JSON：${text.slice(0, 200)}`);
    }
  }

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let cell = "";
    let quoted = false;
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (quoted) {
        if (char === '"' && text[index + 1] === '"') {
          cell += '"';
          index += 1;
        } else if (char === '"') quoted = false;
        else cell += char;
      } else if (char === '"') quoted = true;
      else if (char === ",") {
        row.push(cell);
        cell = "";
      } else if (char === "\n") {
        row.push(cell.replace(/\r$/, ""));
        rows.push(row);
        row = [];
        cell = "";
      } else cell += char;
    }
    if (cell || row.length) {
      row.push(cell.replace(/\r$/, ""));
      rows.push(row);
    }
    return rows;
  }
  function reportSections(text) {
    const sections = [];
    for (const row of parseCsv(text.replace(/^\uFEFF/, ""))) {
      if (clean(row[0]) === "序号") {
        sections.push({ headers: row.map(clean), rows: [] });
        continue;
      }
      const section = sections.at(-1);
      if (!section || !row.some((value, index) => index > 0 && clean(value))) continue;
      section.rows.push(
        Object.fromEntries(
          section.headers.map((header, index) => [header, clean(row[index])]),
        ),
      );
    }
    return sections;
  }
  function rowKey(row) {
    return [row["申购单号"], row["申购物料编码"], row["申购物料名称"]]
      .map(clean)
      .join("\u0000");
  }
  function quantity(value) {
    const parsed = Number(String(value ?? "").replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  }
  function progressStatus(trackingRows, quantityRows) {
    let rank = 0;
    const byKey = new Map(quantityRows.map((row) => [rowKey(row), row]));
    for (const tracking of trackingRows) {
      const quantities = byKey.get(rowKey(tracking));
      const requested = quantity(quantities?.["申购数量"]);
      const purchased = quantity(quantities?.["采购数量"]);
      const inbound = quantity(quantities?.["入库数量"]);
      if (inbound > 0 && requested > 0 && inbound >= requested) rank = Math.max(rank, 3);
      else if (inbound > 0) rank = Math.max(rank, 2);
      else if (purchased > 0 || tracking["采购合同号"]) rank = Math.max(rank, 1);
    }
    return ["已申购", "已采购", "部分入库", "已入库"][rank];
  }
  function parseReport(text, traceNo) {
    const sections = reportSections(text);
    const trackingSection = sections.find((section) =>
      section.headers.includes("追溯码"),
    );
    const quantitySection = sections.find((section) =>
      section.headers.includes("入库数量"),
    );
    if (!trackingSection) throw new Error("导出结果缺少追溯码数据区");
    const matched = trackingSection.rows.filter(
      (row) => clean(row["追溯码"]) === clean(traceNo),
    );
    if (!matched.length) return { count: 0 };
    return {
      count: matched.length,
      salesperson: joined(matched.map((row) => row["采购人"])),
      contractNo: joined(matched.map((row) => row["采购合同号"])),
      vesselNo: joined(matched.map((row) => row["船名"])),
      status: progressStatus(matched, quantitySection?.rows || []),
    };
  }
  function reportUrl(task) {
    const parameters = encodeURIComponent(
      encodeURIComponent(
        JSON.stringify({
          追溯码: task.traceNo,
          申购日期开始: "2020-01-01",
          申购日期截止: "2035-12-31",
          __pi__: true,
        }),
      ),
    );
    return `${PLATFORM_BASE}/view/report?viewlet=${VIEWLET}&__parameters__=${parameters}&${WORKER_PARAM}=${encodeURIComponent(task.id)}`;
  }
  function sessionId() {
    for (const script of document.scripts) {
      if (script.src) continue;
      const match = script.textContent.match(/var\s+sid\s*=\s*"([^"]+)"/);
      if (match) return match[1];
    }
    return "";
  }
  async function waitForReport() {
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      const text = document.body?.innerText || "";
      if (sessionId() && /共\d+行/.test(text) && document.querySelector(".sheet-table-canvas")) {
        await new Promise((resolve) => setTimeout(resolve, 800));
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
    throw new Error("物料申购跟踪报表加载超时");
  }
  async function runWorker(taskId) {
    const task = GM_getValue(TASK_KEY, null);
    if (!task || task.id !== taskId) return;
    const responseKey = `${RESPONSE_PREFIX}${taskId}`;
    try {
      if (document.title !== "物料申购跟踪") {
        throw new Error("物资平台未登录或无权访问物料申购跟踪");
      }
      await waitForReport();
      const sid = sessionId();
      const response = await request({
        method: "POST",
        url: `${PLATFORM_BASE}/url/report/v10/export`,
        headers: {
          Authorization: `Bearer ${task.token}`,
          sessionID: sid,
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        data: form({ format: "csv", extype: "page" }),
        responseType: "arraybuffer",
      });
      const text = new TextDecoder("utf-8").decode(response.response);
      GM_setValue(responseKey, {
        id: taskId,
        ok: true,
        result: parseReport(text, task.traceNo),
      });
    } catch (error) {
      GM_setValue(responseKey, {
        id: taskId,
        ok: false,
        error: error?.message || String(error),
      });
    } finally {
      setTimeout(() => window.close(), 150);
    }
  }

  const workerTaskId = new URLSearchParams(location.search).get(WORKER_PARAM);
  if (location.origin === PLATFORM_ORIGIN) {
    if (workerTaskId) runWorker(workerTaskId);
    return;
  }

  let config = loadConfig();
  let running = false;
  let timer = null;
  let host;
  let ui;
  const logs = [];
  let stats = { scanned: 0, found: 0, updated: 0, skipped: 0, failed: 0 };

  async function db(sql, parameters = {}, maxRows = 1000) {
    const result = await json({
      method: "POST",
      url: `${MATERIALS_API}/agent/database/execute`,
      headers: {
        "Content-Type": "application/json",
        "X-Agent-Username": config.adminUsername,
        "X-Agent-Password": config.adminPassword,
      },
      data: JSON.stringify({ sql, parameters, max_rows: maxRows }),
    });
    if (result?.code && result?.message) throw new Error(result.message);
    return result;
  }
  async function targets() {
    const limit = int(config.batchSize, 50, 1, 200);
    const cursor = Number(GM_getValue(key("cursor"), 0)) || 0;
    const result = await db(
      `SELECT prl.trace_no, COUNT(*) AS target_count, MAX(prl.id) AS cursor_id
FROM purchase_request_line prl
JOIN purchase_request pr ON pr.id = prl.purchase_request_id
WHERE prl.trace_no IS NOT NULL AND TRIM(prl.trace_no) <> ''
  AND (:cursor = 0 OR prl.id < :cursor)
  AND (
    prl.salesperson IS NULL OR TRIM(prl.salesperson) = ''
    OR pr.contract_no IS NULL OR TRIM(pr.contract_no) = ''
    OR pr.vessel_no IS NULL OR TRIM(pr.vessel_no) = ''
    OR prl.status IN ('已申购', '已采购', '部分入库')
  )
GROUP BY prl.trace_no
ORDER BY MAX(prl.id) DESC
LIMIT ${limit}`,
      { cursor },
      limit,
    );
    const rows = Array.isArray(result.rows) ? result.rows : [];
    if (!rows.length && cursor > 0) {
      GM_setValue(key("cursor"), 0);
      return targets();
    }
    return rows;
  }
  async function updateTarget(traceNo, result) {
    const requestSet = [];
    const lineSet = [];
    const parameters = { trace_no: traceNo };
    for (const [column, resultKey] of [
      ["contract_no", "contractNo"],
      ["vessel_no", "vesselNo"],
    ]) {
      if (!result[resultKey]) continue;
      requestSet.push(
        `pr.${column} = CASE WHEN pr.${column} IS NULL OR TRIM(pr.${column}) = '' THEN :${column} ELSE pr.${column} END`,
      );
      parameters[column] = result[resultKey];
    }
    if (result.salesperson) {
      lineSet.push(
        "prl.salesperson = CASE WHEN prl.salesperson IS NULL OR TRIM(prl.salesperson) = '' THEN :salesperson ELSE prl.salesperson END",
      );
      parameters.salesperson = result.salesperson;
    }
    if (result.status) {
      lineSet.push(`prl.status = CASE
  WHEN :status = '已入库' AND prl.status IN ('已申购', '已采购', '部分入库', '已入库') THEN :status
  WHEN :status = '部分入库' AND prl.status IN ('已申购', '已采购', '部分入库') THEN :status
  WHEN :status = '已采购' AND prl.status IN ('已申购', '已采购') THEN :status
  ELSE prl.status END`);
      parameters.status = result.status;
    }
    if (requestSet.length) {
      requestSet.push("pr.version = pr.version + 1", "pr.updated_at = CURRENT_TIMESTAMP(6)");
    }
    if (lineSet.length) {
      lineSet.push("prl.version = prl.version + 1", "prl.updated_at = CURRENT_TIMESTAMP(6)");
    }
    if (!requestSet.length && !lineSet.length) return { affected_rows: 0 };
    return db(
      `UPDATE purchase_request_line prl
JOIN purchase_request pr ON pr.id = prl.purchase_request_id
SET ${[...requestSet, ...lineSet].join(", ")}
WHERE prl.trace_no = :trace_no`,
      parameters,
      1,
    );
  }
  async function loginPlatform() {
    const result = await json({
      method: "POST",
      url: `${PLATFORM_BASE}/login`,
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify({
        username: config.platformUsername,
        password: config.platformPassword,
        validity: -1,
        encrypted: false,
      }),
    });
    const token = result?.data?.accessToken;
    if (!token) throw new Error(result?.errorMsg || "华兴物资平台登录失败");
    await new Promise((resolve, reject) =>
      GM_cookie.set(
        {
          url: PLATFORM_BASE,
          name: "fine_auth_token",
          value: token,
          path: "/",
          expirationDate: Math.floor(Date.now() / 1000) + 7200,
        },
        (error) => (error ? reject(new Error(String(error))) : resolve()),
      ),
    );
    return token;
  }
  async function queryTrace(token, traceNo) {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const task = { id, token, traceNo };
    const responseKey = `${RESPONSE_PREFIX}${id}`;
    GM_deleteValue(responseKey);
    GM_setValue(TASK_KEY, task);
    const tab = GM_openInTab(reportUrl(task), {
      active: false,
      insert: true,
      setParent: true,
    });
    const deadline = Date.now() + 60000;
    try {
      while (Date.now() < deadline) {
        const response = GM_getValue(responseKey, null);
        if (response?.id === id) {
          if (!response.ok) throw new Error(response.error || "报表查询失败");
          return response.result;
        }
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
      throw new Error("等待物资平台查询结果超时");
    } finally {
      GM_deleteValue(responseKey);
      GM_deleteValue(TASK_KEY);
      try {
        tab?.close();
      } catch {}
    }
  }

  function log(message, level = "info") {
    logs.push({
      time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      message: String(message),
      level,
    });
    if (logs.length > 200) logs.splice(0, logs.length - 200);
    if (!ui) return;
    ui.logs.replaceChildren(
      ...logs.map((line) => {
        const item = document.createElement("div");
        item.className = line.level;
        item.textContent = `[${line.time}] ${line.message}`;
        return item;
      }),
    );
    ui.logs.scrollTop = ui.logs.scrollHeight;
  }
  function renderStats() {
    if (ui) {
      ui.stats.textContent = `扫描 ${stats.scanned} · 命中 ${stats.found} · 更新 ${stats.updated} · 跳过 ${stats.skipped} · 失败 ${stats.failed}`;
    }
  }
  function status(text, kind = "idle") {
    if (!ui) return;
    ui.status.textContent = text;
    ui.status.dataset.kind = kind;
  }
  function credentials() {
    const missing = [];
    if (!config.platformUsername) missing.push("物资平台账号");
    if (!config.platformPassword) missing.push("物资平台密码");
    if (!config.adminUsername) missing.push("超管账号");
    if (!config.adminPassword) missing.push("超管密码");
    if (missing.length) throw new Error(`请先填写并保存：${missing.join("、")}`);
  }
  async function run(trigger = "manual") {
    if (running) return log("已有同步任务正在执行", "warn");
    running = true;
    clearTimeout(timer);
    stats = { scanned: 0, found: 0, updated: 0, skipped: 0, failed: 0 };
    renderStats();
    ui.run.disabled = true;
    ui.run.textContent = "同步中…";
    status("连接中", "running");
    try {
      credentials();
      log(`${trigger === "auto" ? "自动" : "手动"}同步开始`);
      const rows = await targets();
      stats.scanned = rows.length;
      renderStats();
      if (!rows.length) {
        status("无需同步", "success");
        log("没有需要补齐且带追溯码的申购记录");
        return;
      }
      const token = await loginPlatform();
      log(`物资平台登录成功：${config.platformUsername}`);
      for (let index = 0; index < rows.length; index += 1) {
        const traceNo = clean(rows[index].trace_no);
        status(`${index + 1}/${rows.length} ${traceNo}`, "running");
        try {
          const result = await queryTrace(token, traceNo);
          if (!result.count) {
            stats.skipped += 1;
            log(`${traceNo}：物资平台未查询到记录`, "warn");
          } else {
            stats.found += 1;
            const summary = [
              ["采购人", result.salesperson],
              ["状态", result.status],
              ["合同号", result.contractNo],
              ["船名", result.vesselNo],
            ]
              .filter(([, value]) => value)
              .map(([label, value]) => `${label}=${value}`)
              .join("，");
            if (config.dryRun) {
              stats.skipped += 1;
              log(`${traceNo}：演练模式，${summary}`);
            } else {
              const updated = await updateTarget(traceNo, result);
              if (Number(updated.affected_rows || 0) > 0) {
                stats.updated += 1;
                log(`${traceNo}：已更新，${summary}`, "success");
              } else {
                stats.skipped += 1;
                log(`${traceNo}：无需更新`, "warn");
              }
            }
          }
        } catch (error) {
          stats.failed += 1;
          log(`${traceNo}：${error.message}`, "error");
        }
        renderStats();
      }
      const cursorIds = rows.map((row) => Number(row.cursor_id)).filter(Number.isFinite);
      if (cursorIds.length) GM_setValue(key("cursor"), Math.min(...cursorIds));
      status(stats.failed ? "完成（有失败）" : "同步完成", stats.failed ? "warn" : "success");
      log(
        `同步完成：扫描 ${stats.scanned}，命中 ${stats.found}，更新 ${stats.updated}，失败 ${stats.failed}`,
        stats.failed ? "warn" : "success",
      );
    } catch (error) {
      stats.failed += 1;
      renderStats();
      status("同步失败", "error");
      log(error.message, "error");
    } finally {
      running = false;
      ui.run.disabled = false;
      ui.run.textContent = "同步一次";
      if (config.autoEnabled) schedule();
    }
  }
  function schedule(delay) {
    clearTimeout(timer);
    if (!config.autoEnabled) return;
    const milliseconds = int(config.intervalMinutes, 10, 1, 1440) * 60000;
    timer = setTimeout(() => run("auto"), typeof delay === "number" ? delay : milliseconds);
    status(`自动模式：${config.intervalMinutes} 分钟`);
  }
  function formConfig() {
    return {
      platformUsername: ui.platformUsername.value.trim(),
      platformPassword: ui.platformPassword.value,
      adminUsername: ui.adminUsername.value.trim(),
      adminPassword: ui.adminPassword.value,
      intervalMinutes: int(ui.interval.value, 10, 1, 1440),
      batchSize: int(ui.batch.value, 50, 1, 200),
      dryRun: ui.dryRun.checked,
      autoEnabled: ui.auto.checked,
    };
  }
  function fillForm() {
    ui.platformUsername.value = config.platformUsername;
    ui.platformPassword.value = config.platformPassword;
    ui.adminUsername.value = config.adminUsername;
    ui.adminPassword.value = config.adminPassword;
    ui.interval.value = config.intervalMinutes;
    ui.batch.value = config.batchSize;
    ui.dryRun.checked = config.dryRun;
    ui.auto.checked = config.autoEnabled;
  }
  function minimize(value = host.dataset.minimized !== "true") {
    host.dataset.minimized = String(value);
    ui.minimize.textContent = value ? "□" : "—";
    saveConfig({ minimized: value });
  }
  function drag(handle) {
    let active = false;
    let startX;
    let startY;
    let startRight;
    let startBottom;
    handle.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      active = true;
      startX = event.clientX;
      startY = event.clientY;
      startRight = Number.parseFloat(host.style.right) || 20;
      startBottom = Number.parseFloat(host.style.bottom) || 20;
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", (event) => {
      if (!active) return;
      host.style.right = `${Math.max(0, startRight - event.clientX + startX)}px`;
      host.style.bottom = `${Math.max(0, startBottom - event.clientY + startY)}px`;
    });
    handle.addEventListener("pointerup", (event) => {
      if (!active) return;
      active = false;
      handle.releasePointerCapture(event.pointerId);
      saveConfig({
        panelRight: Number.parseFloat(host.style.right),
        panelBottom: Number.parseFloat(host.style.bottom),
      });
    });
  }
  function createPanel() {
    host = document.createElement("div");
    host.id = "huaxing-tracking-sync-userscript";
    host.style.cssText = `position:fixed;z-index:2147483647;right:${Number(config.panelRight) || 20}px;bottom:${Number(config.panelBottom) || 20}px`;
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
<style>
:host{all:initial;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;color:#1f2937}*{box-sizing:border-box}.panel{width:380px;overflow:hidden;border:1px solid #cbd5e1;border-radius:8px;background:#fff;box-shadow:0 18px 45px #0f172a38}.head{display:flex;align-items:center;gap:8px;padding:9px 10px 9px 14px;color:#fff;background:#176b5b;cursor:move;user-select:none}.title{flex:1;font-size:14px;font-weight:700}.status{max-width:170px;overflow:hidden;padding:3px 8px;border-radius:4px;background:#ffffff2e;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.status[data-kind=success]{background:#10b98155}.status[data-kind=warn]{background:#f59e0b66}.status[data-kind=error]{background:#ef444466}.mini{width:28px;height:28px;border:0;border-radius:4px;color:#fff;background:#ffffff22;cursor:pointer}.body{padding:12px}:host([data-minimized=true]) .body{display:none}:host([data-minimized=true]) .panel{width:260px}.toolbar{display:flex;align-items:center;gap:9px}.run,.save{height:34px;border-radius:4px;padding:0 14px;font-weight:650;cursor:pointer}.run{border:0;color:#fff;background:#176b5b}.save{border:1px solid #cbd5e1;color:#334155;background:#fff}.switch{display:flex;align-items:center;gap:6px;margin-left:auto;font-size:12px;color:#475569}.switch input,.check input{accent-color:#176b5b}.stats{margin:10px 0;padding:8px 10px;border-radius:4px;color:#475569;background:#f1f5f9;font-size:12px}details{border:1px solid #e2e8f0;border-radius:4px}summary{padding:9px 10px;font-size:12px;font-weight:650;cursor:pointer}.settings{display:grid;grid-template-columns:1fr 1fr;gap:9px;padding:0 10px 10px}label{display:grid;gap:4px;color:#64748b;font-size:11px}input[type=text],input[type=password],input[type=number]{width:100%;height:31px;border:1px solid #cbd5e1;border-radius:4px;padding:0 8px}.full{grid-column:1/-1}.check{display:flex;align-items:center;gap:6px}.notice{grid-column:1/-1;color:#92400e;font-size:11px;line-height:1.5}.logs{height:170px;margin-top:10px;overflow:auto;border-radius:4px;padding:8px;color:#cbd5e1;background:#20252b;font:11px/1.55 Consolas,"Microsoft YaHei",monospace}.logs div{margin-bottom:2px;overflow-wrap:anywhere}.logs .success{color:#6ee7b7}.logs .warn{color:#fcd34d}.logs .error{color:#fca5a5}button:disabled{opacity:.55;cursor:wait}
</style>
<section class="panel"><header class="head"><div class="title">华兴物料跟踪同步</div><div class="status">待机</div><button class="mini" title="最小化">—</button></header><div class="body"><div class="toolbar"><button class="run">同步一次</button><label class="switch"><input class="auto" type="checkbox">自动模式</label></div><div class="stats">扫描 0 · 命中 0 · 更新 0 · 跳过 0 · 失败 0</div><details><summary>连接与同步设置</summary><div class="settings"><label>物资平台账号<input class="platform-user" type="text"></label><label>物资平台密码<input class="platform-pass" type="password"></label><label>超管账号<input class="admin-user" type="text"></label><label>超管密码<input class="admin-pass" type="password"></label><label>自动间隔（分钟）<input class="interval" type="number" min="1" max="1440"></label><label>单次数量<input class="batch" type="number" min="1" max="200"></label><label class="check full"><input class="dry-run" type="checkbox">演练模式（只查询不写库）</label><div class="notice">密码仅保存在油猴脚本私有存储中。首次使用保留演练模式，确认日志字段后再正式写入。</div><button class="save full">保存设置</button></div></details><div class="logs"></div></div></section>`;
    document.documentElement.append(host);
    ui = {
      status: shadow.querySelector(".status"),
      minimize: shadow.querySelector(".mini"),
      run: shadow.querySelector(".run"),
      auto: shadow.querySelector(".auto"),
      stats: shadow.querySelector(".stats"),
      logs: shadow.querySelector(".logs"),
      platformUsername: shadow.querySelector(".platform-user"),
      platformPassword: shadow.querySelector(".platform-pass"),
      adminUsername: shadow.querySelector(".admin-user"),
      adminPassword: shadow.querySelector(".admin-pass"),
      interval: shadow.querySelector(".interval"),
      batch: shadow.querySelector(".batch"),
      dryRun: shadow.querySelector(".dry-run"),
      save: shadow.querySelector(".save"),
    };
    fillForm();
    minimize(Boolean(config.minimized));
    drag(shadow.querySelector(".head"));
    ui.minimize.addEventListener("click", () => minimize());
    ui.run.addEventListener("click", () => run());
    ui.save.addEventListener("click", () => {
      saveConfig(formConfig());
      fillForm();
      log("设置已保存", "success");
      if (config.autoEnabled) schedule(1500);
      else {
        clearTimeout(timer);
        status("待机");
      }
    });
    ui.auto.addEventListener("change", () => {
      saveConfig({ autoEnabled: ui.auto.checked });
      if (config.autoEnabled) {
        log("自动模式已开启");
        schedule(1500);
      } else {
        clearTimeout(timer);
        status("自动模式已关闭");
        log("自动模式已关闭");
      }
    });
    renderStats();
    if (config.autoEnabled) schedule(3000);
  }

  GM_registerMenuCommand("华兴物料跟踪：同步一次", () => run());
  GM_registerMenuCommand("华兴物料跟踪：切换自动模式", () => {
    saveConfig({ autoEnabled: !config.autoEnabled });
    if (ui) ui.auto.checked = config.autoEnabled;
    if (config.autoEnabled) schedule(1000);
    else clearTimeout(timer);
    log(`自动模式已${config.autoEnabled ? "开启" : "关闭"}`);
  });

  createPanel();
  log("脚本已加载；首次使用请填写物资平台密码和超管密码");
})();
