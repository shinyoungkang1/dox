"""
Convert a DoxDocument to a PDF file.

Handles all .dox element types including:
  - Headings (H1-H6 with scaled font sizes)
  - Paragraphs with inline formatting (bold, italic, code)
  - Tables with borders and header styling
  - Code blocks with monospace font and gray background
  - Math blocks (rendered as styled text)
  - Figures (embedded if file exists, placeholder otherwise)
  - Lists (ordered and unordered with proper indentation)
  - Page breaks
  - Footnotes
  - Form fields (rendered as text)
  - Annotations, Charts, CrossRefs (placeholder rendering)

Usage:
    from dox.converters.to_pdf import to_pdf, to_pdf_bytes
    to_pdf(doc, "output.pdf")
    raw_bytes = to_pdf_bytes(doc)
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from dox.models.document import DoxDocument
from dox.models.elements import (
    Annotation,
    Blockquote,
    Chart,
    CodeBlock,
    CrossRef,
    Element,
    Figure,
    Footnote,
    FormField,
    Heading,
    HorizontalRule,
    KeyValuePair,
    ListBlock,
    MathBlock,
    PageBreak,
    Paragraph,
    Table,
)


def to_pdf(
    doc: DoxDocument,
    output_path: str | Path,
    *,
    page_width: float = 595.27,   # A4 in points (8.27")
    page_height: float = 841.89,  # A4 in points (11.69")
    margin: float = 72.0,         # 1 inch
) -> Path:
    """
    Convert a DoxDocument to a PDF file.

    Args:
        doc: The DoxDocument to convert.
        output_path: File path for the output PDF.
        page_width: Page width in points (72 points = 1 inch).
        page_height: Page height in points.
        margin: Page margins in points (all sides).

    Returns:
        Path to the created PDF file.
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph as RLParagraph, Spacer,
            Table as RLTable, TableStyle, Preformatted, Image,
            PageBreak as RLPageBreak, KeepTogether,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise ImportError(
            "reportlab is required: pip install reportlab"
        )

    output_path = Path(output_path)
    pdf_doc = SimpleDocTemplate(
        str(output_path),
        pagesize=(page_width, page_height),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    styles = _build_styles()
    story: list[Any] = []

    for element in doc.elements:
        flowables = _element_to_flowables(element, styles)
        story.extend(flowables)

    # Build PDF
    if not story:
        # Empty doc — add a blank paragraph so reportlab doesn't error
        from reportlab.platypus import Paragraph as RLParagraph
        story.append(RLParagraph("&nbsp;", styles["body"]))

    pdf_doc.build(story)
    return output_path


def to_pdf_bytes(doc: DoxDocument) -> bytes:
    """
    Convert a DoxDocument to PDF bytes in memory.

    Returns:
        Raw PDF file bytes.
    """
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph as RLParagraph
    except ImportError:
        raise ImportError("reportlab is required: pip install reportlab")

    buf = io.BytesIO()
    try:
        pdf_doc = SimpleDocTemplate(
            buf,
            pagesize=(595.27, 841.89),
            leftMargin=72,
            rightMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        styles = _build_styles()
        story: list[Any] = []

        for element in doc.elements:
            flowables = _element_to_flowables(element, styles)
            story.extend(flowables)

        if not story:
            story.append(RLParagraph("&nbsp;", styles["body"]))

        pdf_doc.build(story)
        return buf.getvalue()
    finally:
        buf.close()


# ------------------------------------------------------------------
# Styles
# ------------------------------------------------------------------

def _build_styles() -> dict[str, Any]:
    """Build a dictionary of ReportLab ParagraphStyles."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    base = getSampleStyleSheet()
    styles: dict[str, Any] = {}

    # Body text
    styles["body"] = ParagraphStyle(
        "DoxBody",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
        spaceAfter=8,
    )

    # Headings
    heading_sizes = {1: 24, 2: 20, 3: 16, 4: 14, 5: 12, 6: 11}
    heading_space = {1: 18, 2: 14, 3: 12, 4: 10, 5: 8, 6: 6}
    for level in range(1, 7):
        styles[f"h{level}"] = ParagraphStyle(
            f"DoxH{level}",
            parent=base["Normal"],
            fontSize=heading_sizes[level],
            leading=heading_sizes[level] + 4,
            spaceBefore=heading_space[level],
            spaceAfter=heading_space[level] // 2,
            fontName="Helvetica-Bold",
        )

    # Code
    styles["code"] = ParagraphStyle(
        "DoxCode",
        parent=base["Normal"],
        fontName="Courier",
        fontSize=9,
        leading=12,
        spaceAfter=8,
        backColor=colors.Color(0.96, 0.96, 0.96),
        leftIndent=12,
        rightIndent=12,
    )

    # Math
    styles["math"] = ParagraphStyle(
        "DoxMath",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
        alignment=TA_CENTER,
        spaceAfter=8,
        fontName="Helvetica-Oblique",
    )

    # Caption
    styles["caption"] = ParagraphStyle(
        "DoxCaption",
        parent=base["Normal"],
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        fontName="Helvetica-Oblique",
        textColor=colors.Color(0.4, 0.4, 0.4),
        spaceAfter=8,
    )

    # Footnote
    styles["footnote"] = ParagraphStyle(
        "DoxFootnote",
        parent=base["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.Color(0.33, 0.33, 0.33),
    )

    # List item
    styles["list_bullet"] = ParagraphStyle(
        "DoxListBullet",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
        leftIndent=24,
        bulletIndent=12,
    )

    styles["list_number"] = ParagraphStyle(
        "DoxListNumber",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
        leftIndent=24,
        bulletIndent=12,
    )

    # Annotation
    styles["annotation"] = ParagraphStyle(
        "DoxAnnotation",
        parent=base["Normal"],
        fontSize=10,
        leading=13,
        textColor=colors.Color(0.53, 0.53, 0.0),
        backColor=colors.Color(1.0, 0.95, 0.8),
    )

    # Form field
    styles["form"] = ParagraphStyle(
        "DoxForm",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
    )

    # Blockquote
    styles["blockquote"] = ParagraphStyle(
        "DoxBlockquote",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
        leftIndent=24,
        borderColor=colors.Color(0.8, 0.8, 0.8),
        borderWidth=1,
        borderPadding=12,
        borderLeft=3,
        borderLeftColor=colors.Color(0.5, 0.5, 0.5),
        spaceAfter=8,
        textColor=colors.Color(0.4, 0.4, 0.4),
    )

    return styles


# ------------------------------------------------------------------
# Element → Flowables
# ------------------------------------------------------------------

def _element_to_flowables(element: Element, styles: dict) -> list[Any]:
    """Convert a .dox element to a list of ReportLab flowables."""
    from reportlab.platypus import (
        Paragraph as RLParagraph, Spacer, Preformatted,
        PageBreak as RLPageBreak, Image,
    )

    if isinstance(element, PageBreak):
        return [RLPageBreak()]

    elif isinstance(element, HorizontalRule):
        from reportlab.lib import colors
        from reportlab.platypus import Table as RLTable, TableStyle
        # Create a simple 1x1 table with a line to render a horizontal rule
        table = RLTable([[""], ], colWidths=[None])
        table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return [Spacer(1, 0.1 * 72), table, Spacer(1, 0.1 * 72)]

    elif isinstance(element, Heading):
        level = min(max(element.level, 1), 6)
        text = _escape_xml(element.text or "")
        return [RLParagraph(text, styles[f"h{level}"])]

    elif isinstance(element, Paragraph):
        text = _inline_to_rl(element.text or "")
        return [RLParagraph(text, styles["body"])]

    elif isinstance(element, Blockquote):
        text = _inline_to_rl(element.text or "")
        return [RLParagraph(text, styles["blockquote"])]

    elif isinstance(element, Table):
        return _table_to_flowables(element, styles)

    elif isinstance(element, CodeBlock):
        # Use Preformatted for monospace code
        code_text = _escape_xml(element.code or "")
        return [Preformatted(code_text, styles["code"])]

    elif isinstance(element, MathBlock):
        expr = _escape_xml(element.expression or "")
        return [RLParagraph(f"<i>{expr}</i>", styles["math"])]

    elif isinstance(element, Figure):
        return _figure_to_flowables(element, styles)

    elif isinstance(element, ListBlock):
        return _list_to_flowables(element, styles)

    elif isinstance(element, Footnote):
        text = _escape_xml(element.text or "")
        return [RLParagraph(
            f"<super>{element.number}</super> {text}",
            styles["footnote"],
        )]

    elif isinstance(element, FormField):
        name = _escape_xml(element.field_name or "")
        val = _escape_xml(element.value or "")
        return [RLParagraph(f"<b>{name}:</b> {val}", styles["form"])]

    elif isinstance(element, Chart):
        return [RLParagraph(
            f"<i>[Chart: {_escape_xml(element.chart_type)}]</i>",
            styles["caption"],
        )]

    elif isinstance(element, Annotation):
        text = _escape_xml(element.text)
        atype = _escape_xml(element.annotation_type)
        return [RLParagraph(f"[{atype}] {text}", styles["annotation"])]

    elif isinstance(element, KeyValuePair):
        key = _escape_xml(element.key)
        value = _escape_xml(element.value)
        return [RLParagraph(f"<b>{key}:</b> {value}", styles["body"])]

    elif isinstance(element, CrossRef):
        return [RLParagraph(
            f"<i>[→ {_escape_xml(element.ref_type)}:{_escape_xml(element.ref_id)}]</i>",
            styles["body"],
        )]

    return []


def _table_to_flowables(element: Table, styles: dict) -> list[Any]:
    """Convert a .dox Table to ReportLab Table flowables."""
    from reportlab.platypus import (
        Paragraph as RLParagraph, Table as RLTable, TableStyle,
    )
    from reportlab.lib import colors

    flowables: list[Any] = []

    # Caption above table
    if element.caption:
        flowables.append(RLParagraph(
            f"<i>{_escape_xml(element.caption)}</i>",
            styles["caption"],
        ))

    if not element.rows:
        return flowables

    # Build table data — ReportLab handles merging via SPAN commands
    num_rows = element.num_rows
    num_cols = element.num_cols
    if num_rows == 0 or num_cols == 0:
        return flowables

    # Initialize grid with empty strings
    grid: list[list[str]] = [["" for _ in range(num_cols)] for _ in range(num_rows)]
    span_commands: list[tuple] = []
    header_row_count = 0

    occupied: set[tuple[int, int]] = set()

    for r_idx, row in enumerate(element.rows):
        if row.is_header:
            header_row_count = r_idx + 1

        semantic_c_idx = 0
        for cell in row.cells:
            c_idx = semantic_c_idx
            if (r_idx, c_idx) in occupied:
                semantic_c_idx += max(1, cell.colspan)
                continue

            grid[r_idx][c_idx] = cell.text

            # Handle spans
            end_r = r_idx + cell.rowspan - 1
            end_c = c_idx + cell.colspan - 1
            end_r = min(end_r, num_rows - 1)
            end_c = min(end_c, num_cols - 1)

            if cell.colspan > 1 or cell.rowspan > 1:
                # ReportLab SPAN: (col_start, row_start), (col_end, row_end)
                span_commands.append(
                    ('SPAN', (c_idx, r_idx), (end_c, end_r))
                )
                for mr in range(r_idx, end_r + 1):
                    for mc in range(c_idx, end_c + 1):
                        if (mr, mc) != (r_idx, c_idx):
                            occupied.add((mr, mc))
            semantic_c_idx += max(1, cell.colspan)

    # Convert to Paragraph objects for wrapping
    table_data = []
    for row_data in grid:
        table_data.append([
            RLParagraph(_escape_xml(cell), styles["body"]) if cell else ""
            for cell in row_data
        ])

    # Create table
    rl_table = RLTable(table_data, repeatRows=header_row_count or 0)

    # Styling
    style_commands = [
        ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]

    # Header styling
    if header_row_count > 0:
        style_commands.extend([
            ('BACKGROUND', (0, 0), (-1, header_row_count - 1),
             colors.Color(0.92, 0.92, 0.92)),
            ('FONTNAME', (0, 0), (-1, header_row_count - 1), 'Helvetica-Bold'),
        ])

    # Add span commands
    style_commands.extend(span_commands)

    rl_table.setStyle(TableStyle(style_commands))
    flowables.append(rl_table)

    return flowables


def _figure_to_flowables(element: Figure, styles: dict) -> list[Any]:
    """Convert a .dox Figure to flowables (image + caption)."""
    from reportlab.platypus import (
        Paragraph as RLParagraph, Image, Spacer,
    )
    from reportlab.lib.units import inch

    flowables: list[Any] = []
    source = element.source or ""
    img_path = Path(source)

    if img_path.exists() and img_path.suffix.lower() in (
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'
    ):
        try:
            # NOTE: Image dimensions (5x3 inches) are hardcoded for consistency.
            # To support dynamic sizing, consider adding width/height fields to Figure element.
            img = Image(str(img_path), width=5 * inch, height=3 * inch)
            img.hAlign = 'CENTER'
            flowables.append(img)
        except Exception:
            flowables.append(RLParagraph(
                f"<i>[Image: {_escape_xml(source)}]</i>",
                styles["caption"],
            ))
    else:
        flowables.append(RLParagraph(
            f"<i>[Image: {_escape_xml(source)}]</i>",
            styles["caption"],
        ))

    if element.caption:
        flowables.append(RLParagraph(
            f"<i>{_escape_xml(element.caption)}</i>",
            styles["caption"],
        ))

    return flowables


def _list_to_flowables(element: ListBlock, styles: dict) -> list[Any]:
    """Convert a .dox ListBlock to flowables."""
    from reportlab.platypus import Paragraph as RLParagraph

    flowables: list[Any] = []
    for idx, item in enumerate(element.items):
        if element.ordered:
            marker = f"{element.start + idx}."
            text = f"<b>{marker}</b> {_inline_to_rl(item.text)}"
            flowables.append(RLParagraph(text, styles["list_number"]))
        else:
            text = f"• {_inline_to_rl(item.text)}"
            flowables.append(RLParagraph(text, styles["list_bullet"]))

        # Handle nested items with indentation
        for child in item.children:
            if element.ordered:
                child_marker = f"{element.start + idx + 1}."
                text = f"&nbsp;&nbsp;<b>{child_marker}</b> {_inline_to_rl(child.text)}"
                flowables.append(RLParagraph(text, styles["list_number"]))
            else:
                text = f"&nbsp;&nbsp;◦ {_inline_to_rl(child.text)}"
                flowables.append(RLParagraph(text, styles["list_bullet"]))

    return flowables


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _escape_xml(text: str) -> str:
    """Escape text for ReportLab XML paragraphs."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _inline_to_rl(text: str) -> str:
    """Convert basic Markdown inline formatting to ReportLab XML."""
    # Escape first
    t = _escape_xml(text)

    # Bold: **text** → <b>text</b>
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)

    # Italic: *text* → <i>text</i>
    t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)

    # Code: `text` → <font name="Courier">text</font>
    t = re.sub(r'`(.+?)`', r'<font name="Courier" size="9">\1</font>', t)

    # Links: [text](url) → <u><font color="blue">text</font></u>
    # Security: only allow safe URL schemes to prevent XSS via javascript: URLs
    t = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: _safe_link_rl(m.group(1), m.group(2)),
        t,
    )

    return t


def _safe_link_rl(text: str, url: str) -> str:
    """Safely render a link in ReportLab XML only if the URL scheme is safe."""
    safe_schemes = ("http://", "https://", "mailto:", "#")
    url_lower = url.lower()
    if any(url_lower.startswith(scheme) for scheme in safe_schemes):
        # URL is already XML-escaped from _escape_xml()
        return f'<u><font color="#0056B3">{text}</font></u>'
    # Unsafe URL: render as plain text
    return text
