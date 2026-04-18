"""
Docling → .dox exporter plugin.

Converts a Docling DoclingDocument to a DoxDocument, preserving:
  - Text content and structure (headings, paragraphs, lists)
  - Tables with cell-level data
  - Bounding boxes (spatial annotations)
  - Metadata (extraction provenance, confidence)

Usage:
    from docling.document_converter import DocumentConverter
    from dox.exporters.docling_exporter import docling_to_dox

    converter = DocumentConverter()
    docling_doc = converter.convert("report.pdf").document
    dox_doc = docling_to_dox(docling_doc)

This module is designed to work with Docling >= 2.0 but does NOT import it
at module level. If Docling is not installed, importing this module is safe —
the function will raise ImportError only when called.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    BoundingBox,
    CodeBlock,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Table,
    TableCell,
    TableRow,
)
from dox.models.metadata import Confidence, Metadata, Provenance, VersionEntry
from dox.models.spatial import SpatialAnnotation, SpatialBlock

if TYPE_CHECKING:
    pass  # Docling types would go here


def docling_to_dox(
    docling_doc: Any,
    *,
    source_path: str = "",
    include_spatial: bool = True,
    grid_size: int = 1000,
) -> DoxDocument:
    """
    Convert a Docling DoclingDocument to a DoxDocument.

    Args:
        docling_doc: A docling.datamodel.document.DoclingDocument instance.
        source_path: Original file path (for provenance).
        include_spatial: Whether to generate Layer 1 spatial annotations.
        grid_size: Normalized grid size for bounding boxes.

    Returns:
        A fully populated DoxDocument.

    Raises:
        ImportError: If docling is not installed.
        TypeError: If docling_doc is not a valid Docling document.
    """
    try:
        from docling.datamodel.document import DoclingDocument  # type: ignore
    except ImportError:
        raise ImportError(
            "Docling is required for this exporter. Install with: pip install docling"
        )

    if not isinstance(docling_doc, DoclingDocument):
        raise TypeError(f"Expected DoclingDocument, got {type(docling_doc).__name__}")

    doc = DoxDocument()

    # Frontmatter
    doc.frontmatter = Frontmatter(
        version="1.0",
        source=source_path or getattr(docling_doc, "name", ""),
        pages=getattr(docling_doc, "num_pages", None),
        lang="en",
    )

    # Export content from Docling's document tree
    _export_content(docling_doc, doc)

    # Export spatial annotations if available
    if include_spatial:
        _export_spatial(docling_doc, doc, grid_size)

    # Build metadata
    doc.metadata = _build_metadata(docling_doc, source_path)

    return doc


def _export_content(docling_doc: Any, doc: DoxDocument) -> None:
    """Walk the Docling document tree and convert elements to .dox elements."""
    # Docling exposes content via iterate_items() or the body attribute
    import logging
    logger = logging.getLogger("dox.exporters.docling")

    try:
        items = list(docling_doc.iterate_items())
    except (AttributeError, TypeError) as e:
        logger.warning("iterate_items() failed: %s. Trying markdown fallback.", e)
        try:
            md_text = docling_doc.export_to_markdown()
            _parse_markdown_fallback(md_text, doc)
        except (AttributeError, TypeError) as e2:
            logger.error("Markdown fallback also failed: %s. No content extracted.", e2)
        return

    for item, _level in items:
        item_type = type(item).__name__.lower()

        if "heading" in item_type or "title" in item_type:
            level = getattr(item, "level", 1) or 1
            text = _get_text(item)
            if text:
                doc.add_element(Heading(level=min(level, 6), text=text))

        elif "table" in item_type:
            table = _convert_table(item)
            if table:
                doc.add_element(table)

        elif "code" in item_type:
            code = _get_text(item)
            lang = getattr(item, "language", None)
            doc.add_element(CodeBlock(code=code, language=lang))

        elif "list" in item_type:
            lb = _convert_list(item)
            if lb:
                doc.add_element(lb)

        elif "text" in item_type or "paragraph" in item_type:
            text = _get_text(item)
            if text.strip():
                doc.add_element(Paragraph(text=text))


def _convert_table(item: Any) -> Table | None:
    """Convert a Docling table item to a .dox Table."""
    import logging
    logger = logging.getLogger("dox.exporters.docling")

    try:
        data = item.export_to_dataframe()
    except (AttributeError, TypeError, ValueError) as e:
        logger.debug("Table DataFrame export failed: %s", e)
        data = None

    if data is not None:
        # DataFrame-based conversion
        table = Table()
        # Header row
        header_cells = [TableCell(text=str(col), is_header=True) for col in data.columns]
        table.rows.append(TableRow(cells=header_cells, is_header=True))
        # Data rows
        for _, row in data.iterrows():
            cells = [TableCell(text=str(v)) for v in row]
            table.rows.append(TableRow(cells=cells))
        return table

    # Fallback: try grid-based access
    try:
        grid = item.grid
        table = Table()
        for r_idx, row in enumerate(grid):
            cells = [TableCell(text=str(cell.text), is_header=(r_idx == 0)) for cell in row]
            table.rows.append(TableRow(cells=cells, is_header=(r_idx == 0)))
        return table
    except (AttributeError, TypeError, IndexError) as e:
        logger.debug("Table grid-based access failed: %s", e)

    return None


def _convert_list(item: Any) -> ListBlock | None:
    """Convert a Docling list item to a .dox ListBlock."""
    import logging
    logger = logging.getLogger("dox.exporters.docling")

    try:
        items_data = getattr(item, "items", [])
        items = [ListItem(text=_get_text(li)) for li in items_data]
        if items:
            ordered = getattr(item, "ordered", False)
            return ListBlock(items=items, ordered=ordered)
    except (AttributeError, TypeError) as e:
        logger.debug("List conversion failed: %s", e)
    return None


def _export_spatial(docling_doc: Any, doc: DoxDocument, grid_size: int) -> None:
    """Extract bounding boxes from Docling and create spatial blocks."""
    import logging
    logger = logging.getLogger("dox.exporters.docling")

    try:
        pages = getattr(docling_doc, "pages", {})
    except (AttributeError, TypeError) as e:
        logger.warning("Could not access pages for spatial data: %s", e)
        return

    for page_num, page_data in pages.items():
        block = SpatialBlock(
            page=int(page_num) if isinstance(page_num, (int, str)) else 1,
            grid_width=grid_size,
            grid_height=grid_size,
        )

        try:
            page_width = getattr(page_data, "width", grid_size)
            page_height = getattr(page_data, "height", grid_size)

            for item in getattr(page_data, "items", []):
                bbox_raw = getattr(item, "bbox", None)
                if bbox_raw is not None:
                    # Normalize to grid coordinates
                    try:
                        coords = (
                            bbox_raw
                            if isinstance(bbox_raw, (list, tuple))
                            else [bbox_raw.l, bbox_raw.t, bbox_raw.r, bbox_raw.b]
                        )
                        normalized = BoundingBox(
                            x1=int(coords[0] / page_width * grid_size),
                            y1=int(coords[1] / page_height * grid_size),
                            x2=int(coords[2] / page_width * grid_size),
                            y2=int(coords[3] / page_height * grid_size),
                        )
                        ann = SpatialAnnotation(
                            line_text=_get_text(item)[:80],
                            bbox=normalized,
                        )
                        block.annotations.append(ann)
                    except (TypeError, ValueError, AttributeError, ZeroDivisionError) as e:
                        logger.debug("Bbox normalization failed for item: %s", e)
                        continue
        except (AttributeError, TypeError) as e:
            logger.debug("Spatial extraction failed for page %s: %s", page_num, e)
            continue

        if block.annotations:
            doc.spatial_blocks.append(block)


def _build_metadata(docling_doc: Any, source_path: str) -> Metadata:
    """Build Layer 2 metadata from Docling extraction info."""
    # Try to get version info
    try:
        import docling
        docling_version = getattr(docling, "__version__", "unknown")
    except ImportError:
        docling_version = "unknown"

    # Compute source hash if possible
    source_hash = ""
    if source_path:
        try:
            with open(source_path, "rb") as f:
                source_hash = f"sha256:{hashlib.sha256(f.read()).hexdigest()}"
        except (FileNotFoundError, PermissionError, OSError):
            pass

    return Metadata(
        extracted_by=f"docling-{docling_version} + dox-exporter-0.1.0",
        extracted_at=datetime.now(timezone.utc),
        confidence=Confidence(overall=0.0),  # Docling doesn't expose per-element confidence yet
        provenance=Provenance(
            source_hash=source_hash,
            extraction_pipeline=[f"docling:{docling_version}"],
        ),
        version_history=[
            VersionEntry(
                timestamp=datetime.now(timezone.utc),
                agent=f"docling-{docling_version}",
                action="initial_extraction",
            )
        ],
    )


def _get_text(item: Any) -> str:
    """Safely extract text from a Docling item."""
    for attr in ("text", "content", "value", "raw_text"):
        val = getattr(item, attr, None)
        if val and isinstance(val, str):
            return val
    return str(item) if item else ""


def _parse_markdown_fallback(md_text: str, doc: DoxDocument) -> None:
    """Fallback: parse Docling's Markdown export into .dox elements."""
    from dox.parsers.parser import DoxParser

    temp_doc = DoxParser().parse(md_text)
    doc.elements = temp_doc.elements
