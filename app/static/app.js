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

const visualReportDomains = new Set([
  "tenant_spend_summary",
  "cost_summary",
  "reservation_savings",
  "quota_summary",
  "expiring_reservations",
  "storage_costs",
  "resource_group_costs",
  "subscription_cost_summary",
]);

function numericValue(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatCompactNumber(value) {
  return new Intl.NumberFormat("en-US", {
    notation: Math.abs(value) >= 1000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: Math.abs(value) >= 1000000 ? "compact" : "standard",
    maximumFractionDigits: Math.abs(value) >= 1000 ? 0 : 2,
  }).format(value);
}

function groupTotals(rows, keyField, valueField = "cost") {
  const totals = new Map();
  for (const row of rows) {
    const key = String(row?.[keyField] || "Unspecified");
    totals.set(key, (totals.get(key) || 0) + numericValue(row?.[valueField]));
  }
  return Array.from(totals, ([label, value]) => ({ label, value }));
}

function addKpi(container, label, value, detail = "") {
  const item = document.createElement("div");
  item.className = "report-kpi";
  const labelElement = document.createElement("span");
  labelElement.className = "report-kpi-label";
  labelElement.textContent = label;
  const valueElement = document.createElement("strong");
  valueElement.textContent = value;
  item.append(labelElement, valueElement);
  if (detail) {
    const detailElement = document.createElement("small");
    detailElement.textContent = detail;
    item.appendChild(detailElement);
  }
  container.appendChild(item);
}

function createChartPanel(title, subtitle = "") {
  const panel = document.createElement("section");
  panel.className = "report-chart-panel";
  const heading = document.createElement("h4");
  heading.textContent = title;
  panel.appendChild(heading);
  if (subtitle) {
    const supportingText = document.createElement("p");
    supportingText.textContent = subtitle;
    panel.appendChild(supportingText);
  }
  return panel;
}

function renderLineChart(panel, points, valueFormatter = formatCurrency) {
  const chart = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  chart.setAttribute("viewBox", "0 0 760 250");
  chart.setAttribute("role", "img");
  chart.setAttribute("aria-label", "Cost trend over time");
  chart.classList.add("report-line-chart");

  if (!points.length) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "No dated values were returned for this scope.";
    panel.appendChild(empty);
    return;
  }

  const sorted = [...points].sort((left, right) => left.label.localeCompare(right.label));
  const maxValue = Math.max(...sorted.map((point) => point.value), 1);
  const left = 58;
  const right = 730;
  const top = 20;
  const bottom = 205;
  const xStep = sorted.length > 1 ? (right - left) / (sorted.length - 1) : 0;

  for (let index = 0; index <= 4; index += 1) {
    const y = top + ((bottom - top) * index) / 4;
    const line = document.createElementNS(chart.namespaceURI, "line");
    line.setAttribute("x1", left);
    line.setAttribute("x2", right);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", "chart-gridline");
    chart.appendChild(line);

    const label = document.createElementNS(chart.namespaceURI, "text");
    label.setAttribute("x", left - 8);
    label.setAttribute("y", y + 4);
    label.setAttribute("text-anchor", "end");
    label.setAttribute("class", "chart-axis-label");
    label.textContent = formatCompactNumber(maxValue * (1 - index / 4));
    chart.appendChild(label);
  }

  const coordinates = sorted.map((point, index) => ({
    ...point,
    x: sorted.length === 1 ? (left + right) / 2 : left + index * xStep,
    y: bottom - (point.value / maxValue) * (bottom - top),
  }));
  const area = document.createElementNS(chart.namespaceURI, "path");
  area.setAttribute(
    "d",
    `M ${coordinates[0].x} ${bottom} L ${coordinates.map((point) => `${point.x} ${point.y}`).join(" L ")} L ${coordinates.at(-1).x} ${bottom} Z`,
  );
  area.setAttribute("class", "chart-area");
  chart.appendChild(area);

  const path = document.createElementNS(chart.namespaceURI, "polyline");
  path.setAttribute("points", coordinates.map((point) => `${point.x},${point.y}`).join(" "));
  path.setAttribute("class", "chart-line");
  chart.appendChild(path);

  coordinates.forEach((point, index) => {
    const dot = document.createElementNS(chart.namespaceURI, "circle");
    dot.setAttribute("cx", point.x);
    dot.setAttribute("cy", point.y);
    dot.setAttribute("r", 4);
    dot.setAttribute("class", "chart-point");
    const tooltip = document.createElementNS(chart.namespaceURI, "title");
    tooltip.textContent = `${point.label}: ${valueFormatter(point.value)}`;
    dot.appendChild(tooltip);
    chart.appendChild(dot);

    if (index === 0 || index === coordinates.length - 1 || index % Math.ceil(coordinates.length / 6) === 0) {
      const label = document.createElementNS(chart.namespaceURI, "text");
      label.setAttribute("x", point.x);
      label.setAttribute("y", 232);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("class", "chart-axis-label");
      label.textContent = point.label.slice(0, 10);
      chart.appendChild(label);
    }
  });
  panel.appendChild(chart);
}

