const tenantSelect = document.getElementById("tenantSelect");
const subscriptionList = document.getElementById("subscriptionList");
const domainSelect = document.getElementById("domainSelect");
const results = document.getElementById("results");
const loginState = document.getElementById("loginState");
const contextState = document.getElementById("contextState");
const executionIndicator = document.getElementById("executionIndicator");
const executionText = document.getElementById("executionText");
const resourceGroupSelect = document.getElementById("resourceGroup");
const regionSelect = document.getElementById("region");
const tagKeySelect = document.getElementById("tagKey");
const tagValueSelect = document.getElementById("tagValue");
const severitySelect = document.getElementById("severity");
const subscriptionFilter = document.getElementById("subscriptionFilter");
const subscriptionFilterStatus = document.getElementById("subscriptionFilterStatus");
const resultDialog = document.getElementById("resultDialog");
const resultDialogLabel = document.getElementById("resultDialogLabel");
const resultDialogTitle = document.getElementById("resultDialogTitle");
const resultDialogBody = document.getElementById("resultDialogBody");

let latestBearer = "";
let account = null;
let authInProgress = false;
let pendingOps = 0;
let scopeOptionsCache = { tag_values: {} };
let subscriptionsReady = false;
let scopeRefreshTimer = null;
let scopeRefreshInFlight = false;
let suppressScopeRefresh = 0;
let scopeRefreshSeq = 0;
let completedReportVisible = false;

function setExportButtonsEnabled(enabled) {
  for (const button of document.querySelectorAll(".exportBtn")) {
    button.disabled = !enabled;
  }
}

async function clearAuthContext(message = "Authentication context cleared", clearCliSession = true) {
  try {
    await fetch(`/api/auth/clear-context?clear_cli_session=${clearCliSession ? "true" : "false"}`, {
      method: "POST",
    });
  } catch {
    // Continue with local reset even if backend clear fails.
  }

  latestBearer = "";
  account = null;
  authInProgress = false;
  scopeOptionsCache = { tag_values: {} };
  subscriptionsReady = false;
  sessionStorage.removeItem(pkceVerifierKey);

  loginState.textContent = "Not signed in";
  contextState.textContent = message;

  tenantSelect.innerHTML = "";
  subscriptionList.innerHTML = "";
  subscriptionFilter.value = "";
  subscriptionFilterStatus.textContent = "";
  populateSelectOptions(resourceGroupSelect, []);
  populateSelectOptions(regionSelect, []);
  populateSelectOptions(tagKeySelect, []);
  populateSelectOptions(tagValueSelect, []);
  populateSelectOptions(severitySelect, []);

  document.getElementById("selectAllSubs").checked = false;
  document.getElementById("startDate").value = "";
  document.getElementById("endDate").value = "";
  document.getElementById("strictLive").checked = true;
  renderResults({ auth: "cleared", hint: message });
  updateRunButtonState(false);
  setControlsEnabled(false);
  setExportButtonsEnabled(false);
}

function startExecution(message) {
  pendingOps += 1;
  executionIndicator.classList.remove("idle");
  executionIndicator.classList.add("busy");
  executionText.textContent = message || "Processing...";
}

function stopExecution(message) {
  pendingOps = Math.max(0, pendingOps - 1);
  if (pendingOps === 0) {
    executionIndicator.classList.remove("busy");
    executionIndicator.classList.add("idle");
    executionText.textContent = message || "Idle";
  }
}

function setControlsEnabled(enabled) {
  document.getElementById("loadTenantsBtn").disabled = !enabled;
  document.getElementById("loadSubsBtn").disabled = !enabled;
  tenantSelect.disabled = !enabled;
  document.getElementById("selectAllSubs").disabled = !enabled;
  subscriptionFilter.disabled = !enabled;
  updateRunButtonState(enabled);
}

function updateRunButtonState(enabledOverride = null) {
  const runBtn = document.getElementById("runReportBtn");
  const baseEnabled = enabledOverride === null ? !tenantSelect.disabled : enabledOverride;
  runBtn.disabled = !(baseEnabled && subscriptionsReady && selectedSubscriptions().length > 0);
}

function selectedSubscriptions() {
  return Array.from(document.querySelectorAll(".subCheck:checked")).map((n) => n.value);
}

function visibleSubscriptionChecks() {
  return Array.from(document.querySelectorAll(".subscription-row:not([hidden]) .subCheck"));
}

