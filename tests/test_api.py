import asyncio
from fastapi.testclient import TestClient
from datetime import UTC, datetime

from app.main import LAST_REPORT, app
from app.models import Recommendation, ReportDomain, ReportResult, SourceAudit
from app.services.reporting import build_report
from app.services.azure_live import AzureLiveClient


client = TestClient(app)


def test_list_domains_has_14_domains():
    response = client.get("/api/domains")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 16


def test_export_without_report_returns_404():
    response = client.get("/api/export/csv")
    assert response.status_code == 404


def test_export_with_report_returns_file():
    LAST_REPORT["report"] = ReportResult(
        domain=ReportDomain.ai_token_tracking,
        tenant_id="tenant-a",
        subscription_scope=["sub-a"],
        generated_at_utc=datetime.now(UTC),
        execution_time_ms=10,
        data_quality_score=100.0,
        unresolved_fields_count=0,
        live_data_confirmed=True,
        source_audit=[
            SourceAudit(
                source="Azure Cost Management",
                endpoint="https://management.azure.com/mock",
                duration_ms=10,
                row_count=1,
                executed_at_utc=datetime.now(UTC),
            )
        ],
        rows=[{"subscriptionId": "sub-a", "cost": 1.23, "resourceId": "/subscriptions/sub-a"}],
        enrichment_audit=[{"resolutionStatus": "resolved"}],
        ai_token_tracking=[{"serviceName": "Azure OpenAI", "usageQuantity": 100, "resourceId": "/subscriptions/sub-a"}],
        ai_token_summary=[{"serviceScope": "All AI Services", "records": 1, "totalUsageQuantity": 100, "averageUsageQuantity": 100, "totalEstimatedTokenUnits": 0, "averageEstimatedTokenUnits": 0, "totalCost": 1.23, "averageCost": 1.23}],
        recommendations=[
            Recommendation(
                category="AI workload efficiency",
                impact_estimate="1 impacted resources",
                confidence="Medium",
                affected_scope="Selected subscriptions",
                suggested_action="Review usage trends.",
                evidence="Live query returned one row",
            )
        ],
        warnings=[],
    )

    response = client.get("/api/export/csv")
    assert response.status_code == 200

    response = client.get("/api/export/pptx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.presentationml.presentation")
    assert "report" in LAST_REPORT


def test_exports_do_not_flush_cached_report():
    LAST_REPORT["report"] = ReportResult(
        domain=ReportDomain.ai_token_tracking,
        tenant_id="tenant-a",
        subscription_scope=["sub-a"],
        generated_at_utc=datetime.now(UTC),
        execution_time_ms=10,
        data_quality_score=100.0,
        unresolved_fields_count=0,
        live_data_confirmed=True,
        source_audit=[
            SourceAudit(
                source="Azure Cost Management",
                endpoint="https://management.azure.com/mock",
                duration_ms=10,
                row_count=1,
                executed_at_utc=datetime.now(UTC),
            )
        ],
        rows=[{"subscriptionId": "sub-a", "cost": 1.23, "resourceId": "/subscriptions/sub-a"}],
        enrichment_audit=[{"resolutionStatus": "resolved"}],
        ai_token_tracking=[{"serviceName": "Azure OpenAI", "usageQuantity": 100, "resourceId": "/subscriptions/sub-a"}],
        ai_token_summary=[{"serviceScope": "All AI Services", "records": 1, "totalUsageQuantity": 100, "averageUsageQuantity": 100, "totalEstimatedTokenUnits": 0, "averageEstimatedTokenUnits": 0, "totalCost": 1.23, "averageCost": 1.23}],
        recommendations=[
            Recommendation(
                category="AI workload efficiency",
                impact_estimate="1 impacted resources",
                confidence="Medium",
                affected_scope="Selected subscriptions",
                suggested_action="Review usage trends.",
                evidence="Live query returned one row",
            )
        ],
        warnings=[],
    )

    csv_response = client.get("/api/export/csv")
    assert csv_response.status_code == 200
    assert "report" in LAST_REPORT

    pdf_response = client.get("/api/export/pdf")
    assert pdf_response.status_code == 200
    assert "report" in LAST_REPORT

    pptx_response = client.get("/api/export/pptx")
    assert pptx_response.status_code == 200
    assert "report" in LAST_REPORT


