from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from pathlib import Path
import sys

from fpdf import FPDF
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from app.models import ReportResult


if getattr(sys, "frozen", False):
    EXPORT_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FinOpsCCoE" / "exports"
else:
    EXPORT_DIR = Path("exports")


def _pdf_safe_text(text: object, max_chunk: int = 40) -> str:
    raw = str(text).translate(
        str.maketrans(
            {
                "\u2013": "-",
                "\u2014": "-",
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2022": "-",
                "\u2026": "...",
                "\u00a0": " ",
            }
        )
    ).encode("latin-1", "replace").decode("latin-1")
    # Insert soft breaks into long non-whitespace runs (resource IDs, URLs, GUID chains)
    # so FPDF can always render within cell width.
    return re.sub(
        rf"\S{{{max_chunk + 1},}}",
        lambda m: " ".join(
            m.group(0)[i:i + max_chunk] for i in range(0, len(m.group(0)), max_chunk)
        ),
        raw,
    )


def _pdf_table_text(value: object, max_chunk: int = 36) -> str:
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return _pdf_safe_text(cleaned, max_chunk=max_chunk)


def _pptx_safe_text(value: object, max_chunk: int = 28) -> str:
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return re.sub(
        rf"\S{{{max_chunk + 1},}}",
        lambda match: " ".join(
            match.group(0)[index:index + max_chunk]
            for index in range(0, len(match.group(0)), max_chunk)
        ),
        cleaned,
    )


def ensure_export_dir() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_money(value: float) -> str:
    return f"${value:,.2f}"


def build_executive_brief(report: ReportResult) -> dict[str, object]:
    total_cost = sum(_safe_number(row.get("cost")) for row in report.rows)
    total_savings = sum(
        _safe_number(row.get("savingsEstimate") or row.get("annualSavingsAmount"))
        for row in report.rows
    )
    orphaned_resources = sum(
        1
        for row in report.rows
        if "orphan" in " ".join(
            str(row.get(field, ""))
            for field in ("recommendationType", "category", "resourceName", "reason")
        ).lower()
    )

    savings_evidence = (
        f"Live report identifies {_format_money(total_savings)} in potential savings."
        if total_savings > 0
        else "Live savings evidence is not present in this report; validate the opportunity with Azure Advisor data."
    )
    orphan_evidence = (
        f"{orphaned_resources} orphan-related result(s) are visible in the current report."
        if orphaned_resources > 0
        else "Run or refresh orphan-resource detection to establish the cleanup baseline."
    )

    return {
        "title": "FinOps FY27 Executive Action Report",
        "subtitle": report.domain.value.replace("_", " ").title(),
        "headline": "Begin cost-savings execution immediately while strengthening governance and reporting.",
        "metrics": [
            ("Live potential savings", _format_money(total_savings) if total_savings > 0 else "Not available in this report"),
            ("Cost represented", _format_money(total_cost) if total_cost > 0 else "Not available in this report"),
            ("Resources analyzed", f"{len(report.rows):,}"),
            ("Recommendations", f"{len(report.recommendations):,}"),
            ("Data quality", f"{report.data_quality_score:.1f}%"),
        ],
        "priorities": [
            ("Activate savings now", f"Prioritize Azure Advisor recommendations and orphan-resource cleanup. {savings_evidence} {orphan_evidence}"),
            ("Refresh governance", "Fine-tune FinOps governance, define FY27 KPIs and metrics, and update the RACI for current stakeholders."),
            ("Productionize reporting", "Complete API pagination, validate all returned pages, and move the makeshift Advisor dashboard to a governed operational view."),
            ("Align platform engineering", "Add cost and savings estimates to Terraform re-architecture and disaster-recovery work so benefits are visible with delivery progress."),
        ],
        "actions": [
            ("0-30 days", "Validate Advisor savings, inventory orphaned resources, assign owners, and approve quick-win remediation."),
            ("31-60 days", "Publish refreshed RACI and KPI definitions; complete dashboard pagination and data-quality controls."),
            ("61-90 days", "Report realized savings and incorporate cost estimates and preventive controls into platform-engineering automation."),
        ],
        "executive_decisions": [
            "Confirm accountable owners for savings realization and governance updates.",
            "Approve the Advisor and orphan-resource remediation sequence.",
            "Set the reporting cadence for validated savings, KPI progress, and platform-engineering benefits.",
        ],
        "evidence_note": (
            f"Based on {len(report.rows)} live result(s), {len(report.recommendations)} recommendation(s), "
            f"and {len(report.source_audit)} source call(s) collected at "
            f"{report.generated_at_utc.strftime('%Y-%m-%d %H:%M UTC')}. All values are calculated from this report run."
        ),
    }


