from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.models import Recommendation, ReportDomain, ReportRequest, ReportResult
from app.services.azure_live import AzureLiveClient
from app.services.enrichment import enrich_rows_with_resource_metadata, score_data_quality

DOMAIN_RECOMMENDATION_CATEGORY: dict[ReportDomain, str] = {
    ReportDomain.tenant_spend_summary: "Cost visibility",
    ReportDomain.cost_summary: "Cost visibility",
    ReportDomain.reservation_savings: "Commitment optimization",
    ReportDomain.quota_summary: "Capacity governance",
    ReportDomain.expiring_reservations: "Commitment governance",
    ReportDomain.storage_costs: "Storage optimization",
    ReportDomain.resource_group_costs: "Cost allocation",
    ReportDomain.subscription_cost_summary: "Cost allocation",
    ReportDomain.spend_visibility: "Cost reduction",
    ReportDomain.budget_forecasting: "Cost governance",
    ReportDomain.optimization: "Waste elimination",
    ReportDomain.reservations: "Commitment optimization",
    ReportDomain.savings_plans: "Commitment optimization",
    ReportDomain.savings_potential: "Commitment optimization",
    ReportDomain.reservations_potential: "Commitment optimization",
    ReportDomain.anomaly_detection: "Cost governance",
    ReportDomain.governance: "Governance compliance",
    ReportDomain.tag_compliance: "Tag hygiene",
    ReportDomain.chargeback_showback: "Cost governance",
    ReportDomain.architecture_efficiency: "Architecture modernization",
    ReportDomain.sustainability: "Sustainability improvement",
    ReportDomain.ai_finops: "AI workload efficiency",
    ReportDomain.ai_token_tracking: "AI workload efficiency",
    ReportDomain.idle_waste_detection: "Waste elimination",
}


