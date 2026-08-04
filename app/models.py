from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReportDomain(str, Enum):
    spend_visibility = "spend_visibility"
    budget_forecasting = "budget_forecasting"
    optimization = "optimization"
    reservations = "reservations"
    savings_plans = "savings_plans"
    savings_potential = "savings_potential"
    reservations_potential = "reservations_potential"
    anomaly_detection = "anomaly_detection"
    governance = "governance"
    tag_compliance = "tag_compliance"
    chargeback_showback = "chargeback_showback"
    architecture_efficiency = "architecture_efficiency"
    sustainability = "sustainability"
    ai_finops = "ai_finops"
    ai_token_tracking = "ai_token_tracking"
    idle_waste_detection = "idle_waste_detection"


class FilterSet(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    management_group: str | None = None
    resource_group: str | None = None
    resource_type: str | None = None
    region: str | None = None
    tag_key: str | None = None
    tag_value: str | None = None
    environment: str | None = None
    cost_center: str | None = None
    severity: str | None = None
    actionable_only: bool = False


class ReportRequest(BaseModel):
    tenant_id: str
    subscription_ids: list[str] = Field(default_factory=list)
    filters: FilterSet = Field(default_factory=FilterSet)
    strict_live_mode: bool = True


class AgentReportRequest(ReportRequest):
    max_rows: int = Field(default=25, ge=1, le=100)


class SourceAudit(BaseModel):
    source: str
    endpoint: str
    duration_ms: int
    row_count: int
    executed_at_utc: datetime


class Recommendation(BaseModel):
    category: str
    impact_estimate: str
    confidence: str
    affected_scope: str
    suggested_action: str
    evidence: str


class ReportResult(BaseModel):
    domain: ReportDomain
    tenant_id: str
    subscription_scope: list[str]
    generated_at_utc: datetime
    execution_time_ms: int
    data_quality_score: float
    unresolved_fields_count: int
    live_data_confirmed: bool
    source_audit: list[SourceAudit]
    rows: list[dict[str, Any]]
    enrichment_audit: list[dict[str, Any]] = Field(default_factory=list)
    ai_token_tracking: list[dict[str, Any]] = Field(default_factory=list)
    ai_token_summary: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[Recommendation]
    warnings: list[str] = Field(default_factory=list)


class AgentReportResponse(BaseModel):
    domain: ReportDomain
    tenant_id: str
    subscription_scope: list[str]
    generated_at_utc: datetime
    execution_time_ms: int
    live_data_confirmed: bool
    data_quality_score: float
    unresolved_fields_count: int
    total_row_count: int
    returned_row_count: int
    result_truncated: bool
    source_audit: list[SourceAudit]
    rows: list[dict[str, Any]]
    recommendations: list[Recommendation]
    warnings: list[str] = Field(default_factory=list)
