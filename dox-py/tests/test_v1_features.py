"""Tests for v1 features: blockquotes, TOC, statistics, task lists."""

import pytest
from dox import (
    DoxParser, DoxSerializer, DoxDocument, Blockquote, Heading, Paragraph,
    ListBlock, ListItem, HorizontalRule, CodeBlock, MathBlock
)
from dox.converters import to_html, to_markdown, to_json, to_pdf, to_docx
from dox.converters.to_json import to_dict


# ============================================================================
# BLOCKQUOTE TESTS
# ============================================================================

class TestBlockquoteParser:
    """Test blockquote parsing."""

    def test_parse_single_blockquote(self):
        """Parse a simple blockquote."""
        text = """---dox
version: "1.0"
---

> This is a blockquote
"""
        parser = DoxParser()
        doc = parser.parse(text)
        assert len(doc.elements) == 1
        assert isinstance(doc.elements[0], Blockquote)
        assert doc.elements[0].text == "This is a blockquote"

    def test_parse_multi_line_blockquote(self):
        """Parse blockquote with consecutive > lines."""
        text = """---dox
version: "1.0"
---

> First line
> Second line
> Third line
"""
        parser = DoxParser()
        doc = parser.parse(text)
        assert len(doc.elements) == 1
        assert isinstance(doc.elements[0], Blockquote)
        # Lines are joined with spaces
        assert "First line" in doc.elements[0].text
        assert "Second line" in doc.elements[0].text
        assert "Third line" in doc.elements[0].text

    def test_parse_blockquote_with_metadata(self):
        """Parse blockquote with element metadata."""
        text = """---dox
version: "1.0"
---

> Important quote {id: "bq1", page: 2}
"""
        parser = DoxParser()
        doc = parser.parse(text)
        assert len(doc.elements) == 1
        bq = doc.elements[0]
        assert isinstance(bq, Blockquote)
        assert bq.text == "Important quote"
        assert bq.element_id == "bq1"
        assert bq.page == 2

    def test_parse_blockquote_mixed_with_paragraphs(self):
        """Parse blockquotes mixed with regular paragraphs."""
        text = """---dox
version: "1.0"
---

Regular paragraph.

> This is a blockquote

Another paragraph.
"""
        parser = DoxParser()
        doc = parser.parse(text)
        assert len(doc.elements) == 3
        assert isinstance(doc.elements[0], Paragraph)
        assert isinstance(doc.elements[1], Blockquote)
        assert isinstance(doc.elements[2], Paragraph)


class TestBlockquoteSerializer:
    """Test blockquote serialization."""

    def test_serialize_blockquote(self):
        """Serialize blockquote back to .dox format."""
        doc = DoxDocument()
        doc.add_element(Blockquote(text="This is a quote"))
        serializer = DoxSerializer()
        result = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        assert "> This is a quote" in result

    def test_serialize_blockquote_with_metadata(self):
        """Serialize blockquote with metadata."""
        doc = DoxDocument()
        bq = Blockquote(text="Important", element_id="q1", page=3)
        doc.add_element(bq)
        serializer = DoxSerializer()
        result = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        assert "> Important" in result
        assert 'id: "q1"' in result
        assert "page: 3" in result

    def test_roundtrip_blockquote(self):
        """Test parse -> serialize -> parse roundtrip for blockquotes."""
        original = """---dox
version: "1.0"
---

> This is a blockquote
> With multiple lines
"""
        parser = DoxParser()
        doc = parser.parse(original)
        serializer = DoxSerializer()
        serialized = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        # Parse again
        doc2 = parser.parse(serialized)
        assert len(doc2.elements) == 1
        assert isinstance(doc2.elements[0], Blockquote)
        bq = doc2.elements[0]
        assert "This is a blockquote" in bq.text
        assert "With multiple lines" in bq.text