function buildTrendSeries(rows, seriesField) {
  const rankedSeries = groupTotals(rows, seriesField)
    .sort((left, right) => right.value - left.value)
    .slice(0, 5)
    .map((entry) => entry.label);
  return rankedSeries.map((seriesLabel) => ({
    label: seriesLabel,
    points: groupTotals(
      rows.filter((row) => String(row?.[seriesField] || "Unspecified") === seriesLabel),
      "usageDate",
    ),
  }));
}

function renderMultiLineChart(panel, series) {
  const colors = ["#0f766e", "#2563eb", "#d97706", "#be123c", "#6d28d9"];
  const allPoints = series.flatMap((entry) => entry.points);
  if (!allPoints.length) {
    renderLineChart(panel, []);
    return;
  }

  const dates = [...new Set(allPoints.map((point) => point.label))].sort();
  const maxValue = Math.max(...allPoints.map((point) => point.value), 1);
  const left = 58;
  const right = 730;
  const top = 20;
  const bottom = 188;
  const xStep = dates.length > 1 ? (right - left) / (dates.length - 1) : 0;
  const chart = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  chart.setAttribute("viewBox", "0 0 760 270");
  chart.setAttribute("role", "img");
  chart.setAttribute("aria-label", "Cost trend by scope");
  chart.classList.add("report-line-chart");

  for (let index = 0; index <= 4; index += 1) {
    const y = top + ((bottom - top) * index) / 4;
    const line = document.createElementNS(chart.namespaceURI, "line");
    line.setAttribute("x1", left);
    line.setAttribute("x2", right);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", "chart-gridline");
    chart.appendChild(line);
    const label = document.createElementNS(chart.namespaceURI, "text");
    label.setAttribute("x", left - 8);
    label.setAttribute("y", y + 4);
    label.setAttribute("text-anchor", "end");
    label.setAttribute("class", "chart-axis-label");
    label.textContent = formatCompactNumber(maxValue * (1 - index / 4));
    chart.appendChild(label);
  }

  series.forEach((entry, seriesIndex) => {
    const valuesByDate = new Map(entry.points.map((point) => [point.label, point.value]));
    const coordinates = dates.map((date, index) => ({
      label: date,
      value: valuesByDate.get(date) || 0,
      x: dates.length === 1 ? (left + right) / 2 : left + index * xStep,
      y: bottom - ((valuesByDate.get(date) || 0) / maxValue) * (bottom - top),
    }));
    const line = document.createElementNS(chart.namespaceURI, "polyline");
    line.setAttribute("points", coordinates.map((point) => `${point.x},${point.y}`).join(" "));
    line.setAttribute("class", "chart-series-line");
    line.setAttribute("stroke", colors[seriesIndex]);
    chart.appendChild(line);
    coordinates.forEach((point) => {
      const dot = document.createElementNS(chart.namespaceURI, "circle");
      dot.setAttribute("cx", point.x);
      dot.setAttribute("cy", point.y);
      dot.setAttribute("r", 3);
      dot.setAttribute("fill", "#ffffff");
      dot.setAttribute("stroke", colors[seriesIndex]);
      dot.setAttribute("stroke-width", 2);
      const tooltip = document.createElementNS(chart.namespaceURI, "title");
      tooltip.textContent = `${entry.label} | ${point.label}: ${formatCurrency(point.value)}`;
      dot.appendChild(tooltip);
      chart.appendChild(dot);
    });
  });

  dates.forEach((date, index) => {
    if (index === 0 || index === dates.length - 1 || index % Math.ceil(dates.length / 6) === 0) {
      const label = document.createElementNS(chart.namespaceURI, "text");
      label.setAttribute("x", dates.length === 1 ? (left + right) / 2 : left + index * xStep);
      label.setAttribute("y", 211);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("class", "chart-axis-label");
      label.textContent = date.slice(0, 10);
      chart.appendChild(label);
    }
  });

  series.forEach((entry, index) => {
    const legendX = left + (index % 3) * 220;
    const legendY = 238 + Math.floor(index / 3) * 17;
    const swatch = document.createElementNS(chart.namespaceURI, "line");
    swatch.setAttribute("x1", legendX);
    swatch.setAttribute("x2", legendX + 20);
    swatch.setAttribute("y1", legendY);
    swatch.setAttribute("y2", legendY);
    swatch.setAttribute("stroke", colors[index]);
    swatch.setAttribute("stroke-width", 4);
    chart.appendChild(swatch);
    const label = document.createElementNS(chart.namespaceURI, "text");
    label.setAttribute("x", legendX + 27);
    label.setAttribute("y", legendY + 4);
    label.setAttribute("class", "chart-axis-label");
    label.textContent = entry.label.length > 25 ? `${entry.label.slice(0, 22)}...` : entry.label;
    chart.appendChild(label);
  });
  panel.appendChild(chart);
}

