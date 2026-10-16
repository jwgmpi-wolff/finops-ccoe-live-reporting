from __future__ import annotations

import asyncio
import os
import re
import subprocess
from shutil import which
from pathlib import Path as FsPath
import sys
import threading
import tempfile
from typing import TextIO

from fastapi import FastAPI, Header, HTTPException, Path as ApiPath, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import settings
from app.models import AgentReportRequest, AgentReportResponse, ReportDomain, ReportRequest
from app.services.azure_live import AzureLiveClient
from app.services.exporters import export_csv, export_pdf, export_pptx, export_sqlite
from app.services.reporting import build_report

APP_VERSION = os.getenv("FINOPS_APP_VERSION", "1.2.3")
app = FastAPI(title=settings.app_name, version=APP_VERSION)

APP_ROOT = FsPath(getattr(sys, "_MEIPASS", FsPath(__file__).resolve().parents[1]))
templates = Jinja2Templates(directory=str(APP_ROOT / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "app" / "static")), name="static")

EXPORT_MAP = {
    "csv": export_csv,
    "pdf": export_pdf,
    "pptx": export_pptx,
    "sqlite": export_sqlite,
}

EXPORT_MEDIA_TYPES = {
    "csv": "text/csv",
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "sqlite": "application/x-sqlite3",
}

LAST_REPORT: dict[str, object] = {}
EXPORT_LOCKS = {format_type: asyncio.Lock() for format_type in EXPORT_MAP}
CLI_LOGIN_PROCESS: subprocess.Popen[str] | None = None
CLI_LOGIN_LOCK = threading.Lock()
CLI_LOGIN_OUTPUT: TextIO | None = None


class ScopeOptionsRequest(BaseModel):
    subscription_ids: list[str] = Field(default_factory=list)


def _resolve_az_command() -> str:
    az_cmd = which("az") or which("az.cmd")
    if not az_cmd:
        fallback = FsPath("C:/Program Files/Microsoft SDKs/Azure/CLI2/wbin/az.cmd")
        if fallback.exists():
            az_cmd = str(fallback)

    if not az_cmd:
        raise HTTPException(
            status_code=502,
            detail="Azure CLI not found. Install Azure CLI and restart this app before retrying Sign In. Administrators can alternatively configure browser OAuth.",
        )
    return az_cmd


def _wrap_windows_cmd(az_cmd: str, args: list[str]) -> list[str]:
    command = [az_cmd, *args]
    if az_cmd.lower().endswith(".cmd"):
        return ["cmd", "/c", *command]
    return command


def _azure_cli_process_options() -> dict[str, object]:
    options: dict[str, object] = {}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return options


def _azure_cli_login_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["AZURE_CORE_ENABLE_BROKER_ON_WINDOWS"] = "false"
    environment["AZURE_CORE_LOGIN_EXPERIENCE_V2"] = "off"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _close_cli_login_output() -> None:
    global CLI_LOGIN_OUTPUT
    if CLI_LOGIN_OUTPUT is not None:
        output_path = FsPath(CLI_LOGIN_OUTPUT.name)
        CLI_LOGIN_OUTPUT.close()
        CLI_LOGIN_OUTPUT = None
        output_path.unlink(missing_ok=True)


def _stop_cli_login_process() -> None:
    global CLI_LOGIN_PROCESS
    with CLI_LOGIN_LOCK:
        process = CLI_LOGIN_PROCESS
        CLI_LOGIN_PROCESS = None
        if process is not None and process.poll() is None and sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                **_azure_cli_process_options(),
            )
        elif process is not None and process.poll() is None:
            process.terminate()
        if process is not None:
            process.wait(timeout=10)
        _close_cli_login_output()


app.add_event_handler("shutdown", _stop_cli_login_process)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "entra_client_id": settings.entra_client_id,
            "entra_authority": settings.entra_authority,
            "entra_redirect_uri": settings.entra_redirect_uri,
        },
    )


