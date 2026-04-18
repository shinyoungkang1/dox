"""
JSON Schema generator for the .dox format.

Produces a formal JSON Schema that can be used to validate .dox documents
in any language or tool, without requiring the Python library.

Usage:
    from dox.schema import generate_schema
    schema = generate_schema()  # returns dict

CLI:
    dox schema > dox-schema.json
"""

from __future__ import annotations

import json
from typing import Any


def generate_schema() -> dict[str, Any]:
    """Generate the complete JSON Schema for .dox format (JSON representation)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://dox-format.org/schema/v1.0/dox.json",
        "title": "DOX Document",
        "description": "JSON Schema for .dox (Document Open eXchange Format) v1.0",
        "type": "object",
        "required": ["dox_version", "frontmatter", "elements"],
        "properties": {
            "dox_version": {
                "type": "string",
                "description": "The .dox format version.",
                "enum": ["1.0", "0.1"],
            },
            "frontmatter": _frontmatter_schema(),
            "elements": {
                "type": "array",
                "description": "Ordered list of content elements (Layer 0).",
                "items": {"$ref": "#/$defs/element"},
            },
            "spatial": {
                "type": "array",
                "description": "Page-level spatial annotations (Layer 1). Optional.",
                "items": {"$ref": "#/$defs/spatialBlock"},
            },
            "metadata": {
                "$ref": "#/$defs/metadata",
                "description": "Extraction metadata (Layer 2). Optional.",
            },
        },
        "additionalProperties": False,
        "$defs": {
            "element": _element_schema(),
            "spatialBlock": _spatial_block_schema(),
            "spatialAnnotation": _spatial_annotation_schema(),
            "bbox": _bbox_schema(),
            "metadata": _metadata_schema(),
            "tableRow": _table_row_schema(),
            "tableCell": _table_cell_schema(),
            "listItem": _list_item_schema(),
        },
    }


def _frontmatter_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": "YAML frontmatter block (---dox ... ---).",
        "required": ["version"],
        "properties": {
            "version": {"type": "string", "description": "Format version."},
            "source": {"type": "string", "description": "Original source filename."},
            "pages": {
                "type": ["integer", "null"],
                "minimum": 1,
                "description": "Total page count of the source document.",
            },
            "lang": {
                "type": "string",
                "default": "en",
                "description": "Primary language (BCP 47 code).",
            },
            "doc_type": {
                "type": ["string", "null"],
                "enum": [
                    None, "academic", "financial", "legal", "medical",
                    "invoice", "form", "newspaper", "book",
                    "presentation", "report", "other",
                ],
                "description": "Document type classification.",
            },
        },
        "additionalProperties": True,
    }


def _element_schema() -> dict[str, Any]:
    """Schema for a single document element (discriminated union on 'type')."""
    base_properties = {
        "type": {
            "type": "string",
            "description": "Element type identifier.",
            "enum": [
                "heading", "paragraph", "table", "codeblock", "mathblock",
                "listblock", "blockquote", "horizontalrule", "figure",
                "footnote", "formfield", "chart", "annotation", "crossref",
                "pagebreak", "keyvaluepair",
            ],
        },
        "id": {"type": ["string", "null"], "description": "Unique element ID."},
        "bbox": {
            "$ref": "#/$defs/bbox",
            "description": "Bounding box coordinates.",
        },
        "confidence": {
            "type": ["number", "null"],
            "minimum": 0,
            "maximum": 1,
            "description": "Extraction confidence score.",
        },
        "page": {
            "type": ["integer", "null"],
            "minimum": 1,
            "description": "Source page number.",
        },
        "reading_order": {
            "type": ["integer", "null"],
            "minimum": 0,
            "description": "Reading order index for multi-column layouts.",
        },
        "lang": {
            "type": ["string", "null"],
            "description": "Per-element language override (BCP 47).",
        },
        "is_furniture": {
            "type": "boolean",
            "default": False,
            "description": "True for page headers, footers, and page numbers.",
        },
    }

    # Type-specific properties (all optional since it's a union)
    type_specific = {
        # Heading
        "level": {"type": "integer", "minimum": 1, "maximum": 6},
        "text": {"type": "string"},
        # Table
        "table_id": {"type": ["string", "null"]},
        "caption": {"type": ["string", "null"]},
        "nested": {"type": "boolean"},
        "rows": {"type": "array", "items": {"$ref": "#/$defs/tableRow"}},
        # CodeBlock
        "language": {"type": ["string", "null"]},
        "code": {"type": "string"},
        # MathBlock
        "expression": {"type": "string"},
        "display_mode": {"type": "boolean"},
        # ListBlock
        "ordered": {"type": "boolean"},
        "items": {"type": "array", "items": {"$ref": "#/$defs/listItem"}},
        # Figure
        "source": {"type": "string"},
        "figure_id": {"type": ["string", "null"]},
        "image_data": {"type": ["string", "null"]},
        "image_type": {
            "type": ["string", "null"],
            "enum": [None, "photo", "diagram", "chart", "logo", "screenshot"],
        },
        # Footnote
        "number": {"type": "integer", "minimum": 0},
        # FormField
        "field_name": {"type": "string"},
        "field_type": {
            "type": "string",
            "enum": ["text", "checkbox", "radio", "select", "textarea"],
        },
        "value": {"type": "string"},
        # Chart
        "chart_type": {"type": "string"},
        "data_ref": {"type": ["string", "null"]},
        "x_field": {"type": ["string", "null"]},
        "y_field": {"type": ["string", "null"]},
        # Annotation
        "annotation_type": {"type": "string"},
        # CrossRef
        "ref_type": {"type": "string"},
        "ref_id": {"type": "string"},
        # PageBreak
        "from_page": {"type": "integer"},
        "to_page": {"type": "integer"},
        # KeyValuePair
        "key": {"type": "string"},
    }

    all_properties = {**base_properties, **type_specific}

    return {
        "type": "object",
        "required": ["type"],
        "properties": all_properties,
        "additionalProperties": False,
    }


def _bbox_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "description": "Bounding box as [x1, y1, x2, y2] on the page grid.",
        "items": {"type": "integer"},
        "minItems": 4,
        "maxItems": 4,
    }


def _spatial_block_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": "Spatial annotations for a single page (Layer 1).",
        "required": ["page", "grid"],
        "properties": {
            "page": {"type": "integer", "minimum": 1},
            "grid": {
                "type": "string",
                "pattern": "^\\d+x\\d+$",
                "description": "Grid dimensions (e.g., '1000x1000').",
            },
            "annotations": {
                "type": "array",
                "items": {"$ref": "#/$defs/spatialAnnotation"},
            },
        },
        "additionalProperties": False,
    }


def _spatial_annotation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Content line text."},
            "bbox": {"$ref": "#/$defs/bbox"},
            "cell_bboxes": {
                "type": ["array", "null"],
                "items": {"$ref": "#/$defs/bbox"},
                "description": "Per-cell bounding boxes for table rows.",
            },
        },
        "additionalProperties": False,
    }


def _metadata_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": "Extraction metadata and provenance (Layer 2).",
        "properties": {
            "extracted_by": {
                "type": "string",
                "description": "Tool/model that extracted the document.",
            },
            "extracted_at": {
                "type": "string",
                "format": "date-time",
                "description": "Extraction timestamp (ISO 8601).",
            },
            "confidence": {
                "type": "object",
                "description": "Confidence scores.",
                "properties": {
                    "overall": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "additionalProperties": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "provenance": {
                "type": "object",
                "properties": {
                    "source_hash": {"type": "string"},
                    "extraction_pipeline": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "version_history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ts": {"type": "string", "format": "date-time"},
                        "agent": {"type": "string"},
                        "action": {"type": "string"},
                    },
                },
            },
        },
        "additionalProperties": True,
    }


def _table_row_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "is_header": {"type": "boolean", "default": False},
            "cells": {
                "type": "array",
                "items": {"$ref": "#/$defs/tableCell"},
            },
        },
        "additionalProperties": False,
    }


def _table_cell_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "is_header": {"type": "boolean", "default": False},
            "colspan": {"type": "integer", "minimum": 1, "default": 1},
            "rowspan": {"type": "integer", "minimum": 1, "default": 1},
        },
        "additionalProperties": False,
    }


def _list_item_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "checked": {
                "type": ["boolean", "null"],
                "description": "Task list state. null = not a task item.",
            },
            "children": {
                "type": "array",
                "items": {"$ref": "#/$defs/listItem"},
                "description": "Nested list items.",
            },
        },
        "additionalProperties": False,
    }


def schema_json(indent: int = 2) -> str:
    """Return the .dox JSON Schema as a formatted string."""
    return json.dumps(generate_schema(), indent=indent, ensure_ascii=False)