def export_csv(report: ReportResult) -> Path:
    ensure_export_dir()
    output = EXPORT_DIR / f"{report.domain.value}_{report.generated_at_utc.strftime('%Y%m%d_%H%M%S')}.csv"
    base_rows = [
        {"dataset": "report_rows", **row}
        for row in report.rows
    ]
    ai_rows = [
        {"dataset": "ai_token_tracking", **row}
        for row in report.ai_token_tracking
    ]
    ai_summary_rows = [
        {"dataset": "ai_token_summary", **row}
        for row in report.ai_token_summary
    ]
    rows = base_rows + ai_summary_rows + ai_rows
    headers = sorted(set().union(*(r.keys() for r in rows))) if rows else ["dataset"]
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            normalized = {
                key: json.dumps(value) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            }
            writer.writerow(normalized)
    return output


def export_sqlite(report: ReportResult) -> Path:
    ensure_export_dir()
    output = EXPORT_DIR / f"{report.domain.value}_{report.generated_at_utc.strftime('%Y%m%d_%H%M%S')}.sqlite"
    conn = sqlite3.connect(output)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS report_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            tenant_id TEXT,
            generated_at_utc TEXT,
            execution_time_ms INTEGER,
            data_quality_score REAL,
            unresolved_fields_count INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS report_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            row_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            category TEXT,
            impact_estimate TEXT,
            confidence TEXT,
            affected_scope TEXT,
            suggested_action TEXT,
            evidence TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS source_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            source TEXT,
            endpoint TEXT,
            duration_ms INTEGER,
            row_count INTEGER,
            executed_at_utc TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS enrichment_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            row_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_token_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            row_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_token_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            row_json TEXT
        )
        """
    )

    cur.execute(
        """
        INSERT INTO report_runs (
            domain, tenant_id, generated_at_utc, execution_time_ms,
            data_quality_score, unresolved_fields_count
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            report.domain.value,
            report.tenant_id,
            report.generated_at_utc.isoformat(),
            report.execution_time_ms,
            report.data_quality_score,
            report.unresolved_fields_count,
        ),
    )

    for row in report.rows:
        cur.execute(
            "INSERT INTO report_rows (domain, row_json) VALUES (?, ?)",
            (report.domain.value, json.dumps(row)),
        )

    for rec in report.recommendations:
        cur.execute(
            """
            INSERT INTO recommendations (
                domain, category, impact_estimate, confidence,
                affected_scope, suggested_action, evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.domain.value,
                rec.category,
                rec.impact_estimate,
                rec.confidence,
                rec.affected_scope,
                rec.suggested_action,
                rec.evidence,
            ),
        )

    for audit in report.source_audit:
        cur.execute(
            """
            INSERT INTO source_audit (
                domain, source, endpoint, duration_ms, row_count, executed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report.domain.value,
                audit.source,
                audit.endpoint,
                audit.duration_ms,
                audit.row_count,
                audit.executed_at_utc.isoformat(),
            ),
        )

    for row in report.enrichment_audit:
        cur.execute(
            "INSERT INTO enrichment_audit (domain, row_json) VALUES (?, ?)",
            (report.domain.value, json.dumps(row)),
        )

    for row in report.ai_token_tracking:
        cur.execute(
            "INSERT INTO ai_token_tracking (domain, row_json) VALUES (?, ?)",
            (report.domain.value, json.dumps(row)),
        )

    for row in report.ai_token_summary:
        cur.execute(
            "INSERT INTO ai_token_summary (domain, row_json) VALUES (?, ?)",
            (report.domain.value, json.dumps(row)),
        )

    conn.commit()
    conn.close()
    return output