function renderRankedBars(panel, entries, valueFormatter = formatCurrency, tone = "cost") {
  const list = document.createElement("div");
  list.className = "report-bars";
  const ranked = [...entries].sort((left, right) => right.value - left.value).slice(0, 10);
  const maxValue = Math.max(...ranked.map((entry) => entry.value), 1);

  if (!ranked.length) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "No values were returned for this breakdown.";
    panel.appendChild(empty);
    return;
  }

  ranked.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "report-bar-row";
    const label = document.createElement("span");
    label.className = "report-bar-label";
    label.textContent = entry.label;
    label.title = entry.label;
    const track = document.createElement("span");
    track.className = "report-bar-track";
    const fill = document.createElement("span");
    fill.className = `report-bar-fill ${tone}`;
    fill.style.width = `${Math.max((entry.value / maxValue) * 100, entry.value > 0 ? 2 : 0)}%`;
    track.appendChild(fill);
    const value = document.createElement("strong");
    value.textContent = valueFormatter(entry.value);
    row.append(label, track, value);
    list.appendChild(row);
  });
  panel.appendChild(list);
}

function renderColumns(panel, entries, valueFormatter = formatCurrency, tone = "cost") {
  const values = [...entries].sort((left, right) => left.label.localeCompare(right.label)).slice(-14);
  if (!values.length) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "No values were returned for this diagram.";
    panel.appendChild(empty);
    return;
  }
  const maxValue = Math.max(...values.map((entry) => entry.value), 1);
  const chart = document.createElement("div");
  chart.className = "report-columns";
  values.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "report-column-item";
    const value = document.createElement("strong");
    value.textContent = valueFormatter(entry.value);
    const track = document.createElement("span");
    track.className = "report-column-track";
    const bar = document.createElement("span");
    bar.className = `report-column-bar ${tone}`;
    bar.style.height = `${Math.max((entry.value / maxValue) * 100, entry.value > 0 ? 3 : 0)}%`;
    track.appendChild(bar);
    const label = document.createElement("span");
    label.className = "report-column-label";
    label.textContent = entry.label.slice(0, 12);
    label.title = entry.label;
    item.append(value, track, label);
    chart.appendChild(item);
  });
  panel.appendChild(chart);
}

