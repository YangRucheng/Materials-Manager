// ==UserScript==
// @name         华友何佳 - 备件管理系统状态同步
// @namespace    https://quick-hejia.qcloud.19890605.xyz/hjerp/
// @version      1.4.0
// @description  在华友何佳系统中查询“物资状态查询”，同步备件管理系统中的状态、业务员和申购日期。
// @match        https://quick-hejia.qcloud.19890605.xyz/hjerp/*
// @updateURL    https://github.com/YangRucheng/Materials-Manager/raw/refs/heads/main/example/script/huayou-hejia-sync.user.js
// @downloadURL  https://github.com/YangRucheng/Materials-Manager/raw/refs/heads/main/example/script/huayou-hejia-sync.user.js
// @connect      materials-manager.qcloud.19890605.xyz
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @noframes
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  const HEJIA_BASE = `${location.origin}/hjerp`;
  const MATERIALS_API = "https://materials-manager.qcloud.19890605.xyz/api/v1";
  const MENU_ID = "820017687";
  const MENU_NAME = "物资状态查询";
  const PREFIX = "hejia_sync_";
  const NOT_FOUND_CACHE_NAME = "notFoundCache";
  const NOT_FOUND_TTL = 3 * 24 * 60 * 60 * 1000;
  const defaults = {
    adminUsername: "admin",
    adminPassword: "",
    intervalMinutes: 1,
    batchSize: 100,
    autoEnabled: false,
    dryRun: false,
    minimized: false,
    panelRight: 20,
    panelBottom: 20,
  };

  let config = loadConfig();
  let running = false;
  let timer = null;
  let host;
  let ui;
  const logs = [];
  let stats = {
    scanned: 0,
    found: 0,
    updated: 0,
    skipped: 0,
    failed: 0,
    cached: 0,
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
  function form(data) {
    return Object.entries(data)
      .map(
        ([name, value]) =>
          `${encodeURIComponent(name)}=${encodeURIComponent(value ?? "")}`,
      )
      .join("&");
  }
  function array(value) {
    return value == null ? [] : Array.isArray(value) ? value : [value];
  }
  function boolean(value, fallback) {
    if (value == null || value === "") return fallback;
    return typeof value === "boolean"
      ? value
      : String(value).toLowerCase() === "true";
  }
  function clean(value) {
    return String(value ?? "")
      .replace(/\s+/g, " ")
      .trim();
  }
  function notFoundCache(now = Date.now()) {
    const stored = GM_getValue(key(NOT_FOUND_CACHE_NAME), {});
    const source =
      stored && typeof stored === "object" && !Array.isArray(stored)
        ? stored
        : {};
    const active = {};
    let changed = source !== stored;
    Object.entries(source).forEach(([rawTraceNo, rawTimestamp]) => {
      const traceNo = clean(rawTraceNo);
      const timestamp = Number(rawTimestamp);
      if (
        !traceNo ||
        !Number.isFinite(timestamp) ||
        timestamp <= 0 ||
        timestamp > now ||
        now - timestamp >= NOT_FOUND_TTL
      ) {
        changed = true;
        return;
      }
      if (traceNo !== rawTraceNo || active[traceNo]) changed = true;
      active[traceNo] = Math.max(active[traceNo] || 0, timestamp);
    });
    if (changed) GM_setValue(key(NOT_FOUND_CACHE_NAME), active);
    return active;
  }
  function notFoundTraceNos() {
    return Object.keys(notFoundCache());
  }
  function rememberNotFound(traceNo) {
    const value = clean(traceNo);
    if (!value) return;
    const cache = notFoundCache();
    cache[value] = Date.now();
    GM_setValue(key(NOT_FOUND_CACHE_NAME), cache);
  }
  function forgetNotFound(traceNo) {
    const value = clean(traceNo);
    const cache = notFoundCache();
    if (!value || !(value in cache)) return;
    delete cache[value];
    GM_setValue(key(NOT_FOUND_CACHE_NAME), cache);
  }
  function clearNotFoundCache() {
    GM_setValue(key(NOT_FOUND_CACHE_NAME), {});
    stats.cached = 0;
    renderStats();
    log("已清空何佳无结果缓存", "success");
  }
  function reverse(value) {
    return String(value ?? "")
      .split("")
      .reverse()
      .join("");
  }
  function escapeJs(value) {
    return String(value ?? "")
      .replace(/\\/g, "\\\\")
      .replace(/"/g, '\\"')
      .replace(/\r/g, "\\r")
      .replace(/\n/g, "\\n")
      .replace(/\t/g, "\\t");
  }
  function base64(value) {
    const bytes = new TextEncoder().encode(value);
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 0x8000)
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    return btoa(binary);
  }

  function request({
    method = "GET",
    url,
    headers = {},
    data,
    timeout = 30000,
  }) {
    return new Promise((resolve, reject) =>
      GM_xmlhttpRequest({
        method,
        url,
        headers,
        data,
        timeout,
        anonymous: false,
        onload(response) {
          const text =
            typeof response.responseText === "string"
              ? response.responseText
              : String(response.response || "");
          if (response.status >= 200 && response.status < 300) resolve(text);
          else
            reject(new Error(`HTTP ${response.status}：${text.slice(0, 300)}`));
        },
        ontimeout: () => reject(new Error(`请求超时：${url}`)),
        onerror: (error) =>
          reject(
            new Error(error?.error || error?.message || `网络请求失败：${url}`),
          ),
      }),
    );
  }
  async function json(options) {
    const text = await request(options);
    try {
      return JSON.parse(text);
    } catch {
      throw new Error(`接口返回的不是有效 JSON：${text.slice(0, 200)}`);
    }
  }
  async function hejiaJson(path, data, timeout = 30000) {
    const response = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${HEJIA_BASE}${path}`, true);
      xhr.withCredentials = true;
      xhr.timeout = timeout;
      xhr.setRequestHeader(
        "Content-Type",
        "application/x-www-form-urlencoded; charset=UTF-8",
      );
      xhr.onload = () =>
        resolve({
          status: xhr.status,
          url: xhr.responseURL,
          text: xhr.responseText || "",
        });
      xhr.ontimeout = () => reject(new Error(`何佳请求超时：${path}`));
      xhr.onerror = () => reject(new Error(`何佳请求失败：${path}`));
      xhr.send(data);
    });
    const { text } = response;
    if (response.status < 200 || response.status >= 300)
      throw new Error(`何佳 HTTP ${response.status}：${text.slice(0, 200)}`);
    if (
      response.url.includes("/hjerp/login") ||
      /^\s*<!doctype html/i.test(text) ||
      /^\s*<html/i.test(text)
    )
      throw new Error("请先登录何佳系统，再执行同步");
    try {
      return JSON.parse(text);
    } catch {
      throw new Error(`何佳接口返回的不是有效 JSON：${text.slice(0, 200)}`);
    }
  }
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
    const limit = int(config.batchSize, defaults.batchSize, 1, 200);
    const excludedTraceNos = notFoundTraceNos();
    const parameters = {};
    const exclusion = excludedTraceNos.length
      ? "\n  AND JSON_CONTAINS(:not_found_trace_nos, JSON_QUOTE(TRIM(pr.trace_no))) = 0"
      : "";
    if (excludedTraceNos.length)
      parameters.not_found_trace_nos = JSON.stringify(excludedTraceNos);
    const result = await db(
      `SELECT pr.trace_no, COUNT(*) AS target_count
FROM purchase_request pr
JOIN purchase_request_line prl ON prl.purchase_request_id = pr.id
WHERE pr.trace_no IS NOT NULL AND TRIM(pr.trace_no) <> ''
  AND (pr.salesperson IS NULL OR TRIM(pr.salesperson) = '')${exclusion}
GROUP BY pr.trace_no
ORDER BY MAX(prl.id) DESC
LIMIT ${limit}`,
      parameters,
      limit,
    );
    return {
      rows: Array.isArray(result.rows) ? result.rows : [],
      excludedCount: excludedTraceNos.length,
    };
  }
  async function updateTarget(traceNo, status, salesperson, purchaseDate) {
    const set = [];
    const parameters = { trace_no: traceNo };
    let purchaseRequestChanged = false;
    if (salesperson) {
      set.push("pr.salesperson = :salesperson");
      parameters.salesperson = salesperson;
      purchaseRequestChanged = true;
    }
    if (purchaseDate) {
      set.push("pr.purchase_date = :purchase_date");
      parameters.purchase_date = purchaseDate;
      purchaseRequestChanged = true;
    }
    if (purchaseRequestChanged) {
      set.push(
        "pr.version = pr.version + 1",
        "pr.updated_at = CURRENT_TIMESTAMP(6)",
      );
    }
    if (status) {
      set.push(
        "prl.status = :status",
        "prl.version = prl.version + 1",
        "prl.updated_at = CURRENT_TIMESTAMP(6)",
      );
      parameters.status = status;
    }
    if (!set.length) return { affected_rows: 0 };
    return db(
      `UPDATE purchase_request pr
JOIN purchase_request_line prl ON prl.purchase_request_id = pr.id
SET ${set.join(", ")}
WHERE pr.trace_no = :trace_no
  AND (pr.salesperson IS NULL OR TRIM(pr.salesperson) = '')`,
      parameters,
      1,
    );
  }

  async function dataset() {
    const result = await hejiaJson(
      "/servlet/FlexUIServlet",
      form({ menuId: MENU_ID, menuName: MENU_NAME }),
    );
    if (String(result?.result?.code) !== "1")
      throw new Error(result?.result?.msg || "加载何佳查询配置失败");
    const sets = array(result?.dataSource?.dataSets?.dataSet);
    const value = sets.find((item) => item.compId === MENU_ID) || sets[0];
    if (!value?.fields?.field) throw new Error("何佳查询配置缺少数据集字段");
    return value;
  }
  function fieldJson(field) {
    const table = field.tableAlias || field.tableName || "";
    let output = `{table:"${escapeJs(table)}",col:"${escapeJs(field.name)}",alias:"${escapeJs(field.dataField)}"`;
    if (!boolean(field.visible, true)) output += ",visible:false";
    if (String(field.type ?? "1") !== "1")
      output += `,type:"${escapeJs(field.type)}"`;
    if (boolean(field.sumFlag, false)) output += ",sumFlag:true";
    if (boolean(field.isVirtual, false)) {
      output += ",virtual:true";
      if (field.ext) output += `,ext:"${escapeJs(field.ext)}"`;
    }
    output += `,text:"${escapeJs(field.headerText)}"`;
    output += `,queryCol:${boolean(field.queryCol, true)}`;
    output += `,mainField:${boolean(field.mainField, false)}`;
    output += `,relatCol:"${escapeJs(field.relatCol || "")}"`;
    output += `,format:"${escapeJs(field.format || "")}"}`;
    return output;
  }
  function queryPayload(source, traceNo) {
    const fields = array(source.fields.field);
    const traceField = fields.find((field) => field.name === "var_trackno");
    if (!traceField) throw new Error("何佳配置缺少追踪码字段 var_trackno");
    const table = source.name || source.aliasName;
    const condition = [
      source.defaultQuery,
      `${traceField.tableAlias || table}.var_trackno = '${String(traceNo).replace(/'/g, "''")}'`,
    ]
      .filter(Boolean)
      .join(" and ");
    const parts = [
      `compId:"${escapeJs(source.compId || MENU_ID)}"`,
      `table:"${escapeJs(table)}"`,
      `canSave:${boolean(source.canSave, true)}`,
      `conds:"${escapeJs(reverse(condition))}"`,
      "isQueryButton:true",
      `condsall:"${escapeJs(source.queryAll || "")}"`,
      `queryDrill:"${escapeJs(source.queryDrill || "")}"`,
      "pagePilot:{pageSize:200,currPage:1}",
      `fixSql:"${escapeJs(source.initsql || source.fsql || "")}"`,
      `presqls:"${escapeJs(source.presql || "")}"`,
      `col:"${escapeJs(source.columnId || "")}"`,
      `tables:["${escapeJs(reverse(`${table} ${source.relation || ""}`))}"]`,
      `cols:[${fields.map(fieldJson).join(",")}]`,
      "multiCols:[]",
      `qcols:[${fieldJson(traceField)}]`,
      `orderBy:"${escapeJs(source.orderBy || "")}"`,
    ];
    return `{${parts.join(",")}}`;
  }
  function rowValue(row, alias) {
    const cell = row?.[alias];
    return clean(
      cell && typeof cell === "object" && "val" in cell ? cell.val : cell,
    );
  }
  function limited(value) {
    const text = clean(value);
    return text.length <= 128 ? text : `${text.slice(0, 127)}…`;
  }
  function validDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return false;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const date = new Date(Date.UTC(year, month - 1, day));
    return (
      date.getUTCFullYear() === year &&
      date.getUTCMonth() === month - 1 &&
      date.getUTCDate() === day
    );
  }
  function requestDate(value) {
    const date = clean(value);
    if (date && !validDate(date))
      throw new Error(`何佳申购日期格式异常：${date}`);
    return date;
  }
  function selectBestRow(rows, aliases) {
    const dataFields = [
      ...new Set(Object.values(aliases).map(clean).filter(Boolean)),
    ];
    let selected = null;
    let selectedNonEmptyCount = -1;
    rows.forEach((row) => {
      const nonEmptyCount = dataFields.reduce(
        (count, dataField) => count + (rowValue(row, dataField) ? 1 : 0),
        0,
      );
      if (nonEmptyCount > selectedNonEmptyCount) {
        selected = row;
        selectedNonEmptyCount = nonEmptyCount;
      }
    });
    return {
      row: selected,
      nonEmptyCount: Math.max(0, selectedNonEmptyCount),
    };
  }
  async function queryTrace(source, traceNo) {
    const fields = array(source.fields.field);
    const aliases = Object.fromEntries(
      fields.map((field) => [field.name, field.dataField]),
    );
    const result = await hejiaJson(
      "/servlet/DataSetQueryServlet",
      form({ json: base64(queryPayload(source, traceNo)) }),
      45000,
    );
    if (String(result?.result?.code) !== "1")
      throw new Error(result?.result?.msg || `查询 ${traceNo} 失败`);
    const rows = array(result?.dataSource?.rows?.row);
    const exact = rows.filter(
      (row) => rowValue(row, aliases.var_trackno) === clean(traceNo),
    );
    const matched = exact.length ? exact : rows;
    if (!aliases.date_req) throw new Error("何佳配置缺少申购日期字段 date_req");
    const selected = selectBestRow(matched, aliases);
    return {
      count: matched.length,
      selectedNonEmptyCount: selected.nonEmptyCount,
      status: limited(rowValue(selected.row, aliases.flag_prog)),
      salesperson: limited(rowValue(selected.row, aliases.var_reqclerk)),
      purchaseDate: requestDate(rowValue(selected.row, aliases.date_req)),
    };
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
    if (ui)
      ui.stats.textContent = `扫描 ${stats.scanned} · 命中 ${stats.found} · 更新 ${stats.updated} · 跳过 ${stats.skipped} · 失败 ${stats.failed} · 缓存 ${stats.cached}`;
  }
  function status(text, kind = "idle") {
    if (!ui) return;
    ui.status.textContent = text;
    ui.status.dataset.kind = kind;
  }
  function isLoginPage() {
    return /\/hjerp\/(?:login|loginServlet)(?:[/?#]|$)/i.test(
      location.pathname,
    );
  }
  function credentials() {
    const missing = [];
    if (!config.adminUsername) missing.push("超管账号");
    if (!config.adminPassword) missing.push("超管密码");
    if (missing.length)
      throw new Error(`请先填写并保存：${missing.join("、")}`);
  }

  async function run(trigger = "manual") {
    if (running) return log("已有同步任务正在执行", "warn");
    running = true;
    stopSchedule();
    stats = {
      scanned: 0,
      found: 0,
      updated: 0,
      skipped: 0,
      failed: 0,
      cached: 0,
    };
    renderStats();
    if (ui) {
      ui.run.disabled = true;
      ui.run.textContent = "同步中…";
    }
    status("连接中", "running");
    try {
      if (isLoginPage()) throw new Error("请先登录何佳系统，再执行同步");
      credentials();
      log(`${trigger === "auto" ? "自动" : "手动"}同步开始`);
      const source = await dataset();
      log(
        `已复用当前何佳会话，加载“${source.headerText || MENU_NAME}”查询配置`,
      );
      const targetResult = await targets();
      const rows = targetResult.rows;
      stats.scanned = rows.length;
      stats.cached = targetResult.excludedCount;
      renderStats();
      if (stats.cached)
        log(`SQL 已排除 ${stats.cached} 个三天内无结果的追溯号`);
      if (!rows.length) {
        status("无需同步", "success");
        log(
          stats.cached
            ? "没有需要同步的记录，三天无结果缓存已在 SQL 中排除"
            : "没有缺失业务员且带追溯号的记录",
        );
        return;
      }
      for (let index = 0; index < rows.length; index += 1) {
        const traceNo = clean(rows[index].trace_no);
        status(`${index + 1}/${rows.length} ${traceNo}`, "running");
        try {
          const result = await queryTrace(source, traceNo);
          if (result.count > 1)
            log(
              `${traceNo}：何佳返回 ${result.count} 条，采用非空列最多的一条（${result.selectedNonEmptyCount} 列）`,
            );
          if (!result.count) {
            rememberNotFound(traceNo);
            stats.cached = notFoundTraceNos().length;
            stats.skipped += 1;
            log(`${traceNo}：何佳未查询到记录，三天内不再尝试`, "warn");
          } else if (
            !result.status &&
            !result.salesperson &&
            !result.purchaseDate
          ) {
            forgetNotFound(traceNo);
            stats.found += 1;
            stats.skipped += 1;
            log(`${traceNo}：状态、业务员和申购日期均为空`, "warn");
          } else {
            forgetNotFound(traceNo);
            stats.found += 1;
            const summary = `业务员=${result.salesperson || "空"}，状态=${result.status || "空"}，申购日期=${result.purchaseDate || "空"}`;
            if (config.dryRun) {
              stats.skipped += 1;
              log(`${traceNo}：演练模式，${summary}`);
            } else {
              const updated = await updateTarget(
                traceNo,
                result.status,
                result.salesperson,
                result.purchaseDate,
              );
              if (Number(updated.affected_rows || 0) > 0) {
                stats.updated += 1;
                log(`${traceNo}：已更新，${summary}`, "success");
              } else {
                stats.skipped += 1;
                log(`${traceNo}：数据已变化或无需更新`, "warn");
              }
            }
          }
        } catch (error) {
          stats.failed += 1;
          log(`${traceNo}：${error.message}`, "error");
        }
        renderStats();
      }
      status(
        stats.failed ? "完成（有失败）" : "同步完成",
        stats.failed ? "warn" : "success",
      );
      log(
        `同步完成：扫描 ${stats.scanned}，命中 ${stats.found}，更新 ${stats.updated}，失败 ${stats.failed}`,
        stats.failed ? "warn" : "success",
      );
    } catch (error) {
      stats.failed += 1;
      renderStats();
      const loginRequired = error.message.includes("请先登录何佳系统");
      status(
        loginRequired ? "请先登录何佳系统" : "同步失败",
        loginRequired ? "warn" : "error",
      );
      log(error.message, loginRequired ? "warn" : "error");
    } finally {
      running = false;
      if (ui) {
        ui.run.disabled = false;
        ui.run.textContent = "同步一次";
      }
      if (config.autoEnabled) schedule();
    }
  }
  function stopSchedule() {
    clearTimeout(timer);
    timer = null;
  }
  function countdown(milliseconds) {
    const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const short = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    return hours ? `${hours}:${short}` : short;
  }
  function schedule(delay) {
    stopSchedule();
    if (!config.autoEnabled) return;
    if (isLoginPage()) {
      status("请先登录何佳系统", "warn");
      return;
    }
    const interval =
      int(config.intervalMinutes, defaults.intervalMinutes, 1, 1440) * 60000;
    const runAt = Date.now() + (typeof delay === "number" ? delay : interval);
    const tick = () => {
      if (!config.autoEnabled) return stopSchedule();
      const remaining = runAt - Date.now();
      if (remaining <= 0) {
        timer = null;
        run("auto");
        return;
      }
      status(`自动同步倒计时 ${countdown(remaining)}`);
      timer = setTimeout(tick, Math.min(1000, remaining));
    };
    tick();
  }
  function formConfig() {
    return {
      adminUsername: ui.adminUsername.value.trim(),
      adminPassword: ui.adminPassword.value,
      intervalMinutes: int(
        ui.interval.value,
        defaults.intervalMinutes,
        1,
        1440,
      ),
      batchSize: int(ui.batch.value, defaults.batchSize, 1, 200),
      dryRun: ui.dryRun.checked,
      autoEnabled: ui.auto.checked,
    };
  }
  function fillForm() {
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
    let startX, startY, startRight, startBottom;
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
    host.id = "hejia-sync-userscript";
    host.style.cssText = `position:fixed;z-index:2147483647;right:${Number(config.panelRight) || 20}px;bottom:${Number(config.panelBottom) || 20}px`;
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
<style>
:host{all:initial;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;color:#1f2937}*{box-sizing:border-box}.panel{width:380px;overflow:hidden;border:1px solid #cbd5e1;border-radius:14px;background:#fff;box-shadow:0 18px 45px #0f172a38}.head{display:flex;align-items:center;gap:8px;padding:9px 10px 9px 14px;color:#fff;background:linear-gradient(135deg,#0f766e,#2563eb);cursor:move;user-select:none}.title{flex:1;font-size:14px;font-weight:700}.status{max-width:170px;overflow:hidden;padding:3px 8px;border-radius:999px;background:#ffffff2e;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.status[data-kind=success]{background:#10b98155}.status[data-kind=warn]{background:#f59e0b66}.status[data-kind=error]{background:#ef444466}.mini{width:28px;height:28px;border:0;border-radius:8px;color:#fff;background:#ffffff22;cursor:pointer}.body{padding:12px}:host([data-minimized=true]) .body{display:none}:host([data-minimized=true]) .panel{width:260px}.toolbar{display:flex;align-items:center;gap:9px}.run,.save{height:34px;border-radius:9px;padding:0 14px;font-weight:650;cursor:pointer}.run{border:0;color:#fff;background:#2563eb}.save{border:1px solid #cbd5e1;color:#334155;background:#fff}.switch{display:flex;align-items:center;gap:6px;margin-left:auto;font-size:12px;color:#475569}.switch input,.check input{accent-color:#2563eb}.stats{margin:10px 0;padding:8px 10px;border-radius:9px;color:#475569;background:#f1f5f9;font-size:12px}details{border:1px solid #e2e8f0;border-radius:10px}summary{padding:9px 10px;font-size:12px;font-weight:650;cursor:pointer}.settings{display:grid;grid-template-columns:1fr 1fr;gap:9px;padding:0 10px 10px}label{display:grid;gap:4px;color:#64748b;font-size:11px}input[type=text],input[type=password],input[type=number]{width:100%;height:31px;border:1px solid #cbd5e1;border-radius:7px;padding:0 8px}.full{grid-column:1/-1}.check{display:flex;align-items:center;gap:6px}.notice{grid-column:1/-1;color:#92400e;font-size:11px;line-height:1.5}.logs{height:170px;margin-top:10px;overflow:auto;border-radius:9px;padding:8px;color:#cbd5e1;background:#0f172a;font:11px/1.55 Consolas,"Microsoft YaHei",monospace}.logs div{margin-bottom:2px;overflow-wrap:anywhere}.logs .success{color:#6ee7b7}.logs .warn{color:#fcd34d}.logs .error{color:#fca5a5}button:disabled{opacity:.55;cursor:wait}
</style>
<section class="panel"><header class="head"><div class="title">华友何佳同步</div><div class="status">待机</div><button class="mini" title="最小化">—</button></header><div class="body"><div class="toolbar"><button class="run">同步一次</button><label class="switch"><input class="auto" type="checkbox">自动模式</label></div><div class="stats">扫描 0 · 命中 0 · 更新 0 · 跳过 0 · 失败 0 · 缓存 0</div><details><summary>本系统连接与同步设置</summary><div class="settings"><label>超管账号<input class="admin-user" type="text"></label><label>超管密码<input class="admin-pass" type="password"></label><label>自动间隔（分钟）<input class="interval" type="number" min="1" max="1440"></label><label>单次数量<input class="batch" type="number" min="1" max="200"></label><label class="check full"><input class="dry-run" type="checkbox">演练模式（只查询不写库）</label><div class="notice">脚本直接复用当前何佳登录会话；超管密码保存在油猴脚本私有存储中。何佳明确无结果的追溯号缓存三天，并在 SQL 中排除；可通过油猴菜单手动清空。</div><button class="save full">保存设置</button></div></details><div class="logs"></div></div></section>`;
    document.documentElement.append(host);
    ui = {
      status: shadow.querySelector(".status"),
      minimize: shadow.querySelector(".mini"),
      run: shadow.querySelector(".run"),
      auto: shadow.querySelector(".auto"),
      stats: shadow.querySelector(".stats"),
      logs: shadow.querySelector(".logs"),
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
        stopSchedule();
        status("待机");
      }
    });
    ui.auto.addEventListener("change", () => {
      saveConfig({ autoEnabled: ui.auto.checked });
      if (config.autoEnabled) {
        log("自动模式已开启");
        schedule(1500);
      } else {
        stopSchedule();
        status("自动模式已关闭");
        log("自动模式已关闭");
      }
    });
    renderStats();
    if (config.autoEnabled) schedule(3000);
  }

  GM_registerMenuCommand("华友何佳同步：同步一次", () => run());
  GM_registerMenuCommand("华友何佳同步：切换自动模式", () => {
    saveConfig({ autoEnabled: !config.autoEnabled });
    if (ui) ui.auto.checked = config.autoEnabled;
    if (config.autoEnabled) schedule(1000);
    else stopSchedule();
    log(`自动模式已${config.autoEnabled ? "开启" : "关闭"}`);
  });
  GM_registerMenuCommand("华友何佳同步：清空三天无结果缓存", () =>
    clearNotFoundCache(),
  );

  stats.cached = notFoundTraceNos().length;
  createPanel();
  if (isLoginPage()) {
    status("请先登录何佳系统", "warn");
    log("脚本已加载；请先登录何佳系统，再执行同步", "warn");
  } else {
    log("脚本已加载；当前何佳登录会话将用于查询，请填写本系统超管密码");
  }
  if (stats.cached) log(`已加载 ${stats.cached} 个三天内无结果的追溯号缓存`);
})();