@app.get("/api/run_finops_report", response_class=HTMLResponse)
async def run_finops_report(
    request: Request,
    format: str = Query(default="html", pattern="^html$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=500),
):
    del format, page, page_size
    return await index(request)


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy():
    return HTMLResponse(
        "<h1>FinOps CCoE Agent Privacy</h1>"
        "<p>The service processes Azure resource and cost data only for the signed-in user and "
        "only within subscriptions that user can access. It does not sell personal data or use "
        "report data to train models. Azure and Microsoft 365 administrators control access, "
        "retention, and audit policy.</p>"
    )


@app.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_of_use():
    return HTMLResponse(
        "<h1>FinOps CCoE Agent Terms</h1>"
        "<p>This agent provides informational FinOps analysis from live Azure APIs. Recommendations "
        "must be reviewed by an authorized operator before changing resources or commitments. The "
        "service is provided without a guarantee of savings or completeness.</p>"
    )


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name, "version": APP_VERSION}


@app.get("/api/auth/cli-token")
async def get_cli_token():
    az_cmd = _resolve_az_command()
    command = _wrap_windows_cmd(az_cmd, [
        "account",
        "get-access-token",
        "--resource",
        "https://management.azure.com/",
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ])

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            **_azure_cli_process_options(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=502,
            detail="Azure CLI not found. Install Azure CLI or use Entra sign-in.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="Timed out getting token from Azure CLI. Confirm 'az account show' works and retry.",
        ) from exc

    if proc.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to get Azure CLI token. Run 'az login' and try again. "
                f"CLI error: {proc.stderr.strip()}"
            ),
        )

    token = proc.stdout.strip()
    if not token:
        raise HTTPException(status_code=502, detail="Azure CLI returned an empty token.")

    return {"access_token": token, "source": "azure_cli"}


@app.post("/api/auth/cli-login")
async def cli_login(
    tenant_id: str = Query(default="organizations", pattern=r"^[a-zA-Z0-9.-]+$"),
    force_reauth: bool = False,
    use_device_code: bool = False,
):
    az_cmd = _resolve_az_command()

    login_args = ["login", "--allow-no-subscriptions"]
    # Let Azure CLI choose its neutral authority rather than treating it as a tenant ID.
    if tenant_id.lower() not in {"organizations", "common"}:
        login_args.extend(["--tenant", tenant_id])
    login_args.extend(["--output", "none"])
    if use_device_code:
        login_args.append("--use-device-code")

    command = _wrap_windows_cmd(az_cmd, login_args)

    global CLI_LOGIN_PROCESS, CLI_LOGIN_OUTPUT
    with CLI_LOGIN_LOCK:
        if CLI_LOGIN_PROCESS is not None and CLI_LOGIN_PROCESS.poll() is None:
            return {
                "status": "already_started",
                "message": "Microsoft browser sign-in is already in progress.",
            }

        if force_reauth:
            try:
                for args in (["logout"], ["account", "clear"]):
                    result = subprocess.run(
                        _wrap_windows_cmd(az_cmd, args),
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                        **_azure_cli_process_options(),
                    )
                    already_signed_out = (
                        args == ["logout"]
                        and result.stderr.strip() == "ERROR: There are no active accounts."
                    )
                    if result.returncode != 0 and not already_signed_out:
                        raise HTTPException(status_code=502, detail=f"Could not reset Azure CLI session: {result.stderr.strip()}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise HTTPException(status_code=502, detail=f"Could not reset Azure CLI session: {exc}") from exc

        _close_cli_login_output()
        CLI_LOGIN_OUTPUT = tempfile.NamedTemporaryFile(mode="w+t", encoding="utf-8", delete=False)

        try:
            CLI_LOGIN_PROCESS = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=CLI_LOGIN_OUTPUT,
                stderr=subprocess.STDOUT,
                text=True,
                env=_azure_cli_login_environment(),
                **_azure_cli_process_options(),
            )
        except OSError as exc:
            _close_cli_login_output()
            raise HTTPException(
                status_code=502,
                detail=f"Failed to initiate Microsoft login: {exc}",
            ) from exc

    return {
        "status": "started",
        "message": (
            "Waiting for a device sign-in code. Open the verification link and sign in with your organization's Azure account."
            if use_device_code else
            "Microsoft sign-in is opening in your default browser. Complete your organization's account and MFA prompts there. If no window opens, retry with Device code fallback."
        ),
    }