class TestBlockquoteConverters:
    """Test blockquote conversion to other formats."""

    def test_blockquote_to_html(self):
        """Convert blockquote to HTML."""
        doc = DoxDocument()
        doc.add_element(Blockquote(text="A famous quote"))
        html = to_html(doc, standalone=False)
        assert "<blockquote>" in html
        assert "<p>" in html
        assert "A famous quote" in html

    def test_blockquote_to_markdown(self):
        """Convert blockquote to Markdown."""
        doc = DoxDocument()
        doc.add_element(Blockquote(text="Quote me"))
        md = to_markdown(doc)
        assert "> Quote me" in md

    def test_blockquote_to_json(self):
        """Convert blockquote to JSON."""
        doc = DoxDocument()
        doc.add_element(Blockquote(text="JSON quote"))
        data = to_dict(doc)
        assert len(data["elements"]) == 1
        assert data["elements"][0]["type"] == "blockquote"
        assert data["elements"][0]["text"] == "JSON quote"

    def test_blockquote_to_pdf(self, tmp_path):
        """Convert blockquote to PDF."""
        doc = DoxDocument()
        doc.add_element(Blockquote(text="PDF quote"))
        output = tmp_path / "test.pdf"
        try:
            to_pdf(doc, output)
            assert output.exists()
        except ImportError:
            pytest.skip("reportlab not installed")

    def test_blockquote_to_docx(self, tmp_path):
        """Convert blockquote to DOCX."""
        doc = DoxDocument()
        doc.add_element(Blockquote(text="DOCX quote"))
        output = tmp_path / "test.docx"
        try:
            to_docx(doc, output)
            assert output.exists()
        except ImportError:
            pytest.skip("python-docx not installed")


# ============================================================================
# TABLE OF CONTENTS TESTS
# ============================================================================

class TestTableOfContents:
    """Test TOC generation."""

    def test_generate_toc_simple(self):
        """Generate TOC from simple document."""
        doc = DoxDocument()
        doc.add_element(Heading(level=1, text="Introduction"))
        doc.add_element(Heading(level=2, text="Background"))
        doc.add_element(Heading(level=2, text="Methods"))
        doc.add_element(Heading(level=1, text="Results"))

        toc = doc.generate_toc()
        assert len(toc) == 4
        assert toc[0] == (1, "Introduction", None)
        assert toc[1] == (2, "Background", None)
        assert toc[2] == (2, "Methods", None)
        assert toc[3] == (1, "Results", None)

    def test_generate_toc_with_ids(self):
        """Generate TOC with element IDs."""
        doc = DoxDocument()
        h1 = Heading(level=1, text="Chapter 1", element_id="ch1")
        h2 = Heading(level=2, text="Section 1.1", element_id="sec1")
        doc.add_element(h1)
        doc.add_element(h2)

        toc = doc.generate_toc()
        assert len(toc) == 2
        assert toc[0] == (1, "Chapter 1", "ch1")
        assert toc[1] == (2, "Section 1.1", "sec1")

    def test_generate_toc_empty_doc(self):
        """Generate TOC from document with no headings."""
        doc = DoxDocument()
        doc.add_element(Paragraph(text="Just a paragraph"))
        toc = doc.generate_toc()
        assert len(toc) == 0

    def test_toc_from_parsed_doc(self):
        """Generate TOC from a parsed document."""
        text = """---dox
version: "1.0"
---

# Main Title {id: "main"}

## Section A {id: "a"}

Content here.

## Section B {id: "b"}

More content.

# Conclusion
"""
        parser = DoxParser()
        doc = parser.parse(text)
        toc = doc.generate_toc()
        assert len(toc) == 4
        assert toc[0] == (1, "Main Title", "main")
        assert toc[1] == (2, "Section A", "a")
        assert toc[2] == (2, "Section B", "b")
        assert toc[3] == (1, "Conclusion", None)


# ============================================================================
# STATISTICS TESTS
# ============================================================================

class TestDocumentStatistics:
    """Test document statistics."""

    def test_statistics_simple(self):
        """Get statistics from simple document."""
        doc = DoxDocument()
        doc.add_element(Heading(level=1, text="Title"))
        doc.add_element(Paragraph(text="Para 1"))
        doc.add_element(Paragraph(text="Para 2"))

        stats = doc.statistics()
        assert stats["Heading"] == 1
        assert stats["Paragraph"] == 2

    def test_statistics_mixed_elements(self):
        """Get statistics from document with mixed elements."""
        doc = DoxDocument()
        doc.add_element(Heading(level=1, text="Title"))
        doc.add_element(Paragraph(text="Para"))
        doc.add_element(CodeBlock(code="x = 1"))
        doc.add_element(HorizontalRule())
        doc.add_element(MathBlock(expression="E=mc^2"))

        stats = doc.statistics()
        assert stats["Heading"] == 1
        assert stats["Paragraph"] == 1
        assert stats["CodeBlock"] == 1
        assert stats["HorizontalRule"] == 1
        assert stats["MathBlock"] == 1

    def test_statistics_empty_doc(self):
        """Get statistics from empty document."""
        doc = DoxDocument()
        stats = doc.statistics()
        assert len(stats) == 0

    def test_elements_of_type(self):
        """Filter elements by type."""
        doc = DoxDocument()
        doc.add_element(Heading(level=1, text="H1"))
        doc.add_element(Paragraph(text="P1"))
        doc.add_element(Heading(level=2, text="H2"))
        doc.add_element(Paragraph(text="P2"))

        headings = doc.elements_of_type(Heading)
        paragraphs = doc.elements_of_type(Paragraph)

        assert len(headings) == 2
        assert len(paragraphs) == 2
        assert all(isinstance(h, Heading) for h in headings)
        assert all(isinstance(p, Paragraph) for p in paragraphs)

    def test_elements_of_type_empty(self):
        """Filter for type that doesn't exist."""
        doc = DoxDocument()
        doc.add_element(Heading(level=1, text="Title"))
        doc.add_element(Paragraph(text="Para"))

        codes = doc.elements_of_type(CodeBlock)
        assert len(codes) == 0


