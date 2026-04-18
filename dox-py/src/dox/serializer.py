"""
DoxSerializer — converts a DoxDocument back to .dox format text.

Produces valid Layer 0 + optional Layer 1 + optional Layer 2 output.
"""

from __future__ import annotations

import yaml

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
from dox.models.spatial import SpatialBlock


def _escape_attr(val: str | None) -> str:
    """Escape attribute values for safe inclusion in .dox syntax."""
    if val is None:
        return ""
    return str(val).replace("\\", "\\\\").replace('"', '\\"')


def _escape_md_brackets(val: str | None) -> str:
    """Escape markdown image caption text."""
    if val is None:
        return ""
    return str(val).replace("\\", "\\\\").replace("]", "\\]")


def _escape_md_parens(val: str | None) -> str:
    """Escape markdown image source text."""
    if val is None:
        return ""
    return str(val).replace("\\", "\\\\").replace(")", "\\)")


def _format_meta_value(value: object) -> str:
    """Format a metadata value for inline {key: value} syntax."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{_escape_attr(str(value))}"'


def _append_attr(parts: list[str], key: str, value: object | None) -> None:
    """Append a key=value attribute when the value is present."""
    if value is None:
        return
    if isinstance(value, bool):
        parts.append(f'{key}={"true" if value else "false"}')
        return
    parts.append(f'{key}="{_escape_attr(str(value))}"')


class DoxSerializer:
    """
    Serialize a DoxDocument to .dox format text.

    Usage:
        serializer = DoxSerializer()
        text = serializer.serialize(doc)
        text = serializer.serialize(doc, include_spatial=False, include_metadata=False)
    """

    def serialize(
        self,
        doc: DoxDocument,
        include_spatial: bool = True,
        include_metadata: bool = True,
    ) -> str:
        parts: list[str] = []

        # Frontmatter
        parts.append(self._serialize_frontmatter(doc))

        # Layer 0: Content
        parts.append(self._serialize_content(doc))

        # Layer 1: Spatial
        if include_spatial and doc.spatial_blocks:
            parts.append(self._serialize_spatial(doc))

        # Layer 2: Metadata
        if include_metadata and doc.metadata:
            parts.append(self._serialize_metadata(doc))

        return "\n".join(parts).strip() + "\n"

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def _serialize_frontmatter(self, doc: DoxDocument) -> str:
        data = doc.frontmatter.to_dict()
        try:
            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False).strip()
        except yaml.YAMLError:
            yaml_str = ""
        return f"---dox\n{yaml_str}\n---\n"

    # ------------------------------------------------------------------
    # Content (Layer 0)
    # ------------------------------------------------------------------

    def _serialize_content(self, doc: DoxDocument) -> str:
        parts: list[str] = []
        for element in doc.elements:
            serialized = self._serialize_element(element)
            if serialized is not None:
                parts.append(serialized)
        return "\n\n".join(parts)

    def _element_meta(self, element: Element) -> str:
        """Build inline metadata annotation for canonical round-tripping."""
        parts: list[tuple[str, object]] = []
        if element.page is not None:
            parts.append(("page", element.page))
        if element.element_id:
            parts.append(("id", element.element_id))
        if element.confidence is not None:
            parts.append(("confidence", element.confidence))
        if element.reading_order is not None:
            parts.append(("reading_order", element.reading_order))
        if element.lang:
            parts.append(("lang", element.lang))
        if element.is_furniture:
            parts.append(("is_furniture", True))
        if not parts:
            return ""
        rendered = [f"{key}: {_format_meta_value(value)}" for key, value in parts]
        return " {" + ", ".join(rendered) + "}"

    def _serialize_element(self, element: Element) -> str | None:
        meta = self._element_meta(element)

        if isinstance(element, Heading):
            level = max(1, min(6, element.level))  # Clamp to valid range 1-6
            return f"{'#' * level} {element.text}{meta}"

        elif isinstance(element, Paragraph):
            return f"{element.text}{meta}"

        elif isinstance(element, Blockquote):
            # Prefix each line with "> "
            lines = element.text.split("\n")
            quoted_lines = [f"> {line}" for line in lines]
            return "\n".join(quoted_lines) + meta

        elif isinstance(element, Table):
            return self._serialize_table(element)

        elif isinstance(element, CodeBlock):
            lang = element.language or ""
            return f"```{lang}{meta}\n{element.code}\n```"

        elif isinstance(element, MathBlock):
            hint_parts = []
            if element.display_mode:
                hint_parts.append("math: latex")
            if element.page is not None:
                hint_parts.append(f"page: {element.page}")
            if element.element_id:
                hint_parts.append(f'id: "{element.element_id}"')
            if element.confidence is not None:
                hint_parts.append(f"confidence: {element.confidence}")
            hint = f" {{{', '.join(hint_parts)}}}" if hint_parts else ""
            return f"$${element.expression}$${hint}"

        elif isinstance(element, FormField):
            escaped_value = _escape_attr(element.value)
            return f'::form field="{element.field_name}" type="{element.field_type.value}" value="{escaped_value}"::{meta}'

        elif isinstance(element, Chart):
            parts = [f'::chart type="{element.chart_type}"']
            if element.data_ref:
                parts.append(f'data-ref="{_escape_attr(element.data_ref)}"')
            if element.x_field:
                parts.append(f'x="{_escape_attr(element.x_field)}"')
            if element.y_field:
                parts.append(f'y="{_escape_attr(element.y_field)}"')
            return " ".join(parts) + "::" + meta

        elif isinstance(element, Annotation):
            parts = [f'::annotation type="{element.annotation_type}"']
            if element.confidence is not None:
                parts.append(f"confidence={element.confidence}")
            escaped_text = _escape_attr(element.text)
            parts.append(f'text="{escaped_text}"')
            return " ".join(parts) + "::" + meta

        elif isinstance(element, KeyValuePair):
            key_escaped = _escape_attr(element.key)
            val_escaped = _escape_attr(element.value)
            return f'::kv key="{key_escaped}" value="{val_escaped}"::' + meta

        elif isinstance(element, Figure):
            base = f"![{_escape_md_brackets(element.caption)}]({_escape_md_parens(element.source)})"
            fig_parts = []
            if element.figure_id:
                _append_attr(fig_parts, "id", element.figure_id)
            if element.element_id:
                _append_attr(fig_parts, "eid", element.element_id)
            _append_attr(fig_parts, "page", element.page)
            _append_attr(fig_parts, "confidence", element.confidence)
            _append_attr(fig_parts, "reading_order", element.reading_order)
            _append_attr(fig_parts, "lang", element.lang)
            if element.is_furniture:
                _append_attr(fig_parts, "is_furniture", True)
            _append_attr(fig_parts, "image_type", element.image_type)
            _append_attr(fig_parts, "image_data", element.image_data)
            if fig_parts:
                base += " {figure: " + ", ".join(fig_parts) + "}"
            return base

        elif isinstance(element, Footnote):
            return f"[^{element.number}]: {element.text}{meta}"

        elif isinstance(element, ListBlock):
            return self._serialize_list(element)

        elif isinstance(element, CrossRef):
            return f"[[ref:{element.ref_type}:{element.ref_id}]]{meta}"

        elif isinstance(element, HorizontalRule):
            return "---"

        elif isinstance(element, PageBreak):
            return f"---page-break from={element.from_page} to={element.to_page}---"

        return None

    def _serialize_table(self, table: Table) -> str:
        lines: list[str] = []

        # Opening delimiter with attributes
        attrs: list[str] = []
        _append_attr(attrs, "id", table.table_id)
        _append_attr(attrs, "caption", table.caption)
        if table.nested:
            attrs.append("nested=true")
        if table.page_range:
            _append_attr(attrs, "pages", f"{table.page_range[0]}-{table.page_range[1]}")
        if table.continuation_of:
            _append_attr(attrs, "continuation-of", table.continuation_of)
        if table.element_id and table.element_id != table.table_id:
            _append_attr(attrs, "eid", table.element_id)
        _append_attr(attrs, "page", table.page)
        _append_attr(attrs, "confidence", table.confidence)
        _append_attr(attrs, "reading_order", table.reading_order)
        _append_attr(attrs, "lang", table.lang)
        if table.is_furniture:
            _append_attr(attrs, "is_furniture", True)
        attr_str = " ".join(attrs)
        lines.append(f"||| table {attr_str}".strip())

        # Handle empty table (zero rows)
        if not table.rows:
            lines.append("|||")
            return "\n".join(lines)

        num_cols = table.num_cols
        if num_cols == 0:
            lines.append("|||")
            return "\n".join(lines)

        has_spans = any(
            c.colspan > 1 or c.rowspan > 1
            for row in table.rows
            for c in row.cells
        )

        def _cell_text_with_spans(cell) -> str:
            """Annotate cell text with span info if needed."""
            text = cell.text
            if has_spans:
                parts = []
                if cell.colspan > 1:
                    parts.append(f"cs={cell.colspan}")
                if cell.rowspan > 1:
                    parts.append(f"rs={cell.rowspan}")
                if parts:
                    text = f"{text} {{{' '.join(parts)}}}"
            return text

        def format_row(cells) -> str:
            rendered = [_cell_text_with_spans(cell) for cell in cells]
            return "| " + " | ".join(rendered) + " |"

        # Header rows
        headers = table.header_rows()
        data = table.data_rows()

        for row in headers:
            lines.append(format_row(row.cells))

        # Separator
        if headers:
            lines.append("|" + "|".join("---" for _ in range(num_cols)) + "|")

        # Data rows
        for row in data:
            lines.append(format_row(row.cells))

        lines.append("|||")
        return "\n".join(lines)

    def _serialize_list(self, lb: ListBlock) -> str:
        lines: list[str] = []
        start = lb.start if lb.start is not None else 1
        meta = self._element_meta(lb)
        needs_header = (
            not lb.items
            or lb.start != 1
            or bool(meta)
        )

        if needs_header:
            attrs: list[str] = []
            _append_attr(attrs, "ordered", lb.ordered)
            if lb.ordered:
                _append_attr(attrs, "start", start)
            header = "::list"
            if attrs:
                header += " " + " ".join(attrs)
            header += "::"
            if meta:
                header += meta
            lines.append(header)

        for idx, item in enumerate(lb.items):
            marker = f"{start + idx}." if lb.ordered else "-"
            # Emit task-list syntax if checked is not None
            if item.checked is not None:
                checkbox = "[x]" if item.checked else "[ ]"
                lines.append(f"{marker} {checkbox} {item.text}")
            else:
                lines.append(f"{marker} {item.text}")
            # Handle nested items (2-level nesting)
            for child_idx, child in enumerate(item.children, start=1):
                child_marker = f"  {child_idx}." if lb.ordered else "  -"
                if child.checked is not None:
                    checkbox = "[x]" if child.checked else "[ ]"
                    lines.append(f"{child_marker} {checkbox} {child.text}")
                else:
                    lines.append(f"{child_marker} {child.text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Spatial (Layer 1)
    # ------------------------------------------------------------------

    def _serialize_spatial(self, doc: DoxDocument) -> str:
        parts: list[str] = []
        for block in doc.spatial_blocks:
            header = f"---spatial page={block.page} grid={block.grid}"
            lines = [header]
            for ann in block.annotations:
                lines.append(str(ann))
            lines.append("---/spatial")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Metadata (Layer 2)
    # ------------------------------------------------------------------

    def _serialize_metadata(self, doc: DoxDocument) -> str:
        if not doc.metadata:
            return ""
        data = doc.metadata.to_dict()
        try:
            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False).strip()
        except yaml.YAMLError:
            yaml_str = ""
        return f"---meta\n{yaml_str}\n---/meta"
