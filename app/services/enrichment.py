from __future__ import annotations

from typing import Any


def parse_resource_id(resource_id: str) -> dict[str, str]:
    parts = [p for p in resource_id.split("/") if p]
    out = {
        "subscriptionId": "",
        "resourceGroup": "",
        "provider": "",
        "resourceType": "",
        "resourceName": "",
    }
    if len(parts) < 2:
        return out
    for idx, value in enumerate(parts):
        key = value.lower()
        if key == "subscriptions" and idx + 1 < len(parts):
            out["subscriptionId"] = parts[idx + 1]
        elif key == "resourcegroups" and idx + 1 < len(parts):
            out["resourceGroup"] = parts[idx + 1]
        elif key == "providers" and idx + 2 < len(parts):
            out["provider"] = parts[idx + 1]
            out["resourceType"] = parts[idx + 2]
            out["resourceName"] = parts[-1]
    return out


def enrich_rows_with_resource_metadata(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    unresolved_fields = 0
    enriched: list[dict[str, Any]] = []
    enrichment_audit: list[dict[str, Any]] = []

    for row in rows:
        next_row = dict(row)
        resource_id = str(row.get("resourceId", ""))
        unresolved_for_row: list[str] = []
        parsed = {
            "subscriptionId": "",
            "resourceGroup": "",
            "provider": "",
            "resourceType": "",
            "resourceName": "",
        }

        if resource_id:
            parsed = parse_resource_id(resource_id)
            next_row.update(
                {
                    "resourceSubscriptionId": parsed["subscriptionId"],
                    "resourceGroup": next_row.get("resourceGroup") or parsed["resourceGroup"],
                    "resourceProvider": parsed["provider"],
                    "resourceType": next_row.get("resourceType") or parsed["resourceType"],
                    "resourceName": next_row.get("resourceName") or parsed["resourceName"],
                }
            )
            if not next_row.get("resourceName"):
                unresolved_fields += 1
                unresolved_for_row.append("resourceName")
        else:
            unresolved_fields += 1
            unresolved_for_row.append("resourceId")

        fields_to_check = ["resourceName", "resourceType", "resourceGroup"]
        for key in fields_to_check:
            if not next_row.get(key):
                unresolved_fields += 1
                if key not in unresolved_for_row:
                    unresolved_for_row.append(key)

        enriched.append(next_row)

        enrichment_audit.append(
            {
                "sourceResourceId": resource_id,
                "resolvedResourceName": next_row.get("resourceName", ""),
                "resolvedResourceType": next_row.get("resourceType", ""),
                "resolvedResourceGroup": next_row.get("resourceGroup", ""),
                "resolvedSubscriptionId": next_row.get("resourceSubscriptionId", ""),
                "provider": parsed.get("provider", ""),
                "unresolvedFields": unresolved_for_row,
                "resolutionStatus": "resolved" if not unresolved_for_row else "partial",
            }
        )

    return enriched, unresolved_fields, enrichment_audit


def score_data_quality(total_rows: int, unresolved_fields: int) -> float:
    if total_rows == 0:
        return 0.0
    expected_fields = total_rows * 3
    resolved = max(expected_fields - unresolved_fields, 0)
    return round((resolved / expected_fields) * 100, 2)
