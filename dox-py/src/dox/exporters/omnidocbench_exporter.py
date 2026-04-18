"""
OmniDocBench → .dox exporter.

Converts OmniDocBench JSON annotations (CVPR 2025 benchmark) into
DoxDocument objects, enabling testing against real-world ground truth data.

The annotation format is per-page JSON with layout_dets containing
element bounding boxes and recognized content in text/html/latex.

Usage:
    from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox

    import json
    with open("OmniDocBench.json") as f:
        pages = json.load(f)

    # Convert a single page
    doc = omnidocbench_page_to_dox(pages[0])

    # Convert all pages into a single multi-page document
    doc = omnidocbench_to_dox(pages[:5])
"""

from __future__ import annotations

import re
from typing import Any

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    BoundingBox,
    CodeBlock,
    Figure,
    Footnote,
    Heading,
    MathBlock,
    PageBreak,
    Paragraph,
    Table,
    TableCell,
    TableRow,
)
from dox.models.metadata import Confidence, Metadata, Provenance
from dox.models.spatial import SpatialAnnotation, SpatialBlock


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

# Map OmniDocBench categories to .dox element types
_CATEGORY_MAP = {
    "title": "heading",
    "text_block": "paragraph",
    "table": "table",
    "equation_isolated": "math",
    "equation_semantic": "math",
    "figure": "figure",
    "figure_caption": "paragraph",
    "table_caption": "paragraph",
    "table_footnote": "footnote",
    "figure_footnote": "footnote",
    "page_footnote": "footnote",
    "header": "paragraph",
    "footer": "paragraph",
    "page_number": "skip",
    "abandon": "skip",
    "text_mask": "skip",
    "equation_caption": "paragraph",
    "reference": "paragraph",
    "code_txt": "code",
    "list_group": "paragraph",
}


def omnidocbench_to_dox(
    pages: list[dict[str, Any]],
    *,
    source: str = "OmniDocBench",
    include_spatial: bool = True,
    grid_size: int = 1000,
) -> DoxDocument:
    """
    Convert multiple OmniDocBench pages into a single multi-page DoxDocument.

    Args:
        pages: List of OmniDocBench page annotation dicts.
        source: Source identifier for frontmatter.
        include_spatial: Whether to generate Layer 1 spatial annotations.
        grid_size: Normalized grid size for bounding boxes.

    Returns:
        A DoxDocument with all pages, including PageBreak markers.
    """
    doc = DoxDocument()
    doc.frontmatter = Frontmatter(
        version="1.0",
        source=source,
        pages=len(pages),
        lang=_detect_language(pages),
    )

    for i, page in enumerate(pages):
        if i > 0:
            doc.add_element(PageBreak(from_page=i, to_page=i + 1))

        page_info = page.get("page_info", {})
        page_no = page_info.get("page_no", i) + 1  # OmniDocBench is 0-indexed
        page_w = page_info.get("width", grid_size)
        page_h = page_info.get("height", grid_size)

        # Sort elements by reading order (handle None values)
        layout_dets = sorted(
            page.get("layout_dets", []),
            key=lambda d: d.get("order") if d.get("order") is not None else 999
        )

        spatial_block = SpatialBlock(
            page=page_no,
            grid_width=grid_size,
            grid_height=grid_size,
        ) if include_spatial else None

        for det in layout_dets:
            cat = det.get("category_type", "")
            mapped = _CATEGORY_MAP.get(cat, "paragraph")

            if mapped == "skip":
                continue

            # Build element
            el = _convert_element(det, mapped, page_no)
            if el is not None:
                doc.add_element(el)

            # Build spatial annotation
            if spatial_block is not None:
                poly = det.get("poly", [])
                if len(poly) >= 4:
                    bbox = _poly_to_normalized_bbox(poly, page_w, page_h, grid_size)
                    text_preview = _get_text_preview(det)
                    spatial_block.annotations.append(
                        SpatialAnnotation(line_text=text_preview, bbox=bbox)
                    )

        if spatial_block and spatial_block.annotations:
            doc.spatial_blocks.append(spatial_block)

    # Build metadata
    doc.metadata = Metadata(
        extracted_by="OmniDocBench ground truth",
        confidence=Confidence(overall=1.0),
        provenance=Provenance(
            source_hash="",
            extraction_pipeline=["OmniDocBench-v1.5"],
        ),
    )

    return doc


def omnidocbench_page_to_dox(
    page: dict[str, Any],
    **kwargs: Any,
) -> DoxDocument:
    """Convert a single OmniDocBench page to a DoxDocument."""
    return omnidocbench_to_dox([page], **kwargs)


# ---------------------------------------------------------------------------
# Element conversion
# ---------------------------------------------------------------------------