function syncSelectAllState() {
  const checks = visibleSubscriptionChecks();
  const checked = checks.filter((c) => c.checked);
  const allBox = document.getElementById("selectAllSubs");
  allBox.checked = checks.length > 0 && checked.length === checks.length;
  allBox.indeterminate = checked.length > 0 && checked.length < checks.length;
  allBox.disabled = tenantSelect.disabled || checks.length === 0;
  updateRunButtonState();
}

function applySubscriptionFilter() {
  const query = subscriptionFilter.value.trim().toLocaleLowerCase();
  const rows = Array.from(subscriptionList.querySelectorAll(".subscription-row"));
  let visibleCount = 0;
  for (const row of rows) {
    const matches = !query || row.dataset.searchText.includes(query);
    row.hidden = !matches;
    if (matches) {
      visibleCount += 1;
    }
  }
  subscriptionFilterStatus.textContent = rows.length
    ? `${visibleCount} of ${rows.length} subscriptions shown`
    : "";
  syncSelectAllState();
}

function populateSelectOptions(selectEl, values) {
  const current = selectEl.value;
  selectEl.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All";
  selectEl.appendChild(allOption);

  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    selectEl.appendChild(opt);
  });

  if (current && values.includes(current)) {
    selectEl.value = current;
  }
}

function refreshTagValueDropdown() {
  const key = tagKeySelect.value;
  const values = key ? (scopeOptionsCache.tag_values?.[key] || []) : [];
  populateSelectOptions(tagValueSelect, values);
}

async function refreshScopeDropdowns() {
  const requestSeq = ++scopeRefreshSeq;
  if (!latestBearer) {
    return;
  }

  const subs = selectedSubscriptions();
  if (subs.length === 0) {
    populateSelectOptions(resourceGroupSelect, []);
    populateSelectOptions(regionSelect, []);
    populateSelectOptions(tagKeySelect, []);
    populateSelectOptions(tagValueSelect, []);
    populateSelectOptions(severitySelect, []);
    return;
  }

  startExecution("Refreshing scope options...");
  let refreshState = "Scope options ready";
  try {
    const response = await fetch("/api/scope-options", {
      method: "POST",
      headers: getAuthHeader(),
      body: JSON.stringify({ subscription_ids: subs }),
    });
    const payload = await response.json();

    if (requestSeq !== scopeRefreshSeq) {
      refreshState = "Idle";
      return;
    }

    if (!response.ok) {
      renderResults(payload);
      refreshState = "Scope options failed";
      return;
    }

    scopeOptionsCache = payload;
    populateSelectOptions(resourceGroupSelect, payload.resource_groups || []);
    populateSelectOptions(regionSelect, payload.regions || []);
    populateSelectOptions(tagKeySelect, payload.tag_keys || []);
    refreshTagValueDropdown();
    populateSelectOptions(severitySelect, payload.severity || []);
  } catch (err) {
    if (requestSeq === scopeRefreshSeq) {
      renderResults({ scopeOptionsError: String(err) });
    }
    refreshState = "Scope options failed";
  } finally {
    stopExecution(refreshState);
  }
}

async function refreshScopeDropdownsSafe() {
  if (scopeRefreshInFlight) {
    return;
  }

  scopeRefreshInFlight = true;
  try {
    await refreshScopeDropdowns();
  } finally {
    scopeRefreshInFlight = false;
  }
}

function queueScopeRefresh(delayMs = 450) {
  if (suppressScopeRefresh > 0) {
    return;
  }

  if (scopeRefreshTimer) {
    clearTimeout(scopeRefreshTimer);
  }

  scopeRefreshTimer = setTimeout(() => {
    scopeRefreshTimer = null;
    refreshScopeDropdownsSafe();
  }, delayMs);
}

async function flushScopeRefresh() {
  if (scopeRefreshTimer) {
    clearTimeout(scopeRefreshTimer);
    scopeRefreshTimer = null;
    await refreshScopeDropdownsSafe();
  }
}

function formatCellValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function humanizeFieldName(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/^./, (letter) => letter.toUpperCase());
}

function findResourceId(item) {
  const resourceIdEntry = Object.entries(item || {}).find(([key, value]) => {
    const normalized = key.replace(/[^a-z0-9]/gi, "").toLowerCase();
    return normalized === "resourceid" && typeof value === "string" && value.startsWith("/subscriptions/");
  });
  return resourceIdEntry?.[1] || "";
}

function appendDialogFields(container, item) {
  const fields = document.createElement("dl");
  fields.className = "dialog-fields";

  Object.entries(item || {}).forEach(([key, value]) => {
    const term = document.createElement("dt");
    term.textContent = humanizeFieldName(key);
    const detail = document.createElement("dd");
    detail.textContent = formatCellValue(value) || "Not returned by source";
    fields.append(term, detail);
  });
  container.appendChild(fields);
}