async def build_report(domain: ReportDomain, request: ReportRequest, bearer_token: str) -> ReportResult:
    start = time.perf_counter()
    client = AzureLiveClient(bearer_token)
    source_audit = []
    rows: list[dict[str, Any]] = []
    ai_token_tracking: list[dict[str, Any]] = []
    ai_token_summary: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not request.subscription_ids:
        raise ValueError("At least one subscription must be selected")

    if domain in {
        ReportDomain.tenant_spend_summary,
        ReportDomain.cost_summary,
        ReportDomain.storage_costs,
        ReportDomain.resource_group_costs,
        ReportDomain.subscription_cost_summary,
    }:
        cost_details: list[dict[str, Any]] = []
        for subscription_id in request.subscription_ids:
            try:
                cost_rows, audit = await client.query_cost_details(
                    subscription_id,
                    start_date=request.filters.start_date,
                    end_date=request.filters.end_date,
                )
                source_audit.append(audit)
                cost_details.extend(
                    _normalize_cost_row(subscription_id, entry)
                    for entry in cost_rows
                )
            except Exception as exc:
                warnings.append(
                    f"Cost Management detail query skipped for subscription {subscription_id}: {exc}"
                )

        if domain == ReportDomain.tenant_spend_summary:
            rows = _aggregate_cost_rows(
                cost_details,
                [
                    "usageDate",
                    "meterCategory",
                    "meterSubCategory",
                    "meterName",
                    "unitOfMeasure",
                    "serviceName",
                    "chargeType",
                    "subscriptionId",
                ],
            )
        elif domain == ReportDomain.storage_costs:
            storage_rows = [
                row
                for row in cost_details
                if "storage" in " ".join(
                    str(row.get(field, ""))
                    for field in ("serviceName", "meterCategory", "resourceType")
                ).lower()
            ]
            rows = _aggregate_cost_rows(
                storage_rows,
                [
                    "usageDate",
                    "meterCategory",
                    "meterSubCategory",
                    "meterName",
                    "unitOfMeasure",
                    "serviceName",
                    "chargeType",
                    "subscriptionId",
                    "resourceGroup",
                    "resourceName",
                ],
            )
        elif domain == ReportDomain.resource_group_costs:
            rows = _aggregate_cost_rows(
                cost_details,
                [
                    "usageDate",
                    "meterCategory",
                    "meterSubCategory",
                    "meterName",
                    "unitOfMeasure",
                    "serviceName",
                    "chargeType",
                    "subscriptionId",
                    "resourceGroup",
                    "resourceName",
                ],
            )
        elif domain == ReportDomain.subscription_cost_summary:
            rows = _aggregate_cost_rows(
                cost_details,
                [
                    "usageDate",
                    "meterCategory",
                    "meterSubCategory",
                    "meterName",
                    "unitOfMeasure",
                    "serviceName",
                    "chargeType",
                    "subscriptionId",
                    "resourceName",
                ],
            )
        else:
            rows = cost_details

    if domain in {
        ReportDomain.spend_visibility,
        ReportDomain.budget_forecasting,
        ReportDomain.reservations,
        ReportDomain.savings_plans,
        ReportDomain.chargeback_showback,
    }:
        for subscription_id in request.subscription_ids:
            try:
                cost_rows, audit = await client.query_cost_management(subscription_id)
                source_audit.append(audit)
                for entry in cost_rows:
                    rows.append(
                        {
                            "subscriptionId": subscription_id,
                            "cost": entry[0] if len(entry) > 0 else None,
                            "resourceId": entry[1] if len(entry) > 1 else "",
                            "resourceGroup": entry[2] if len(entry) > 2 else "",
                            "serviceName": entry[3] if len(entry) > 3 else "",
                        }
                    )
            except Exception as exc:
                warnings.append(
                    f"Cost Management query skipped for subscription {subscription_id}: {exc}"
                )

    if domain in {
        ReportDomain.optimization,
        ReportDomain.idle_waste_detection,
        ReportDomain.architecture_efficiency,
        ReportDomain.savings_potential,
        ReportDomain.reservations_potential,
        ReportDomain.reservation_savings,
    }:
        for subscription_id in request.subscription_ids:
            try:
                advisories, audit = await client.list_advisor_recommendations(subscription_id)
                source_audit.append(audit)
                for item in advisories:
                    properties = item.get("properties", {})
                    problem = str(properties.get("shortDescription", {}).get("problem", ""))
                    solution = str(properties.get("shortDescription", {}).get("solution", ""))
                    impact = str(properties.get("impact", ""))
                    category = str(properties.get("category", ""))
                    savings_estimate = properties.get("extendedProperties", {}).get("annualSavingsAmount", "")
                    recommendation_text = " ".join([problem, solution, impact, category]).lower()

                    if domain == ReportDomain.savings_potential and not any(
                        keyword in recommendation_text for keyword in ("saving", "savings", "cost", "optimiz", "right-size", "rightsizing")
                    ):
                        continue
                    if domain == ReportDomain.reservations_potential and not any(
                        keyword in recommendation_text for keyword in ("reservation", "reserved", "savings plan", "commitment", "commitment tier")
                    ):
                        continue
                    if domain == ReportDomain.reservation_savings and not any(
                        keyword in recommendation_text for keyword in ("reservation", "reserved", "savings plan", "commitment", "commitment tier")
                    ):
                        continue

                    rows.append(
                        {
                            "recordType": "advisor_recommendation",
                            "subscriptionId": subscription_id,
                            "resourceId": properties.get("resourceMetadata", {}).get("resourceId", ""),
                            "recommendationType": problem,
                            "recommendationSolution": solution,
                            "impact": impact,
                            "category": category,
                            "savingsEstimate": savings_estimate,
                        }
                    )
            except Exception as exc:
                warnings.append(
                    f"Advisor query skipped for subscription {subscription_id}: {exc}"
                )

    reservation_cost_rows: list[dict[str, Any]] = []
    if domain in {ReportDomain.reservation_savings, ReportDomain.expiring_reservations}:
        for subscription_id in request.subscription_ids:
            try:
                cost_rows, audit = await client.query_reservation_costs(
                    subscription_id,
                    start_date=request.filters.start_date,
                    end_date=request.filters.end_date,
                )
                source_audit.append(audit)
                reservation_cost_rows.extend(cost_rows)
            except Exception as exc:
                warnings.append(
                    f"Reservation cost query skipped for subscription {subscription_id}: {exc}"
                )
        if domain == ReportDomain.reservation_savings:
            rows.extend(reservation_cost_rows)

    if domain == ReportDomain.expiring_reservations:
        try:
            reservation_rows, audit = await client.list_reservations()
            source_audit.append(audit)
            selected_scope = {subscription_id.lower() for subscription_id in request.subscription_ids}
            costs_by_reservation: dict[str, float] = defaultdict(float)
            for cost_row in reservation_cost_rows:
                reservation_id = str(cost_row.get("reservationId") or "").lower()
                if reservation_id:
                    costs_by_reservation[reservation_id] += _safe_number(cost_row.get("cost"))
            for reservation in reservation_rows:
                applied_scopes = reservation.get("appliedScopes") or []
                applies_to_selection = not applied_scopes or any(
                    any(f"/subscriptions/{subscription_id}" in str(scope).lower() for subscription_id in selected_scope)
                    for scope in applied_scopes
                )
                if not applies_to_selection:
                    continue
                expiry_date = _parse_azure_datetime(reservation.get("expiryDate"))
                reservation_id = str(reservation.get("reservationId") or "").lower()
                rows.append(
                    {
                        "recordType": "reservation_inventory",
                        **reservation,
                        "incurredCost": round(costs_by_reservation[reservation_id], 6)
                        if reservation_id in costs_by_reservation
                        else None,
                        "remainingDays": (expiry_date - datetime.now(UTC)).days if expiry_date else None,
                    }
                )
            rows.sort(key=lambda row: (row.get("remainingDays") is None, row.get("remainingDays") or 0))
        except Exception as exc:
            warnings.append(f"Reservation inventory query failed: {exc}")

    if domain == ReportDomain.quota_summary:
        try:
            location_rows, audit = await client.query_resource_graph(
                request.subscription_ids,
                "Resources | where type startswith 'microsoft.compute/' "
                "| where isnotempty(location) | distinct subscriptionId, location",
            )
            source_audit.append(audit)
        except Exception as exc:
            location_rows = []
            warnings.append(f"Compute region discovery failed: {exc}")

        for location_row in location_rows:
            subscription_id = str(location_row.get("subscriptionId", ""))
            location = str(location_row.get("location", ""))
            if not subscription_id or not location:
                continue
            try:
                usage_rows, audit = await client.list_compute_usages(subscription_id, location)
                source_audit.append(audit)
                for usage in usage_rows:
                    limit = _safe_number(usage.get("limit"))
                    current = _safe_number(usage.get("currentValue"))
                    rows.append(
                        {
                            **usage,
                            "utilizationPercent": round((current / limit) * 100, 2) if limit > 0 else None,
                            "remaining": max(limit - current, 0) if limit > 0 else None,
                        }
                    )
            except Exception as exc:
                warnings.append(
                    f"Compute usage query skipped for subscription {subscription_id} in {location}: {exc}"
                )
        rows.sort(
            key=lambda row: (
                -_safe_number(row.get("utilizationPercent")),
                str(row.get("subscriptionId", "")),
                str(row.get("region", "")),
                str(row.get("quotaName", "")),
            )
        )

    if domain in {
        ReportDomain.governance,
        ReportDomain.tag_compliance,
        ReportDomain.anomaly_detection,
        ReportDomain.ai_finops,
        ReportDomain.sustainability,
    }:
        query = (
            "Resources | project subscriptionId, id, name, type, resourceGroup, location, tags"
        )
        try:
            resource_rows, audit = await client.query_resource_graph(request.subscription_ids, query)
            source_audit.append(audit)
            for item in resource_rows:
                rows.append(
                    {
                        "subscriptionId": item.get("subscriptionId", ""),
                        "resourceId": item.get("id", ""),
                        "resourceName": item.get("name", ""),
                        "resourceType": item.get("type", ""),
                        "resourceGroup": item.get("resourceGroup", ""),
                        "region": item.get("location", ""),
                        "tags": item.get("tags", {}),
                    }
                )
        except Exception as exc:
            warnings.append(f"Resource Graph query failed: {exc}")

    if domain in {
        ReportDomain.governance,
        ReportDomain.tag_compliance,
    }:
        try:
            policy_rows, policy_audit = await client.query_policy_compliance(request.subscription_ids)
            source_audit.append(policy_audit)
            for item in policy_rows:
                rows.append(
                    {
                        "subscriptionId": item.get("subscriptionId", ""),
                        "resourceId": item.get("resourceId", ""),
                        "policyAssignmentName": item.get("policyAssignmentName", ""),
                        "policyDefinitionName": item.get("policyDefinitionName", ""),
                        "complianceState": item.get("complianceState", ""),
                        "policyTimestamp": item.get("timestamp", ""),
                    }
                )
        except Exception as exc:
            warnings.append(f"Policy compliance query failed: {exc}")

    if domain in {ReportDomain.ai_finops, ReportDomain.ai_token_tracking}:
        for subscription_id in request.subscription_ids:
            try:
                ai_rows, ai_audit = await client.query_ai_token_tracking(
                    subscription_id,
                    start_date=request.filters.start_date,
                    end_date=request.filters.end_date,
                )
                source_audit.append(ai_audit)
                for entry in ai_rows:
                    if isinstance(entry, dict):
                        usage_quantity = entry.get("usageQuantity", entry.get("UsageQuantity"))
                        cost = entry.get("totalCost", entry.get("PreTaxCost"))
                        resource_id = entry.get("resourceId", entry.get("ResourceId", ""))
                        service_name = entry.get("serviceName", entry.get("ServiceName", ""))
                        meter_name = entry.get("meterName", entry.get("Meter", ""))
                    else:
                        usage_quantity = entry[0] if len(entry) > 0 else None
                        cost = entry[1] if len(entry) > 1 else None
                        resource_id = entry[2] if len(entry) > 2 else ""
                        service_name = entry[3] if len(entry) > 3 else ""
                        meter_name = entry[4] if len(entry) > 4 else ""
                    meter_text = str(meter_name or "")
                    estimated_token_units = usage_quantity if "token" in meter_text.lower() else None

                    ai_token_tracking.append(
                        {
                            "subscriptionId": subscription_id,
                            "serviceName": service_name,
                            "meterName": meter_name,
                            "usageQuantity": usage_quantity,
                            "estimatedTokenUnits": estimated_token_units,
                            "cost": cost,
                            "resourceId": resource_id,
                        }
                    )
            except Exception as exc:
                warnings.append(
                    f"AI token tracking skipped for subscription {subscription_id}: {exc}"
                )

    ai_token_summary = _build_ai_token_summary(ai_token_tracking)

    if domain == ReportDomain.ai_token_tracking:
        rows = list(ai_token_summary)

    enriched_rows, unresolved, enrichment_audit = enrich_rows_with_resource_metadata(rows)
    quality_score = score_data_quality(len(enriched_rows), unresolved)

    if request.strict_live_mode and enriched_rows and quality_score < 95:
        warnings.append(
            f"Strict-live threshold not met: data quality score {quality_score}% is below 95%. Results returned with caution."
        )

    if not enriched_rows and warnings:
        warnings.append(
            "No rows returned from accessible subscriptions. This is commonly caused by API-level permission gaps (e.g., Cost Management Reader needed for cost query endpoints)."
        )
    if not source_audit:
        warnings.append("No live Azure source call completed successfully; no report values were synthesized.")

    execution_ms = int((time.perf_counter() - start) * 1000)
    recommendation_rows = ai_token_tracking if domain == ReportDomain.ai_token_tracking else enriched_rows
    recommendations = _generate_recommendations(domain, recommendation_rows)

    return ReportResult(
        domain=domain,
        tenant_id=request.tenant_id,
        subscription_scope=request.subscription_ids,
        generated_at_utc=datetime.now(UTC),
        execution_time_ms=execution_ms,
        data_quality_score=quality_score,
        unresolved_fields_count=unresolved,
        live_data_confirmed=bool(source_audit),
        source_audit=source_audit,
        rows=enriched_rows,
        enrichment_audit=enrichment_audit,
        ai_token_tracking=ai_token_tracking,
        ai_token_summary=ai_token_summary,
        recommendations=recommendations,
        warnings=warnings,
    )


