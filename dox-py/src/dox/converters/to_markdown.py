"""
Convert a DoxDocument to standard Markdown (strip .dox extensions).
"""

from __future__ import annotations

from dox.models.document import DoxDocument
from dox.models.elements import (
    Annotation,
    Blockquote,
    Chart,
    CodeBlock,
    CrossRef,
    Figure,
    Footnote,
    FormField,
    Heading,
    HorizontalRule,
    KeyValuePair,
    ListBlock,
    MathBlock,
    Paragraph,
    Table,
)


def to_markdown(doc: DoxDocument) -> str:
    """Convert a DoxDocument to standard CommonMark Markdown."""
    parts: list[str] = []

    # YAML frontmatter (standard markdown format)
    fm = doc.frontmatter.to_dict()
    if fm:
        import yaml
        yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
        parts.append(f"---\n{yaml_str}\n---")

    for element in doc.elements:
        if isinstance(element, Heading):
            parts.append(f"{'#' * element.level} {element.text}")

        elif isinstance(element, Paragraph):
            parts.append(element.text)

        elif isinstance(element, Blockquote):
            lines = element.text.split("\n")
            quoted = "\n".join(f"> {line}" for line in lines)
            parts.append(quoted)

        elif isinstance(element, HorizontalRule):
            parts.append("---")

        elif isinstance(element, Table):
            parts.append(_table_to_md(element))

        elif isinstance(element, CodeBlock):
            lang = element.language or ""
            code = element.code or ""
            # Use ~~~~ fence if code contains ``` to avoid breaking the fence
            if "```" in code:
                parts.append(f"~~~~{lang}\n{code}\n~~~~")
            else:
                parts.append(f"```{lang}\n{code}\n```")

        elif isinstance(element, MathBlock):
            parts.append(f"$${element.expression}$$")

        elif isinstance(element, FormField):
            if element.field_type.value == "checkbox":
                checked = "x" if element.value.lower() in ("true", "yes", "1") else " "
                parts.append(f"- [{checked}] {element.field_name}")
            else:
                parts.append(f"**{element.field_name}**: {element.value}")

        elif isinstance(element, Chart):
            parts.append(f"*[Chart: {element.chart_type} — data from {element.data_ref}]*")

        elif isinstance(element, Annotation):
            parts.append(f"*[{element.annotation_type}: {element.text}]*")

        elif isinstance(element, KeyValuePair):
            parts.append(f"**{element.key}**: {element.value}")

        elif isinstance(element, Figure):
            parts.append(f"![{element.caption}]({element.source})")

        elif isinstance(element, Footnote):
            parts.append(f"[^{element.number}]: {element.text}")

        elif isinstance(element, ListBlock):
            for idx, item in enumerate(element.items):
                marker = f"{element.start + idx}." if element.ordered else "-"
                if item.checked is not None:
                    checkbox = "[x]" if item.checked else "[ ]"
                    parts.append(f"{marker} {checkbox} {item.text}")
                else:
                    parts.append(f"{marker} {item.text}")
                # Handle nested items
                for child_idx, child in enumerate(item.children, start=1):
                    child_marker = f"{child_idx}." if element.ordered else "-"
                    if child.checked is not None:
                        checkbox = "[x]" if child.checked else "[ ]"
                        parts.append(f"  {child_marker} {checkbox} {child.text}")
                    else:
                        parts.append(f"  {child_marker} {child.text}")

        elif isinstance(element, CrossRef):
            parts.append(f"[{element.ref_type}:{element.ref_id}]")

    return "\n\n".join(parts) + "\n"


def _table_to_md(table: Table) -> str:
    if not table.rows:
        return ""

    lines: list[str] = []

    if table.caption:
        lines.append(f"*{table.caption}*")
        lines.append("")

    num_cols = table.num_cols
    col_widths = [3] * num_cols
    for row in table.rows:
        col_idx = 0
        for cell in row.cells:
            if col_idx < num_cols:
                col_widths[col_idx] = max(col_widths[col_idx], len(cell.text))
            col_idx += max(1, cell.colspan)

    def fmt_row(cells):
        """Format a row, expanding colspan cells with empty cells for Markdown compatibility.

        Note: Markdown doesn't natively support colspan/rowspan. For cells with colspan > 1,
        we add empty cells to maintain column count alignment.
        """
        padded = []
        col_idx = 0
        for cell in cells:
            if col_idx >= num_cols:
                break
            t = cell.text
            padded.append(f" {t:<{col_widths[col_idx]}} ")
            col_idx += 1
            # For colspan > 1, add empty cells to fill the columns
            for _ in range(cell.colspan - 1):
                if col_idx < num_cols:
                    padded.append(f" {'':<{col_widths[col_idx]}} ")
                    col_idx += 1
        # Fill remaining columns with empty cells
        while col_idx < num_cols:
            padded.append(f" {'':<{col_widths[col_idx]}} ")
            col_idx += 1
        return "|" + "|".join(padded) + "|"

    headers = table.header_rows()
    data = table.data_rows()

    if headers:
        for row in headers:
            lines.append(fmt_row(row.cells))
        sep = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
        lines.append(sep)

    for row in data:
        lines.append(fmt_row(row.cells))

    return "\n".join(lines)
