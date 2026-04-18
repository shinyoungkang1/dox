"""
Core element types for the .dox document model.

Every block in a .dox file maps to one of these dataclasses. Layer 0 (content)
elements are always present; spatial annotations (Layer 1) are optional fields
on each element.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Spatial primitives
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    """Normalized bounding box on a page grid (default 1000x1000)."""
    x1: int
    y1: int
    x2: int
    y2: int

    def to_list(self) -> list[int]:
        return [self.x1, self.y1, self.x2, self.y2]

    @classmethod
    def from_list(cls, coords: list[int]) -> BoundingBox:
        if len(coords) != 4:
            raise ValueError(f"BoundingBox requires exactly 4 coordinates, got {len(coords)}")
        return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])

    def __str__(self) -> str:
        return f"@[{self.x1},{self.y1},{self.x2},{self.y2}]"


# ---------------------------------------------------------------------------
# Base element
# ---------------------------------------------------------------------------

@dataclass
class Element:
    """Base class for all .dox content elements."""
    bbox: BoundingBox | None = None
    confidence: float | None = None
    element_id: str | None = None
    page: int | None = None
    dirty: bool = False
    reading_order: int | None = None
    lang: str | None = None  # Per-element language override
    is_furniture: bool = False  # True for headers/footers/page numbers


# ---------------------------------------------------------------------------
# Block elements
# ---------------------------------------------------------------------------

@dataclass
class Heading(Element):
    """A heading (h1–h6)."""
    level: int = 1
    text: str = ""


@dataclass
class Paragraph(Element):
    """A paragraph of inline content (may contain bold, italic, links, etc.)."""
    text: str = ""


@dataclass
class TableCell:
    """A single table cell."""
    text: str = ""
    bbox: BoundingBox | None = None
    is_header: bool = False
    colspan: int = 1
    rowspan: int = 1

    def __post_init__(self) -> None:
        """Validate colspan and rowspan are >= 1."""
        if self.colspan < 1:
            raise ValueError(f"colspan must be >= 1, got {self.colspan}")
        if self.rowspan < 1:
            raise ValueError(f"rowspan must be >= 1, got {self.rowspan}")


@dataclass
class TableRow:
    """A table row."""
    cells: list[TableCell] = field(default_factory=list)
    bbox: BoundingBox | None = None
    is_header: bool = False


@dataclass
class Table(Element):
    """
    A table block delimited by ||| ... |||.
    Supports metadata attributes: id, caption, nested.

    Cross-page tables:
      - ``page_range``: tuple (start_page, end_page) if the table spans pages.
      - ``continuation_of``: ID of the table this is a continuation of.
        When set, this table's rows are the tail that spilled onto a new page.
    """
    rows: list[TableRow] = field(default_factory=list)
    caption: str | None = None
    nested: bool = False
    table_id: str | None = None
    page_range: tuple[int, int] | None = None
    continuation_of: str | None = None

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        if not self.rows:
            return 0
        return max(sum(max(1, c.colspan) for c in r.cells) for r in self.rows)

    def header_rows(self) -> list[TableRow]:
        return [r for r in self.rows if r.is_header]

    def data_rows(self) -> list[TableRow]:
        return [r for r in self.rows if not r.is_header]


@dataclass
class MathBlock(Element):
    """A math expression: $$...$$ {math: latex}."""
    expression: str = ""
    display_mode: bool = False  # True for block-level $$...$$


@dataclass
class Blockquote(Element):
    """A blockquote (> text)."""
    text: str = ""


@dataclass
class HorizontalRule(Element):
    """A horizontal rule / thematic break: ---, ***, ___."""
    pass


@dataclass
class KeyValuePair(Element):
    """A key-value pair extracted from forms, invoices, or structured documents.

    Syntax: ::kv key="Field Name" value="Field Value"::
    """
    key: str = ""
    value: str = ""


@dataclass
class CodeBlock(Element):
    """A fenced code block with optional language hint."""
    code: str = ""
    language: str | None = None


class FormFieldType(str, Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    TEXTAREA = "textarea"


@dataclass
class FormField(Element):
    """An inline form field: ::form field="name" type="..." value="..."::."""
    field_name: str = ""
    field_type: FormFieldType = FormFieldType.TEXT
    value: str = ""


@dataclass
class Chart(Element):
    """A declarative chart reference: ::chart type="bar" data-ref="t1" ...::."""
    chart_type: str = "bar"
    data_ref: str | None = None
    x_field: str | None = None
    y_field: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Annotation(Element):
    """A handwriting or other annotation: ::annotation type="..." text="..."::."""
    annotation_type: str = "handwriting"
    text: str = ""


@dataclass
class CrossRef(Element):
    """A cross-reference: [[ref:id]] or [[ref:section:2.3]]."""
    ref_type: str = ""  # "table", "section", "figure", etc.
    ref_id: str = ""


@dataclass
class Figure(Element):
    """An image/figure: ![caption](figure-id) {figure: id="f1"}."""
    caption: str = ""
    source: str = ""
    figure_id: str | None = None
    image_data: str | None = None  # Base64-encoded image data
    image_type: str | None = None  # photo, diagram, chart, logo, screenshot


@dataclass
class Footnote(Element):
    """A footnote: [^N] with content."""
    number: int = 0
    text: str = ""

    def __post_init__(self) -> None:
        """Validate footnote number is >= 0."""
        if self.number < 0:
            raise ValueError(f"Footnote number must be >= 0, got {self.number}")


@dataclass
class ListItem:
    """A single list item."""
    text: str = ""
    children: list[ListItem] = field(default_factory=list)
    checked: bool | None = None  # None = not a task list item


@dataclass
class ListBlock(Element):
    """An ordered or unordered list."""
    items: list[ListItem] = field(default_factory=list)
    ordered: bool = False
    start: int = 1

    def __post_init__(self) -> None:
        """Validate list start index is >= 1."""
        if self.start < 1:
            raise ValueError(f"ListBlock start must be >= 1, got {self.start}")


# ---------------------------------------------------------------------------
# Cross-page support
# ---------------------------------------------------------------------------

@dataclass
class PageBreak(Element):
    """
    Explicit page boundary marker.

    Inserted between elements to indicate a physical page transition.
    ``from_page`` is the page ending, ``to_page`` is the page beginning.
    """
    from_page: int = 0
    to_page: int = 0
