from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models import ReportResult


REPORT_DIAGRAM_SPECS = {
    "tenant_spend_summary": {
        "scope": "Selected subscriptions in the authenticated tenant",
        "logic": "Sum actual pre-tax cost by usage date, then compare each subscription as a separate monthly series.",
    },
    "cost_summary": {
        "scope": "Selected subscriptions and date range",
        "logic": "Sum actual cost and usage by subscription, charge type, meter category, and usage date.",
    },
    "reservation_savings": {
        "scope": "Azure Cost Management and Advisor evidence in selected subscriptions",
        "logic": "Show incurred reservation cost separately from annual savings estimates returned by Azure Advisor.",
    },
    "quota_summary": {
        "scope": "Compute regions discovered in selected subscriptions",
        "logic": "Compare current regional Compute usage with the returned limit; exceeded means current usage is at least the limit.",
    },
    "expiring_reservations": {
        "scope": "Reservations that apply to the selected subscriptions",
        "logic": "Calculate remaining calendar days from live expiry dates; join incurred cost only when Cost Management returns the same reservation ID.",
    },
    "storage_costs": {
        "scope": "Storage-classified cost rows in selected subscriptions",
        "logic": "Sum actual cost and usage quantity by storage resource and usage date.",
    },
    "resource_group_costs": {
        "scope": "Resource groups in selected subscriptions",
        "logic": "Sum actual pre-tax cost by resource group and usage date.",
    },
    "subscription_cost_summary": {
        "scope": "Selected subscriptions",
        "logic": "Calculate monthly subscription cost share, subscription totals, meter-category totals, and resource-level cost from live rows.",
    },
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
        {
            "label": category,
            "values": [round(totals[category].get(label, 0.0), 6) for label in series],
        }
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
    elif domain == "reservation_savings":
        incurred = [row for row in rows if row.get("recordType") == "reservation_cost"]
        advisor = [row for row in rows if row.get("recordType") == "advisor_recommendation"]
        panels = [
            _panel("Reservation cost incurred", "Actual reservation cost by usage date", "columns", _group(incurred, "usageDate", chronological=True)),
            _panel("Cost by reservation", "Actual cost returned by Cost Management", "bars", _group(incurred, ("reservationName", "reservationId"))),
            _panel("Savings by recommendation", "Annual savings estimate returned by Azure Advisor", "bars", _group(advisor, "recommendationType", "savingsEstimate")),
            _panel("Savings by impact", "Advisor impact distribution weighted by savings", "donut", _group(advisor, "impact", "savingsEstimate")),
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
        "scope": spec["scope"],
        "logic": spec["logic"],
        "panels": panels,
    }