def test_clear_auth_context_clears_cached_report():
    LAST_REPORT["report"] = ReportResult(
        domain=ReportDomain.ai_token_tracking,
        tenant_id="tenant-a",
        subscription_scope=["sub-a"],
        generated_at_utc=datetime.now(UTC),
        execution_time_ms=10,
        data_quality_score=100.0,
        unresolved_fields_count=0,
        live_data_confirmed=True,
        source_audit=[
            SourceAudit(
                source="Azure Cost Management",
                endpoint="https://management.azure.com/mock",
                duration_ms=10,
                row_count=1,
                executed_at_utc=datetime.now(UTC),
            )
        ],
        rows=[{"subscriptionId": "sub-a", "cost": 1.23, "resourceId": "/subscriptions/sub-a"}],
        enrichment_audit=[{"resolutionStatus": "resolved"}],
        ai_token_tracking=[],
        ai_token_summary=[],
        recommendations=[
            Recommendation(
                category="AI workload efficiency",
                impact_estimate="1 impacted resources",
                confidence="Medium",
                affected_scope="Selected subscriptions",
                suggested_action="Review usage trends.",
                evidence="Live query returned one row",
            )
        ],
        warnings=[],
    )

    clear_response = client.post("/api/auth/clear-context?clear_cli_session=false")
    assert clear_response.status_code == 200
    assert clear_response.json().get("status") == "cleared"
    assert "report" not in LAST_REPORT

    export_response = client.get("/api/export/csv")
    assert export_response.status_code == 404


def test_governance_report_includes_policy_compliance(monkeypatch):
    async def fake_query_resource_graph(self, subscription_ids, query):
        return [], SourceAudit(
            source="Azure Resource Graph",
            endpoint="https://management.azure.com/mock",
            duration_ms=1,
            row_count=0,
            executed_at_utc=datetime.now(UTC),
        )

    async def fake_query_policy_compliance(self, subscription_ids):
        return [
            {
                "subscriptionId": "sub-a",
                "resourceId": "/subscriptions/sub-a/providers/Microsoft.PolicyInsights/policystates/latest",
                "policyAssignmentName": "enforce-tags",
                "policyDefinitionName": "require-tags",
                "complianceState": "NonCompliant",
                "timestamp": "2026-07-24T00:00:00Z",
            }
        ], SourceAudit(
            source="Azure Policy Compliance",
            endpoint="https://management.azure.com/mock-policy",
            duration_ms=2,
            row_count=1,
            executed_at_utc=datetime.now(UTC),
        )

    monkeypatch.setattr(AzureLiveClient, "query_resource_graph", fake_query_resource_graph)
    monkeypatch.setattr(AzureLiveClient, "query_policy_compliance", fake_query_policy_compliance)

    report = asyncio.run(
        build_report(
            ReportDomain.governance,
            __import__("app.models", fromlist=["ReportRequest"]).ReportRequest(
                tenant_id="tenant-a",
                subscription_ids=["sub-a"],
                strict_live_mode=False,
            ),
            bearer_token="token",
        )
    )

    assert report.rows
    assert any(row.get("complianceState") == "NonCompliant" for row in report.rows)


def test_savings_potential_report_uses_advisor_data(monkeypatch):
    async def fake_list_advisor_recommendations(self, subscription_id):
        return [
            {
                "properties": {
                    "category": "Cost",
                    "impact": "Medium",
                    "shortDescription": {
                        "problem": "Right-size underutilized VM",
                        "solution": "Reduce SKU or shut down when idle",
                    },
                    "extendedProperties": {"annualSavingsAmount": 125.5},
                    "resourceMetadata": {"resourceId": "/subscriptions/sub-a/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"},
                }
            },
            {
                "properties": {
                    "category": "Cost",
                    "impact": "Low",
                    "shortDescription": {
                        "problem": "Purchase reservation for steady workload",
                        "solution": "Use a 1-year reservation",
                    },
                    "extendedProperties": {"annualSavingsAmount": 40.0},
                    "resourceMetadata": {"resourceId": "/subscriptions/sub-a/resourceGroups/rg/providers/Microsoft.Sql/servers/sql1"},
                }
            },
        ], SourceAudit(
            source="Azure Advisor",
            endpoint="https://management.azure.com/mock-advisor",
            duration_ms=2,
            row_count=2,
            executed_at_utc=datetime.now(UTC),
        )

    async def fake_query_ai_token_tracking(self, subscription_id, timeframe="MonthToDate"):
        return [], SourceAudit(
            source="Azure Cost Management (AI Token Tracking)",
            endpoint="https://management.azure.com/mock-ai",
            duration_ms=1,
            row_count=0,
            executed_at_utc=datetime.now(UTC),
        )

    monkeypatch.setattr(AzureLiveClient, "list_advisor_recommendations", fake_list_advisor_recommendations)
    monkeypatch.setattr(AzureLiveClient, "query_ai_token_tracking", fake_query_ai_token_tracking)

    report = asyncio.run(
        build_report(
            ReportDomain.savings_potential,
            __import__("app.models", fromlist=["ReportRequest"]).ReportRequest(
                tenant_id="tenant-a",
                subscription_ids=["sub-a"],
                strict_live_mode=False,
            ),
            bearer_token="token",
        )
    )

    assert report.rows
    assert all("saving" in str(row.get("recommendationType", "")).lower() or "cost" in str(row.get("category", "")).lower() for row in report.rows)
    assert any(row.get("savingsEstimate") == 125.5 for row in report.rows)


