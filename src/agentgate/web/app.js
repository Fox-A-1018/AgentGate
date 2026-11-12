const scenarios = {
  "public-file": {
    subject: "demo-viewer",
    role: "viewer",
    tool: "file.read",
    parameters: { path: "public/welcome.txt" },
  },
  "private-file": {
    subject: "demo-viewer",
    role: "viewer",
    tool: "file.read",
    parameters: { path: "private/secret.txt" },
  },
  database: {
    subject: "demo-analyst",
    role: "analyst",
    tool: "db.select",
    parameters: { table: "inventory", fields: ["sku", "stock"], filters: {}, limit: 101 },
  },
  mail: {
    subject: "demo-operator",
    role: "operator",
    tool: "mail.send",
    parameters: {
      recipients: ["reviewer@example.test"],
      subject: "AgentGate 演示消息",
      body: "这是一条只会写入本地 outbox 的合成消息。",
    },
  },
};

const decisionCopy = {
  ALLOW: { label: "ALLOW · 允许", title: "请求已通过安全检查", className: "allow" },
  DENY: { label: "DENY · 拒绝", title: "请求已被安全策略阻断", className: "deny" },
  REQUIRE_APPROVAL: { label: "REQUIRE APPROVAL · 待审批", title: "请求需要人工确认", className: "approval" },
};

const eventLabels = {
  REQUEST_RECEIVED: "收到工具调用请求",
  NORMALIZATION_REJECTED: "请求规范化失败",
  POLICY_EVALUATED: "完成策略判定",
  REQUEST_DENIED: "阻断请求",
  APPROVAL_CREATED: "创建审批任务",
  APPROVAL_GRANTED: "审批通过",
  APPROVAL_DENIED: "审批拒绝",
  APPROVAL_VALIDATION_FAILED: "审批凭证校验失败",
  IDEMPOTENCY_REPLAYED: "复用幂等请求结果",
  IDEMPOTENCY_REJECTED: "拒绝重复或冲突请求",
  EXECUTION_STARTED: "开始受控执行",
  EXECUTION_SUCCEEDED: "工具执行成功",
  EXECUTION_FAILED: "工具执行失败",
};

const elements = {
  serviceState: document.querySelector("#service-state"),
  health: document.querySelector("#metric-health"),
  policy: document.querySelector("#metric-policy"),
  pending: document.querySelector("#metric-pending"),
  events: document.querySelector("#metric-events"),
  form: document.querySelector("#request-form"),
  subject: document.querySelector("#subject-id"),
  role: document.querySelector("#role"),
  tool: document.querySelector("#tool-name"),
  toolFields: document.querySelector("#tool-fields"),
  submit: document.querySelector("#submit-request"),
  resultEmpty: document.querySelector("#result-empty"),
  resultContent: document.querySelector("#result-content"),
  decisionBadge: document.querySelector("#decision-badge"),
  riskBadge: document.querySelector("#risk-badge"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionReason: document.querySelector("#decision-reason"),
  reasonCode: document.querySelector("#reason-code"),
  traceId: document.querySelector("#trace-id"),
  approvalId: document.querySelector("#approval-id"),
  executionOutput: document.querySelector("#execution-output"),
  executionStatus: document.querySelector("#execution-status"),
  executionJson: document.querySelector("#execution-json"),
  viewTrace: document.querySelector("#view-trace"),
  approvalList: document.querySelector("#approval-list"),
  auditList: document.querySelector("#audit-list"),
  auditHeading: document.querySelector("#audit-heading"),
  refreshApprovals: document.querySelector("#refresh-approvals"),
  refreshAudit: document.querySelector("#refresh-audit"),
  toast: document.querySelector("#toast"),
};

let currentTraceId = null;
let toastTimer = null;

function escapeForDisplay(value) {
  return JSON.stringify(value, null, 2);
}

async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message || `请求失败（${response.status}）`;
    throw new Error(message);
  }
  return payload;
}