function renderDonut(panel, entries, valueFormatter = formatCurrency) {
  const colors = ["#168aad", "#184e77", "#52b788", "#f4a261", "#9b5de5", "#e76f51"];
  const ranked = [...entries].filter((entry) => entry.value > 0).sort((left, right) => right.value - left.value).slice(0, 6);
  const total = ranked.reduce((sum, entry) => sum + entry.value, 0);
  if (!total) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "No values were returned for this share diagram.";
    panel.appendChild(empty);
    return;
  }
  let cursor = 0;
  const stops = ranked.map((entry, index) => {
    const start = cursor;
    cursor += (entry.value / total) * 100;
    return `${colors[index]} ${start}% ${cursor}%`;
  });
  const layout = document.createElement("div");
  layout.className = "report-donut-layout";
  const donut = document.createElement("div");
  donut.className = "report-donut";
  donut.style.background = `conic-gradient(${stops.join(", ")})`;
  donut.setAttribute("role", "img");
  donut.setAttribute("aria-label", ranked.map((entry) => `${entry.label} ${valueFormatter(entry.value)}`).join(", "));
  const center = document.createElement("span");
  center.textContent = valueFormatter(total);
  donut.appendChild(center);
  const legend = document.createElement("div");
  legend.className = "report-donut-legend";
  ranked.forEach((entry, index) => {
    const row = document.createElement("div");
    const swatch = document.createElement("span");
    swatch.style.background = colors[index];
    const label = document.createElement("span");
    label.textContent = entry.label;
    const value = document.createElement("strong");
    value.textContent = `${((entry.value / total) * 100).toFixed(1)}%`;
    row.append(swatch, label, value);
    legend.appendChild(row);
  });
  layout.append(donut, legend);
  panel.appendChild(layout);
}

function renderShareBars(panel, rows, categoryField, seriesField) {
  const categories = [...new Set(rows.map((row) => String(row?.[categoryField] || "Unspecified")))].sort().slice(-12);
  const series = groupTotals(rows, seriesField).sort((left, right) => right.value - left.value).slice(0, 5).map((entry) => entry.label);
  const colors = ["#168aad", "#184e77", "#52b788", "#f4a261", "#9b5de5"];
  const chart = document.createElement("div");
  chart.className = "report-share-chart";
  categories.forEach((category) => {
    const categoryRows = rows.filter((row) => String(row?.[categoryField] || "Unspecified") === category);
    const totals = new Map(groupTotals(categoryRows, seriesField).map((entry) => [entry.label, entry.value]));
    const categoryTotal = [...totals.values()].reduce((sum, value) => sum + value, 0);
    const row = document.createElement("div");
    row.className = "report-share-row";
    const label = document.createElement("span");
    label.textContent = category.slice(0, 12);
    label.title = category;
    const track = document.createElement("span");
    track.className = "report-share-track";
    series.forEach((seriesLabel, index) => {
      const segment = document.createElement("span");
      segment.style.width = `${categoryTotal ? ((totals.get(seriesLabel) || 0) / categoryTotal) * 100 : 0}%`;
      segment.style.background = colors[index];
      segment.title = `${seriesLabel}: ${formatCurrency(totals.get(seriesLabel) || 0)}`;
      track.appendChild(segment);
    });
    row.append(label, track);
    chart.appendChild(row);
  });
  const legend = document.createElement("div");
  legend.className = "report-series-legend";
  series.forEach((label, index) => {
    const item = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.style.background = colors[index];
    item.append(swatch, document.createTextNode(label));
    legend.appendChild(item);
  });
  panel.append(chart, legend);
}

