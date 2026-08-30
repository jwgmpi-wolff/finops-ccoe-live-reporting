from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
import re
from typing import Any

import httpx

from app.models import SourceAudit

ARM_API = "https://management.azure.com"
GRAPH_API = "https://graph.microsoft.com/v1.0"


class AzureLiveClient:
    def __init__(self, bearer_token: str):
        self._headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

    async def list_tenants(self) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = f"{ARM_API}/tenants?api-version=2022-12-01"
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            payload = response.json().get("value", [])
        elapsed = int((time.perf_counter() - start) * 1000)
        return payload, SourceAudit(
            source="Azure Resource Manager",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(payload),
            executed_at_utc=datetime.now(UTC),
        )

    async def list_subscriptions(self) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = f"{ARM_API}/subscriptions?api-version=2022-12-01"
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            payload = response.json().get("value", [])
        elapsed = int((time.perf_counter() - start) * 1000)
        return payload, SourceAudit(
            source="Azure Resource Manager",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(payload),
            executed_at_utc=datetime.now(UTC),
        )

    async def query_resource_graph(self, subscription_ids: list[str], query: str) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = f"{ARM_API}/providers/Microsoft.ResourceGraph/resources?api-version=2024-04-01"
        body = {"subscriptions": subscription_ids, "query": query}
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, headers=self._headers, json=body)
            response.raise_for_status()
            payload = response.json().get("data", [])
        elapsed = int((time.perf_counter() - start) * 1000)
        return payload, SourceAudit(
            source="Azure Resource Graph",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(payload),
            executed_at_utc=datetime.now(UTC),
        )

    async def query_policy_compliance(self, subscription_ids: list[str]) -> tuple[list[dict[str, Any]], SourceAudit]:
        query = (
            "policyresources "
            "| where type =~ 'microsoft.policyinsights/policystates' "
            "| project subscriptionId, resourceId = tostring(properties.resourceId), "
            "policyAssignmentName = tostring(properties.policyAssignmentName), "
            "policyDefinitionName = tostring(properties.policyDefinitionName), "
            "complianceState = tostring(properties.complianceState), "
            "timestamp = tostring(properties.timestamp)"
        )
        rows, audit = await self.query_resource_graph(subscription_ids, query)
        return rows, SourceAudit(
            source="Azure Policy Compliance",
            endpoint=audit.endpoint,
            duration_ms=audit.duration_ms,
            row_count=audit.row_count,
            executed_at_utc=audit.executed_at_utc,
        )

    async def list_advisor_recommendations(self, subscription_id: str) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = (
            f"{ARM_API}/subscriptions/{subscription_id}/providers/Microsoft.Advisor/recommendations"
            "?api-version=2023-01-01"
        )
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            payload = response.json().get("value", [])
        elapsed = int((time.perf_counter() - start) * 1000)
        return payload, SourceAudit(
            source="Azure Advisor",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(payload),
            executed_at_utc=datetime.now(UTC),
        )

    async def query_cost_management(self, subscription_id: str, timeframe: str = "MonthToDate") -> tuple[list[dict[str, Any]], SourceAudit]:
        url = (
            f"{ARM_API}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
            "?api-version=2023-03-01"
        )
        body = {
            "type": "ActualCost",
            "timeframe": timeframe,
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {"name": "PreTaxCost", "function": "Sum"},
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ResourceGroup"},
                    {"type": "Dimension", "name": "ServiceName"},
                ],
            },
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=self._headers, json=body)
            response.raise_for_status()
            rows = response.json().get("properties", {}).get("rows", [])
        elapsed = int((time.perf_counter() - start) * 1000)
        return rows, SourceAudit(
            source="Azure Cost Management",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(rows),
            executed_at_utc=datetime.now(UTC),
        )

    async def query_cost_details(
        self,
        subscription_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = (
            f"{ARM_API}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
            "?api-version=2023-03-01"
        )
        body: dict[str, Any] = {
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "cost": {"name": "PreTaxCost", "function": "Sum"},
                    "usageQuantity": {"name": "UsageQuantity", "function": "Sum"},
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ResourceGroup"},
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "MeterCategory"},
                    {"type": "Dimension", "name": "ChargeType"},
                ],
            },
        }
        if start_date and end_date:
            body["timeframe"] = "Custom"
            body["timePeriod"] = {
                "from": f"{start_date}T00:00:00Z",
                "to": f"{end_date}T23:59:59Z",
            }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=self._headers, json=body)
            response.raise_for_status()
            properties = response.json().get("properties", {})

        column_names = [
            str(column.get("name") or f"column{index}")
            for index, column in enumerate(properties.get("columns", []))
        ]
        rows = [
            dict(zip(column_names, row, strict=False))
            for row in properties.get("rows", [])
            if isinstance(row, list)
        ]
        elapsed = int((time.perf_counter() - start) * 1000)
        return rows, SourceAudit(
            source="Azure Cost Management",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(rows),
            executed_at_utc=datetime.now(UTC),
        )

    async def query_reservation_costs(
        self,
        subscription_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = (
            f"{ARM_API}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
            "?api-version=2023-03-01"
        )
        body: dict[str, Any] = {
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"cost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ReservationId"},
                    {"type": "Dimension", "name": "ReservationName"},
                    {"type": "Dimension", "name": "ChargeType"},
                    {"type": "Dimension", "name": "MeterCategory"},
                ],
            },
        }
        if start_date and end_date:
            body["timeframe"] = "Custom"
            body["timePeriod"] = {
                "from": f"{start_date}T00:00:00Z",
                "to": f"{end_date}T23:59:59Z",
            }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=self._headers, json=body)
            response.raise_for_status()
            properties = response.json().get("properties", {})
        column_names = [
            str(column.get("name") or f"column{index}")
            for index, column in enumerate(properties.get("columns", []))
        ]
        parsed_rows = [
            dict(zip(column_names, row, strict=False))
            for row in properties.get("rows", [])
            if isinstance(row, list)
        ]
        rows = [
            {
                "recordType": "reservation_cost",
                "subscriptionId": subscription_id,
                "usageDate": _case_insensitive_value(row, "UsageDate", "Date"),
                "reservationId": _case_insensitive_value(row, "ReservationId") or "",
                "reservationName": _case_insensitive_value(row, "ReservationName") or "",
                "chargeType": _case_insensitive_value(row, "ChargeType") or "",
                "meterCategory": _case_insensitive_value(row, "MeterCategory") or "",
                "cost": _case_insensitive_value(row, "cost", "PreTaxCost"),
            }
            for row in parsed_rows
            if _case_insensitive_value(row, "ReservationId", "ReservationName")
        ]
        elapsed = int((time.perf_counter() - start) * 1000)
        return rows, SourceAudit(
            source="Azure Cost Management (Reservations)",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(rows),
            executed_at_utc=datetime.now(UTC),
        )

    async def list_reservations(self) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = f"{ARM_API}/providers/Microsoft.Capacity/reservationOrders?api-version=2022-11-01"
        start = time.perf_counter()
        reservations: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            orders = response.json().get("value", [])
            for order in orders:
                order_id = str(order.get("id", "")).rstrip("/")
                if not order_id:
                    continue
                reservation_url = f"{ARM_API}{order_id}/reservations?api-version=2022-11-01"
                reservation_response = await client.get(reservation_url, headers=self._headers)
                reservation_response.raise_for_status()
                for reservation in reservation_response.json().get("value", []):
                    properties = reservation.get("properties", {})
                    reservations.append(
                        {
                            "reservationOrderId": order_id.rsplit("/", 1)[-1],
                            "reservationId": reservation.get("name", ""),
                            "displayName": properties.get("displayName", ""),
                            "provisioningState": properties.get("provisioningState", ""),
                            "reservedResourceType": properties.get("reservedResourceType", ""),
                            "quantity": properties.get("quantity"),
                            "term": properties.get("term", ""),
                            "purchaseDate": properties.get("purchaseDate", ""),
                            "expiryDate": properties.get("expiryDate", ""),
                            "appliedScopeType": properties.get("appliedScopeType", ""),
                            "appliedScopes": properties.get("appliedScopes", []),
                        }
                    )
        elapsed = int((time.perf_counter() - start) * 1000)
        return reservations, SourceAudit(
            source="Azure Reservations",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(reservations),
            executed_at_utc=datetime.now(UTC),
        )

    async def list_compute_usages(
        self,
        subscription_id: str,
        location: str,
    ) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = (
            f"{ARM_API}/subscriptions/{subscription_id}/providers/Microsoft.Compute/"
            f"locations/{location}/usages?api-version=2024-07-01"
        )
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            usages = response.json().get("value", [])
        rows = [
            {
                "subscriptionId": subscription_id,
                "region": location,
                "quotaName": item.get("name", {}).get("localizedValue")
                or item.get("name", {}).get("value", ""),
                "currentValue": item.get("currentValue"),
                "limit": item.get("limit"),
                "unit": item.get("unit", ""),
            }
            for item in usages
        ]
        elapsed = int((time.perf_counter() - start) * 1000)
        return rows, SourceAudit(
            source="Azure Compute Usage",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(rows),
            executed_at_utc=datetime.now(UTC),
        )

    async def query_ai_token_tracking(
        self,
        subscription_id: str,
        timeframe: str = "MonthToDate",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[dict[str, Any]], SourceAudit]:
        url = (
            f"{ARM_API}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
            "?api-version=2023-03-01"
        )

        resolved_timeframe = timeframe
        body: dict[str, Any] = {
            "type": "ActualCost",
            "timeframe": resolved_timeframe,
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "usageQuantity": {"name": "UsageQuantity", "function": "Sum"},
                    "totalCost": {"name": "PreTaxCost", "function": "Sum"},
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "Meter"},
                ],
            },
        }

        if start_date and end_date:
            resolved_timeframe = "Custom"
            body["timeframe"] = resolved_timeframe
            body["timePeriod"] = {
                "from": f"{start_date}T00:00:00Z",
                "to": f"{end_date}T23:59:59Z",
            }

        ai_service_pattern = re.compile(
            r"(openai|ai foundry|ai services|cognitive|machine learning|azureml)",
            re.IGNORECASE,
        )
        ai_meter_pattern = re.compile(
            r"(token|prompt|completion|embedding|reasoning|cache\s*read|cache\s*write|audio\s*output)",
            re.IGNORECASE,
        )

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            last_exc: Exception | None = None
            properties: dict[str, Any] = {}
            rows: list[Any] = []
            columns: list[dict[str, Any]] = []
            for attempt in range(4):
                try:
                    response = await client.post(url, headers=self._headers, json=body)
                    response.raise_for_status()
                    properties = response.json().get("properties", {})
                    rows = properties.get("rows", [])
                    columns = properties.get("columns", [])
                    last_exc = None
                    break
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    if status == 429 and attempt < 3:
                        retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                        try:
                            delay = float(retry_after) if retry_after else 1.0 + attempt
                        except ValueError:
                            delay = 1.0 + attempt
                        await asyncio.sleep(max(delay, 0.5))
                        last_exc = exc
                        continue
                    raise
                except Exception as exc:
                    last_exc = exc
                    raise
            if last_exc is not None:
                raise last_exc

        column_names = [str(col.get("name", "")).strip() for col in columns]
        parsed_rows: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                parsed_rows.append(row)
                continue
            if not isinstance(row, list):
                continue
            item: dict[str, Any] = {}
            for idx, value in enumerate(row):
                key = column_names[idx] if idx < len(column_names) and column_names[idx] else f"col_{idx}"
                item[key] = value
            parsed_rows.append(item)

        def looks_like_ai_token_usage(item: dict[str, Any]) -> bool:
            service_name = str(item.get("ServiceName") or item.get("serviceName") or "")
            meter_name = str(item.get("Meter") or item.get("meterName") or "")
            resource_id = str(item.get("ResourceId") or item.get("resourceId") or "")
            signal = " ".join([service_name, meter_name, resource_id])
            return bool(ai_service_pattern.search(signal) or ai_meter_pattern.search(signal))

        filtered_rows = [item for item in parsed_rows if looks_like_ai_token_usage(item)]
        elapsed = int((time.perf_counter() - start) * 1000)
        return filtered_rows, SourceAudit(
            source="Azure Cost Management (AI Token Tracking)",
            endpoint=url,
            duration_ms=elapsed,
            row_count=len(filtered_rows),
            executed_at_utc=datetime.now(UTC),
        )

    async def resolve_principal_name(self, object_id: str) -> str | None:
        url = f"{GRAPH_API}/directoryObjects/{object_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._headers)
            if response.status_code >= 400:
                return None
            data = response.json()
        return data.get("displayName") or data.get("userPrincipalName")


def _case_insensitive_value(row: dict[str, Any], *names: str) -> Any:
    normalized = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in normalized:
            return normalized[name.lower()]
    return None