function appendRemediationSteps(container, recommendation) {
  const heading = document.createElement("h3");
  heading.textContent = "Recommended remediation";
  container.appendChild(heading);

  const steps = document.createElement("ol");
  steps.className = "remediation-steps";
  const action = recommendation.suggested_action || recommendation.suggestedAction || "Review the affected resources and recommendation evidence.";
  [
    `Review the evidence and confirm the affected scope: ${recommendation.affected_scope || recommendation.affectedScope || "selected report scope"}.`,
    action,
    "Validate the proposed change against workload requirements, ownership, and maintenance policies before applying it.",
    "Apply the approved change in Azure, then rerun this live report to verify the outcome.",
  ].forEach((text) => {
    const step = document.createElement("li");
    step.textContent = text;
    steps.appendChild(step);
  });
  container.appendChild(steps);
}

function openResultDialog(title, item, isRecommendation = false) {
  resultDialogLabel.textContent = isRecommendation ? "Recommendation review" : "Live result record";
  resultDialogTitle.textContent = title;
  resultDialogBody.innerHTML = "";

  if (isRecommendation) {
    appendRemediationSteps(resultDialogBody, item);
  }
  appendDialogFields(resultDialogBody, item);

  const resourceId = findResourceId(item);
  if (resourceId) {
    const portalLink = document.createElement("a");
    portalLink.className = "portal-link";
    portalLink.href = `https://portal.azure.com/#resource${resourceId}/overview`;
    portalLink.target = "_blank";
    portalLink.rel = "noopener noreferrer";
    portalLink.textContent = "Open resource in Azure Portal";
    resultDialogBody.appendChild(portalLink);
  }

  resultDialog.showModal();
}

document.getElementById("closeResultDialog").addEventListener("click", () => resultDialog.close());
resultDialog.addEventListener("click", (event) => {
  if (event.target === resultDialog) {
    resultDialog.close();
  }
});

function shouldCollapseSection(title) {
  const normalized = String(title || "").toLowerCase();
  return normalized === "summary" || normalized.startsWith("source audit") || normalized.startsWith("enrichment audit") || normalized === "warnings";
}

function appendSectionHeading(container, title, collapsible) {
  const headingText = title;
  if (!collapsible) {
    const heading = document.createElement("h3");
    heading.textContent = headingText;
    container.appendChild(heading);
    return container;
  }

  const details = document.createElement("details");
  details.className = "result-collapsible";
  details.open = false;

  const summary = document.createElement("summary");
  summary.textContent = headingText;
  details.appendChild(summary);
  container.appendChild(details);
  return details;
}

