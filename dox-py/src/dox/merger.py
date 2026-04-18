"""
Cross-page element merger for .dox documents.

When documents are extracted from PDFs, elements that span physical page
boundaries arrive as separate fragments — a table whose bottom half is on
the next page, a paragraph that wraps across a page break, or a figure
caption that lands on a different page from the figure.

This module provides utilities to:
  1. **Merge continuation tables** — reassemble tables split across pages.
  2. **Merge split paragraphs** — join paragraph fragments across page breaks.
  3. **Assign page numbers** — populate Element.page from PageBreak markers
     or from spatial block alignment.
  4. **Remove redundant PageBreaks** after merging.

Usage:
    from dox.merger import DoxMerger
    merger = DoxMerger()
    merged_doc = merger.merge(doc)
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from dox.models.document import DoxDocument
from dox.models.elements import (
    Element,
    Heading,
    PageBreak,
    Paragraph,
    Table,
    TableRow,
)
from dox.models.spatial import SpatialBlock


@dataclass
class MergeConfig:
    """Configuration for the cross-page merger."""
    merge_tables: bool = True
    merge_paragraphs: bool = True
    assign_pages: bool = True
    remove_page_breaks: bool = False
    # For paragraph merging — if two paragraph fragments have a similarity
    # ratio above this threshold for their first/last N chars, don't merge
    # (they're distinct paragraphs that happen to be adjacent to a page break).
    paragraph_distinct_threshold: float = 0.9
    # Minimum overlap characters to check for duplicate text at merge boundary
    paragraph_overlap_check: int = 30


@dataclass
class MergeResult:
    """Result of a merge operation."""
    document: DoxDocument
    tables_merged: int = 0
    paragraphs_merged: int = 0
    pages_assigned: int = 0
    page_breaks_removed: int = 0

    @property
    def has_changes(self) -> bool:
        return (self.tables_merged + self.paragraphs_merged +
                self.pages_assigned + self.page_breaks_removed) > 0

    def summary(self) -> str:
        parts = []
        if self.tables_merged:
            parts.append(f"{self.tables_merged} tables merged")
        if self.paragraphs_merged:
            parts.append(f"{self.paragraphs_merged} paragraphs merged")
        if self.pages_assigned:
            parts.append(f"{self.pages_assigned} pages assigned")
        if self.page_breaks_removed:
            parts.append(f"{self.page_breaks_removed} page breaks removed")
        return ", ".join(parts) if parts else "No changes"


class DoxMerger:
    """
    Merge cross-page elements in a DoxDocument.

    The merger works in passes:
      1. Assign page numbers from PageBreak markers.
      2. Merge continuation tables (tables with ``continuation_of`` set).
      3. Merge split paragraphs adjacent to PageBreak markers.
      4. Optionally remove PageBreak elements.
    """

    def __init__(self, config: MergeConfig | None = None):
        self.config = config or MergeConfig()

    def merge(self, doc: DoxDocument) -> MergeResult:
        """
        Merge cross-page elements and return the result.

        The input document is NOT mutated; a deep copy is used.
        """
        merged = deepcopy(doc)
        result = MergeResult(document=merged)

        if self.config.assign_pages:
            result.pages_assigned = self._assign_pages(merged)

        if self.config.merge_tables:
            result.tables_merged = self._merge_tables(merged)

        if self.config.merge_paragraphs:
            result.paragraphs_merged = self._merge_paragraphs(merged)

        if self.config.remove_page_breaks:
            result.page_breaks_removed = self._remove_page_breaks(merged)

        return result

    # ------------------------------------------------------------------
    # Pass 1: Assign page numbers from PageBreak markers
    # ------------------------------------------------------------------

    def _assign_pages(self, doc: DoxDocument) -> int:
        """
        Walk through elements and assign .page based on PageBreak markers.

        If no PageBreaks exist, try to infer from spatial blocks.
        """
        assigned = 0
        current_page = 1

        # First pass: use PageBreak markers
        has_page_breaks = any(isinstance(e, PageBreak) for e in doc.elements)

        if has_page_breaks:
            for el in doc.elements:
                if isinstance(el, PageBreak):
                    current_page = el.to_page
                    continue
                if el.page is None:
                    el.page = current_page
                    assigned += 1
        else:
            # Fallback: try to match elements to spatial blocks by text
            assigned = self._assign_pages_from_spatial(doc)

        return assigned

    def _assign_pages_from_spatial(self, doc: DoxDocument) -> int:
        """
        Assign page numbers by fuzzy-matching element text against spatial
        block annotations.
        """
        if not doc.spatial_blocks:
            return 0

        assigned = 0
        # Build a lookup: page_num → set of line texts
        page_texts: dict[int, set[str]] = {}
        for block in doc.spatial_blocks:
            texts = set()
            for ann in block.annotations:
                if ann.line_text:
                    # Normalize
                    texts.add(ann.line_text.strip().lower()[:60])
            page_texts[block.page] = texts

        for el in doc.elements:
            if el.page is not None:
                continue

            el_text = _get_element_text(el).strip().lower()[:60]
            if not el_text:
                continue

            best_page = None
            best_ratio = 0.0

            for page_num, texts in page_texts.items():
                for t in texts:
                    ratio = SequenceMatcher(None, el_text, t).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_page = page_num

            if best_page is not None and best_ratio > 0.5:
                el.page = best_page
                assigned += 1

        return assigned

    # ------------------------------------------------------------------
    # Pass 2: Merge continuation tables
    # ------------------------------------------------------------------

    def _merge_tables(self, doc: DoxDocument) -> int:
        """
        Find tables with ``continuation_of`` set and merge them into the
        parent table.
        """
        merged_count = 0
        tables_by_id: dict[str, Table] = {}

        # Index tables by ID
        for el in doc.elements:
            if isinstance(el, Table) and el.table_id:
                tables_by_id[el.table_id] = el

        # Find continuations and merge
        to_remove: list[int] = []
        for idx, el in enumerate(doc.elements):
            if isinstance(el, Table) and el.continuation_of:
                parent = tables_by_id.get(el.continuation_of)
                if parent is not None:
                    # Append continuation rows to parent
                    parent.rows.extend(el.rows)
                    # Update page range
                    if parent.page_range and el.page:
                        parent.page_range = (
                            parent.page_range[0],
                            max(parent.page_range[1], el.page),
                        )
                    elif el.page:
                        start = parent.page or 1
                        parent.page_range = (start, el.page)
                    to_remove.append(idx)
                    merged_count += 1

        # Also merge adjacent identical-structure tables across page breaks
        # (common pattern: extractor splits table at page boundary without
        # setting continuation_of)
        i = 0
        while i < len(doc.elements) - 2:
            el = doc.elements[i]
            if isinstance(el, Table) and not el.continuation_of:
                # Check if next element is PageBreak followed by another Table
                # with matching column count and no header rows
                j = i + 1
                if j < len(doc.elements) and isinstance(doc.elements[j], PageBreak):
                    k = j + 1
                    if k < len(doc.elements) and isinstance(doc.elements[k], Table):
                        next_table = doc.elements[k]
                        if (not next_table.continuation_of
                                and el.num_cols == next_table.num_cols
                                and not next_table.header_rows()):
                            # Looks like a split table — merge
                            el.rows.extend(next_table.rows)
                            if el.page and next_table.page:
                                el.page_range = (el.page, next_table.page)
                            to_remove.append(k)
                            merged_count += 1
            i += 1

        # Remove merged continuations (reverse order to preserve indices)
        for idx in sorted(to_remove, reverse=True):
            doc.elements.pop(idx)

        return merged_count

    # ------------------------------------------------------------------
    # Pass 3: Merge split paragraphs
    # ------------------------------------------------------------------

    def _merge_paragraphs(self, doc: DoxDocument) -> int:
        """
        Merge paragraph fragments split across page breaks.

        Pattern: Paragraph → PageBreak → Paragraph where the first paragraph
        doesn't end with sentence-ending punctuation.
        """
        merged_count = 0
        to_remove: list[int] = []
        i = 0

        while i < len(doc.elements) - 2:
            el = doc.elements[i]
            if isinstance(el, Paragraph):
                j = i + 1
                if j < len(doc.elements) and isinstance(doc.elements[j], PageBreak):
                    k = j + 1
                    if k < len(doc.elements) and isinstance(doc.elements[k], Paragraph):
                        para_a = el
                        para_b = doc.elements[k]

                        if self._should_merge_paragraphs(para_a, para_b):
                            # Check for duplicate text at boundary
                            merged_text = self._merge_paragraph_text(
                                para_a.text, para_b.text
                            )
                            para_a.text = merged_text
                            # Keep the earlier page number
                            to_remove.append(k)
                            merged_count += 1
                            i = k + 1
                            continue
            i += 1

        for idx in sorted(to_remove, reverse=True):
            doc.elements.pop(idx)

        return merged_count

    def _should_merge_paragraphs(self, a: Paragraph, b: Paragraph) -> bool:
        """Decide whether two paragraphs across a page break should merge."""
        if not a.text or not b.text:
            return False

        # If first paragraph ends with sentence-ending punctuation, probably distinct
        last_char = a.text.rstrip()[-1] if a.text.rstrip() else ""
        if last_char in ".!?:":
            return False

        # If second paragraph starts with uppercase and first ends with period,
        # likely a new paragraph
        first_char = b.text.lstrip()[0] if b.text.lstrip() else ""
        if first_char.isupper() and last_char in ".!?":
            return False

        # Check if they're too similar (might be duplicates not fragments)
        if len(a.text) > 20 and len(b.text) > 20:
            overlap = min(self.config.paragraph_overlap_check, len(a.text), len(b.text))
            ratio = SequenceMatcher(
                None, a.text[-overlap:], b.text[:overlap]
            ).ratio()
            if ratio > self.config.paragraph_distinct_threshold:
                return False

        return True

    def _merge_paragraph_text(self, text_a: str, text_b: str) -> str:
        """
        Join two paragraph fragments, handling hyphenated line breaks
        and overlapping text.
        """
        a = text_a.rstrip()
        b = text_b.lstrip()

        # Handle word-break hyphenation: "hypothe-" + "sis" → "hypothesis"
        if a.endswith("-"):
            # Check if it's a real hyphenated word or a line-break hyphen
            # Heuristic: if the next fragment starts lowercase, it's a break
            if b and b[0].islower():
                return a[:-1] + b

        # Check for overlapping text at boundary
        overlap_len = min(self.config.paragraph_overlap_check, len(a), len(b))
        for size in range(overlap_len, 5, -1):
            if a.endswith(b[:size]):
                return a + b[size:]

        return a + " " + b

    # ------------------------------------------------------------------
    # Pass 4: Remove PageBreak elements
    # ------------------------------------------------------------------

    def _remove_page_breaks(self, doc: DoxDocument) -> int:
        """Remove all PageBreak elements from the document."""
        before = len(doc.elements)
        doc.elements = [e for e in doc.elements if not isinstance(e, PageBreak)]
        return before - len(doc.elements)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def merge_document(
    doc: DoxDocument,
    *,
    merge_tables: bool = True,
    merge_paragraphs: bool = True,
    assign_pages: bool = True,
    remove_page_breaks: bool = False,
) -> MergeResult:
    """
    Merge cross-page elements in a document.

    Convenience wrapper around DoxMerger.
    """
    config = MergeConfig(
        merge_tables=merge_tables,
        merge_paragraphs=merge_paragraphs,
        assign_pages=assign_pages,
        remove_page_breaks=remove_page_breaks,
    )
    return DoxMerger(config).merge(doc)


def _get_element_text(el: Element) -> str:
    """Get the primary text content of an element."""
    if isinstance(el, (Paragraph, Heading)):
        return el.text
    elif isinstance(el, Table):
        # Use first row text as representative
        if el.rows and el.rows[0].cells:
            return " ".join(c.text for c in el.rows[0].cells)
    return ""
