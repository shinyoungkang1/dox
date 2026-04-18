"""
Convert a DoxDocument to standalone HTML.
"""

from __future__ import annotations

import html
from typing import Any

from dox.converters._figure_utils import figure_display_src
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


def to_html(doc: DoxDocument, standalone: bool = True) -> str:
    """
    Convert a DoxDocument to HTML.

    Args:
        doc: The document to convert.
        standalone: If True, wrap in a full HTML page with <head>/<body>.
    """
    body_parts: list[str] = []

    for element in doc.elements:
        if isinstance(element, Heading):
            # Clamp heading level to valid HTML range (1-6)
            level = min(max(element.level, 1), 6)
            tag = f"h{level}"
            eid = f' id="{_esc(element.element_id)}"' if element.element_id else ""
            text = _esc(element.text or "")
            body_parts.append(f"<{tag}{eid}>{text}</{tag}>")

        elif isinstance(element, Paragraph):
            body_parts.append(f"<p>{_inline(element.text)}</p>")

        elif isinstance(element, Blockquote):
            body_parts.append(f"<blockquote><p>{_inline(element.text)}</p></blockquote>")

        elif isinstance(element, HorizontalRule):
            body_parts.append("<hr>")

        elif isinstance(element, Table):
            body_parts.append(_table_to_html(element))

        elif isinstance(element, CodeBlock):
            lang_attr = f' class="language-{element.language}"' if element.language else ""
            body_parts.append(f"<pre><code{lang_attr}>{_esc(element.code)}</code></pre>")

        elif isinstance(element, MathBlock):
            cls = "math-block" if element.display_mode else "math-inline"
            # Escape quotes in data-latex attribute to prevent XSS
            escaped_expr = _esc(element.expression or "")
            safe_expr = escaped_expr.replace('"', '&quot;')
            body_parts.append(
                f'<span class="{cls}" data-latex="{safe_expr}">'
                f"$${escaped_expr}$$</span>"
            )

        elif isinstance(element, FormField):
            body_parts.append(_form_to_html(element))

        elif isinstance(element, Chart):
            body_parts.append(
                f'<div class="dox-chart" data-type="{_esc(element.chart_type)}"'
                f' data-ref="{_esc(element.data_ref or "")}"'
                f' data-x="{_esc(element.x_field or "")}"'
                f' data-y="{_esc(element.y_field or "")}">'
                f"[Chart: {_esc(element.chart_type)}]</div>"
            )

        elif isinstance(element, Annotation):
            # Escape quotes in data-type attribute to prevent XSS
            safe_type = _esc(element.annotation_type or "").replace('"', '&quot;')
            body_parts.append(
                f'<mark class="dox-annotation" data-type="{safe_type}">'
                f"{_esc(element.text)}</mark>"
            )

        elif isinstance(element, KeyValuePair):
            body_parts.append(
                f'<div class="dox-kv"><span class="dox-kv-key">{_esc(element.key)}</span>: '
                f'<span class="dox-kv-value">{_esc(element.value)}</span></div>'
            )

        elif isinstance(element, Figure):
            cap = f"<figcaption>{_esc(element.caption)}</figcaption>" if element.caption else ""
            fid = f' id="{_esc(element.figure_id)}"' if element.figure_id else ""
            img_src = figure_display_src(element)
            body_parts.append(
                f"<figure{fid}><img src=\"{_esc(img_src)}\" "
                f'alt="{_esc(element.caption)}" />{cap}</figure>'
            )

        elif isinstance(element, Footnote):
            body_parts.append(
                f'<aside class="footnote" id="fn-{element.number}">'
                f"<sup>{element.number}</sup> {_esc(element.text)}</aside>"
            )

        elif isinstance(element, ListBlock):
            tag = "ol" if element.ordered else "ul"
            items_html = []
            for it in element.items:
                if it.checked is not None:
                    # Render as checkbox list
                    checked_attr = 'checked disabled' if it.checked else 'disabled'
                    checkbox = f'<input type="checkbox" {checked_attr}> '
                    items_html.append(f"  <li>{checkbox}{_inline(it.text)}")
                else:
                    items_html.append(f"  <li>{_inline(it.text)}")
                if it.children:
                    nested_tag = "ol" if element.ordered else "ul"
                    nested_items = []
                    for child in it.children:
                        if child.checked is not None:
                            checked_attr = 'checked disabled' if child.checked else 'disabled'
                            checkbox = f'<input type="checkbox" {checked_attr}> '
                            nested_items.append(f"    <li>{checkbox}{_inline(child.text)}</li>")
                        else:
                            nested_items.append(f"    <li>{_inline(child.text)}</li>")
                    nested = "\n".join(nested_items)
                    items_html.append(f"\n    <{nested_tag}>\n{nested}\n    </{nested_tag}>\n  ")
                items_html.append("</li>")
            items = "\n".join(items_html)
            start = f' start="{element.start}"' if element.ordered and element.start != 1 else ""
            body_parts.append(f"<{tag}{start}>\n{items}\n</{tag}>")

        elif isinstance(element, CrossRef):
            body_parts.append(
                f'<a class="dox-ref" href="#{element.ref_id}">'
                f"{element.ref_type}:{element.ref_id}</a>"
            )

    body = "\n".join(body_parts)

    if not standalone:
        return body

    title = ""
    for el in doc.elements:
        if isinstance(el, Heading) and el.level == 1:
            title = el.text
            break

    return f"""<!DOCTYPE html>
<html lang="{doc.frontmatter.lang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_esc(title)}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }}
th {{ background: #f5f5f5; font-weight: 600; }}
pre {{ background: #f8f8f8; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
code {{ font-family: 'SF Mono', Menlo, monospace; font-size: 0.9em; }}
.dox-chart {{ background: #f0f4ff; border: 1px dashed #4a90d9; padding: 1rem; border-radius: 4px; text-align: center; color: #666; }}
.dox-annotation {{ background: #fff3cd; padding: 0.1em 0.3em; border-radius: 2px; }}
.dox-kv {{ margin: 0.25rem 0; }} .dox-kv-key {{ font-weight: 600; }}
figure {{ margin: 1rem 0; text-align: center; }}
figcaption {{ font-style: italic; color: #666; margin-top: 0.5rem; }}
.footnote {{ font-size: 0.85em; color: #555; border-top: 1px solid #eee; padding-top: 0.5rem; margin-top: 1rem; }}
.math-block {{ display: block; text-align: center; margin: 1rem 0; font-style: italic; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _table_to_html(table: Table) -> str:
    parts: list[str] = []
    tid = f' id="{table.table_id}"' if table.table_id else ""
    parts.append(f"<table{tid}>")

    if table.caption:
        parts.append(f"  <caption>{_esc(table.caption)}</caption>")

    headers = table.header_rows()
    data = table.data_rows()

    if headers:
        parts.append("  <thead>")
        for row in headers:
            parts.append("    <tr>")
            for cell in row.cells:
                attrs = ""
                if cell.colspan > 1:
                    attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    attrs += f' rowspan="{cell.rowspan}"'
                parts.append(f"      <th{attrs}>{_esc(cell.text)}</th>")
            parts.append("    </tr>")
        parts.append("  </thead>")

    parts.append("  <tbody>")
    for row in data:
        parts.append("    <tr>")
        for cell in row.cells:
            attrs = ""
            if cell.colspan > 1:
                attrs += f' colspan="{cell.colspan}"'
            if cell.rowspan > 1:
                attrs += f' rowspan="{cell.rowspan}"'
            parts.append(f"      <td{attrs}>{_esc(cell.text)}</td>")
        parts.append("    </tr>")
    parts.append("  </tbody>")

    parts.append("</table>")
    return "\n".join(parts)


def _form_to_html(field: FormField) -> str:
    ftype = field.field_type.value
    name = _esc(field.field_name)
    val = _esc(field.value)

    if ftype == "checkbox":
        checked = " checked" if field.value.lower() in ("true", "yes", "1") else ""
        return (
            f'<label><input type="checkbox" name="{name}"{checked} /> {name}</label>'
        )
    elif ftype == "radio":
        return f'<label><input type="radio" name="{name}" value="{val}" /> {name}</label>'
    elif ftype == "select":
        return f'<select name="{name}"><option>{val}</option></select>'
    elif ftype == "textarea":
        return f'<textarea name="{name}">{val}</textarea>'
    else:
        return f'<input type="text" name="{name}" value="{val}" />'


def _esc(text: Any) -> str:
    return html.escape(str(text))


def _inline(text: str) -> str:
    """Basic inline Markdown → HTML (bold, italic, code, links)."""
    import re

    t = _esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    # Security: only allow safe URL schemes to prevent XSS via javascript: URLs
    t = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: _safe_link(m.group(1), m.group(2)),
        t,
    )
    return t


def _safe_link(text: str, url: str) -> str:
    """Safely render a link only if the URL scheme is safe."""
    safe_schemes = ("http://", "https://", "mailto:", "#")
    url_lower = url.lower()
    if any(url_lower.startswith(scheme) for scheme in safe_schemes):
        # URL is already entity-escaped from _esc(), but re-escape for attribute context
        safe_url = url.replace('"', '&quot;')
        return f'<a href="{safe_url}">{text}</a>'
    # Unsafe URL: render as plain text
    return text