def export_pdf(report: ReportResult) -> Path:
    ensure_export_dir()
    output = EXPORT_DIR / f"{report.domain.value}_{report.generated_at_utc.strftime('%Y%m%d_%H%M%S')}.pdf"
    brief = build_executive_brief(report)

    pdf = FPDF(orientation="L")
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    palette = {
        "navy": (20, 31, 56),
        "teal": (15, 118, 110),
        "sky": (226, 232, 240),
        "slate": (51, 65, 85),
        "white": (255, 255, 255),
    }

    page_width = pdf.w - pdf.l_margin - pdf.r_margin

    def ensure_space(required_height: float) -> None:
        if pdf.get_y() + required_height > pdf.h - 15:
            pdf.add_page()

    def section_title(title: str, *, register: bool = True) -> None:
        ensure_space(12)
        if register:
            pdf.start_section(_pdf_safe_text(title), level=0)
        pdf.set_fill_color(*palette["teal"])
        pdf.set_text_color(*palette["white"])
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(pdf.l_margin)
        pdf.cell(page_width, 8, _pdf_safe_text(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(*palette["slate"])

    def topic_header(title: str, context: str) -> None:
        ensure_space(28)
        if pdf.get_y() > pdf.t_margin + 1:
            pdf.ln(10)
        section_title(title)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 4.5, _pdf_table_text(context, 48))
        pdf.ln(1)

    def render_toc(toc_pdf: FPDF, outline: list[object]) -> None:
        toc_pdf.set_fill_color(*palette["navy"])
        toc_pdf.rect(0, 0, toc_pdf.w, 24, style="F")
        toc_pdf.set_text_color(*palette["white"])
        toc_pdf.set_font("Helvetica", "B", 18)
        toc_pdf.set_xy(toc_pdf.l_margin, 8)
        toc_pdf.cell(page_width, 8, "Table of Contents")
        toc_pdf.set_text_color(*palette["slate"])
        toc_pdf.set_y(32)
        toc_pdf.set_font("Helvetica", "", 10)
        for item in outline:
            if item.level != 0:
                continue
            link = toc_pdf.add_link(page=item.page_number)
            toc_pdf.set_x(toc_pdf.l_margin)
            toc_pdf.cell(page_width - 18, 7, _pdf_safe_text(item.name), link=link)
            toc_pdf.cell(18, 7, str(item.page_number), align="R", link=link, new_x="LMARGIN", new_y="NEXT")

    def draw_table(title: str, columns: list[tuple[str, float]], rows: list[dict[str, object]]) -> None:
        section_title(title, register=False)
        ensure_space(8)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(*palette["sky"])
        for label, width in columns:
            pdf.cell(width, 6, _pdf_table_text(label, 24)[:36], border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        for row in rows:
            ensure_space(6)
            for key, width in columns:
                text = _pdf_table_text(row.get(key, ""), 32)[:140]
                pdf.cell(width, 6, text, border=1)
            pdf.ln()

    # Header band
    pdf.set_fill_color(*palette["navy"])
    pdf.rect(0, 0, pdf.w, 32, style="F")
    pdf.set_text_color(*palette["white"])
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(pdf.l_margin, 10)
    pdf.cell(page_width, 8, _pdf_safe_text(brief["title"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(page_width, 6, _pdf_safe_text(brief["subtitle"]), new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(*palette["slate"])
    pdf.set_y(39)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(page_width, 6, _pdf_table_text(brief["headline"], 48))
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(
        page_width,
        5,
        _pdf_table_text(
            f"Tenant: {report.tenant_id} | Subscriptions: {len(report.subscription_scope)} | "
            f"Generated: {report.generated_at_utc.strftime('%Y-%m-%d %H:%M UTC')}",
            48,
        ),
    )

    pdf.add_page()
    pdf.insert_toc_placeholder(render_toc, pages=1)

    # Executive summary
    topic_header("Executive Summary", "Current-run financial, coverage, and data-quality indicators for executive review.")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(page_width, 6, _pdf_table_text(brief["headline"], 40))
    for label, value in brief["metrics"]:
        ensure_space(6)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 6, _pdf_table_text(f"{label}: {value}", 40))

    topic_header("Executive Priorities", "Priority outcomes framed by the report context and supported only by current-run evidence.")
    pdf.set_font("Helvetica", "", 9)
    for title, detail in brief["priorities"]:
        ensure_space(8)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 5.5, _pdf_table_text(f"{title}: {detail}", 40))

    topic_header("90-Day Action Plan", "Sequenced actions for validating, assigning, and realizing the opportunities in this report.")
    pdf.set_font("Helvetica", "", 9)
    for period, action in brief["actions"]:
        ensure_space(8)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 5.5, _pdf_table_text(f"{period}: {action}", 40))

    topic_header("Executive Decisions", "Decisions and ownership required to move report findings into accountable execution.")
    pdf.set_font("Helvetica", "", 9)
    for decision in brief["executive_decisions"]:
        ensure_space(7)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 5.5, _pdf_table_text(f"- {decision}", 40))
    ensure_space(8)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_width, 5.5, _pdf_table_text(brief["evidence_note"], 40))

    def row_summary(row: dict[str, object]) -> str:
        if row.get("recommendationType"):
            parts = [str(row.get("recommendationType", ""))]
            if row.get("category"):
                parts.append(str(row.get("category")))
            if row.get("impact"):
                parts.append(f"impact {row.get('impact')}")
            if row.get("savingsEstimate") not in (None, ""):
                parts.append(f"estimated savings {_format_money(_safe_number(row.get('savingsEstimate')))}")
            return " | ".join(parts)

        parts = []
        for field in ("resourceName", "serviceName", "resourceGroup", "region"):
            value = row.get(field)
            if value not in (None, ""):
                parts.append(f"{field}: {_pdf_table_text(value, 18)}")
        if row.get("cost") not in (None, ""):
            parts.append(f"cost {_format_money(_safe_number(row.get('cost')))}")
        if row.get("usageQuantity") not in (None, ""):
            parts.append(f"usage {_pdf_table_text(row.get('usageQuantity'), 18)}")
        if row.get("estimatedTokenUnits") not in (None, ""):
            parts.append(f"tokens {_pdf_table_text(row.get('estimatedTokenUnits'), 18)}")
        if row.get("savingsEstimate") not in (None, ""):
            parts.append(f"estimated savings {_format_money(_safe_number(row.get('savingsEstimate')))}")
        return " | ".join(parts) or "Result item"

    # Recommendations table
    recommendation_rows = [
        {
            "Category": rec.category,
            "Impact": rec.impact_estimate,
            "Confidence": rec.confidence,
            "Action": rec.suggested_action,
        }
        for rec in report.recommendations
    ]
    if recommendation_rows:
        topic_header("Recommendations", "Prioritized findings, impact, confidence, and accountable remediation actions.")
        draw_table(
            "Top Recommendations",
            [("Category", 38), ("Impact", 36), ("Confidence", 24), ("Action", page_width - 98)],
            recommendation_rows[:8],
        )

    # AI summary table
    if report.ai_token_summary:
        topic_header("AI Usage", "Aggregated Azure AI consumption, token estimates, and current-run cost evidence.")
        ai_summary_rows = [
            {
                "Scope": row.get("serviceScope", ""),
                "Total": row.get("totalUsageQuantity", ""),
                "Avg": row.get("averageUsageQuantity", ""),
                "Tokens": row.get("totalEstimatedTokenUnits", ""),
                "AvgTok": row.get("averageEstimatedTokenUnits", ""),
                "Cost": row.get("totalCost", ""),
            }
            for row in report.ai_token_summary
        ]
        draw_table(
            "AI Usage Summary",
            [("Scope", 44), ("Total", 24), ("Avg", 24), ("Tokens", 24), ("AvgTok", 24), ("Cost", page_width - 140)],
            ai_summary_rows[:10],
        )

    # Report results table
    if report.rows:
        topic_header("Report Results", "Representative live results for the selected report topic and subscription scope.")
        section_title("Results Highlights", register=False)
        pdf.set_font("Helvetica", "", 8)
        highlight_lines = [row_summary(row) for row in report.rows[:8]]
        for line in highlight_lines:
            ensure_space(6)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(page_width, 5.5, _pdf_table_text(f"- {line}", 40))

    if report.source_audit or report.enrichment_audit:
        topic_header("Data Provenance", "Source execution and enrichment evidence supporting this report.")
        if report.source_audit:
            source_rows = [
                {
                    "Source": item.source,
                    "Rows": item.row_count,
                    "Duration": f"{item.duration_ms} ms",
                    "Executed": item.executed_at_utc.strftime("%Y-%m-%d %H:%M UTC"),
                }
                for item in report.source_audit
            ]
            draw_table(
                "Source Audit",
                [("Source", 70), ("Rows", 24), ("Duration", 32), ("Executed", page_width - 126)],
                source_rows[:10],
            )
        if report.enrichment_audit:
            pdf.set_font("Helvetica", "", 8)
            ensure_space(7)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                page_width,
                5,
                f"Enrichment audit records: {len(report.enrichment_audit):,} | "
                f"Unresolved key fields: {report.unresolved_fields_count:,}",
            )

    # Footer notes
    if report.warnings:
        topic_header("Operational Notes", "Warnings, partial-access conditions, and limitations affecting interpretation.")
        section_title("Warnings", register=False)
        pdf.set_font("Helvetica", "", 8)
        for warning in report.warnings[:6]:
            ensure_space(6)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(page_width, 6, _pdf_table_text(f"- {warning}", 40))

    pdf.output(str(output))
    return output