function appendChart(charts, title, subtitle, render) {
  const panel = createChartPanel(title, subtitle);
  render(panel);
  charts.appendChild(panel);
}

const reportDiagramSpecs = {
  tenant_spend_summary: {
    scope: "Selected subscriptions in the authenticated tenant",
    logic: "Sum actual pre-tax cost by usage date, then compare each subscription as a separate monthly series.",
  },
  cost_summary: {
    scope: "Selected subscriptions and date range",
    logic: "Sum actual cost and usage by subscription, charge type, meter category, and usage date.",
  },
  reservation_savings: {
    scope: "Azure Advisor recommendations in selected subscriptions",
    logic: "Show incurred reservation cost from Cost Management separately from annual savings estimates returned by Azure Advisor.",
  },
  quota_summary: {
    scope: "Compute regions discovered in selected subscriptions",
    logic: "Compare current regional Compute usage with the returned limit; exceeded means current usage is at least the limit.",
  },
  expiring_reservations: {
    scope: "Reservations that apply to the selected subscriptions",
    logic: "Calculate remaining calendar days from live expiry dates; join incurred cost only when Cost Management returns the same reservation ID.",
  },
  storage_costs: {
    scope: "Storage-classified cost rows in selected subscriptions",
    logic: "Sum actual cost and usage quantity by storage resource and usage date.",
  },
  resource_group_costs: {
    scope: "Resource groups in selected subscriptions",
    logic: "Sum actual pre-tax cost by resource group and usage date.",
  },
  subscription_cost_summary: {
    scope: "Selected subscriptions",
    logic: "Calculate monthly subscription cost share, subscription totals, meter-category totals, and resource-level cost from live rows.",
  },
};