def _convert_element(
    det: dict[str, Any],
    mapped_type: str,
    page_no: int,
) -> Any:
    """Convert a single OmniDocBench layout detection to a .dox Element."""
    text = det.get("text", "")

    if mapped_type == "heading":
        # Heuristic: detect heading level from text or default to 2
        level = _detect_heading_level(text, det)
        return Heading(level=level, text=text.strip(), page=page_no)

    elif mapped_type == "paragraph":
        if text.strip():
            return Paragraph(text=text.strip(), page=page_no)

    elif mapped_type == "table":
        return _convert_table(det, page_no)

    elif mapped_type == "math":
        latex = det.get("latex", text)
        if latex:
            # Strip existing $$ delimiters — .dox serializer adds its own
            expr = latex.strip()
            if expr.startswith("$$") and expr.endswith("$$"):
                expr = expr[2:-2].strip()
            elif expr.startswith("$") and expr.endswith("$"):
                expr = expr[1:-1].strip()
            if expr:
                return MathBlock(expression=expr, display_mode=True, page=page_no)

    elif mapped_type == "figure":
        anno_id = str(det.get("anno_id", ""))
        return Figure(
            caption="",
            source=anno_id or "figure",
            figure_id=anno_id or None,
            page=page_no,
        )

    elif mapped_type == "footnote":
        if text.strip():
            return Footnote(number=0, text=text.strip(), page=page_no)

    elif mapped_type == "code":
        if text.strip():
            return CodeBlock(code=text.strip(), page=page_no)

    return None


def _convert_table(det: dict[str, Any], page_no: int) -> Table | None:
    """
    Convert an OmniDocBench table annotation to a .dox Table.

    OmniDocBench provides table content in HTML format.
    """
    html = det.get("html", "")
    if not html:
        return None

    table = Table(page=page_no)
    table.table_id = det.get("anno_id")
    if table.table_id:
        table.element_id = table.table_id

    # Parse HTML table
    rows = _parse_html_table(html)
    if not rows:
        return None

    for r_idx, row_cells in enumerate(rows):
        cells = []
        for cell_text, is_header, colspan, rowspan in row_cells:
            cells.append(TableCell(
                text=cell_text,
                is_header=is_header,
                colspan=colspan,
                rowspan=rowspan,
            ))
        table.rows.append(TableRow(
            cells=cells,
            is_header=(r_idx == 0 and any(c.is_header for c in cells)),
        ))

    return table


def _parse_html_table(html: str) -> list[list[tuple[str, bool, int, int]]]:
    """
    Parse a simple HTML table into a list of rows.

    Each row is a list of (text, is_header, colspan, rowspan) tuples.
    """
    rows: list[list[tuple[str, bool, int, int]]] = []

    # Find all <tr>...</tr>
    tr_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    # Find <td> or <th> with optional attributes
    cell_pattern = re.compile(
        r"<(td|th)([^>]*)>(.*?)</(?:td|th)>", re.DOTALL | re.IGNORECASE
    )
    colspan_pattern = re.compile(r'colspan\s*=\s*["\']?(\d+)', re.IGNORECASE)
    rowspan_pattern = re.compile(r'rowspan\s*=\s*["\']?(\d+)', re.IGNORECASE)

    for tr_match in tr_pattern.finditer(html):
        row_html = tr_match.group(1)
        row: list[tuple[str, bool, int, int]] = []

        for cell_match in cell_pattern.finditer(row_html):
            tag = cell_match.group(1).lower()
            attrs = cell_match.group(2)
            content = cell_match.group(3)

            # Strip nested HTML tags but preserve text
            text = re.sub(r"<[^>]+>", "", content).strip()
            is_header = tag == "th"

            colspan = 1
            cs_match = colspan_pattern.search(attrs)
            if cs_match:
                colspan = int(cs_match.group(1))

            rowspan = 1
            rs_match = rowspan_pattern.search(attrs)
            if rs_match:
                rowspan = int(rs_match.group(1))

            row.append((text, is_header, colspan, rowspan))

        if row:
            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _poly_to_normalized_bbox(
    poly: list[float],
    page_w: int | float,
    page_h: int | float,
    grid_size: int,
) -> BoundingBox:
    """Convert an 8-value polygon to a normalized BoundingBox."""
    xs = [poly[i] for i in range(0, min(len(poly), 8), 2)]
    ys = [poly[i] for i in range(1, min(len(poly), 8), 2)]
    # Clamp coordinates to non-negative to handle floating-point rounding
    x1 = max(0, int(min(xs) / page_w * grid_size))
    y1 = max(0, int(min(ys) / page_h * grid_size))
    x2 = max(0, int(max(xs) / page_w * grid_size))
    y2 = max(0, int(max(ys) / page_h * grid_size))
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


def _detect_heading_level(text: str, det: dict[str, Any]) -> int:
    """Heuristic heading level detection."""
    attribute = det.get("attribute", {})
    if isinstance(attribute, dict):
        level = attribute.get("level")
        if level and isinstance(level, int):
            return min(max(level, 1), 6)

    # Heuristic: shorter titles = higher level
    text_len = len(text.strip())
    if text_len < 30:
        return 1
    elif text_len < 60:
        return 2
    return 3


def _detect_language(pages: list[dict[str, Any]]) -> str:
    """Detect document language from page info."""
    for page in pages[:3]:
        lang = page.get("page_info", {}).get("page_attribute", {}).get("language", "")
        if lang:
            return lang[:2]  # "english" → "en", "chinese" → "ch"
    return "en"


def _get_text_preview(det: dict[str, Any]) -> str:
    """Get a short text preview for spatial annotation."""
    text = det.get("text", "")
    if not text:
        text = det.get("latex", "")
    if not text:
        text = det.get("category_type", "")
    return text[:80]