function buildKeyValueTable(title, data) {
  const block = document.createElement("div");
  block.className = "result-block";

  const target = appendSectionHeading(block, title, shouldCollapseSection(title));

  const table = document.createElement("table");
  table.className = "result-table";
  table.innerHTML = "<thead><tr><th>Field</th><th>Value</th></tr></thead>";

  const body = document.createElement("tbody");
  Object.entries(data).forEach(([key, value]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(key)}</td><td>${escapeHtml(formatCellValue(value))}</td>`;
    body.appendChild(tr);
  });
  table.appendChild(body);
  target.appendChild(table);
  return block;
}

function buildArrayTable(title, rows) {
  const block = document.createElement("div");
  block.className = "result-block";

  const displayTitle = `${title} (${rows.length})`;
  const target = appendSectionHeading(block, displayTitle, shouldCollapseSection(title));

  if (!rows.length) {
    const empty = document.createElement("div");
    empty.textContent = "No rows returned.";
    target.appendChild(empty);
    return block;
  }

  const discoveredColumns = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row || {}).forEach((key) => set.add(key));
      return set;
    }, new Set())
  );

  const longFieldKeyHints = [
    "endpoint",
    "resourceid",
    "resource_id",
    "id",
    "guid",
    "tenantid",
    "tenant_id",
    "subscriptionid",
    "subscription_id",
    "resourcesubscriptionid",
    "resource_subscription_id",
    "uri",
    "url",
  ];

  const looksLikeGuid = (value) => {
    if (typeof value !== "string") {
      return false;
    }
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value.trim());
  };

  const looksLongIdentifierValue = (value) => {
    if (value === null || value === undefined) {
      return false;
    }
    if (typeof value === "number" || typeof value === "boolean") {
      return false;
    }

    const text = formatCellValue(value).trim();
    if (!text) {
      return false;
    }

    if (text.startsWith("http://") || text.startsWith("https://")) {
      return true;
    }
    if (text.startsWith("/subscriptions/") || text.includes("/providers/")) {
      return true;
    }
    if (looksLikeGuid(text)) {
      return true;
    }
    if (text.length >= 36 && /[a-z]/i.test(text) && /\d/.test(text)) {
      return true;
    }

    return false;
  };

  const isLongIdentifierColumn = (column) => {
    const normalized = column.replace(/[^a-z0-9_]/gi, "").toLowerCase();
    if (longFieldKeyHints.some((hint) => normalized.includes(hint))) {
      return true;
    }

    return rows.some((row) => looksLongIdentifierValue(row?.[column]));
  };

  const isResourceIdColumn = (column) => {
    const normalized = column.replace(/[^a-z0-9_]/gi, "").toLowerCase();
    return normalized === "resourceid";
  };

  const columns = discoveredColumns
    .map((name, index) => ({
      name,
      index,
      longIdentifier: isLongIdentifierColumn(name),
      resourceId: isResourceIdColumn(name),
    }))
    .sort((a, b) => {
      if (a.resourceId !== b.resourceId) {
        return a.resourceId ? 1 : -1;
      }
      if (a.longIdentifier !== b.longIdentifier) {
        return a.longIdentifier ? 1 : -1;
      }
      return a.index - b.index;
    })
    .map((entry) => entry.name);

  const table = document.createElement("table");
  table.className = "result-table";
  const isRecommendationTable = title.toLowerCase() === "recommendations";
  const headerCells = columns
    .map((col) => {
      const headerClass = isResourceIdColumn(col) ? "col-resourceid" : "";
      return `<th class="${headerClass}">${escapeHtml(col)}</th>`;
    })
    .join("");
  const actionHeader = isRecommendationTable ? '<th class="col-action">Action</th>' : "";
  table.innerHTML = `<thead><tr>${headerCells}${actionHeader}</tr></thead>`;

  const body = document.createElement("tbody");
  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    tr.className = "result-row-clickable";
    tr.tabIndex = 0;
    tr.setAttribute("aria-label", `${isRecommendationTable ? "Review recommendation" : "View result details"} ${index + 1}`);
    tr.innerHTML = columns
      .map((col) => {
        const value = formatCellValue(row?.[col]);
        const cellClass = isResourceIdColumn(col) ? "col-resourceid" : "";
        return `<td class="${cellClass}">${escapeHtml(value)}</td>`;
      })
      .join("");
    if (isRecommendationTable) {
      const actionCell = document.createElement("td");
      actionCell.className = "col-action";
      const actionLink = document.createElement("button");
      actionLink.type = "button";
      actionLink.className = "table-action-link";
      actionLink.textContent = "Remedy steps";
      actionLink.addEventListener("click", (event) => {
        event.stopPropagation();
        openResultDialog(row.category || `Recommendation ${index + 1}`, row, true);
      });
      actionCell.appendChild(actionLink);
      tr.appendChild(actionCell);
    }
    const openDetails = () => openResultDialog(
      isRecommendationTable ? (row.category || `Recommendation ${index + 1}`) : `${title} record ${index + 1}`,
      row,
      isRecommendationTable
    );
    tr.addEventListener("click", openDetails);
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDetails();
      }
    });
    body.appendChild(tr);
  });
  table.appendChild(body);
  target.appendChild(table);
  return block;
}

function renderResults(data) {
  if (completedReportVisible) {
    return;
  }
  results.innerHTML = "";

  if (Array.isArray(data)) {
    results.appendChild(buildArrayTable("Results", data));
    return;
  }

  if (!data || typeof data !== "object") {
    results.textContent = formatCellValue(data);
    return;
  }

  const summary = {};
  Object.entries(data).forEach(([key, value]) => {
    if (!Array.isArray(value) && typeof value !== "object") {
      summary[key] = value;
    }
  });
  if (Object.keys(summary).length > 0) {
    results.appendChild(buildKeyValueTable("Summary", summary));
  }

  if (Array.isArray(data.source_audit)) {
    results.appendChild(buildArrayTable("Source Audit", data.source_audit));
  }
  if (Array.isArray(data.enrichment_audit)) {
    results.appendChild(buildArrayTable("Enrichment Audit", data.enrichment_audit));
  }
  if (Array.isArray(data.ai_token_summary)) {
    results.appendChild(buildArrayTable("AI Token Summary", data.ai_token_summary));
  }
  if (Array.isArray(data.ai_token_tracking)) {
    results.appendChild(buildArrayTable("AI Token Tracking", data.ai_token_tracking));
  }
  if (Array.isArray(data.recommendations)) {
    results.appendChild(buildArrayTable("Recommendations", data.recommendations));
  }
  if (Array.isArray(data.rows)) {
    results.appendChild(buildArrayTable("Rows", data.rows));
  }
  if (Array.isArray(data.warnings)) {
    results.appendChild(buildArrayTable("Warnings", data.warnings.map((message) => ({ message }))));
  }

  const unknownSections = Object.entries(data)
    .filter(([key, value]) => {
      if (["source_audit", "enrichment_audit", "ai_token_summary", "ai_token_tracking", "recommendations", "rows", "warnings"].includes(key)) {
        return false;
      }
      return Array.isArray(value) || (value && typeof value === "object");
    })
    .reduce((obj, [key, value]) => {
      obj[key] = value;
      return obj;
    }, {});

  if (Object.keys(unknownSections).length > 0) {
    const raw = document.createElement("div");
    raw.className = "result-raw";
    raw.textContent = JSON.stringify(unknownSections, null, 2);
    results.appendChild(raw);
  }
}

async function loadTenantsData() {
  startExecution("Loading tenants...");
  const response = await fetch("/api/tenants", { headers: getAuthHeader() });
  const payload = await response.json();
  if (!response.ok) {
      renderResults(payload);
    stopExecution("Tenant load failed");
    return false;
  }

  tenantSelect.innerHTML = "";
  for (const tenant of payload.items) {
    const opt = document.createElement("option");
    opt.value = tenant.tenantId;
    opt.textContent = `${tenant.displayName || tenant.tenantId} (${tenant.tenantId})`;
    tenantSelect.appendChild(opt);
  }
  renderResults(payload.audit);
  stopExecution("Tenants loaded");
  return true;
}

async function loadSubscriptionsData() {
  startExecution("Loading subscriptions...");
  subscriptionsReady = false;
  updateRunButtonState();
  const response = await fetch("/api/subscriptions", { headers: getAuthHeader() });
  const payload = await response.json();
  if (!response.ok) {
      renderResults(payload);
    stopExecution("Subscription load failed");
    return false;
  }

  subscriptionList.innerHTML = "";
  suppressScopeRefresh += 1;
  for (const sub of payload.items) {
    const row = document.createElement("label");
    row.className = "subscription-row";
    row.dataset.searchText = `${sub.displayName || ""} ${sub.subscriptionId || ""}`.toLocaleLowerCase();
    row.innerHTML = `<input type="checkbox" value="${sub.subscriptionId}" class="subCheck" /> ${sub.displayName} (${sub.subscriptionId})`;
    const checkbox = row.querySelector(".subCheck");
    checkbox.addEventListener("change", () => {
      syncSelectAllState();
      queueScopeRefresh();
    });
    subscriptionList.appendChild(row);
  }
  applySubscriptionFilter();

  if (selectedSubscriptions().length === 0) {
    const first = document.querySelector(".subCheck");
    if (first) {
      first.checked = true;
    }
  }
  syncSelectAllState();
  suppressScopeRefresh = Math.max(0, suppressScopeRefresh - 1);
  queueScopeRefresh(150);
  subscriptionsReady = true;
  updateRunButtonState();

  renderResults(payload.audit);
  contextState.textContent = `Context loaded: ${tenantSelect.options.length} tenants, ${payload.items.length} subscriptions discovered`;
  stopExecution("Subscriptions loaded");
  return true;
}

async function enableContextAfterLogin() {
  setControlsEnabled(true);
  subscriptionsReady = false;
  updateRunButtonState();
  const tenantsOk = await loadTenantsData();
  if (!tenantsOk) {
    contextState.textContent = "Authenticated but tenant discovery failed";
    return;
  }

  const subsOk = await loadSubscriptionsData();
  contextState.textContent = subsOk ? contextState.textContent : "Authenticated but subscription discovery failed";
}

const oauthConfig = {
  clientId: window.finopsConfig.clientId,
  authority: window.finopsConfig.authority,
  redirectUri: window.finopsConfig.redirectUri,
  scope: "https://management.azure.com/user_impersonation openid profile offline_access",
};

const pkceVerifierKey = "finops_pkce_verifier";

function base64UrlEncode(bytes) {
  const str = btoa(String.fromCharCode(...bytes));
  return str.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function randomString(length = 64) {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

async function sha256(text) {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return new Uint8Array(digest);
}

async function beginPkceLogin() {
  if (authInProgress) {
    return;
  }

  await clearAuthContext("Starting a new sign-in flow...", false);

  if (!oauthConfig.clientId) {
    startExecution("Initiating Microsoft login...");
    authInProgress = true;
    contextState.textContent = "Opening web-based Microsoft account selection...";
    const loginResponse = await fetch("/api/auth/cli-login?force_reauth=true", { method: "POST" });
    const loginPayload = await loginResponse.json();
    if (!loginResponse.ok) {
      renderResults(loginPayload);
      contextState.textContent = "Microsoft login failed";
      authInProgress = false;
      stopExecution("Microsoft login failed");
      return;
    }
    renderResults({ microsoft_login: loginPayload.status, details: loginPayload.message });
    contextState.textContent = "Microsoft sign-in opened in your browser. Waiting for completion...";

    const loginComplete = await waitForCliSessionReady();
    if (!loginComplete) {
      contextState.textContent = "Waiting timed out. Complete sign-in and click Use Azure CLI Session.";
      stopExecution("Login wait timed out");
    } else {
      stopExecution("Login completed");
    }
    authInProgress = false;
    return;
  }

  startExecution("Opening Entra OAuth login...");

  const verifier = randomString(64);
  const challenge = base64UrlEncode(await sha256(verifier));
  sessionStorage.setItem(pkceVerifierKey, verifier);

  const authorizeUrl = new URL(`${oauthConfig.authority}/oauth2/v2.0/authorize`);
  authorizeUrl.searchParams.set("client_id", oauthConfig.clientId);
  authorizeUrl.searchParams.set("response_type", "code");
  authorizeUrl.searchParams.set("redirect_uri", oauthConfig.redirectUri);
  authorizeUrl.searchParams.set("response_mode", "query");
  authorizeUrl.searchParams.set("scope", oauthConfig.scope);
  authorizeUrl.searchParams.set("code_challenge", challenge);
  authorizeUrl.searchParams.set("code_challenge_method", "S256");
  authorizeUrl.searchParams.set("prompt", "select_account");

  window.location.assign(authorizeUrl.toString());
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForCliSessionReady(maxAttempts = 30, intervalMs = 2000) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const ok = await loginWithCliSession({ silent: true, loadContext: true });
    if (ok) {
      contextState.textContent = "Microsoft login complete and context loaded";
      renderResults({ microsoft_login: "completed", attempts: attempt, source: "azure_cli" });
      return true;
    }

    contextState.textContent = `Waiting for Microsoft login completion... (${attempt}/${maxAttempts})`;
    await sleep(intervalMs);
  }

  return false;
}

async function loginWithCliSession(options = {}) {
  const silent = options.silent === true;
  const loadContext = options.loadContext !== false;

  if (!silent) {
    await clearAuthContext("Refreshing Azure CLI sign-in context...", false);
  }

  if (!silent) {
    startExecution("Getting Azure CLI session token...");
  }
  const response = await fetch("/api/auth/cli-token");
  const payload = await response.json();
  if (!response.ok) {
    if (!silent) {
      renderResults(payload);
      stopExecution("CLI token failed");
    }
    return false;
  }

  latestBearer = payload.access_token || "";
  loginState.textContent = "Signed in via Azure CLI session";
  if (!silent) {
    renderResults({ auth: "ok", source: payload.source });
  }
  if (loadContext) {
    await enableContextAfterLogin();
  }
  if (!silent) {
    stopExecution("CLI token ready");
  }
  return true;
}

async function completePkceIfRedirected() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const error = params.get("error");

  if (error) {
    loginState.textContent = `Sign-in failed: ${error}`;
    renderResults({ authError: error, details: params.get("error_description") });
    return;
  }

  if (!code) {
    return;
  }

  const verifier = sessionStorage.getItem(pkceVerifierKey);
  if (!verifier) {
    loginState.textContent = "Sign-in failed: missing PKCE verifier";
    return;
  }

  const tokenUrl = `${oauthConfig.authority}/oauth2/v2.0/token`;
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: oauthConfig.clientId,
    code,
    redirect_uri: oauthConfig.redirectUri,
    code_verifier: verifier,
    scope: oauthConfig.scope,
  });

  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  const payload = await response.json();
  if (!response.ok) {
    loginState.textContent = "Sign-in failed";
    renderResults({ tokenError: payload });
    return;
  }

  latestBearer = payload.access_token || "";
  account = { username: payload.id_token_claims?.preferred_username || "signed-in user" };
  loginState.textContent = `Signed in: ${account.username}`;
  await enableContextAfterLogin();

  sessionStorage.removeItem(pkceVerifierKey);
  window.history.replaceState({}, document.title, window.location.pathname);
}

function getAuthHeader() {
  return {
    Authorization: `Bearer ${latestBearer}`,
    "Content-Type": "application/json",
  };
}

async function loadDomains() {
  startExecution("Loading report domains...");
  const response = await fetch("/api/domains");
  const domains = await response.json();
  domainSelect.innerHTML = "";
  for (const d of domains) {
    const opt = document.createElement("option");
    opt.value = d.key;
    opt.textContent = d.label;
    domainSelect.appendChild(opt);
  }
  stopExecution("Domains loaded");
}

async function probeBackend() {
  startExecution("Checking backend health...");
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error(`Health check failed with status ${response.status}`);
    }
    const data = await response.json();
    renderResults({ backend: "connected", health: data });
    stopExecution("Backend connected");
  } catch (err) {
    renderResults(
      {
        backend: "failed_to_connect",
        hint: "Start the API with uvicorn app.main:app --reload and refresh the page.",
        error: String(err),
      }
    );
    stopExecution("Backend unavailable");
  }
}

function showAuthConfigState() {
  if (!oauthConfig.clientId) {
    loginState.textContent = "Browser OAuth not configured (CLI session sign-in available)";
    renderResults(
      {
        auth: "not_configured",
        hint: "Click Sign In with Entra to initiate Microsoft login via Azure CLI, or set FINOPS_ENTRA_CLIENT_ID for browser OAuth.",
      }
    );
  }
}

document.getElementById("loadTenantsBtn").addEventListener("click", async () => {
  if (!latestBearer) {
    await loginWithCliSession();
    if (!latestBearer) {
      return;
    }
  }
  await loadTenantsData();
});

document.getElementById("loadSubsBtn").addEventListener("click", async () => {
  if (!latestBearer) {
    renderResults(
      { auth: "required", hint: "Click Sign In with Entra or Use Azure CLI Session first." },
    );
    return;
  }

  await loadSubscriptionsData();
});

document.getElementById("selectAllSubs").addEventListener("change", (e) => {
  const checks = visibleSubscriptionChecks();
  suppressScopeRefresh += 1;
  for (const check of checks) {
    check.checked = e.target.checked;
  }
  suppressScopeRefresh = Math.max(0, suppressScopeRefresh - 1);
  syncSelectAllState();
  updateRunButtonState();
  queueScopeRefresh(100);
});

subscriptionFilter.addEventListener("input", applySubscriptionFilter);

tagKeySelect.addEventListener("change", refreshTagValueDropdown);

document.getElementById("runReportBtn").addEventListener("click", async () => {
  if (!latestBearer) {
    renderResults(
      { auth: "required", hint: "Authenticate first using one of the login buttons." },
    );
    return;
  }

  let subs = selectedSubscriptions();
  if (!tenantSelect.value) {
    renderResults(
      { tenant: "required", hint: "Click Load Tenants and pick a tenant before running report." },
    );
    return;
  }

  if (subs.length === 0) {
    const first = document.querySelector(".subCheck");
    if (first) {
      first.checked = true;
      syncSelectAllState();
      subs = selectedSubscriptions();
      renderResults({
        subscriptions: "auto-selected",
        hint: "No subscription was selected, so the first available subscription was selected automatically.",
      });
      await flushScopeRefresh();
    } else {
      renderResults(
        { subscriptions: "required", hint: "Select one or more subscriptions before running report." },
      );
      return;
    }
  }

  await flushScopeRefresh();

  const payload = {
    tenant_id: tenantSelect.value,
    subscription_ids: subs,
    strict_live_mode: document.getElementById("strictLive").checked,
    filters: {
      start_date: document.getElementById("startDate").value || null,
      end_date: document.getElementById("endDate").value || null,
      resource_group: document.getElementById("resourceGroup").value || null,
      region: document.getElementById("region").value || null,
      tag_key: document.getElementById("tagKey").value || null,
      tag_value: document.getElementById("tagValue").value || null,
      severity: document.getElementById("severity").value || null,
      actionable_only: document.getElementById("actionableOnly").checked,
    },
  };

  completedReportVisible = false;
  results.innerHTML = "";
  setExportButtonsEnabled(false);
  startExecution("Running report...");
  const domain = domainSelect.value;
  const response = await fetch(`/api/reports/${domain}`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    renderResults({ error: data, hint: "Adjust scope/filters or disable strict live validation for sparse data." });
    stopExecution("Report failed");
    return;
  }
  renderResults(data);
  completedReportVisible = true;
  setExportButtonsEnabled(true);
  stopExecution("Report complete");
});

const exportFileTypes = {
  csv: {
    description: "CSV report",
    mimeType: "text/csv",
    extension: ".csv",
  },
  pdf: {
    description: "Executive PDF report",
    mimeType: "application/pdf",
    extension: ".pdf",
    suggestedName: "finops-executive-report.pdf",
  },
  pptx: {
    description: "Executive PowerPoint report",
    mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    extension: ".pptx",
    suggestedName: "finops-executive-report.pptx",
  },
  sqlite: {
    description: "SQLite database",
    mimeType: "application/x-sqlite3",
    extension: ".sqlite",
  },
};

async function chooseExportDestination(type) {
  if (!("showSaveFilePicker" in window)) {
    return null;
  }

  const fileType = exportFileTypes[type];
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const baseName = (fileType.suggestedName || `finops-report${fileType.extension}`)
    .slice(0, -fileType.extension.length);
  return window.showSaveFilePicker({
    suggestedName: `${baseName}-${timestamp}${fileType.extension}`,
    types: [{
      description: fileType.description,
      accept: { [fileType.mimeType]: [fileType.extension] },
    }],
  });
}

function downloadExportBlob(blob, type) {
  const fileType = exportFileTypes[type];
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const baseName = (fileType.suggestedName || `finops-report${fileType.extension}`)
    .slice(0, -fileType.extension.length);
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = `${baseName}-${timestamp}${fileType.extension}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

function withTimeout(promise, timeoutMs, message) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(message)), timeoutMs);
    }),
  ]);
}