def test_reservations_potential_report_uses_advisor_data(monkeypatch):
    async def fake_list_advisor_recommendations(self, subscription_id):
        return [
            {
                "properties": {
                    "category": "Cost",
                    "impact": "High",
                    "shortDescription": {
                        "problem": "Purchase reservation for steady SQL workload",
                        "solution": "Use a 1-year reservation",
                    },
                    "extendedProperties": {"annualSavingsAmount": 99.0},
                    "resourceMetadata": {"resourceId": "/subscriptions/sub-a/resourceGroups/rg/providers/Microsoft.Sql/servers/sql1"},
                }
            },
            {
                "properties": {
                    "category": "Cost",
                    "impact": "Low",
                    "shortDescription": {
                        "problem": "Reduce app service scale out",
                        "solution": "Right-size the instance",
                    },
                    "extendedProperties": {"annualSavingsAmount": 12.0},
                    "resourceMetadata": {"resourceId": "/subscriptions/sub-a/resourceGroups/rg/providers/Microsoft.Web/sites/app1"},
                }
            },
        ], SourceAudit(
            source="Azure Advisor",
            endpoint="https://management.azure.com/mock-advisor",
            duration_ms=2,
            row_count=2,
            executed_at_utc=datetime.now(UTC),
        )

    async def fake_query_ai_token_tracking(self, subscription_id, timeframe="MonthToDate"):
        return [], SourceAudit(
            source="Azure Cost Management (AI Token Tracking)",
            endpoint="https://management.azure.com/mock-ai",
            duration_ms=1,
            row_count=0,
            executed_at_utc=datetime.now(UTC),
        )

    monkeypatch.setattr(AzureLiveClient, "list_advisor_recommendations", fake_list_advisor_recommendations)
    monkeypatch.setattr(AzureLiveClient, "query_ai_token_tracking", fake_query_ai_token_tracking)

    report = asyncio.run(
        build_report(
            ReportDomain.reservations_potential,
            __import__("app.models", fromlist=["ReportRequest"]).ReportRequest(
                tenant_id="tenant-a",
                subscription_ids=["sub-a"],
                strict_live_mode=False,
            ),
            bearer_token="token",
        )
    )

    assert report.rows
    assert any("reservation" in str(row.get("recommendationType", "")).lower() for row in report.rows)
    assert any(row.get("savingsEstimate") == 99.0 for row in report.rows)


def test_ai_token_tracking_uses_filter_dates_and_dict_rows(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_query_ai_token_tracking(self, subscription_id, timeframe="MonthToDate", start_date=None, end_date=None):
        captured["subscription_id"] = subscription_id
        captured["start_date"] = start_date
        captured["end_date"] = end_date
        return [
            {
                "UsageQuantity": 250,
                "totalCost": 3.5,
                "ResourceId": "/subscriptions/sub-a/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/aoai1",
                "ServiceName": "Azure OpenAI",
                "Meter": "InputToken",
            }
        ], SourceAudit(
            source="Azure Cost Management (AI Token Tracking)",
            endpoint="https://management.azure.com/mock-ai",
            duration_ms=1,
            row_count=1,
            executed_at_utc=datetime.now(UTC),
        )

    async def fake_query_resource_graph(self, subscription_ids, query):
        return [], SourceAudit(
            source="Azure Resource Graph",
            endpoint="https://management.azure.com/mock-rg",
            duration_ms=1,
            row_count=0,
            executed_at_utc=datetime.now(UTC),
        )

    monkeypatch.setattr(AzureLiveClient, "query_ai_token_tracking", fake_query_ai_token_tracking)
    monkeypatch.setattr(AzureLiveClient, "query_resource_graph", fake_query_resource_graph)

    report = asyncio.run(
        build_report(
            ReportDomain.ai_token_tracking,
            __import__("app.models", fromlist=["ReportRequest", "FilterSet"]).ReportRequest(
                tenant_id="tenant-a",
                subscription_ids=["sub-a"],
                strict_live_mode=False,
                filters=__import__("app.models", fromlist=["FilterSet"]).FilterSet(
                    start_date="2026-01-01",
                    end_date="2026-07-24",
                ),
            ),
            bearer_token="token",
        )
    )

    assert captured["subscription_id"] == "sub-a"
    assert captured["start_date"] == "2026-01-01"
    assert captured["end_date"] == "2026-07-24"
    assert report.ai_token_tracking
    assert report.ai_token_tracking[0]["serviceName"] == "Azure OpenAI"
    assert report.ai_token_tracking[0]["usageQuantity"] == 250
