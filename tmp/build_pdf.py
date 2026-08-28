from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(r"E:\project\世界稀疏建模\世界稀疏建模01")
SOURCE = ROOT / "docs" / "semantic_world_model_proposal.md"
OUTPUT = ROOT / "outputs" / "semantic_world_model_proposal.pdf"

FONT_PATH = r"C:\Windows\Fonts\simsun.ttc"
pdfmetrics.registerFont(TTFont("SimSun", FONT_PATH, subfontIndex=0))
pdfmetrics.registerFontFamily("SimSun", normal="SimSun", bold="SimSun", italic="SimSun", boldItalic="SimSun")

NAVY = colors.HexColor("#0B2545")
BLUE = colors.HexColor("#2E74B5")
DARK_BLUE = colors.HexColor("#1F4D78")
MUTED = colors.HexColor("#666666")
LIGHT_BLUE = colors.HexColor("#E8EEF5")
LIGHT_GREEN = colors.HexColor("#EAF4EA")
LIGHT_YELLOW = colors.HexColor("#FFF1D6")
LIGHT_PURPLE = colors.HexColor("#F3E8F8")
LIGHT_GRAY = colors.HexColor("#F2F4F7")
GRID = colors.HexColor("#C7D0D9")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline_markup(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyCN", parent=styles["BodyText"], fontName="SimSun", fontSize=9.4, leading=14.2, spaceAfter=5, textColor=colors.black, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="BodyLead", parent=styles["BodyCN"], fontName="SimSun", fontSize=10.2, leading=15, textColor=NAVY, backColor=colors.HexColor("#F4F6F9"), borderPadding=(5, 7, 5, 7), spaceBefore=3, spaceAfter=8))
styles.add(ParagraphStyle(name="H1CN", parent=styles["Heading1"], fontName="SimSun", fontSize=15, leading=19, textColor=BLUE, spaceBefore=13, spaceAfter=7, keepWithNext=True))
styles.add(ParagraphStyle(name="H2CN", parent=styles["Heading2"], fontName="SimSun", fontSize=12.2, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="H3CN", parent=styles["Heading3"], fontName="SimSun", fontSize=10.8, leading=14, textColor=DARK_BLUE, spaceBefore=7, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="CodeCN", parent=styles["Code"], fontName="SimSun", fontSize=7.2, leading=9, leftIndent=5, rightIndent=5, spaceBefore=2, spaceAfter=2, textColor=colors.HexColor("#2B2B2B")))
styles.add(ParagraphStyle(name="TableCN", parent=styles["BodyText"], fontName="SimSun", fontSize=7.5, leading=9.4, spaceAfter=0, textColor=colors.black))
styles.add(ParagraphStyle(name="TableHeadCN", parent=styles["TableCN"], fontName="SimSun", textColor=NAVY))
styles.add(ParagraphStyle(name="CaptionCN", parent=styles["BodyText"], fontName="SimSun", fontSize=8, leading=10, alignment=TA_CENTER, textColor=MUTED, spaceBefore=2, spaceAfter=6))
styles.add(ParagraphStyle(name="TitleCN", parent=styles["Title"], fontName="SimSun", fontSize=24, leading=31, alignment=TA_CENTER, textColor=NAVY, spaceAfter=12))
styles.add(ParagraphStyle(name="SubtitleCN", parent=styles["BodyText"], fontName="SimSun", fontSize=12, leading=17, alignment=TA_CENTER, textColor=MUTED, spaceAfter=20))
styles.add(ParagraphStyle(name="TOCCN", parent=styles["BodyText"], fontName="SimSun", fontSize=9.6, leading=15, leftIndent=10, textColor=NAVY, spaceAfter=2))


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=self.draw_footer)])

    def draw_footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("SimSun", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18*mm, 10*mm, "世界稀疏建模 | 语义世界模型方案 | 2026-08-27")
        canvas.drawRightString(A4[0] - 18*mm, 10*mm, f"第 {doc.page} 页")
        canvas.restoreState()


def flow_diagram():
    stages = [
        ("传感输入", "RGB-D 双目相机 + IMU", LIGHT_BLUE),
        ("长期定位", "视觉惯性定位、稀疏地标、关键帧、回环位姿图", LIGHT_BLUE),
        ("长期语义", "对象、地点、粗锚点、截图证据、语义索引", LIGHT_GREEN),
        ("长期通行", "房间、门口、转折点、楼梯、电梯、连通边", LIGHT_PURPLE),
        ("短期执行", "局部稠密点云、局部代价地图、避障与精细对准", LIGHT_YELLOW),
        ("任务闭环", "检索候选 -> 选可观察目标位姿 -> 全局拓扑路由 -> 局部安全执行", LIGHT_BLUE),
    ]
    data = []
    for idx, (label, detail, fill) in enumerate(stages):
        data.append([Paragraph(f"<b>{esc(label)}</b>", styles["TableCN"]), Paragraph(esc(detail), styles["TableCN"])])
        if idx < len(stages) - 1:
            data.append([Paragraph("↓", ParagraphStyle("arrow", parent=styles["TableCN"], alignment=TA_CENTER, fontSize=11, textColor=colors.HexColor("#456B86"))), ""])
    table = Table(data, colWidths=[35*mm, 125*mm], hAlign="CENTER")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for idx, (_, _, fill) in enumerate(stages):
        commands.append(("BACKGROUND", (0, idx * 2), (-1, idx * 2), fill))
        if idx < len(stages) - 1:
            commands.append(("SPAN", (0, idx * 2 + 1), (1, idx * 2 + 1)))
            commands.append(("LINEBELOW", (0, idx * 2 + 1), (1, idx * 2 + 1), 0, colors.white))
    table.setStyle(TableStyle(commands))
    return [table, Paragraph("图 1. 长期稀疏世界模型与短期稠密执行缓存分离", styles["CaptionCN"])]