@app.get("/api/auth/cli-login-status")
async def cli_login_status():
    with CLI_LOGIN_LOCK:
        if CLI_LOGIN_PROCESS is None:
            return {"status": "not_started"}
        return_code = CLI_LOGIN_PROCESS.poll()
        output = ""
        if CLI_LOGIN_OUTPUT is not None:
            output = FsPath(CLI_LOGIN_OUTPUT.name).read_text(encoding="utf-8", errors="replace")
        if return_code is not None:
            if return_code != 0:
                raise HTTPException(
                    status_code=502,
                    detail=output.strip()[-4000:] or f"Azure CLI sign-in exited with code {return_code}.",
                )
            return {"status": "completed"}
        code = re.search(r"\bcode\s+([A-Z0-9-]{6,})\b", output)
        return {
            "status": "pending",
            "user_code": code.group(1) if code else None,
            "verification_uri": "https://microsoft.com/devicelogin" if code else None,
        }


@app.post("/api/auth/clear-context")
async def clear_auth_context(clear_cli_session: bool = False):
    cleared = {"report_cache": False, "cli_session": False}

    _stop_cli_login_process()

    if "report" in LAST_REPORT:
        LAST_REPORT.clear()
        cleared["report_cache"] = True

    if clear_cli_session:
        try:
            az_cmd = _resolve_az_command()
            command = _wrap_windows_cmd(az_cmd, ["logout"])
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                **_azure_cli_process_options(),
            )
            cleared["cli_session"] = proc.returncode == 0
        except Exception:
            # Clearing local browser context is still useful even when CLI logout fails.
            cleared["cli_session"] = False

    return {"status": "cleared", "cleared": cleared}


@app.get("/api/domains")
async def list_domains():
    return [{"key": d.value, "label": d.value.replace("_", " ").title()} for d in ReportDomain]


@app.get("/api/tenants")
async def list_tenants(authorization: str = Header(default="")):
    token = _extract_bearer(authorization)
    client = AzureLiveClient(token)
    try:
        tenants, audit = await client.list_tenants()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve live tenant data: {exc}") from exc
    return {"items": tenants, "audit": audit.model_dump()}


@app.get("/api/subscriptions")
async def list_subscriptions(authorization: str = Header(default="")):
    token = _extract_bearer(authorization)
    client = AzureLiveClient(token)
    try:
        subscriptions, audit = await client.list_subscriptions()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve live subscription data: {exc}") from exc
    return {"items": subscriptions, "audit": audit.model_dump()}


@app.post("/api/scope-options")
async def get_scope_options(payload: ScopeOptionsRequest, authorization: str = Header(default="")):
    token = _extract_bearer(authorization)

    if not payload.subscription_ids:
        return {
            "resource_groups": [],
            "regions": [],
            "tag_keys": [],
            "tag_values": {},
            "severity": [],
            "source_audit": [],
        }

    client = AzureLiveClient(token)
    source_audit = []
    warnings: list[str] = []

    query = (
        "Resources "
        "| project resourceGroup, location, tags "
        "| mv-expand tagKey = bag_keys(tags) to typeof(string) "
        "| extend tagValue = tostring(tags[tagKey]) "
        "| project resourceGroup, location, tagKey, tagValue"
    )
    try:
        rows, audit = await client.query_resource_graph(payload.subscription_ids, query)
        source_audit.append(audit.model_dump())
    except Exception as exc:
        rows = []
        warnings.append(
            "Resource Graph scope discovery was unavailable for part or all of the selected subscriptions: "
            f"{exc}"
        )

    resource_groups = sorted(
        {str(row.get("resourceGroup", "")).strip() for row in rows if str(row.get("resourceGroup", "")).strip()}
    )[:500]
    regions = sorted(
        {str(row.get("location", "")).strip() for row in rows if str(row.get("location", "")).strip()}
    )[:200]

    tag_values: dict[str, set[str]] = {}
    for row in rows:
        key = str(row.get("tagKey", "")).strip()
        value = str(row.get("tagValue", "")).strip()
        if not key:
            continue
        tag_values.setdefault(key, set())
        if value:
            tag_values[key].add(value)

    tag_keys = sorted(tag_values.keys())[:300]
    tag_values_out = {key: sorted(values)[:300] for key, values in tag_values.items()}

    severities: set[str] = set()
    for subscription_id in payload.subscription_ids[:20]:
        try:
            recommendations, advisor_audit = await client.list_advisor_recommendations(subscription_id)
            source_audit.append(advisor_audit.model_dump())
            for rec in recommendations:
                impact = rec.get("properties", {}).get("impact")
                if impact:
                    severities.add(str(impact))
        except Exception as exc:
            warnings.append(
                f"Advisor scope discovery skipped for subscription {subscription_id}: {exc}"
            )

    return {
        "resource_groups": resource_groups,
        "regions": regions,
        "tag_keys": tag_keys,
        "tag_values": tag_values_out,
        "severity": sorted(severities),
        "source_audit": source_audit,
        "warnings": warnings,
    }