function renderDomainDiagrams(data, charts) {
  const rows = data.rows;
  if (data.domain === "tenant_spend_summary") {
    const subscriptions = groupTotals(rows, "subscriptionId").sort((left, right) => right.value - left.value).slice(0, 4);
    subscriptions.forEach((subscription) => appendChart(
      charts,
      `${subscription.label} monthly spend`,
      "Actual cost by usage date",
      (panel) => renderColumns(panel, groupTotals(rows.filter((row) => String(row.subscriptionId || "Unspecified") === subscription.label), "usageDate")),
    ));
    return;
  }

  if (data.domain === "cost_summary") {
    appendChart(charts, "Cost by subscription", "Absolute cost comparison", (panel) => renderColumns(panel, groupTotals(rows, "subscriptionId")));
    appendChart(charts, "Subscription share", "Percent of selected-scope cost", (panel) => renderDonut(panel, groupTotals(rows, "subscriptionId")));
    appendChart(charts, "Monthly charge-type mix", "100% cost share by purchase or usage charge", (panel) => renderShareBars(panel, rows, "usageDate", "chargeType"));
    appendChart(charts, "Cost by meter category", "Ranked service meter categories", (panel) => renderRankedBars(panel, groupTotals(rows, "meterCategory")));
    return;
  }

  if (data.domain === "reservation_savings") {
    const incurredCosts = rows.filter((row) => row.recordType === "reservation_cost");
    const recommendations = rows.filter((row) => row.recordType === "advisor_recommendation");
    appendChart(charts, "Reservation cost incurred", "Actual reservation cost by usage date", (panel) => renderColumns(panel, groupTotals(incurredCosts, "usageDate")));
    appendChart(charts, "Cost by reservation", "Actual cost returned by Cost Management", (panel) => renderRankedBars(panel, groupTotals(incurredCosts, "reservationName")));
    appendChart(charts, "Savings by recommendation", "Annual savings estimate returned by Azure Advisor", (panel) => renderRankedBars(panel, groupTotals(recommendations, "recommendationType", "savingsEstimate"), formatCurrency, "savings"));
    appendChart(charts, "Savings by impact", "Advisor impact distribution weighted by savings", (panel) => renderDonut(panel, groupTotals(recommendations, "impact", "savingsEstimate")));
    return;
  }

  if (data.domain === "quota_summary") {
    appendChart(charts, "Current usage by region", "Sum of returned Compute usage counters", (panel) => renderColumns(panel, groupTotals(rows, "region", "currentValue"), formatCompactNumber, "quota"));
    appendChart(charts, "Highest quota utilization", "Current value divided by limit", (panel) => renderRankedBars(panel, groupTotals(rows, "quotaName", "utilizationPercent"), (value) => `${value.toFixed(1)}%`, "quota"));
    const exceeded = rows.filter((row) => numericValue(row.limit) > 0 && numericValue(row.currentValue) >= numericValue(row.limit));
    appendChart(charts, "Reached or exceeded limits", "Only counters at 100% utilization or higher", (panel) => renderRankedBars(panel, groupTotals(exceeded, "quotaName", "currentValue"), formatCompactNumber, "expiry"));
    return;
  }

  if (data.domain === "expiring_reservations") {
    const cohorts = rows.map((row) => {
      const days = numericValue(row.remainingDays);
      const expiryCohort = days < 0 ? "Expired" : days <= 30 ? "0-30 days" : days <= 90 ? "31-90 days" : days <= 365 ? "91-365 days" : "Over 365 days";
      return { ...row, expiryCohort, reservationCount: 1 };
    });
    appendChart(charts, "Reservations by expiry cohort", "Count grouped by calculated remaining days", (panel) => renderColumns(panel, groupTotals(cohorts, "expiryCohort", "reservationCount"), formatCompactNumber, "expiry"));
    appendChart(charts, "Nearest reservation expirations", "Remaining days by reservation", (panel) => renderRankedBars(panel, rows.map((row) => ({ label: row.displayName || row.reservationId || "Unnamed reservation", value: Math.max(numericValue(row.remainingDays), 0) })), (value) => `${formatCompactNumber(value)} days`, "expiry"));
    appendChart(charts, "Matched incurred cost", "Cost is shown only where reservation IDs matched across live sources", (panel) => renderRankedBars(panel, rows.filter((row) => row.incurredCost !== null && row.incurredCost !== undefined).map((row) => ({ label: row.displayName || row.reservationId || "Unnamed reservation", value: numericValue(row.incurredCost) }))));
    appendChart(charts, "Reservation resource types", "Share of live reservation inventory", (panel) => renderDonut(panel, groupTotals(rows.map((row) => ({ ...row, reservationCount: 1 })), "reservedResourceType", "reservationCount"), formatCompactNumber));
    return;
  }

  if (data.domain === "storage_costs") {
    appendChart(charts, "Storage cost share", "Actual cost by storage resource", (panel) => renderDonut(panel, groupTotals(rows, "resourceName")));
    appendChart(charts, "Storage usage share", "Usage quantity by storage resource", (panel) => renderDonut(panel, groupTotals(rows, "resourceName", "usageQuantity"), formatCompactNumber));
    appendChart(charts, "Storage cost by resource", "Top storage resources", (panel) => renderRankedBars(panel, groupTotals(rows, "resourceName")));
    appendChart(charts, "Storage usage by resource", "Top storage resources by quantity", (panel) => renderRankedBars(panel, groupTotals(rows, "resourceName", "usageQuantity"), formatCompactNumber));
    return;
  }

  if (data.domain === "resource_group_costs") {
    appendChart(charts, "Cost by resource group", "Ranked actual cost", (panel) => renderRankedBars(panel, groupTotals(rows, "resourceGroup")));
    appendChart(charts, "Monthly resource-group cost", "Actual cost by usage date", (panel) => renderColumns(panel, groupTotals(rows, "usageDate")));
    appendChart(charts, "Resource-group cost mix", "Share of selected-scope cost", (panel) => renderDonut(panel, groupTotals(rows, "resourceGroup")));
    return;
  }

  if (data.domain === "subscription_cost_summary") {
    appendChart(charts, "Monthly subscription mix", "100% monthly cost share", (panel) => renderShareBars(panel, rows, "usageDate", "subscriptionId"));
    appendChart(charts, "Cost by subscription", "Percent of selected-scope cost", (panel) => renderDonut(panel, groupTotals(rows, "subscriptionId")));
    appendChart(charts, "Cost by meter category", "Ranked meter categories", (panel) => renderRankedBars(panel, groupTotals(rows, "meterCategory")));
    appendChart(charts, "Cost by resource", "Ranked resource totals", (panel) => renderRankedBars(panel, groupTotals(rows, "resourceName")));
  }
}

