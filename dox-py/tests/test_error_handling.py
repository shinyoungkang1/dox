"""
Error handling and malformed input tests.

Tests that the parser, serializer, and converters handle bad input
gracefully without crashing — returning degraded output instead of
raising unhandled exceptions.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    BoundingBox, Heading, ListBlock, ListItem, Paragraph,
    Table, TableCell, TableRow, Footnote, MathBlock, CodeBlock,
    FormField, FormFieldType, Figure, Annotation, PageBreak,
    TableCell,
)
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.converters.to_docx import to_docx, to_docx_bytes
from dox.converters.to_pdf import to_pdf, to_pdf_bytes
from dox.converters.to_html import to_html
from dox.converters.to_json import to_json
from dox.converters.to_markdown import to_markdown
from dox.validator import DoxValidator

parser = DoxParser()
serializer = DoxSerializer()


# ═══════════════════════════════════════════════════════════════════
# PARSER ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

class TestParserMalformedInput:
    """Parser should NOT crash on any malformed input."""

    def test_completely_empty_string(self):
        doc = parser.parse("")
        assert doc is not None
        assert isinstance(doc, DoxDocument)

    def test_only_whitespace(self):
        doc = parser.parse("   \n\n   \n  ")
        assert doc is not None

    def test_only_frontmatter_markers(self):
        doc = parser.parse("---\n---")
        assert doc is not None

    def test_invalid_yaml_frontmatter(self):
        """Broken YAML should not crash."""
        text = "---\n: invalid: yaml: [broken\n---\n# Hello"
        doc = parser.parse(text)
        assert doc is not None

    def test_yaml_with_tabs(self):
        """YAML with tabs (invalid) should not crash."""
        text = "---\n\tversion: 1.0\n---\n# Hello"
        doc = parser.parse(text)
        assert doc is not None

    def test_non_utf8_characters_in_text(self):
        """Unusual unicode should not crash."""
        text = "---\nversion: '1.0'\n---\n# Hello \x00 World"
        doc = parser.parse(text)
        assert doc is not None

    def test_only_hashes_no_text(self):
        """Heading with no text after #."""
        text = "---\nversion: '1.0'\n---\n# \n## \n### "
        doc = parser.parse(text)
        assert doc is not None

    def test_malformed_table_no_closing(self):
        """Table opened but never closed."""
        text = "---\nversion: '1.0'\n---\n|||\n| A | B |\n| 1 | 2 |"
        doc = parser.parse(text)
        assert doc is not None

    def test_malformed_table_empty(self):
        """Table with just delimiters."""
        text = "---\nversion: '1.0'\n---\n|||\n|||"
        doc = parser.parse(text)
        assert doc is not None

    def test_malformed_math_unclosed(self):
        """Math block opened but never closed."""
        text = "---\nversion: '1.0'\n---\n$$x^2 + y^2"
        doc = parser.parse(text)
        assert doc is not None

    def test_malformed_code_unclosed(self):
        """Code block opened but never closed."""
        text = "---\nversion: '1.0'\n---\n```python\nprint('hello')"
        doc = parser.parse(text)
        assert doc is not None

    def test_page_number_not_integer(self):
        """Non-integer page number should not crash."""
        text = "---\nversion: '1.0'\n---\n# Hello {page: abc, id: 'h1'}"
        doc = parser.parse(text)
        assert doc is not None

    def test_confidence_not_float(self):
        """Non-float confidence should not crash."""
        text = "---\nversion: '1.0'\n---\n# Hello {confidence: xyz}"
        doc = parser.parse(text)
        assert doc is not None

    def test_very_deeply_nested_yaml(self):
        """Deep YAML nesting should not crash."""
        deep = "a:\n" + "".join(f"{'  ' * i}b:\n" for i in range(1, 50))
        text = f"---\n{deep}---\n# Hello"
        doc = parser.parse(text)
        assert doc is not None

    def test_binary_content_in_text(self):
        """Binary-like content should not crash."""
        text = "---\nversion: '1.0'\n---\n# Title\n\xFF\xFE\x00\x01"
        doc = parser.parse(text)
        assert doc is not None

    def test_enormous_heading_level(self):
        """####### (7+ hashes) should not crash."""
        text = "---\nversion: '1.0'\n---\n####### Too many hashes"
        doc = parser.parse(text)
        assert doc is not None

    def test_table_with_mismatched_columns(self):
        """Rows with different column counts."""
        text = "---\nversion: '1.0'\n---\n|||\n| A | B | C |\n| 1 |\n| x | y | z | w |\n|||"
        doc = parser.parse(text)
        assert doc is not None