def export_pptx(report: ReportResult) -> Path:
    ensure_export_dir()
    output = EXPORT_DIR / f"{report.domain.value}_{report.generated_at_utc.strftime('%Y%m%d_%H%M%S')}.pptx"
    brief = build_executive_brief(report)

    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    palette = {
        "navy": RGBColor(20, 31, 56),
        "teal": RGBColor(15, 118, 110),
        "slate": RGBColor(51, 65, 85),
        "pale": RGBColor(245, 247, 250),
        "light": RGBColor(226, 232, 240),
        "white": RGBColor(255, 255, 255),
    }
    section_slides: dict[str, int] = {}

    def set_text(
        text_frame,
        text: str,
        *,
        size: int = 18,
        bold: bool = False,
        color: RGBColor | None = None,
        align: PP_ALIGN = PP_ALIGN.LEFT,
    ) -> None:
        text_frame.clear()
        text_frame.word_wrap = True
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        paragraph = text_frame.paragraphs[0]
        paragraph.text = str(text)
        paragraph.alignment = align
        run = paragraph.runs[0]
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color or palette["slate"]

    def add_title_slide() -> None:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        banner = slide.shapes.add_shape(
            1, Inches(0), Inches(0), presentation.slide_width, Inches(1.3)
        )
        banner.fill.solid()
        banner.fill.fore_color.rgb = palette["navy"]
        banner.line.fill.background()

        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12.3), Inches(0.5))
        set_text(title_box.text_frame, str(brief["title"]), size=26, bold=True, color=palette["white"])

        domain_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.75), Inches(12.3), Inches(0.35))
        set_text(
            domain_box.text_frame,
            str(brief["subtitle"]),
            size=12,
            color=palette["white"],
        )

        summary_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12.0), Inches(1.4))
        summary_lines = [
            f"Tenant: {report.tenant_id}",
            f"Subscriptions: {len(report.subscription_scope)}",
            f"Generated: {report.generated_at_utc.isoformat()}",
            f"Execution: {report.execution_time_ms} ms | Data Quality: {report.data_quality_score}%",
        ]
        text_frame = summary_box.text_frame
        text_frame.clear()
        text_frame.word_wrap = True
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        for idx, line in enumerate(summary_lines):
            paragraph = text_frame.paragraphs[0] if idx == 0 else text_frame.add_paragraph()
            paragraph.text = line
            paragraph.level = 0
            if paragraph.runs:
                run = paragraph.runs[0]
                run.font.size = Pt(14 if idx == 0 else 12)
                run.font.color.rgb = palette["slate"]

    def add_summary_slide() -> None:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        header = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.0), Inches(0.5))
        set_text(header.text_frame, "Executive Summary", size=22, bold=True, color=palette["navy"])

        bullets = [str(brief["headline"])] + [
            f"{label}: {value}" for label, value in brief["metrics"]
        ] + [str(brief["evidence_note"])]

        body = slide.shapes.add_textbox(Inches(0.7), Inches(1.0), Inches(12.0), Inches(4.8))
        tf = body.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        for idx, line in enumerate(bullets):
            paragraph = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            paragraph.text = line
            paragraph.level = 0
            if paragraph.runs:
                run = paragraph.runs[0]
                run.font.size = Pt(16 if idx == 0 else 13)
                run.font.color.rgb = palette["slate"]

    def add_contents_slide():
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        header = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.0), Inches(0.5))
        set_text(header.text_frame, "Report Contents", size=22, bold=True, color=palette["navy"])
        body = slide.shapes.add_textbox(Inches(0.7), Inches(1.0), Inches(12.0), Inches(5.6))
        text_frame = body.text_frame
        text_frame.clear()
        text_frame.word_wrap = True
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        return text_frame

    def render_contents(text_frame, topics: list[tuple[str, str]]) -> None:
        for index, (title, context) in enumerate(topics):
            paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
            slide_number = section_slides.get(title)
            page_reference = f"Slide {slide_number}" if slide_number else "Section"
            paragraph.text = f"{index + 1}. {title} - {context}  |  {page_reference}"
            paragraph.space_after = Pt(5)
            paragraph.line_spacing = 1.0
            if paragraph.runs:
                paragraph.runs[0].font.size = Pt(13)
                paragraph.runs[0].font.color.rgb = palette["slate"]

    def add_bullet_slide(title: str, bullets: list[str]) -> None:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        header = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.0), Inches(0.5))
        set_text(header.text_frame, title, size=22, bold=True, color=palette["navy"])

        body = slide.shapes.add_textbox(Inches(0.7), Inches(1.0), Inches(12.0), Inches(5.5))
        text_frame = body.text_frame
        text_frame.clear()
        text_frame.word_wrap = True
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        for index, line in enumerate(bullets):
            paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
            paragraph.text = line
            paragraph.level = 0
            paragraph.space_after = Pt(6)
            paragraph.line_spacing = 1.0
            if paragraph.runs:
                run = paragraph.runs[0]
                run.font.size = Pt(14)
                run.font.color.rgb = palette["slate"]

    def add_section_divider(title: str, subtitle: str) -> None:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        section_slides[title] = len(presentation.slides)
        banner = slide.shapes.add_shape(1, Inches(0), Inches(0), presentation.slide_width, presentation.slide_height)
        banner.fill.solid()
        banner.fill.fore_color.rgb = palette["navy"]
        banner.line.fill.background()

        title_box = slide.shapes.add_textbox(Inches(0.75), Inches(2.0), Inches(11.8), Inches(0.7))
        set_text(title_box.text_frame, title, size=24, bold=True, color=palette["white"])

        subtitle_box = slide.shapes.add_textbox(Inches(0.75), Inches(2.8), Inches(11.8), Inches(0.5))
        set_text(subtitle_box.text_frame, subtitle, size=12, bold=False, color=palette["light"])

    def add_footers() -> None:
        total_slides = len(presentation.slides)
        for index, slide in enumerate(presentation.slides, start=1):
            footer = slide.shapes.add_textbox(Inches(0.5), Inches(7.0), Inches(12.0), Inches(0.22))
            footer_frame = footer.text_frame
            footer_frame.clear()
            paragraph = footer_frame.paragraphs[0]
            paragraph.text = f"FinOps CCoE Live Reporting | Slide {index} of {total_slides}"
            paragraph.alignment = PP_ALIGN.RIGHT
            if paragraph.runs:
                run = paragraph.runs[0]
                run.font.size = Pt(8)
                run.font.color.rgb = palette["slate"]

    def add_table_slide(title: str, rows: list[dict[str, object]], preferred_columns: list[str], rows_per_slide: int = 12) -> None:
        if not rows:
            return

        columns = [col for col in preferred_columns if any(col in row for row in rows)]
        for row in rows:
            columns.extend(col for col in row if col not in columns)

        index_candidates = [
            "serviceScope",
            "subscriptionId",
            "resourceName",
            "category",
            "source",
            "serviceName",
            "scope",
            "resourceId",
        ]
        index_columns = [col for col in index_candidates if col in columns][:3]
        detail_columns = [col for col in columns if col not in index_columns]
        fixed_columns = ["__rowNumber", *index_columns]
        detail_chunk_size = max(1, 6 - len(fixed_columns))
        column_groups = [
            [*fixed_columns, *detail_columns[start:start + detail_chunk_size]]
            for start in range(0, len(detail_columns), detail_chunk_size)
        ]
        if not column_groups:
            column_groups = [fixed_columns]

        for group_index, group_columns in enumerate(column_groups, start=1):
            group_rows_per_slide = rows_per_slide
            if len(group_columns) >= 4:
                group_rows_per_slide = min(rows_per_slide, 8)
            elif len(group_columns) >= 3:
                group_rows_per_slide = min(rows_per_slide, 10)

            for start in range(0, len(rows), group_rows_per_slide):
                chunk = rows[start:start + group_rows_per_slide]
                slide = presentation.slides.add_slide(presentation.slide_layouts[6])
                header = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12.0), Inches(0.45))
                suffix = f" ({start + 1}-{start + len(chunk)} of {len(rows)})"
                if len(column_groups) > 1:
                    column_label = f" [Part {group_index}/{len(column_groups)}]"
                else:
                    column_label = ""
                set_text(header.text_frame, f"{title}{column_label}{suffix}", size=18, bold=True, color=palette["navy"])

                max_table_width = 12.5
                preferred_widths = []
                for col in group_columns:
                    values = [str(row.get(col, "")) for row in chunk]
                    header_text = "Row" if col == "__rowNumber" else col
                    longest = max([len(header_text), *(min(len(value), 72) for value in values)])
                    if col == "__rowNumber":
                        preferred_widths.append(0.55)
                    elif col == "resourceId":
                        preferred_widths.append(min(7.5, max(3.5, longest * 0.085)))
                    elif col in {"action", "evidence", "endpoint", "warning"}:
                        preferred_widths.append(min(6.0, max(2.4, longest * 0.085)))
                    elif col in {"resourceName", "serviceName", "serviceScope", "resourceType", "resourceGroup", "category", "scope"}:
                        preferred_widths.append(min(4.0, max(1.5, longest * 0.085)))
                    else:
                        preferred_widths.append(min(2.8, max(1.15, longest * 0.085)))

                preferred_total = sum(preferred_widths)
                if preferred_total > max_table_width:
                    scale = max_table_width / preferred_total
                    widths = [width * scale for width in preferred_widths]
                else:
                    widths = preferred_widths
                table_width = sum(widths)

                header_height = 0.38
                data_row_height = min(0.62, max(0.36, 5.7 / max(1, len(chunk))))
                table_height = header_height + (data_row_height * len(chunk))
                table_shape = slide.shapes.add_table(
                    len(chunk) + 1,
                    len(group_columns),
                    Inches(0.4),
                    Inches(0.8),
                    Inches(table_width),
                    Inches(table_height),
                )
                table = table_shape.table

                for idx, width in enumerate(widths):
                    table.columns[idx].width = Inches(width)
                table.rows[0].height = Inches(header_height)
                for row_index in range(1, len(table.rows)):
                    table.rows[row_index].height = Inches(data_row_height)

                for col_idx, col in enumerate(group_columns):
                    cell = table.cell(0, col_idx)
                    cell.text = "Row" if col == "__rowNumber" else col
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = palette["teal"]
                    cell.margin_left = Inches(0.08)
                    cell.margin_right = Inches(0.08)
                    cell.margin_top = Inches(0.04)
                    cell.margin_bottom = Inches(0.04)
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                    cell.text_frame.word_wrap = True
                    cell.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
                    if cell.text_frame.paragraphs and cell.text_frame.paragraphs[0].runs:
                        run = cell.text_frame.paragraphs[0].runs[0]
                        run.font.bold = True
                        run.font.size = Pt(9)
                        run.font.color.rgb = palette["white"]

                for row_idx, row in enumerate(chunk, start=1):
                    row_fill = palette["white"] if row_idx % 2 else palette["pale"]
                    for col_idx, col in enumerate(group_columns):
                        value = start + row_idx if col == "__rowNumber" else _pptx_safe_text(row.get(col, ""), 28)
                        cell = table.cell(row_idx, col_idx)
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = row_fill
                        cell.text = str(value)
                        cell.margin_left = Inches(0.08)
                        cell.margin_right = Inches(0.08)
                        cell.margin_top = Inches(0.04)
                        cell.margin_bottom = Inches(0.04)
                        cell.vertical_anchor = MSO_ANCHOR.TOP
                        cell.text_frame.word_wrap = True
                        cell.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
                        if cell.text_frame.paragraphs and cell.text_frame.paragraphs[0].runs:
                            run = cell.text_frame.paragraphs[0].runs[0]
                            run.font.size = Pt(8 if len(group_columns) >= 4 else 9)
                            run.font.color.rgb = palette["slate"]

    report_topics = [
        ("Executive Overview", "summary, priorities, action plan, and decisions"),
        ("Report Results", "live records for the selected report topic"),
    ]
    if report.recommendations:
        report_topics.insert(1, ("Recommendations", "impact, confidence, scope, actions, and evidence"))
    if report.ai_token_summary or report.ai_token_tracking:
        report_topics.insert(-1, ("AI Usage", "token and cost summaries"))
    if report.source_audit or report.enrichment_audit:
        report_topics.append(("Data Provenance", "source and enrichment audit context"))
    if report.warnings:
        report_topics.append(("Operational Notes", "warnings and partial-access conditions"))

    add_title_slide()
    contents_frame = add_contents_slide()
    add_section_divider("Executive Overview", "Current-run summary, priorities, action plan, and decisions.")
    add_summary_slide()
    add_bullet_slide(
        "Executive Priorities",
        [f"{title}: {detail}" for title, detail in brief["priorities"]],
    )
    add_bullet_slide(
        "90-Day Action Plan",
        [f"{period}: {action}" for period, action in brief["actions"]],
    )
    add_bullet_slide(
        "Executive Decisions",
        [str(decision) for decision in brief["executive_decisions"]],
    )

    if report.recommendations:
        add_section_divider("Recommendations", "Impact, confidence, scope, actions, and supporting evidence.")
        add_table_slide(
            "Recommendations",
            [
                {
                    "category": rec.category,
                    "impact": rec.impact_estimate,
                    "confidence": rec.confidence,
                    "scope": rec.affected_scope,
                    "action": rec.suggested_action,
                    "evidence": rec.evidence,
                }
                for rec in report.recommendations
            ],
            ["category", "impact", "confidence", "scope", "action", "evidence"],
            rows_per_slide=10,
        )

    if report.ai_token_summary or report.ai_token_tracking:
        add_section_divider("AI Usage", "Token and cost summaries for Azure AI services when available.")
    add_table_slide(
        "AI Token Summary",
        report.ai_token_summary,
        [
            "serviceScope",
            "records",
            "totalUsageQuantity",
            "averageUsageQuantity",
            "totalEstimatedTokenUnits",
            "averageEstimatedTokenUnits",
            "totalCost",
            "averageCost",
        ],
    )

    add_table_slide(
        "AI Token Tracking",
        report.ai_token_tracking,
        [
            "subscriptionId",
            "serviceName",
            "meterName",
            "usageQuantity",
            "estimatedTokenUnits",
            "cost",
            "resourceId",
        ],
    )

    add_section_divider("Report Results", "Live records for the selected report topic and subscription scope.")
    add_table_slide(
        "Report Results",
        report.rows,
        [
            "subscriptionId",
            "resourceName",
            "serviceName",
            "resourceType",
            "resourceGroup",
            "region",
            "cost",
            "usageQuantity",
            "estimatedTokenUnits",
            "resourceId",
        ],
    )

    if report.source_audit or report.enrichment_audit:
        add_section_divider("Data Provenance", "Source calls and enrichment outcomes supporting this report.")
    add_table_slide(
        "Source Audit",
        [
            {
                "source": item.source,
                "endpoint": item.endpoint,
                "durationMs": item.duration_ms,
                "rowCount": item.row_count,
                "executedAtUtc": item.executed_at_utc.isoformat(),
            }
            for item in report.source_audit
        ],
        ["source", "durationMs", "rowCount", "executedAtUtc", "endpoint"],
        rows_per_slide=10,
    )

    add_table_slide(
        "Enrichment Audit",
        report.enrichment_audit,
        [
            "resolutionStatus",
            "resolvedResourceName",
            "resolvedResourceType",
            "resolvedResourceGroup",
            "resolvedSubscriptionId",
            "sourceResourceId",
        ],
    )

    if report.warnings:
        add_section_divider("Operational Notes", "Warnings and partial-access notes.")
        add_table_slide(
            "Warnings",
            [{"warning": warning} for warning in report.warnings],
            ["warning"],
            rows_per_slide=15,
        )

    render_contents(contents_frame, report_topics)
    add_footers()

    presentation.save(str(output))
    return output