# ============================================================================
# TASK LIST TESTS
# ============================================================================

class TestTaskListParser:
    """Test task list (checked items) parsing."""

    def test_parse_task_list_checked(self):
        """Parse task list with checked items."""
        text = """---dox
version: "1.0"
---

- [x] Completed task
- [ ] Pending task
- [x] Another done
"""
        parser = DoxParser()
        doc = parser.parse(text)
        assert len(doc.elements) == 1
        lb = doc.elements[0]
        assert isinstance(lb, ListBlock)
        assert len(lb.items) == 3
        assert lb.items[0].checked is True
        assert lb.items[0].text == "Completed task"
        assert lb.items[1].checked is False
        assert lb.items[1].text == "Pending task"
        assert lb.items[2].checked is True

    def test_parse_regular_list_no_checkbox(self):
        """Parse regular list without checkboxes."""
        text = """---dox
version: "1.0"
---

- Item one
- Item two
"""
        parser = DoxParser()
        doc = parser.parse(text)
        lb = doc.elements[0]
        assert lb.items[0].checked is None
        assert lb.items[1].checked is None

    def test_parse_nested_task_list(self):
        """Parse nested task lists."""
        text = """---dox
version: "1.0"
---

- [x] Parent task
  - [ ] Child task 1
  - [x] Child task 2
"""
        parser = DoxParser()
        doc = parser.parse(text)
        lb = doc.elements[0]
        assert lb.items[0].checked is True
        assert len(lb.items[0].children) == 2
        assert lb.items[0].children[0].checked is False
        assert lb.items[0].children[1].checked is True


class TestTaskListSerializer:
    """Test task list serialization."""

    def test_serialize_task_list(self):
        """Serialize task list back to .dox format."""
        doc = DoxDocument()
        items = [
            ListItem(text="Task 1", checked=True),
            ListItem(text="Task 2", checked=False),
            ListItem(text="Regular item", checked=None),
        ]
        doc.add_element(ListBlock(items=items, ordered=False))
        serializer = DoxSerializer()
        result = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        assert "- [x] Task 1" in result
        assert "- [ ] Task 2" in result
        assert "- Regular item" in result

    def test_roundtrip_task_list(self):
        """Test roundtrip for task lists."""
        original = """---dox
version: "1.0"
---

- [x] Done
- [ ] Not done
"""
        parser = DoxParser()
        doc = parser.parse(original)
        serializer = DoxSerializer()
        serialized = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        doc2 = parser.parse(serialized)
        lb = doc2.elements[0]
        assert lb.items[0].checked is True
        assert lb.items[1].checked is False


class TestTaskListConverters:
    """Test task list conversion to other formats."""

    def test_task_list_to_html(self):
        """Convert task list to HTML."""
        doc = DoxDocument()
        items = [
            ListItem(text="Done", checked=True),
            ListItem(text="Pending", checked=False),
        ]
        doc.add_element(ListBlock(items=items))
        html = to_html(doc, standalone=False)
        assert 'type="checkbox"' in html
        assert 'checked disabled' in html

    def test_task_list_to_markdown(self):
        """Convert task list to Markdown."""
        doc = DoxDocument()
        items = [
            ListItem(text="Done", checked=True),
            ListItem(text="Pending", checked=False),
        ]
        doc.add_element(ListBlock(items=items))
        md = to_markdown(doc)
        assert "- [x] Done" in md
        assert "- [ ] Pending" in md

    def test_task_list_to_json(self):
        """Convert task list to JSON."""
        doc = DoxDocument()
        items = [
            ListItem(text="Done", checked=True),
            ListItem(text="Pending", checked=False),
        ]
        doc.add_element(ListBlock(items=items))
        data = to_dict(doc)
        assert data["elements"][0]["items"][0]["checked"] is True
        assert data["elements"][0]["items"][1]["checked"] is False


# ============================================================================
# HORIZONTAL RULE TESTS (existing feature)
# ============================================================================