# ═══════════════════════════════════════════════════════════════════
# SERIALIZER ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

class TestSerializerEdgeCases:
    """Serializer should handle edge cases without crashing."""

    def test_empty_document(self):
        doc = DoxDocument()
        text = serializer.serialize(doc)
        assert isinstance(text, str)

    def test_document_no_frontmatter(self):
        doc = DoxDocument()
        doc.add_element(Heading(level=1, text="Hello"))
        text = serializer.serialize(doc)
        assert "Hello" in text

    def test_heading_level_zero(self):
        """Level 0 should be clamped, not crash."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(Heading(level=0, text="Bad level"))
        text = serializer.serialize(doc)
        assert "Bad level" in text

    def test_heading_level_99(self):
        """Level 99 should be clamped, not crash."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(Heading(level=99, text="Way too deep"))
        text = serializer.serialize(doc)
        assert "Way too deep" in text

    def test_empty_table(self):
        """Table with no rows."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(Table(rows=[]))
        text = serializer.serialize(doc)
        assert isinstance(text, str)

    def test_table_empty_rows(self):
        """Table with rows but no cells."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(Table(rows=[TableRow(cells=[])]))
        text = serializer.serialize(doc)
        assert isinstance(text, str)

    def test_formfield_with_quotes_in_value(self):
        """Form field value containing quotes."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(FormField(
            field_name="test",
            field_type=FormFieldType.TEXT,
            value='He said "hello"',
        ))
        text = serializer.serialize(doc)
        assert isinstance(text, str)
        assert "test" in text

    def test_none_text_paragraph(self):
        """Paragraph with None text (edge case)."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        p = Paragraph()
        p.text = None  # type: ignore
        doc.add_element(p)
        # Should not crash
        text = serializer.serialize(doc)
        assert isinstance(text, str)

    def test_figure_caption_with_brackets(self):
        """Caption with ] that could break markdown."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(Figure(caption="Image [1] of [3]", source="img.png"))
        text = serializer.serialize(doc)
        assert isinstance(text, str)


# ═══════════════════════════════════════════════════════════════════
# CONVERTER ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

class TestConverterErrorHandling:
    """All converters should handle edge cases without crashing."""

    def _make_doc(self) -> DoxDocument:
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        return doc

    def test_docx_empty_document(self):
        doc = self._make_doc()
        data = to_docx_bytes(doc)
        assert len(data) > 0

    def test_pdf_empty_document(self):
        doc = self._make_doc()
        data = to_pdf_bytes(doc)
        assert len(data) > 0

    def test_html_empty_document(self):
        doc = self._make_doc()
        html = to_html(doc)
        assert "<html" in html.lower() or "<div" in html.lower() or html == "" or isinstance(html, str)

    def test_json_empty_document(self):
        doc = self._make_doc()
        j = to_json(doc)
        assert isinstance(j, (str, dict))

    def test_markdown_empty_document(self):
        doc = self._make_doc()
        md = to_markdown(doc)
        assert isinstance(md, str)

    def test_docx_with_none_text_heading(self):
        """Heading with empty text should not crash DOCX."""
        doc = self._make_doc()
        doc.add_element(Heading(level=1, text=""))
        data = to_docx_bytes(doc)
        assert len(data) > 0

    def test_pdf_with_none_text_heading(self):
        """Heading with empty text should not crash PDF."""
        doc = self._make_doc()
        doc.add_element(Heading(level=1, text=""))
        data = to_pdf_bytes(doc)
        assert len(data) > 0

    def test_docx_table_with_zero_rows(self):
        doc = self._make_doc()
        doc.add_element(Table(rows=[]))
        data = to_docx_bytes(doc)
        assert len(data) > 0

    def test_pdf_table_with_zero_rows(self):
        doc = self._make_doc()
        doc.add_element(Table(rows=[]))
        data = to_pdf_bytes(doc)
        assert len(data) > 0

    def test_docx_with_special_chars(self):
        """Special XML chars in text should not crash DOCX."""
        doc = self._make_doc()
        doc.add_element(Paragraph(text='<script>alert("xss")</script> & "quotes"'))
        data = to_docx_bytes(doc)
        assert len(data) > 0

    def test_pdf_with_special_chars(self):
        """Special XML chars should not crash PDF."""
        doc = self._make_doc()
        doc.add_element(Paragraph(text='<script>alert("xss")</script> & "quotes"'))
        data = to_pdf_bytes(doc)
        assert len(data) > 0

    def test_html_with_special_chars(self):
        """Special chars should be escaped in HTML."""
        doc = self._make_doc()
        doc.add_element(Paragraph(text='<script>alert("xss")</script>'))
        html = to_html(doc)
        assert "<script>" not in html  # should be escaped

    def test_code_with_backticks_in_markdown(self):
        """Code containing ``` should not break markdown output."""
        doc = self._make_doc()
        doc.add_element(CodeBlock(code='print("```hello```")', language="python"))
        md = to_markdown(doc)
        assert "print" in md

    def test_all_element_types_to_all_formats(self):
        """Every element type should survive conversion to every format."""
        doc = self._make_doc()
        doc.add_element(Heading(level=1, text="Title"))
        doc.add_element(Paragraph(text="Body text"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[TableCell(text="H", is_header=True)]),
            TableRow(cells=[TableCell(text="D")]),
        ]))
        doc.add_element(CodeBlock(code="x = 1", language="python"))
        doc.add_element(MathBlock(expression="E=mc^2"))
        doc.add_element(ListBlock(ordered=True, items=[ListItem(text="Item 1")]))
        doc.add_element(Footnote(number=1, text="Footnote text"))
        doc.add_element(FormField(field_name="name", field_type=FormFieldType.TEXT, value="John"))
        doc.add_element(Figure(caption="A figure", source="fig.png"))
        doc.add_element(Annotation(annotation_type="comment", text="Note"))
        doc.add_element(PageBreak(from_page=1, to_page=2))

        # DOCX
        data = to_docx_bytes(doc)
        assert len(data) > 0

        # PDF
        data = to_pdf_bytes(doc)
        assert len(data) > 0

        # HTML
        html = to_html(doc)
        assert isinstance(html, str)

        # JSON
        j = to_json(doc)
        assert isinstance(j, (str, dict))

        # Markdown
        md = to_markdown(doc)
        assert isinstance(md, str)
        assert "Title" in md


# ═══════════════════════════════════════════════════════════════════
# VALIDATOR ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

class TestValidatorEdgeCases:

    def test_validate_empty_document(self):
        doc = DoxDocument()
        v = DoxValidator()
        result = v.validate(doc)
        # Returns ValidationResult, not a plain list
        assert hasattr(result, 'issues')
        assert isinstance(result.issues, list)

    def test_validate_threshold_out_of_range(self):
        """Threshold > 1 should be clamped, not crash."""
        v = DoxValidator(confidence_threshold=5.0)
        assert v.confidence_threshold <= 1.0

    def test_validate_negative_threshold(self):
        """Negative threshold should be clamped."""
        v = DoxValidator(confidence_threshold=-0.5)
        assert v.confidence_threshold >= 0.0

    def test_validate_document_with_all_element_types(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test", lang="en")
        doc.add_element(Heading(level=1, text="Title"))
        doc.add_element(Paragraph(text="Body"))
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="cell")])
        ]))
        doc.add_element(MathBlock(expression="x"))
        doc.add_element(CodeBlock(code="y"))
        doc.add_element(Footnote(number=1, text="fn"))
        v = DoxValidator()
        result = v.validate(doc)
        assert hasattr(result, 'issues')
        assert isinstance(result.issues, list)


# ═══════════════════════════════════════════════════════════════════
# MODEL VALIDATION
# ═══════════════════════════════════════════════════════════════════

class TestModelValidation:

    def test_tablecell_colspan_zero_raises(self):
        """colspan=0 should raise."""
        with pytest.raises(ValueError):
            TableCell(text="bad", colspan=0)

    def test_tablecell_rowspan_negative_raises(self):
        """rowspan=-1 should raise."""
        with pytest.raises(ValueError):
            TableCell(text="bad", rowspan=-1)

    def test_tablecell_defaults_valid(self):
        """Default TableCell should work."""
        cell = TableCell()
        assert cell.colspan == 1
        assert cell.rowspan == 1

    def test_footnote_negative_number_raises(self):
        with pytest.raises(ValueError):
            Footnote(number=-1, text="bad")

    def test_footnote_zero_allowed(self):
        """0 is the default, should be allowed."""
        fn = Footnote(number=0, text="ok")
        assert fn.number == 0

    def test_listblock_start_zero_raises(self):
        with pytest.raises(ValueError):
            ListBlock(start=0, items=[ListItem(text="item")])

    def test_listblock_default_valid(self):
        lb = ListBlock(items=[ListItem(text="item")])
        assert lb.start == 1