def _safe_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_value(row: dict[str, Any], *names: str) -> Any:
    lower_row = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lower_row:
            return lower_row[name.lower()]
    return None


def _normalize_cost_row(subscription_id: str, row: dict[str, Any]) -> dict[str, Any]:
    resource_id = str(_first_value(row, "ResourceId") or "")
    return {
        "subscriptionId": subscription_id,
        "usageDate": _first_value(row, "UsageDate", "Date"),
        "cost": _first_value(row, "cost", "PreTaxCost"),
        "usageQuantity": _first_value(row, "usageQuantity"),
        "resourceId": resource_id,
        "resourceName": resource_id.rstrip("/").rsplit("/", 1)[-1] if resource_id else "",
        "resourceGroup": _first_value(row, "ResourceGroup") or "",
        "serviceName": _first_value(row, "ServiceName") or "",
        "meterCategory": _first_value(row, "MeterCategory") or "",
        "meterSubCategory": _first_value(row, "MeterSubCategory", "MeterSubcategory") or "",
        "meterName": _first_value(row, "Meter", "MeterName") or "",
        "unitOfMeasure": _first_value(row, "UnitOfMeasure") or "",
        "chargeType": _first_value(row, "ChargeType") or "",
    }


def _aggregate_cost_rows(rows: list[dict[str, Any]], group_fields: list[str]) -> list[dict[str, Any]]:
    totals: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in group_fields)
        aggregate = totals.setdefault(
            key,
            {field: row.get(field) for field in group_fields}
            | {"cost": 0.0, "usageQuantity": 0.0, "recordCount": 0},
        )
        aggregate["cost"] += _safe_number(row.get("cost"))
        aggregate["usageQuantity"] += _safe_number(row.get("usageQuantity"))
        aggregate["recordCount"] += 1
    return sorted(
        (
            {
                **row,
                "cost": round(row["cost"], 6),
                "usageQuantity": round(row["usageQuantity"], 6),
            }
            for row in totals.values()
        ),
        key=lambda row: tuple(str(row.get(field, "")) for field in group_fields),
    )


