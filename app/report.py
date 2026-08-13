from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"


def _register_fonts() -> str:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"


def build_pdf_report(result: dict) -> tuple[str, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    report_id = uuid4().hex[:12]
    path = REPORT_DIR / f"compliance_report_{report_id}.pdf"
    font = _register_fonts()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font
    title_style = ParagraphStyle("CNTitle", parent=styles["Title"], fontName=font, fontSize=18, leading=24)
    h_style = ParagraphStyle("CNHeading", parent=styles["Heading2"], fontName=font, fontSize=12, leading=16, textColor=colors.HexColor("#1f2937"))
    body = ParagraphStyle("CNBody", parent=styles["BodyText"], fontName=font, fontSize=9.5, leading=14)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = [
        Paragraph("AI科创企业数据合规智能审查报告", title_style),
        Spacer(1, 8),
    ]
    meta = [
        ["审查文件", result.get("filename", "")],
        ["总体评级", result.get("overall_level", "")],
        ["风险数量", str(result.get("risk_count", 0))],
    ]
    table = Table(meta, colWidths=[3 * cm, 12 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([
        table,
        Spacer(1, 12),
        Paragraph("审查摘要", h_style),
        Paragraph(_safe(result.get("summary", "")), body),
        Spacer(1, 10),
    ])
    for idx, risk in enumerate(result.get("risks", []), start=1):
        story.append(Paragraph(f"{idx}. {_safe(risk.get('title'))}（{_safe(risk.get('severity'))}）", h_style))
        story.append(Paragraph(f"风险类型：{_safe(risk.get('risk_type', ''))}", body))
        story.append(Paragraph(f"命中关键词：{_safe(', '.join(risk.get('matched_keywords', [])) or '无')}", body))
        story.append(Paragraph(f"触发原因：{_safe(risk.get('reason', ''))}", body))
        story.append(Paragraph(f"原文片段：{_safe(risk.get('excerpt', ''))}", body))
        legal_basis = "；".join([f"{b.get('title')}：{b.get('text')}" for b in risk.get("legal_basis", [])[:3]])
        story.append(Paragraph(f"法律依据：{_safe(legal_basis or '暂无匹配依据')}", body))
        case_basis = "；".join([f"{b.get('title')}（{b.get('case_no', '')}）" for b in risk.get("case_basis", [])[:3]])
        story.append(Paragraph(f"类案参考：{_safe(case_basis or '暂无匹配类案')}", body))
        story.append(Paragraph(f"整改建议：{_safe(risk.get('recommendation', ''))}", body))
        story.append(Spacer(1, 8))
    story.append(Paragraph("提示：本报告由AI生成，仅用于竞赛演示和内部合规辅助，不替代正式法律意见。", body))
    doc.build(story)
    return report_id, path


def _safe(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
