# Copyright (c) 2026 jerry wolff

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models import ReportResult


REPORT_DIAGRAM_SPECS = {
    "hybrid_use_benefit": ("Windows Server and SQL license configuration visible in selected subscriptions", "Count observed benefit states and products. Review candidates require entitlement validation; no savings or license ownership is inferred. Pooled databases inherit pool licensing."),
    "tenant_spend_summary": ("Selected subscriptions in the authenticated tenant", "Sum actual pre-tax cost by usage date, then compare each subscription as a separate monthly series."),
    "cost_summary": ("Selected subscriptions and date range", "Sum actual cost and usage by subscription, charge type, meter category, and usage date."),
    "budget_forecasting": ("Selected subscriptions in the authenticated tenant", "Summarize the current Cost Management response by subscription, service, and resource group as a baseline for budget planning."),
    "spend_visibility": ("Current Cost Management response for selected subscriptions", "Group returned cost by subscription, service, and resource group without synthesizing missing time-series values."),
    "optimization": ("Azure Advisor recommendations in selected subscriptions", "Summarize recommendation counts and reported annual savings estimates by recommendation, impact, and category."),
    "reservations": ("Current Cost Management response for selected subscriptions", "Show the returned cost baseline by subscription, service, and resource group for reservation review."),
    "savings_plans": ("Azure Cost Management Savings Plan recommendations for selected subscriptions", "Show Azure's 1-year and 3-year estimated savings from a trailing 30-day usage simulation. Estimates are projections, not realized savings."),
    "savings_potential": ("Cost-related Azure Advisor recommendations in selected subscriptions", "Summarize only Advisor recommendations matched to cost and savings keywords, using reported annual savings estimates where available."),
    "reservations_potential": ("Commitment-related Azure Advisor recommendations in selected subscriptions", "Summarize only Advisor recommendations matched to reservation, savings-plan, or commitment keywords."),
    "anomaly_detection": ("Resource inventory in selected subscriptions", "Show inventory coverage available for anomaly analysis; the current source does not return a measured anomaly signal."),
    "governance": ("Resource inventory and Azure Policy evidence in selected subscriptions", "Count returned policy states and inventory records by policy, resource type, and region."),
    "tag_compliance": ("Resource tags and Azure Policy evidence in selected subscriptions", "Count observed tag coverage, tag keys, policy states, and resource types from live records."),
    "chargeback_showback": ("Current Cost Management response for selected subscriptions", "Group returned cost by subscription, service, and resource group for allocation review."),
    "architecture_efficiency": ("Azure Advisor recommendations in selected subscriptions", "Summarize recommendation counts and reported annual savings estimates as architecture review evidence."),
    "sustainability": ("Resource inventory in selected subscriptions", "Show inventory distribution relevant to sustainability review; the current source does not return measured emissions."),
    "ai_finops": ("AI usage and cost evidence plus AI resource inventory in selected subscriptions", "Summarize returned AI cost, usage, estimated token units, and inventory without treating non-token meters as tokens."),
    "ai_token_tracking": ("AI meters returned for selected subscriptions and date range", "Chart service-level totals from normalized AI usage; estimated token units include only meters identified as token meters."),
    "idle_waste_detection": ("Azure Advisor recommendations in selected subscriptions", "Summarize recommendation counts and reported annual savings estimates as idle-waste review evidence."),
    "reservation_savings": ("Azure Cost Management and Advisor evidence in selected subscriptions", "Show incurred reservation cost separately from annual savings estimates returned by Azure Advisor."),
    "quota_summary": ("Compute regions discovered in selected subscriptions", "Compare current regional Compute usage with the returned limit; exceeded means current usage is at least the limit."),
    "expiring_reservations": ("Reservations that apply to the selected subscriptions", "Calculate remaining calendar days from live expiry dates; join incurred cost only when Cost Management returns the same reservation ID."),
    "storage_costs": ("Storage-classified cost rows in selected subscriptions", "Sum actual cost and usage quantity by storage resource and usage date."),
    "resource_group_costs": ("Resource groups in selected subscriptions", "Sum actual pre-tax cost by resource group and usage date."),
    "subscription_cost_summary": ("Selected subscriptions", "Calculate monthly subscription cost share, subscription totals, meter-category totals, and resource-level cost from live rows."),
}


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _label(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return "Unspecified"


def _group(
    rows: list[dict[str, Any]],
    label_keys: str | tuple[str, ...],
    value_key: str = "cost",
    *,
    chronological: bool = False,
    ascending: bool = False,
) -> list[dict[str, object]]:
    keys = (label_keys,) if isinstance(label_keys, str) else label_keys
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[_label(row, *keys)] += _number(row.get(value_key))
    entries = [{"label": label, "value": round(value, 6)} for label, value in totals.items()]
    if chronological:
        return sorted(entries, key=lambda entry: str(entry["label"]))
    return sorted(entries, key=lambda entry: float(entry["value"]), reverse=not ascending)


def _panel(
    title: str,
    subtitle: str,
    kind: str,
    entries: list[dict[str, object]],
    value_format: str = "currency",
) -> dict[str, object]:
    return {
        "title": title,
        "subtitle": subtitle,
        "kind": kind,
        "entries": entries,
        "valueFormat": value_format,
    }


def _count_group(rows: list[dict[str, Any]], label_keys: str | tuple[str, ...]) -> list[dict[str, object]]:
    return _group([{**row, "diagramCount": 1} for row in rows], label_keys, "diagramCount")


def _tag_key_entries(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    totals: dict[str, int] = defaultdict(int)
    for row in rows:
        tags = row.get("tags")
        if isinstance(tags, dict):
            for key in tags:
                totals[str(key)] += 1
    return [{"label": label, "value": value} for label, value in sorted(totals.items(), key=lambda item: (-item[1], item[0]))]


def _share_panel(
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    category_key: str,
    series_key: str,
) -> dict[str, object]:
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    series_totals: dict[str, float] = defaultdict(float)
    for row in rows:
        category = _label(row, category_key)
        series = _label(row, series_key)
        value = _number(row.get("cost"))
        totals[category][series] += value
        series_totals[series] += value
    series = sorted(series_totals, key=lambda label: (-series_totals[label], label))
    categories = [
        {"label": category, "values": [round(totals[category].get(label, 0.0), 6) for label in series]}
        for category in sorted(totals)
    ]
    return {
        "title": title,
        "subtitle": subtitle,
        "kind": "share",
        "series": series,
        "categories": categories,
        "valueFormat": "percent",
    }


def build_report_diagram(report: ReportResult) -> dict[str, object] | None:
    domain = report.domain.value
    spec = REPORT_DIAGRAM_SPECS.get(domain)
    if spec is None:
        return None

    rows = report.rows
    panels: list[dict[str, object]] = []

    if domain == "tenant_spend_summary":
        ranked_subscriptions = [str(entry["label"]) for entry in _group(rows, "subscriptionId")]
        for subscription_id in report.subscription_scope:
            if subscription_id not in ranked_subscriptions:
                ranked_subscriptions.append(subscription_id)
        for subscription_id in ranked_subscriptions[:4]:
            subscription_rows = [
                row for row in rows if _label(row, "subscriptionId") == subscription_id
            ]
            panels.append(_panel(
                f"{subscription_id} monthly spend",
                "Actual cost by usage date",
                "columns",
                _group(subscription_rows, "usageDate", chronological=True),
            ))
    elif domain == "cost_summary":
        panels = [
            _panel("Cost by subscription", "Absolute cost comparison", "columns", _group(rows, "subscriptionId")),
            _panel("Subscription share", "Percent of selected-scope cost", "donut", _group(rows, "subscriptionId")),
            _share_panel("Monthly charge-type mix", "100% cost share by purchase or usage charge", rows, "usageDate", "chargeType"),
            _panel("Cost by meter category", "Ranked service meter categories", "bars", _group(rows, "meterCategory")),
        ]
    elif domain == "budget_forecasting":
        panels = [
            _panel("Cost by subscription", "Current scoped cost baseline", "columns", _group(rows, "subscriptionId")),
            _panel("Subscription share", "Percent of current scoped cost", "donut", _group(rows, "subscriptionId")),
            _panel("Cost by service", "Services contributing most to the baseline", "bars", _group(rows, "serviceName")),
            _panel("Cost by resource group", "Resource groups contributing most to the baseline", "bars", _group(rows, "resourceGroup")),
        ]
    elif domain == "savings_plans":
        recommendations = [row for row in rows if row.get("isTopSavingsOption")]
        panels = []
        for term in ("P1Y", "P3Y"):
            for currency_code in sorted(
                {str(row.get("currencyCode")) for row in recommendations if row.get("term") == term and row.get("currencyCode")}
            ):
                term_rows = [
                    row for row in recommendations
                    if row.get("term") == term and row.get("currencyCode") == currency_code
                ]
                term_label = "1-year" if term == "P1Y" else "3-year"
                panels.append(
                    _panel(
                        f"{term_label} estimated savings by subscription ({currency_code})",
                        "Azure estimate for the trailing 30-day usage window; top option per subscription",
                        "bars",
                        _group(term_rows, "subscriptionId", "savingsAmount"),
                    )
                )
        if not panels:
            panels = [
                _panel(
                    "Savings Plan recommendations",
                    "No recommendation rows were returned for the selected subscriptions",
                    "bars",
                    [],
                )
            ]
    elif domain in {"spend_visibility", "reservations", "chargeback_showback"}:
        panels = [
            _panel("Cost by subscription", "Current scoped cost", "columns", _group(rows, "subscriptionId")),
            _panel("Cost by service", "Returned cost grouped by Azure service", "bars", _group(rows, "serviceName")),
            _panel("Cost by resource group", "Returned cost grouped by resource group", "bars", _group(rows, "resourceGroup")),
            _panel("Service cost share", "Share of current scoped cost", "donut", _group(rows, "serviceName")),
        ]
    elif domain in {"optimization", "savings_potential", "reservations_potential", "architecture_efficiency", "idle_waste_detection"}:
        panels = [
            _panel("Savings by recommendation", "Annual savings estimate reported by Azure Advisor", "bars", _group(rows, "recommendationType", "savingsEstimate")),
            _panel("Savings by impact", "Advisor-reported savings grouped by impact", "donut", _group(rows, "impact", "savingsEstimate")),
            _panel("Recommendations by category", "Count of returned Advisor recommendations", "columns", _count_group(rows, "category"), "number"),
            _panel("Recommendations by subscription", "Count across selected subscriptions", "bars", _count_group(rows, "subscriptionId"), "number"),
        ]
    elif domain in {"anomaly_detection", "sustainability"}:
        inventory = [row for row in rows if row.get("resourceType")]
        panels = [
            _panel("Resources by type", "Inventory coverage returned for analysis", "bars", _count_group(inventory, "resourceType"), "number"),
            _panel("Resources by region", "Inventory distribution by Azure region", "donut", _count_group(inventory, "region"), "number"),
            _panel("Resources by subscription", "Inventory count across selected subscriptions", "columns", _count_group(inventory, "subscriptionId"), "number"),
        ]
    elif domain == "governance":
        inventory = [row for row in rows if row.get("resourceType")]
        policy = [row for row in rows if row.get("complianceState") or row.get("policyDefinitionName")]
        panels = [
            _panel("Policy evidence by state", "Count of returned Azure Policy records", "donut", _count_group(policy, "complianceState"), "number"),
            _panel("Policy evidence by definition", "Most frequently returned policy definitions", "bars", _count_group(policy, "policyDefinitionName"), "number"),
            _panel("Resources by type", "Resource inventory included in the governance scope", "bars", _count_group(inventory, "resourceType"), "number"),
            _panel("Resources by region", "Inventory distribution by Azure region", "columns", _count_group(inventory, "region"), "number"),
        ]
    elif domain == "tag_compliance":
        inventory = [row for row in rows if row.get("resourceType")]
        policy = [row for row in rows if row.get("complianceState")]
        coverage = [{"tagCoverage": "Tagged" if isinstance(row.get("tags"), dict) and row["tags"] else "Untagged"} for row in inventory]
        panels = [
            _panel("Tag coverage", "Count of resources with and without observed tags", "donut", _count_group(coverage, "tagCoverage"), "number"),
            _panel("Most common tag keys", "Number of resources carrying each observed key", "bars", _tag_key_entries(inventory), "number"),
            _panel("Policy evidence by state", "Count of returned Azure Policy records", "columns", _count_group(policy, "complianceState"), "number"),
            _panel("Resources by type", "Inventory included in tag analysis", "bars", _count_group(inventory, "resourceType"), "number"),
        ]
    elif domain == "ai_finops":
        usage = report.ai_token_tracking
        inventory = [row for row in rows if row.get("resourceType")]
        panels = [
            _panel("AI cost by service", "Cost returned for AI meters", "bars", _group(usage, "serviceName")),
            _panel("Estimated token units by service", "Usage from meters identified as token meters", "bars", _group(usage, "serviceName", "estimatedTokenUnits"), "number"),
            _panel("AI usage by meter", "Returned usage quantity by meter", "bars", _group(usage, "meterName", "usageQuantity"), "number"),
            _panel("AI resources by type", "Resource inventory in the AI FinOps scope", "donut", _count_group(inventory, "resourceType"), "number"),
        ]
    elif domain == "ai_token_tracking":
        service_rows = [row for row in rows if row.get("serviceScope") != "All AI Services"]
        panels = [
            _panel("AI cost by service", "Normalized total cost", "bars", _group(service_rows, "serviceScope", "totalCost")),
            _panel("Estimated token units by service", "Totals from identified token meters", "bars", _group(service_rows, "serviceScope", "totalEstimatedTokenUnits"), "number"),
            _panel("Usage quantity by service", "Normalized total usage quantity", "bars", _group(service_rows, "serviceScope", "totalUsageQuantity"), "number"),
            _panel("Meter records by service", "Count of normalized source records", "columns", _group(service_rows, "serviceScope", "records"), "number"),
        ]
    elif domain == "reservation_savings":
        incurred = [row for row in rows if row.get("recordType") == "reservation_cost"]
        advisor = [row for row in rows if row.get("recordType") == "advisor_recommendation"]
        panels = [
            _panel("Reservation cost incurred", "Actual reservation cost by usage date", "columns", _group(incurred, "usageDate", chronological=True)),
            _panel("Cost by reservation", "Actual cost returned by Cost Management", "bars", _group(incurred, ("reservationName", "reservationId"))),
            _panel("Savings by recommendation", "Annual savings estimate returned by Azure Advisor", "bars", _group(advisor, "recommendationType", "savingsEstimate")),
            _panel("Savings by impact", "Advisor impact distribution weighted by savings", "donut", _group(advisor, "impact", "savingsEstimate")),
        ]
    elif domain == "hybrid_use_benefit":
        candidates = [row for row in rows if row.get("reviewCandidate")]
        panels = [
            _panel("Hybrid Benefit configuration", "Observed status, not proof of license entitlement", "donut", _count_group(rows, "benefitStatus"), "number"),
            _panel("License products", "Configuration records; not owned license quantities", "bars", _count_group(rows, "licenseProduct"), "number"),
            _panel("Review candidates by subscription", "Validate qualifying licenses before enabling the benefit", "bars", _count_group(candidates, "subscriptionId"), "number"),
        ]
    elif domain == "quota_summary":
        exceeded = [
            row for row in rows
            if _number(row.get("limit")) > 0 and _number(row.get("currentValue")) >= _number(row.get("limit"))
        ]
        panels = [
            _panel("Current usage by region", "Sum of returned Compute usage counters", "columns", _group(rows, "region", "currentValue"), "number"),
            _panel("Highest quota utilization", "Current value divided by limit", "bars", _group(rows, "quotaName", "utilizationPercent"), "percent"),
            _panel("Reached or exceeded limits", "Only counters at 100% utilization or higher", "bars", _group(exceeded, "quotaName", "currentValue"), "number"),
        ]
    elif domain == "expiring_reservations":
        inventory = [row for row in rows if row.get("recordType") in (None, "reservation_inventory")]
        cohort_rows = []
        for row in inventory:
            days = _number(row.get("remainingDays"))
            cohort = "Expired" if days < 0 else "0-30 days" if days <= 30 else "31-90 days" if days <= 90 else "91-365 days" if days <= 365 else "Over 365 days"
            cohort_rows.append({"expiryCohort": cohort, "reservationCount": 1})
        named_inventory = [{**row, "diagramLabel": _label(row, "displayName", "reservationId")} for row in inventory]
        matched_costs = [row for row in named_inventory if row.get("incurredCost") is not None]
        panels = [
            _panel("Reservations by expiry cohort", "Count grouped by calculated remaining days", "columns", _group(cohort_rows, "expiryCohort", "reservationCount"), "number"),
            _panel("Nearest reservation expirations", "Remaining days by reservation", "bars", _group(
                [row for row in named_inventory if _number(row.get("remainingDays")) >= 0],
                "diagramLabel",
                "remainingDays",
                ascending=True,
            ), "days"),
            _panel("Matched incurred cost", "Cost is shown only where reservation IDs matched across live sources", "bars", _group(matched_costs, "diagramLabel", "incurredCost")),
            _panel("Reservation resource types", "Share of live reservation inventory", "donut", _group([{**row, "reservationCount": 1} for row in inventory], "reservedResourceType", "reservationCount"), "number"),
        ]
    elif domain == "storage_costs":
        panels = [
            _panel("Storage cost share", "Actual cost by storage resource", "donut", _group(rows, ("resourceName", "resourceId"))),
            _panel("Storage usage share", "Usage quantity by storage resource", "donut", _group(rows, ("resourceName", "resourceId"), "usageQuantity"), "number"),
            _panel("Storage cost by resource", "Top storage resources", "bars", _group(rows, ("resourceName", "resourceId"))),
            _panel("Storage usage by resource", "Top storage resources by quantity", "bars", _group(rows, ("resourceName", "resourceId"), "usageQuantity"), "number"),
        ]
    elif domain == "resource_group_costs":
        panels = [
            _panel("Cost by resource group", "Ranked actual cost", "bars", _group(rows, "resourceGroup")),
            _panel("Monthly resource-group cost", "Actual cost by usage date", "columns", _group(rows, "usageDate", chronological=True)),
            _panel("Resource-group cost mix", "Share of selected-scope cost", "donut", _group(rows, "resourceGroup")),
        ]
    elif domain == "subscription_cost_summary":
        panels = [
            _share_panel("Monthly subscription mix", "100% monthly cost share", rows, "usageDate", "subscriptionId"),
            _panel("Cost by subscription", "Percent of selected-scope cost", "donut", _group(rows, "subscriptionId")),
            _panel("Cost by meter category", "Ranked meter categories", "bars", _group(rows, "meterCategory")),
            _panel("Cost by resource", "Ranked resource totals", "bars", _group(rows, ("resourceName", "resourceId"))),
        ]

    return {
        "title": domain.replace("_", " ").title(),
        "scope": spec[0],
        "logic": spec[1],
        "panels": panels,
    }