class TestHorizontalRule:
    """Test horizontal rules (should already work)."""

    def test_parse_horizontal_rules(self):
        """Parse various horizontal rule patterns."""
        text = """---dox
version: "1.0"
---

---

***

___
"""
        parser = DoxParser()
        doc = parser.parse(text)
        # Should have 3 horizontal rules
        hrs = [e for e in doc.elements if isinstance(e, HorizontalRule)]
        assert len(hrs) == 3


# ============================================================================
# MULTI-LINE MATH BLOCKS (existing feature)
# ============================================================================

class TestMultilineMathBlocks:
    """Test multi-line math blocks."""

    def test_parse_multiline_math(self):
        """Parse multi-line math blocks."""
        text = """---dox
version: "1.0"
---

$$
x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}
$$
"""
        parser = DoxParser()
        doc = parser.parse(text)
        assert len(doc.elements) == 1
        mb = doc.elements[0]
        assert isinstance(mb, MathBlock)
        assert mb.display_mode is True
        assert "frac" in mb.expression


# ============================================================================
# NESTED LISTS TESTS (existing feature)
# ============================================================================

class TestNestedLists:
    """Test nested list parsing."""

    def test_parse_nested_lists_two_levels(self):
        """Parse 2-level nested lists."""
        text = """---dox
version: "1.0"
---

- Item 1
  - Nested 1.1
  - Nested 1.2
- Item 2
  - Nested 2.1
"""
        parser = DoxParser()
        doc = parser.parse(text)
        lb = doc.elements[0]
        assert len(lb.items) == 2
        assert len(lb.items[0].children) == 2
        assert lb.items[0].children[0].text == "Nested 1.1"
        assert len(lb.items[1].children) == 1

    def test_roundtrip_nested_lists(self):
        """Test roundtrip for nested lists."""
        original = """---dox
version: "1.0"
---

- Parent 1
  - Child 1.1
  - Child 1.2
- Parent 2
"""
        parser = DoxParser()
        doc = parser.parse(original)
        serializer = DoxSerializer()
        serialized = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        doc2 = parser.parse(serialized)
        lb = doc2.elements[0]
        assert len(lb.items) == 2
        assert len(lb.items[0].children) == 2


# ============================================================================
# COMPREHENSIVE INTEGRATION TESTS
# ============================================================================

class TestV1FeaturesIntegration:
    """Integration tests combining multiple v1 features."""

    def test_document_with_all_features(self):
        """Parse document with blockquotes, task lists, and complex structure."""
        text = """---dox
version: "1.0"
source: test.pdf
---

# Report {id: "main"}

## Executive Summary

> "This is a blockquote from a source."

### Accomplishments

- [x] Completed item 1
- [x] Completed item 2
- [ ] Pending item

### Notes

Regular paragraph with no special formatting.

---

Another section after the horizontal rule.
"""
        parser = DoxParser()
        doc = parser.parse(text)

        # Check structure
        headings = doc.headings()
        assert len(headings) == 4  # Report, Executive Summary, Accomplishments, Notes
        assert headings[0].element_id == "main"

        blockquotes = doc.elements_of_type(Blockquote)
        assert len(blockquotes) == 1

        lists = doc.elements_of_type(ListBlock)
        assert len(lists) == 1
        assert lists[0].items[0].checked is True
        assert lists[0].items[2].checked is False

        # Check statistics
        stats = doc.statistics()
        assert stats["Heading"] == 4  # Report, Executive Summary, Accomplishments, Notes
        assert stats["Blockquote"] == 1
        assert stats["ListBlock"] == 1

        # Check TOC
        toc = doc.generate_toc()
        assert len(toc) == 4  # All 4 headings

        # Test serialization
        serializer = DoxSerializer()
        serialized = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        doc2 = parser.parse(serialized)
        assert len(doc2.headings()) == len(doc.headings())

    def test_full_roundtrip_with_converters(self):
        """Full roundtrip with multiple converters."""
        text = """---dox
version: "1.0"
---

# Title

This is content.

> A quote

- [x] Task done
- [ ] Task pending

---

End.
"""
        parser = DoxParser()
        doc = parser.parse(text)

        # Test serialization
        serializer = DoxSerializer()
        serialized = serializer.serialize(doc, include_spatial=False, include_metadata=False)
        doc2 = parser.parse(serialized)

        # Test converters
        html = to_html(doc2, standalone=False)
        assert "<h1>" in html

        md = to_markdown(doc2)
        assert "# Title" in md
        assert "> A quote" in md

        json_dict = to_dict(doc2)
        assert len(json_dict["elements"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