function showToast(message, type = "info") {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast show${type === "error" ? " error" : ""}`;
  toastTimer = window.setTimeout(() => {
    elements.toast.className = "toast";
  }, 3200);
}

function renderToolFields(parameters = {}) {
  if (elements.tool.value === "file.read") {
    elements.toolFields.innerHTML = `
      <label><span>文件路径</span><input id="file-path" value="${parameters.path || "public/welcome.txt"}" required /></label>
    `;
    return;
  }
  if (elements.tool.value === "db.select") {
    elements.toolFields.innerHTML = `
      <div class="form-grid two-columns">
        <label><span>数据表</span><select id="db-table"><option value="inventory">inventory</option><option value="orders">orders</option><option value="users_public">users_public</option></select></label>
        <label><span>最多返回行数</span><input id="db-limit" type="number" min="1" value="${parameters.limit || 20}" required /></label>
      </div>
      <label><span>查询字段（英文逗号分隔）</span><input id="db-fields" value="${(parameters.fields || ["sku", "stock"]).join(", ")}" required /></label>
      <label><span>过滤条件（JSON 对象）</span><textarea id="db-filters">${escapeForDisplay(parameters.filters || {})}</textarea></label>
    `;
    const table = document.querySelector("#db-table");
    table.value = parameters.table || "inventory";
    return;
  }
  elements.toolFields.innerHTML = `
    <label><span>收件人（英文逗号分隔）</span><input id="mail-recipients" value="${(parameters.recipients || ["reviewer@example.test"]).join(", ")}" required /></label>
    <label><span>消息主题</span><input id="mail-subject" value="${parameters.subject || "AgentGate 演示消息"}" maxlength="200" /></label>
    <label><span>消息正文</span><textarea id="mail-body" maxlength="5000">${parameters.body || "这是一条只会写入本地 outbox 的合成消息。"}</textarea></label>
  `;
}

function buildParameters() {
  if (elements.tool.value === "file.read") {
    return { path: document.querySelector("#file-path").value.trim() };
  }
  if (elements.tool.value === "db.select") {
    let filters;
    try {
      filters = JSON.parse(document.querySelector("#db-filters").value || "{}");
    } catch {
      throw new Error("过滤条件必须是合法的 JSON 对象");
    }
    return {
      table: document.querySelector("#db-table").value,
      fields: document.querySelector("#db-fields").value.split(",").map((item) => item.trim()).filter(Boolean),
      filters,
      limit: Number(document.querySelector("#db-limit").value),
    };
  }
  return {
    recipients: document.querySelector("#mail-recipients").value.split(",").map((item) => item.trim()).filter(Boolean),
    subject: document.querySelector("#mail-subject").value,
    body: document.querySelector("#mail-body").value,
  };
}

function applyScenario(name) {
  const scenario = scenarios[name];
  elements.subject.value = scenario.subject;
  elements.role.value = scenario.role;
  elements.tool.value = scenario.tool;
  renderToolFields(scenario.parameters);
  document.querySelectorAll(".scenario").forEach((button) => {
    button.classList.toggle("active", button.dataset.scenario === name);
  });
}

function setBusy(busy) {
  elements.submit.disabled = busy;
  elements.submit.querySelector("span").textContent = busy ? "正在进行安全检查…" : "提交到 AgentGate";
}

function showResult(result) {
  const copy = decisionCopy[result.decision] || decisionCopy.DENY;
  currentTraceId = result.trace_id;
  elements.resultEmpty.classList.add("hidden");
  elements.resultContent.classList.remove("hidden");
  elements.decisionBadge.className = `decision-badge ${copy.className}`;
  elements.decisionBadge.textContent = copy.label;
  elements.riskBadge.className = `risk-badge ${result.risk_level}`;
  elements.riskBadge.textContent = `${String(result.risk_level).toUpperCase()} RISK`;
  elements.decisionTitle.textContent = copy.title;
  elements.decisionReason.textContent = result.reason;
  elements.reasonCode.textContent = result.reason_code;
  elements.traceId.textContent = result.trace_id;
  elements.approvalId.textContent = result.approval_id || "无需审批";
  elements.viewTrace.disabled = false;

  if (result.execution) {
    elements.executionOutput.classList.remove("hidden");
    elements.executionStatus.textContent = result.execution.status;
    elements.executionJson.textContent = escapeForDisplay(result.execution.output || { summary: result.execution.summary });
  } else {
    elements.executionOutput.classList.add("hidden");
  }
}

async function submitRequest(event) {
  event.preventDefault();
  setBusy(true);
  try {
    const request = {
      subject_id: elements.subject.value.trim(),
      role: elements.role.value,
      tool_name: elements.tool.value,
      parameters: buildParameters(),
      session_id: "agentgate-web-demo",
    };
    const result = await apiFetch("/v1/requests", { method: "POST", body: JSON.stringify(request) });
    showResult(result);
    await Promise.all([refreshApprovals(), loadTrace(result.trace_id)]);
    showToast(result.decision === "DENY" ? "安全策略已阻断请求" : "请求已完成策略判定");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function createApprovalCard(record) {
  const card = document.createElement("article");
  card.className = "approval-card";

  const top = document.createElement("div");
  top.className = "approval-top";
  const title = document.createElement("strong");
  title.textContent = `${record.tool_name} · ${record.subject_id}`;
  const status = document.createElement("span");
  status.textContent = record.status;
  top.append(title, status);

  const meta = document.createElement("p");
  meta.textContent = `${record.role} · 创建于 ${formatDate(record.created_at)} · ${shortId(record.approval_id)}`;

  const params = document.createElement("div");
  params.className = "approval-params";
  params.textContent = JSON.stringify(record.parameters);

  const actions = document.createElement("div");
  actions.className = "approval-actions";
  const approve = document.createElement("button");
  approve.type = "button";
  approve.className = "approve-button";
  approve.textContent = "批准并执行";
  approve.addEventListener("click", () => approveAndExecute(record, card));
  const deny = document.createElement("button");
  deny.type = "button";
  deny.className = "deny-button";
  deny.textContent = "拒绝";
  deny.addEventListener("click", () => denyApproval(record, card));
  actions.append(approve, deny);
  card.append(top, meta, params, actions);
  return card;
}

async function refreshApprovals() {
  try {
    const records = await apiFetch("/v1/approvals?status=PENDING&limit=100");
    elements.pending.textContent = String(records.length);
    elements.approvalList.replaceChildren();
    if (!records.length) {
      const empty = document.createElement("div");
      empty.className = "list-empty";
      empty.textContent = "暂无待审批请求";
      elements.approvalList.append(empty);
      return;
    }
    records.forEach((record) => elements.approvalList.append(createApprovalCard(record)));
  } catch (error) {
    showToast(`审批队列加载失败：${error.message}`, "error");
  }
}

async function approveAndExecute(record, card) {
  const buttons = card.querySelectorAll("button");
  buttons.forEach((button) => (button.disabled = true));
  try {
    const grant = await apiFetch(`/v1/approvals/${record.approval_id}/grant`, {
      method: "POST",
      body: JSON.stringify({ approver_id: "demo-approver", approver_role: "approver", reason: "课堂演示批准" }),
    });
    const request = {
      subject_id: record.subject_id,
      role: record.role,
      tool_name: record.tool_name,
      parameters: record.parameters,
      trace_id: record.trace_id,
      request_id: record.request_id,
      session_id: "agentgate-web-demo",
    };
    const result = await apiFetch(`/v1/approvals/${record.approval_id}/execute`, {
      method: "POST",
      body: JSON.stringify({ request, token: grant.token }),
    });
    showResult(result);
    await Promise.all([refreshApprovals(), loadTrace(record.trace_id)]);
    showToast("审批通过，工具已受控执行");
  } catch (error) {
    buttons.forEach((button) => (button.disabled = false));
    showToast(error.message, "error");
  }
}

async function denyApproval(record, card) {
  const buttons = card.querySelectorAll("button");
  buttons.forEach((button) => (button.disabled = true));
  try {
    await apiFetch(`/v1/approvals/${record.approval_id}/deny`, {
      method: "POST",
      body: JSON.stringify({ approver_id: "demo-approver", approver_role: "approver", reason: "课堂演示拒绝" }),
    });
    await Promise.all([refreshApprovals(), loadTrace(record.trace_id)]);
    showToast("审批请求已拒绝");
  } catch (error) {
    buttons.forEach((button) => (button.disabled = false));
    showToast(error.message, "error");
  }
}

function shortId(value) {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function formatDate(value) {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value));
}

function eventTone(event) {
  if (["EXECUTION_SUCCEEDED"].includes(event.event_type)) return "success";
  if (["REQUEST_DENIED", "NORMALIZATION_REJECTED", "APPROVAL_VALIDATION_FAILED", "EXECUTION_FAILED"].includes(event.event_type)) return "danger";
  if (["APPROVAL_CREATED", "APPROVAL_GRANTED", "APPROVAL_DENIED"].includes(event.event_type)) return "approval";
  return "";
}

function eventDescription(event) {
  const fragments = [event.tool_name, event.decision, event.reason_code, event.execution_status].filter(Boolean);
  return fragments.length ? fragments.join(" · ") : `trace ${shortId(event.trace_id)}`;
}

function renderAudit(events, traceId = null) {
  elements.auditList.replaceChildren();
  elements.events.textContent = String(events.length);
  elements.auditHeading.textContent = traceId ? `审计链 · ${shortId(traceId)}` : "最近审计事件";
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "list-empty";
    empty.textContent = "暂无审计记录";
    elements.auditList.append(empty);
    return;
  }
  events.forEach((event) => {
    const item = document.createElement("article");
    item.className = `audit-event ${eventTone(event)}`;
    const top = document.createElement("div");
    top.className = "audit-title";
    const title = document.createElement("strong");
    title.textContent = eventLabels[event.event_type] || event.event_type;
    const time = document.createElement("time");
    time.dateTime = event.occurred_at;
    time.textContent = formatDate(event.occurred_at);
    top.append(title, time);
    const detail = document.createElement("p");
    detail.textContent = eventDescription(event);
    item.append(top, detail);
    elements.auditList.append(item);
  });
}

async function refreshAudit() {
  try {
    const events = await apiFetch("/v1/audit/recent?limit=60");
    currentTraceId = null;
    elements.viewTrace.disabled = true;
    renderAudit(events);
  } catch (error) {
    showToast(`审计记录加载失败：${error.message}`, "error");
  }
}

async function loadTrace(traceId) {
  try {
    const events = await apiFetch(`/v1/traces/${traceId}`);
    currentTraceId = traceId;
    elements.viewTrace.disabled = false;
    renderAudit(events, traceId);
  } catch (error) {
    showToast(`审计链加载失败：${error.message}`, "error");
  }
}

async function refreshHealth() {
  try {
    const health = await apiFetch("/health");
    elements.health.textContent = "运行正常";
    elements.policy.textContent = health.policy_version;
    elements.serviceState.className = "service-state online";
    elements.serviceState.lastElementChild.textContent = "网关运行正常";
  } catch (error) {
    elements.health.textContent = "连接失败";
    elements.serviceState.className = "service-state offline";
    elements.serviceState.lastElementChild.textContent = "网关连接失败";
    showToast(error.message, "error");
  }
}

document.querySelectorAll(".scenario").forEach((button) => {
  button.addEventListener("click", () => applyScenario(button.dataset.scenario));
});
elements.tool.addEventListener("change", () => renderToolFields());
elements.form.addEventListener("submit", submitRequest);
elements.refreshApprovals.addEventListener("click", refreshApprovals);
elements.refreshAudit.addEventListener("click", refreshAudit);
elements.viewTrace.addEventListener("click", () => currentTraceId && loadTrace(currentTraceId));

applyScenario("public-file");
Promise.all([refreshHealth(), refreshApprovals(), refreshAudit()]);
