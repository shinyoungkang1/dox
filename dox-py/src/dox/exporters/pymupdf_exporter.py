"""
PyMuPDF → .dox exporter.

Converts real PDF files to DoxDocument using PyMuPDF (fitz) for extraction.
This is a REAL extraction pipeline — no ground truth, just raw PDF parsing.

PyMuPDF extracts:
  - Text blocks with bounding boxes
  - Page dimensions
  - Font information (size, bold, italic)
  - Image locations
  - Basic table detection via text alignment

This exporter demonstrates what .dox can do with real extractor output,
including cross-page handling, spatial annotations, and structure inference.

Usage:
    from dox.exporters.pymupdf_exporter import pdf_to_dox
    doc = pdf_to_dox("path/to/file.pdf")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    BoundingBox,
    Figure,
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

# Grid size for normalized bounding boxes
GRID_SIZE = 1000


def pdf_to_dox(
    pdf_path: str | Path,
    *,
    detect_tables: bool = True,
    detect_headings: bool = True,
    include_spatial: bool = True,
    include_images: bool = True,
) -> DoxDocument:
    """
    Convert a PDF file to a DoxDocument using PyMuPDF.

    Args:
        pdf_path: Path to the PDF file.
        detect_tables: Attempt to detect and structure tables.
        detect_headings: Use font size heuristics to detect headings.
        include_spatial: Generate Layer 1 spatial annotations.
        include_images: Include image references.

    Returns:
        A DoxDocument with content extracted from the PDF.
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required: pip install pymupdf")

    pdf_path = Path(pdf_path)
    pdf_doc = fitz.open(str(pdf_path))

    doc = DoxDocument()
    doc.frontmatter = Frontmatter(
        version="1.0",
        source=pdf_path.name,
        pages=pdf_doc.page_count,
        lang="en",
    )

    all_font_sizes: list[float] = []

    # First pass: collect font size statistics for heading detection
    if detect_headings:
        for page in pdf_doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            all_font_sizes.append(span.get("size", 11))

    # Compute font size thresholds
    if all_font_sizes:
        avg_size = sum(all_font_sizes) / len(all_font_sizes)
        median_size = sorted(all_font_sizes)[len(all_font_sizes) // 2]
        body_size = median_size
    else:
        body_size = 11.0

    # Second pass: extract content
    for page_idx, page in enumerate(pdf_doc):
        page_no = page_idx + 1

        if page_idx > 0:
            doc.add_element(PageBreak(from_page=page_idx, to_page=page_no))

        page_w = page.rect.width
        page_h = page.rect.height

        # Get structured text blocks
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        spatial_block = SpatialBlock(
            page=page_no,
            grid_width=GRID_SIZE,
            grid_height=GRID_SIZE,
        ) if include_spatial else None

        # Extract images
        if include_images:
            image_list = page.get_images(full=True)
            for img_idx, img in enumerate(image_list):
                xref = img[0]
                # Get image bbox
                img_rects = page.get_image_rects(xref)
                for rect in img_rects:
                    fig = Figure(
                        caption="",
                        source=f"image-p{page_no}-{img_idx}",
                        figure_id=f"img-p{page_no}-{img_idx}",
                        page=page_no,
                    )
                    doc.add_element(fig)

                    if spatial_block:
                        bbox = _rect_to_bbox(rect, page_w, page_h)
                        spatial_block.annotations.append(
                            SpatialAnnotation(line_text=f"[image]", bbox=bbox)
                        )

        # Process text blocks
        table_detector = _TableDetector() if detect_tables else None

        for block in blocks:
            if block.get("type") != 0:  # Skip image blocks
                continue

            block_bbox = block.get("bbox", (0, 0, 0, 0))
            block_text = ""
            block_font_size = body_size
            is_bold = False

            lines = block.get("lines", [])
            line_texts = []

            for line in lines:
                line_text = ""
                for span in line.get("spans", []):
                    line_text += span.get("text", "")
                    block_font_size = max(block_font_size, span.get("size", body_size))
                    flags = span.get("flags", 0)
                    if flags & 2 ** 4:  # bold flag
                        is_bold = True
                line_texts.append(line_text.strip())

            block_text = " ".join(t for t in line_texts if t)

            if not block_text.strip():
                continue

            # Feed to table detector
            if table_detector:
                table_detector.add_block(block, block_text, page_no)

            # Classify block
            element = None

            if detect_headings and _is_heading(block_font_size, body_size, block_text, is_bold):
                level = _heading_level(block_font_size, body_size)
                element = Heading(level=level, text=block_text.strip(), page=page_no)
            elif _looks_like_math(block_text):
                element = MathBlock(
                    expression=block_text.strip(),
                    display_mode=True,
                    page=page_no,
                )
            else:
                element = Paragraph(text=block_text.strip(), page=page_no)

            if element:
                doc.add_element(element)

            # Spatial annotation
            if spatial_block:
                bbox = _tuple_to_bbox(block_bbox, page_w, page_h)
                spatial_block.annotations.append(
                    SpatialAnnotation(line_text=block_text[:80], bbox=bbox)
                )

        # Emit detected tables
        if table_detector:
            tables = table_detector.flush()
            for table in tables:
                doc.add_element(table)

        if spatial_block and spatial_block.annotations:
            doc.spatial_blocks.append(spatial_block)

    # Metadata
    pdf_meta = pdf_doc.metadata or {}
    doc.metadata = Metadata(
        extracted_by="PyMuPDF",
        confidence=Confidence(overall=0.7),  # Honest: PyMuPDF is basic
        provenance=Provenance(
            source_hash="",
            extraction_pipeline=["PyMuPDF", "dox-pymupdf-exporter"],
        ),
    )

    pdf_doc.close()
    return doc


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

def _is_heading(font_size: float, body_size: float, text: str, is_bold: bool) -> bool:
    """Heuristic: text is a heading if font is significantly larger than body."""
    if len(text.strip()) > 200:  # Too long for a heading
        return False
    if font_size > body_size * 1.3:
        return True
    if is_bold and font_size >= body_size and len(text.strip()) < 80:
        return True
    return False


def _heading_level(font_size: float, body_size: float) -> int:
    """Map font size ratio to heading level."""
    ratio = font_size / max(body_size, 1)
    if ratio > 1.8:
        return 1
    elif ratio > 1.4:
        return 2
    elif ratio > 1.2:
        return 3
    return 4


# ---------------------------------------------------------------------------
# Math detection
# ---------------------------------------------------------------------------

def _looks_like_math(text: str) -> bool:
    """Heuristic: text looks like a mathematical expression."""
    math_indicators = [
        r"\\frac", r"\\sum", r"\\int", r"\\sqrt", r"\\alpha", r"\\beta",
        r"\\begin\{", r"\\end\{", r"\\left", r"\\right",
    ]
    for indicator in math_indicators:
        if re.search(indicator, text):
            return True
    return False


# ---------------------------------------------------------------------------
# Table detection (alignment-based heuristic)
# ---------------------------------------------------------------------------

class _TableDetector:
    """
    Detect tables by looking for aligned text blocks.

    This is a basic heuristic: if multiple consecutive blocks have similar
    x-coordinates for their text segments, they might be table rows.
    """

    def __init__(self):
        self._blocks: list[tuple[dict, str, int]] = []

    def add_block(self, block: dict, text: str, page_no: int):
        self._blocks.append((block, text, page_no))

    def flush(self) -> list[Table]:
        """Analyze collected blocks and return detected tables."""
        # For now, this is a placeholder — real table detection from raw
        # text is extremely hard without visual layout analysis.
        # PyMuPDF's built-in find_tables() is available in newer versions.
        return []


# ---------------------------------------------------------------------------
# Bounding box helpers
# ---------------------------------------------------------------------------

def _rect_to_bbox(rect: Any, page_w: float, page_h: float) -> BoundingBox:
    """Convert a fitz.Rect to a normalized BoundingBox."""
    return BoundingBox(
        x1=int(rect.x0 / page_w * GRID_SIZE),
        y1=int(rect.y0 / page_h * GRID_SIZE),
        x2=int(rect.x1 / page_w * GRID_SIZE),
        y2=int(rect.y1 / page_h * GRID_SIZE),
    )


def _tuple_to_bbox(bbox: tuple, page_w: float, page_h: float) -> BoundingBox:
    """Convert a (x0, y0, x1, y1) tuple to a normalized BoundingBox."""
    x0, y0, x1, y1 = bbox
    return BoundingBox(
        x1=int(x0 / page_w * GRID_SIZE),
        y1=int(y0 / page_h * GRID_SIZE),
        x2=int(x1 / page_w * GRID_SIZE),
        y2=int(y1 / page_h * GRID_SIZE),
    )