def split_table(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_sep(line):
    return bool(re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?", line))


def make_table(rows):
    data = [split_table(row) for row in rows if not is_sep(row)]
    cols = max(len(row) for row in data)
    widths = [160*mm / cols] * cols
    result = []
    for ridx, row in enumerate(data):
        result.append([Paragraph(inline_markup(row[c] if c < len(row) else ""), styles["TableHeadCN" if ridx == 0 else "TableCN"]) for c in range(cols)])
    table = Table(result, colWidths=widths, repeatRows=1, hAlign="CENTER")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    table.setStyle(TableStyle(commands))
    return table


def title_page(story):
    story.append(Spacer(1, 28*mm))
    story.append(Paragraph("技术方案", ParagraphStyle("Kicker", parent=styles["BodyText"], fontName="SimSun", fontSize=10.5, alignment=TA_CENTER, textColor=BLUE, spaceAfter=8)))
    story.append(Paragraph("单 RGB-D 双目相机 + IMU<br/>语义世界稀疏三维建模与导航", styles["TitleCN"]))
    story.append(Paragraph("概念设计、原型实施与验证基线", styles["SubtitleCN"]))
    meta = Table([
        [Paragraph("文档版本", styles["TableHeadCN"]), Paragraph("0.2", styles["TableCN"])],
        [Paragraph("适用范围", styles["TableHeadCN"]), Paragraph("室内语义建图、跨房间/楼层导航、对象检索", styles["TableCN"])],
        [Paragraph("日期", styles["TableHeadCN"]), Paragraph("2026-08-27", styles["TableCN"])],
    ], colWidths=[42*mm, 118*mm], hAlign="CENTER")
    meta.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.35, GRID), ("BACKGROUND", (0,0), (0,-1), LIGHT_GRAY), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story.append(meta)
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph("核心判断：地图内全局坐标可由视觉、深度、IMU 与回环稳定维护；绝对建筑坐标仍需要外部基准。", styles["BodyLead"]))
    story.append(PageBreak())


def toc(story, headings):
    story.append(Paragraph("阅读导航", styles["H1CN"]))
    for h in headings:
        story.append(Paragraph("• " + inline_markup(h), styles["TOCCN"]))
    story.append(PageBreak())


def build():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    headings = [line[3:] for line in lines if line.startswith("## ")]
    story = []
    title_page(story)
    toc(story, headings)
    i = 0
    flow_added = False
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            i += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline_markup(line[3:]), styles["H1CN"]))
            if line.startswith("## 2. 总体架构") and not flow_added:
                story.extend(flow_diagram())
                flow_added = True
            i += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(inline_markup(line[4:]), styles["H2CN"]))
            i += 1
            continue
        if line.startswith("#### "):
            story.append(Paragraph(inline_markup(line[5:]), styles["H3CN"]))
            i += 1
            continue
        if line.startswith("```"):
            fence = line[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(esc(lines[i]))
                i += 1
            if fence == "mermaid":
                i += 1
                continue
            code_table = Table([[Paragraph("<br/>".join(code), styles["CodeCN"])]], colWidths=[160*mm])
            code_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F7F9FB")), ("BOX", (0,0), (-1,-1), 0.35, GRID), ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
            story.append(code_table)
            story.append(Spacer(1, 3))
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            story.append(make_table(rows))
            story.append(Spacer(1, 4))
            continue
        if re.match(r"^[-*] ", line):
            story.append(Paragraph("• " + inline_markup(line[2:]), styles["BodyCN"]))
            i += 1
            continue
        if re.match(r"^\d+\. ", line):
            story.append(Paragraph(inline_markup(re.sub(r"^\d+\. ", "", line)), styles["BodyCN"]))
            i += 1
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip() or nxt.startswith(("#", "```", "|")) or re.match(r"^[-*] ", nxt) or re.match(r"^\d+\. ", nxt):
                break
            para.append(nxt.strip())
            i += 1
        text = " ".join(para)
        story.append(Paragraph(inline_markup(text), styles["BodyLead" if text.startswith(("本方案将目标定义为：", "将项目第一版定义为")) else "BodyCN"]))

    ReportDoc(str(OUTPUT)).build(story)


if __name__ == "__main__":
    build()
