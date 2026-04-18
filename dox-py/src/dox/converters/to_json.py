"""
Convert a DoxDocument to a structured JSON representation.
"""

from __future__ import annotations

import json
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


def to_json(doc: DoxDocument, indent: int = 2) -> str:
    """Convert a DoxDocument to a JSON string."""
    return json.dumps(to_dict(doc), indent=indent, ensure_ascii=False)


def to_dict(doc: DoxDocument) -> dict[str, Any]:
    """Convert a DoxDocument to a Python dictionary."""
    result: dict[str, Any] = {
        "dox_version": doc.frontmatter.version,
        "frontmatter": doc.frontmatter.to_dict(),
        "elements": [_element_to_dict(el) for el in doc.elements],
    }

    if doc.spatial_blocks:
        result["spatial"] = [
            {
                "page": sb.page,
                "grid": sb.grid,
                "annotations": [
                    {
                        "text": a.line_text,
                        "bbox": a.bbox.to_list() if a.bbox else None,
                        "cell_bboxes": (
                            [c.to_list() for c in a.cell_bboxes]
                            if a.cell_bboxes
                            else None
                        ),
                    }
                    for a in sb.annotations
                ],
            }
            for sb in doc.spatial_blocks
        ]

    if doc.metadata:
        result["metadata"] = doc.metadata.to_dict()

    return result


def _element_to_dict(element: Element) -> dict[str, Any]:
    base: dict[str, Any] = {"type": type(element).__name__.lower()}

    if element.element_id:
        base["id"] = element.element_id
    if element.bbox:
        base["bbox"] = element.bbox.to_list()
    if element.confidence is not None:
        base["confidence"] = element.confidence
    if element.page is not None:
        base["page"] = element.page
    if element.reading_order is not None:
        base["reading_order"] = element.reading_order
    if element.lang:
        base["lang"] = element.lang
    if element.is_furniture:
        base["is_furniture"] = True

    if isinstance(element, Heading):
        base["level"] = element.level
        base["text"] = element.text

    elif isinstance(element, Paragraph):
        base["text"] = element.text

    elif isinstance(element, Blockquote):
        base["text"] = element.text

    elif isinstance(element, HorizontalRule):
        # No additional fields needed beyond the base type
        pass

    elif isinstance(element, PageBreak):
        base["from_page"] = element.from_page
        base["to_page"] = element.to_page

    elif isinstance(element, Table):
        base["table_id"] = element.table_id
        base["caption"] = element.caption
        base["nested"] = element.nested
        base["rows"] = [
            {
                "is_header": row.is_header,
                "cells": [
                    {
                        "text": cell.text,
                        "is_header": cell.is_header,
                        "colspan": cell.colspan,
                        "rowspan": cell.rowspan,
                    }
                    for cell in row.cells
                ],
            }
            for row in element.rows
        ]

    elif isinstance(element, CodeBlock):
        base["language"] = element.language
        base["code"] = element.code

    elif isinstance(element, MathBlock):
        base["expression"] = element.expression
        base["display_mode"] = element.display_mode

    elif isinstance(element, FormField):
        base["field_name"] = element.field_name
        base["field_type"] = element.field_type.value
        base["value"] = element.value

    elif isinstance(element, Chart):
        base["chart_type"] = element.chart_type
        base["data_ref"] = element.data_ref
        base["x_field"] = element.x_field
        base["y_field"] = element.y_field

    elif isinstance(element, Annotation):
        base["annotation_type"] = element.annotation_type
        base["text"] = element.text

    elif isinstance(element, KeyValuePair):
        base["key"] = element.key
        base["value"] = element.value

    elif isinstance(element, Figure):
        base["caption"] = element.caption
        base["source"] = element.source
        base["figure_id"] = element.figure_id
        if element.image_type:
            base["image_type"] = element.image_type
        if element.image_data:
            base["image_data"] = element.image_data

    elif isinstance(element, Footnote):
        base["number"] = element.number
        base["text"] = element.text

    elif isinstance(element, ListBlock):
        base["ordered"] = element.ordered
        items_list = []
        for it in element.items:
            item_dict = {"text": it.text}
            if it.checked is not None:
                item_dict["checked"] = it.checked
            if it.children:
                children_list = []
                for child in it.children:
                    child_dict = {"text": child.text}
                    if child.checked is not None:
                        child_dict["checked"] = child.checked
                    children_list.append(child_dict)
                item_dict["children"] = children_list
            items_list.append(item_dict)
        base["items"] = items_list

    elif isinstance(element, CrossRef):
        base["ref_type"] = element.ref_type
        base["ref_id"] = element.ref_id

    return base