function buildVisualReport(data) {
  if (!visualReportDomains.has(data.domain) || !Array.isArray(data.rows)) {
    return null;
  }

  const dashboard = document.createElement("article");
  dashboard.className = "live-report-dashboard";
  const heading = document.createElement("div");
  heading.className = "live-report-heading";
  const titleGroup = document.createElement("div");
  const eyebrow = document.createElement("span");
  eyebrow.textContent = "Live Azure report";
  const title = document.createElement("h3");
  title.textContent = humanizeFieldName(data.domain);
  titleGroup.append(eyebrow, title);
  const freshness = document.createElement("div");
  freshness.className = "report-freshness";
  freshness.textContent = `Collected ${new Date(data.generated_at_utc).toLocaleString()} | ${data.subscription_scope?.length || 0} subscription(s)`;
  heading.append(titleGroup, freshness);
  dashboard.appendChild(heading);

  const spec = reportDiagramSpecs[data.domain];
  const definition = document.createElement("div");
  definition.className = "report-definition";
  const scope = document.createElement("p");
  scope.innerHTML = `<strong>Scope</strong><span>${escapeHtml(spec.scope)}</span>`;
  const logic = document.createElement("p");
  logic.innerHTML = `<strong>Logic</strong><span>${escapeHtml(spec.logic)}</span>`;
  definition.append(scope, logic);
  dashboard.appendChild(definition);

  const kpis = document.createElement("div");
  kpis.className = "report-kpis";
  const totalCost = data.rows.reduce((sum, row) => sum + numericValue(row.cost || row.savingsEstimate), 0);
  if (data.domain === "quota_summary") {
    const peakUtilization = Math.max(...data.rows.map((row) => numericValue(row.utilizationPercent)), 0);
    addKpi(kpis, "Peak utilization", `${peakUtilization.toFixed(1)}%`);
  } else if (data.domain === "expiring_reservations") {
    const remainingDays = data.rows.map((row) => numericValue(row.remainingDays)).filter((value) => value >= 0);
    addKpi(kpis, "Next expiration", remainingDays.length ? `${Math.min(...remainingDays)} days` : "Not available");
  } else {
    const metricTotal = data.domain === "reservation_savings"
      ? data.rows.filter((row) => row.recordType === "advisor_recommendation").reduce((sum, row) => sum + numericValue(row.savingsEstimate), 0)
      : totalCost;
    addKpi(kpis, data.domain === "reservation_savings" ? "Potential savings" : "Cost represented", formatCurrency(metricTotal));
  }
  addKpi(kpis, "Live records", formatCompactNumber(data.rows.length));
  addKpi(kpis, "Data quality", `${numericValue(data.data_quality_score).toFixed(1)}%`);
  addKpi(kpis, "Source calls", formatCompactNumber(data.source_audit?.length || 0), data.live_data_confirmed ? "Live data confirmed" : "No source confirmed");
  dashboard.appendChild(kpis);

  const charts = document.createElement("div");
  charts.className = "report-chart-grid";
  renderDomainDiagrams(data, charts);
  dashboard.appendChild(charts);
  return dashboard;
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

  const visualReport = buildVisualReport(data);
  if (visualReport) {
    results.appendChild(visualReport);
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