def _parse_azure_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _build_ai_token_summary(ai_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ai_rows:
        return []

    aggregates: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "usageTotal": 0.0,
            "usageCount": 0.0,
            "tokenTotal": 0.0,
            "tokenCount": 0.0,
            "costTotal": 0.0,
            "costCount": 0.0,
            "recordCount": 0.0,
        }
    )

    for row in ai_rows:
        service_name = str(row.get("serviceName") or "Unknown AI Service")
        usage = _safe_number(row.get("usageQuantity"))
        token_units = row.get("estimatedTokenUnits")
        token_value = _safe_number(token_units) if token_units is not None else None
        cost = _safe_number(row.get("cost"))

        for key in (service_name, "All AI Services"):
            bucket = aggregates[key]
            bucket["usageTotal"] += usage
            bucket["usageCount"] += 1
            if token_value is not None:
                bucket["tokenTotal"] += token_value
                bucket["tokenCount"] += 1
            bucket["costTotal"] += cost
            bucket["costCount"] += 1
            bucket["recordCount"] += 1

    summary_rows: list[dict[str, Any]] = []
    for service_name, bucket in aggregates.items():
        usage_avg = bucket["usageTotal"] / bucket["usageCount"] if bucket["usageCount"] else 0.0
        token_avg = bucket["tokenTotal"] / bucket["tokenCount"] if bucket["tokenCount"] else 0.0
        cost_avg = bucket["costTotal"] / bucket["costCount"] if bucket["costCount"] else 0.0

        summary_rows.append(
            {
                "serviceScope": service_name,
                "records": int(bucket["recordCount"]),
                "totalUsageQuantity": round(bucket["usageTotal"], 6),
                "averageUsageQuantity": round(usage_avg, 6),
                "totalEstimatedTokenUnits": round(bucket["tokenTotal"], 6),
                "averageEstimatedTokenUnits": round(token_avg, 6),
                "totalCost": round(bucket["costTotal"], 6),
                "averageCost": round(cost_avg, 6),
            }
        )

    summary_rows.sort(key=lambda item: (item["serviceScope"] != "All AI Services", item["serviceScope"]))
    return summary_rows


def _generate_recommendations(domain: ReportDomain, rows: list[dict[str, Any]]) -> list[Recommendation]:
    if not rows:
        return [
            Recommendation(
                category=DOMAIN_RECOMMENDATION_CATEGORY[domain],
                impact_estimate="None",
                confidence="Low",
                affected_scope="Selected scope",
                suggested_action="No records returned. Validate permissions and filters.",
                evidence="Live query returned zero rows",
            )
        ]

    category = DOMAIN_RECOMMENDATION_CATEGORY[domain]
    impacted_count = len(rows)
    return [
        Recommendation(
            category=category,
            impact_estimate=f"{impacted_count} impacted resources",
            confidence="Medium",
            affected_scope="Selected subscriptions",
            suggested_action="Review top impacted resources and apply domain-specific remediation.",
            evidence="Derived from live Azure API response set",
        )
    ]
