from __future__ import annotations

import csv
from collections import Counter
import json
import re
import sqlite3
from pathlib import Path

from fpdf import FPDF
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from app.models import ReportResult


EXPORT_DIR = Path("exports")


def _pdf_safe_text(text: object, max_chunk: int = 40) -> str:
    raw = str(text)
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


def ensure_export_dir() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


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

    pdf = FPDF(orientation="L")
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

    def section_title(title: str) -> None:
        ensure_space(12)
        pdf.set_fill_color(*palette["teal"])
        pdf.set_text_color(*palette["white"])
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(pdf.l_margin)
        pdf.cell(page_width, 8, _pdf_safe_text(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(*palette["slate"])

    def draw_table(title: str, columns: list[tuple[str, float]], rows: list[dict[str, object]]) -> None:
        section_title(title)
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
    pdf.cell(page_width, 8, "FinOps Executive Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(page_width, 6, f"Domain: {report.domain.value.replace('_', ' ').title()}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(*palette["slate"])
    pdf.ln(6)

    # Executive summary
    section_title("Executive Summary")
    pdf.set_font("Helvetica", "", 10)
    def safe_number(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def format_money(value: float) -> str:
        return f"${value:,.2f}"

    def row_summary(row: dict[str, object]) -> str:
        if row.get("recommendationType"):
            parts = [str(row.get("recommendationType", ""))]
            if row.get("category"):
                parts.append(str(row.get("category")))
            if row.get("impact"):
                parts.append(f"impact {row.get('impact')}")
            if row.get("savingsEstimate") not in (None, ""):
                parts.append(f"estimated savings {format_money(safe_number(row.get('savingsEstimate')))}")
            return " | ".join(parts)

        parts = []
        for field in ("resourceName", "serviceName", "resourceGroup", "region"):
            value = row.get(field)
            if value not in (None, ""):
                parts.append(f"{field}: {_pdf_table_text(value, 18)}")
        if row.get("cost") not in (None, ""):
            parts.append(f"cost {format_money(safe_number(row.get('cost')))}")
        if row.get("usageQuantity") not in (None, ""):
            parts.append(f"usage {_pdf_table_text(row.get('usageQuantity'), 18)}")
        if row.get("estimatedTokenUnits") not in (None, ""):
            parts.append(f"tokens {_pdf_table_text(row.get('estimatedTokenUnits'), 18)}")
        if row.get("savingsEstimate") not in (None, ""):
            parts.append(f"estimated savings {format_money(safe_number(row.get('savingsEstimate')))}")
        return " | ".join(parts) or "Result item"

    def summarize_top(counter: Counter[str]) -> str | None:
        if not counter:
            return None
        label, count = counter.most_common(1)[0]
        if label == "Unspecified":
            return None
        return f"{label} ({count} result(s))"

    total_cost = sum(safe_number(row.get("cost")) for row in report.rows)
    total_savings = sum(
        safe_number(row.get("savingsEstimate") or row.get("annualSavingsAmount"))
        for row in report.rows
    )
    top_subscription = summarize_top(Counter(str(row.get("subscriptionId") or "Unspecified") for row in report.rows))
    top_service = summarize_top(Counter(str(row.get("serviceName") or row.get("category") or row.get("recommendationType") or "Unspecified") for row in report.rows))
    top_resource_group = summarize_top(Counter(str(row.get("resourceGroup") or "Unspecified") for row in report.rows))

    summary_lines = [
        f"Results captured: {len(report.rows)}",
        f"Recommendations generated: {len(report.recommendations)}",
    ]
    if total_cost > 0:
        summary_lines.append(f"Total cost identified: {format_money(total_cost)}")
    if total_savings > 0:
        summary_lines.append(f"Potential savings identified: {format_money(total_savings)}")
    if top_subscription:
        summary_lines.append(f"Top subscription by result count: {top_subscription}")
    if top_service:
        summary_lines.append(f"Top service or category: {top_service}")
    if top_resource_group:
        summary_lines.append(f"Top resource group: {top_resource_group}")
    for line in summary_lines:
        ensure_space(6)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 6, _pdf_table_text(line, 40))

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
        draw_table(
            "Top Recommendations",
            [("Category", 38), ("Impact", 36), ("Confidence", 24), ("Action", page_width - 98)],
            recommendation_rows[:8],
        )

    # AI summary table
    if report.ai_token_summary:
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
        section_title("Results Highlights")
        pdf.set_font("Helvetica", "", 8)
        highlight_lines = [row_summary(row) for row in report.rows[:8]]
        for line in highlight_lines:
            ensure_space(6)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(page_width, 5.5, f"- {line}")

    # Footer notes
    if report.warnings:
        section_title("Warnings")
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
        set_text(title_box.text_frame, "FinOps Executive Report", size=26, bold=True, color=palette["white"])

        domain_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.75), Inches(12.3), Inches(0.35))
        set_text(
            domain_box.text_frame,
            f"Domain: {report.domain.value.replace('_', ' ').title()}",
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

        total_ai_usage = sum(float(row.get("totalUsageQuantity", 0) or 0) for row in report.ai_token_summary)
        total_ai_tokens = sum(float(row.get("totalEstimatedTokenUnits", 0) or 0) for row in report.ai_token_summary)

        bullets = [
            f"Rows analyzed: {len(report.rows)}",
            f"Recommendations: {len(report.recommendations)}",
            f"Source API calls: {len(report.source_audit)}",
            f"AI usage quantity total: {round(total_ai_usage, 4)}",
            f"AI estimated token units total: {round(total_ai_tokens, 4)}",
            f"Warnings: {len(report.warnings)}",
        ]

        body = slide.shapes.add_textbox(Inches(0.7), Inches(1.0), Inches(12.0), Inches(4.8))
        tf = body.text_frame
        tf.clear()
        for idx, line in enumerate(bullets):
            paragraph = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            paragraph.text = line
            paragraph.level = 0
            if paragraph.runs:
                run = paragraph.runs[0]
                run.font.size = Pt(16 if idx == 0 else 13)
                run.font.color.rgb = palette["slate"]

    def add_section_divider(title: str, subtitle: str) -> None:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
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
        if not columns:
            columns = list(rows[0].keys())[:6]
        columns = columns[:10]

        resource_id_present = "resourceId" in columns
        non_resource_columns = [col for col in columns if col != "resourceId"]

        column_groups: list[list[str]] = []
        chunk_size = 4 if len(columns) >= 6 else 5
        for start in range(0, len(non_resource_columns), chunk_size):
            column_groups.append(non_resource_columns[start:start + chunk_size])
        if resource_id_present:
            column_groups.append(["resourceId"])

        if not column_groups:
            column_groups = [columns[:4]]

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

                table_shape = slide.shapes.add_table(
                    len(chunk) + 1,
                    len(group_columns),
                    Inches(0.4),
                    Inches(0.8),
                    Inches(12.5),
                    Inches(6.3),
                )
                table = table_shape.table

                total_width = 12.5
                weights = []
                for col in group_columns:
                    if col == "resourceId":
                        weights.append(3.2)
                    elif col in {"resourceName", "serviceName", "resourceType", "resourceGroup", "endpoint"}:
                        weights.append(2.0)
                    elif col in {"cost", "usageQuantity", "estimatedTokenUnits", "records", "totalUsageQuantity", "averageUsageQuantity", "totalEstimatedTokenUnits", "averageEstimatedTokenUnits", "totalCost", "averageCost"}:
                        weights.append(1.3)
                    else:
                        weights.append(1.6)
                weight_sum = sum(weights) or 1.0
                widths = [(total_width * weight) / weight_sum for weight in weights]

                for idx, width in enumerate(widths):
                    table.columns[idx].width = Inches(width)

                for col_idx, col in enumerate(group_columns):
                    cell = table.cell(0, col_idx)
                    cell.text = col
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = palette["teal"]
                    if cell.text_frame.paragraphs and cell.text_frame.paragraphs[0].runs:
                        run = cell.text_frame.paragraphs[0].runs[0]
                        run.font.bold = True
                        run.font.size = Pt(10)
                        run.font.color.rgb = palette["white"]

                for row_idx, row in enumerate(chunk, start=1):
                    row_fill = palette["white"] if row_idx % 2 else palette["pale"]
                    for col_idx, col in enumerate(group_columns):
                        value = _pdf_safe_text(row.get(col, ""), 28)
                        cell = table.cell(row_idx, col_idx)
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = row_fill
                        cell.text = str(value)
                        if cell.text_frame.paragraphs and cell.text_frame.paragraphs[0].runs:
                            run = cell.text_frame.paragraphs[0].runs[0]
                            run.font.size = Pt(8 if len(group_columns) >= 4 else 9)
                            run.font.color.rgb = palette["slate"]

    add_title_slide()
    add_summary_slide()

    if report.recommendations:
        add_section_divider("Detailed Findings", "Recommendations and report outputs follow on the next slides.")

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

    add_footers()

    presentation.save(str(output))
    return output
