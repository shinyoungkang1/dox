"""
Top-level DoxDocument — the in-memory representation of a .dox file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dox.models.elements import Element, Heading, Paragraph, Table
from dox.models.metadata import Metadata
from dox.models.spatial import SpatialBlock


@dataclass
class Frontmatter:
    """The ---dox ... --- YAML frontmatter block."""
    version: str = "1.0"
    source: str = ""
    pages: int | None = None
    lang: str = "en"
    doc_type: str | None = None  # academic, financial, legal, medical, invoice, form, newspaper, book, presentation, report
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"version": self.version}
        if self.source:
            d["source"] = self.source
        if self.pages is not None:
            d["pages"] = self.pages
        if self.lang:
            d["lang"] = self.lang
        if self.doc_type:
            d["doc_type"] = self.doc_type
        d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Frontmatter:
        fm = cls()
        fm.version = str(d.get("version", "1.0"))
        fm.source = d.get("source", "")
        fm.pages = d.get("pages")
        fm.lang = d.get("lang", "en")
        fm.doc_type = d.get("doc_type")
        known = {"version", "source", "pages", "lang", "doc_type"}
        fm.extra = {k: v for k, v in d.items() if k not in known}
        return fm


@dataclass
class DoxDocument:
    """
    Complete in-memory representation of a .dox file.

    - frontmatter: Layer 0 YAML header
    - elements: ordered list of content blocks (Layer 0)
    - spatial_blocks: page-level spatial annotations (Layer 1)
    - metadata: extraction/provenance metadata (Layer 2)
    """

    frontmatter: Frontmatter = field(default_factory=Frontmatter)
    elements: list[Element] = field(default_factory=list)
    spatial_blocks: list[SpatialBlock] = field(default_factory=list)
    metadata: Metadata | None = None

    # ---- convenience accessors ----

    def headings(self) -> list[Heading]:
        return [e for e in self.elements if isinstance(e, Heading)]

    def tables(self) -> list[Table]:
        return [e for e in self.elements if isinstance(e, Table)]

    def paragraphs(self) -> list[Paragraph]:
        return [e for e in self.elements if isinstance(e, Paragraph)]

    def get_element_by_id(self, element_id: str) -> Element | None:
        """
        Retrieve an element by its ID.

        Searches for an element matching the given element_id. Returns the first match found.
        If multiple elements have the same ID, this returns the first one encountered.
        Tables are also searched by table_id.

        Args:
            element_id: The element ID to search for.

        Returns:
            The matching Element, or None if not found.
        """
        for e in self.elements:
            if getattr(e, "element_id", None) == element_id:
                return e
            if isinstance(e, Table) and e.table_id == element_id:
                return e
        return None

    def flagged_for_review(self, threshold: float = 0.90) -> list[Element]:
        """Return elements with confidence below threshold."""
        return [e for e in self.elements if e.confidence is not None and e.confidence < threshold]

    @property
    def page_count(self) -> int | None:
        return self.frontmatter.pages

    def add_element(self, element: Element) -> None:
        self.elements.append(element)

    def layer0_text(self) -> str:
        """Return just the Layer 0 content as plain text (headings + paragraphs)."""
        parts = []
        for el in self.elements:
            if isinstance(el, Heading):
                parts.append(f"{'#' * el.level} {el.text}")
            elif isinstance(el, Paragraph):
                parts.append(el.text)
        return "\n\n".join(parts)

    def generate_toc(self) -> list[tuple[int, str, str | None]]:
        """Generate table of contents from headings.

        Returns:
            List of (level, text, element_id) tuples from all headings in order.
        """
        return [(h.level, h.text, h.element_id) for h in self.headings()]

    def statistics(self) -> dict[str, int]:
        """Return counts of each element type in the document.

        Returns:
            Dictionary mapping element type names to their counts.
        """
        from collections import Counter
        counts = Counter(type(el).__name__ for el in self.elements)
        return dict(counts)

    def elements_of_type(self, element_type: type) -> list[Element]:
        """Return all elements of a specific type.

        Args:
            element_type: The Element subclass to filter by.

        Returns:
            List of elements matching the specified type.
        """
        return [e for e in self.elements if isinstance(e, element_type)]

    def key_value_pairs(self) -> list:
        """Return all KeyValuePair elements."""
        from dox.models.elements import KeyValuePair
        return [e for e in self.elements if isinstance(e, KeyValuePair)]

    def furniture(self) -> list[Element]:
        """Return all elements marked as furniture (headers/footers)."""
        return [e for e in self.elements if e.is_furniture]

    def body_elements(self) -> list[Element]:
        """Return all non-furniture elements."""
        return [e for e in self.elements if not e.is_furniture]