for (const button of document.querySelectorAll(".exportBtn")) {
  button.addEventListener("click", async (e) => {
    const type = e.target.getAttribute("data-export");
    const isExecutiveReport = type === "pdf" || type === "pptx";
    try {
      // Chromium requires the picker to run directly from the click, before any
      // awaited network work consumes the transient user activation.
      const fileHandle = await chooseExportDestination(type);
      startExecution(isExecutiveReport ? "Creating executive report..." : "Exporting results...");

      const response = await fetch(`/api/export/${type}`, { cache: "no-store" });
      if (!response.ok) {
        const data = await response.json();
        renderResults(data);
        stopExecution("Export failed");
        return;
      }

      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.byteLength === 0) {
        throw new Error("The export service returned an empty file.");
      }

      const blob = new Blob([bytes], { type: exportFileTypes[type].mimeType });
      if (fileHandle) {
        let writable = null;
        try {
          writable = await withTimeout(
            fileHandle.createWritable({ keepExistingData: false }),
            10000,
            "Timed out opening the selected file.",
          );
          await withTimeout(writable.write(blob), 30000, "Timed out writing the selected file.");
          await withTimeout(writable.close(), 10000, "Timed out closing the selected file.");
          writable = null;
          const savedFile = await withTimeout(
            fileHandle.getFile(),
            10000,
            "Timed out verifying the selected file.",
          );
          if (savedFile.size !== blob.size) {
            throw new Error(`Saved file verification failed: expected ${blob.size} bytes, found ${savedFile.size}.`);
          }
          stopExecution(`Export complete (${bytes.byteLength.toLocaleString()} bytes)`);
          return;
        } catch {
          if (writable) {
            try {
              await withTimeout(writable.abort(), 3000, "Timed out cancelling the selected file write.");
            } catch {
              // The browser may already have closed the failed stream.
            }
          }
          downloadExportBlob(blob, type);
          stopExecution(`Selected file was unavailable; downloaded a new copy (${bytes.byteLength.toLocaleString()} bytes)`);
          return;
        }
      }

      downloadExportBlob(blob, type);
      stopExecution(`Export complete (${bytes.byteLength.toLocaleString()} bytes)`);
    } catch (error) {
      if (error.name === "AbortError") {
        stopExecution("Export cancelled");
        return;
      }

      renderResults({ exportError: String(error), format: type });
      stopExecution("Export failed");
    }
  });
}

document.getElementById("loginBtn").addEventListener("click", async () => {
  try {
    await beginPkceLogin();
  } catch (err) {
    renderResults({ loginError: String(err) });
  }
});

document.getElementById("cliAuthBtn").addEventListener("click", async () => {
  try {
    await loginWithCliSession();
  } catch (err) {
    renderResults({ authError: String(err) });
  }
});

document.getElementById("clearAuthBtn").addEventListener("click", () => {
  clearAuthContext("Ready for a different sign-in.", false);
});

loadDomains();
probeBackend();
completePkceIfRedirected();
showAuthConfigState();
setControlsEnabled(false);
setExportButtonsEnabled(false);