@app.post("/api/reports/{domain}")
async def run_report(domain: ReportDomain, payload: ReportRequest, authorization: str = Header(default="")):
    token = _extract_bearer(authorization)
    try:
        report = await build_report(domain, payload, token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Live query execution failed: {exc}") from exc

    LAST_REPORT.clear()
    LAST_REPORT["report"] = report.model_copy(deep=True)
    LAST_REPORT["exports"] = {}
    return report.model_dump()


@app.post(
    "/api/agent/reports/{domain}",
    operation_id="runFinOpsReport",
    response_model=AgentReportResponse,
    tags=["Microsoft 365 Copilot"],
)
async def run_agent_report(
    domain: ReportDomain,
    payload: AgentReportRequest,
    authorization: str = Header(default=""),
):
    token = _extract_bearer(authorization)
    try:
        report = await build_report(domain, payload, token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Live query execution failed: {exc}") from exc

    LAST_REPORT.clear()
    LAST_REPORT["report"] = report.model_copy(deep=True)
    LAST_REPORT["exports"] = {}
    selected_rows = report.rows[: payload.max_rows]
    return AgentReportResponse(
        domain=report.domain,
        tenant_id=report.tenant_id,
        subscription_scope=report.subscription_scope,
        generated_at_utc=report.generated_at_utc,
        execution_time_ms=report.execution_time_ms,
        live_data_confirmed=report.live_data_confirmed,
        data_quality_score=report.data_quality_score,
        unresolved_fields_count=report.unresolved_fields_count,
        total_row_count=len(report.rows),
        returned_row_count=len(selected_rows),
        result_truncated=len(selected_rows) < len(report.rows),
        source_audit=report.source_audit,
        rows=selected_rows,
        recommendations=report.recommendations,
        warnings=report.warnings,
    )


@app.get("/api/export/{format_type}")
async def export_latest_report(format_type: str = ApiPath(pattern="^(csv|pdf|pptx|sqlite)$")):
    if "report" not in LAST_REPORT:
        raise HTTPException(status_code=404, detail="No report available for export")

    exporter = EXPORT_MAP.get(format_type)
    if exporter is None:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    report = LAST_REPORT["report"].model_copy(deep=True)
    report_key = report.generated_at_utc.isoformat()

    async with EXPORT_LOCKS[format_type]:
        cached_exports = LAST_REPORT.get("exports", {})
        cached_output = cached_exports.get(format_type) if isinstance(cached_exports, dict) else None
        output_path = FsPath(cached_output) if cached_output else None

        if output_path is None or not output_path.exists() or output_path.stat().st_size == 0:
            output = await asyncio.to_thread(exporter, report)
            output_path = FsPath(output)
            current_report = LAST_REPORT.get("report")
            if (
                current_report is not None
                and current_report.generated_at_utc.isoformat() == report_key
            ):
                exports = LAST_REPORT.setdefault("exports", {})
                if isinstance(exports, dict):
                    exports[format_type] = str(output_path)

    return FileResponse(output_path, filename=output_path.name, media_type=EXPORT_MEDIA_TYPES.get(format_type))


def _extract_bearer(authorization: str) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token is required")
    return authorization.split(" ", 1)[1].strip()
