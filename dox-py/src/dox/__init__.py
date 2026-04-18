"""
dox — Document Open eXchange Format

A layered document format that is as readable as Markdown, as precise as PDF,
as structured as JSON, and as lightweight as plain text.

Quick start:
    from dox import DoxParser, DoxSerializer, DoxValidator
    doc = DoxParser().parse_file("report.dox")
    text = DoxSerializer().serialize(doc)
    result = DoxValidator().validate(doc)

Chunking for RAG:
    from dox.chunker import chunk_document
    chunks = chunk_document(doc, strategy="semantic", max_tokens=512)

Diffing:
    from dox.diff import DoxDiff
    result = DoxDiff().diff(old_doc, new_doc)

Rendering:
    from dox.renderer import DoxRenderer
    DoxRenderer().to_pdf(doc, "output.pdf")

Conversion:
    from dox.converters import to_html, to_json, to_markdown
"""

__version__ = "1.0.0"

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Annotation,
    BoundingBox,
    Blockquote,
    Chart,
    CodeBlock,
    CrossRef,
    Element,
    Figure,
    Footnote,
    FormField,
    FormFieldType,
    Heading,
    HorizontalRule,
    KeyValuePair,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Table,
    TableCell,
    TableRow,
)
from dox.models.metadata import Confidence, Metadata, Provenance, VersionEntry
from dox.models.spatial import SpatialAnnotation, SpatialBlock
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.validator import DoxValidator, ValidationResult, ValidationIssue, Severity

__all__ = [
    # Core
    "DoxDocument",
    "DoxParser",
    "DoxSerializer",
    "DoxValidator",
    "Frontmatter",
    "ValidationResult",
    "ValidationIssue",
    "Severity",
    # Elements
    "Annotation",
    "BoundingBox",
    "Blockquote",
    "Chart",
    "CodeBlock",
    "CrossRef",
    "Element",
    "Figure",
    "Footnote",
    "FormField",
    "FormFieldType",
    "Heading",
    "HorizontalRule",
    "KeyValuePair",
    "ListBlock",
    "ListItem",
    "MathBlock",
    "Paragraph",
    "Table",
    "TableCell",
    "TableRow",
    # Metadata
    "Confidence",
    "Metadata",
    "Provenance",
    "VersionEntry",
    # Spatial
    "SpatialAnnotation",
    "SpatialBlock",
]
