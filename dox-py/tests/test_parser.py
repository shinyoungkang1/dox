"""Tests for the .dox parser."""

import pytest
from dox.parsers.parser import DoxParser
from dox.models.elements import (
    Heading, Paragraph, Table, CodeBlock, MathBlock,
    FormField, Chart, Annotation, Figure, Footnote, ListBlock,
)


@pytest.fixture
def parser():
    return DoxParser()


MINIMAL_DOX = """---dox
version: "1.0"
source: test.pdf
---

# Hello World

This is a paragraph.
"""


FULL_DOX = """---dox
version: "1.0"
source: annual-report.pdf
pages: 10
lang: en
---

# Q3 Results

Revenue grew **15%** year over year.

## Sales Table

||| table id="t1" caption="Regional Sales"
| Region   | Q3 2024 | Q3 2025 |
|----------|---------|---------|
| Americas | 105     | 120     |
| Europe   | 88      | 95      |
|||

$$E = mc^2$$ {math: latex}

```python
print("hello")
```

::form field="approved" type="checkbox" value="true"::

::chart type="bar" data-ref="t1" x="Region" y="Q3 2025"::

::annotation type="handwriting" confidence=0.85 text="OK"::

![Revenue chart](fig1.png) {figure: id="f1"}

[^1]: All figures in millions.

- Item one
- Item two
- Item three

---spatial page=1 grid=1000x1000
# Q3 Results @[45,62,520,95]
Revenue grew... @[45,120,890,145]
---/spatial

---meta
extracted_by: test-parser
extracted_at: "2026-04-10T14:30:00Z"
confidence:
  overall: 0.97
  t1: 0.99
provenance:
  source_hash: "sha256:abc123"
  extraction_pipeline:
    - "ocr:easyocr"
    - "vlm:granite-docling"
version_history:
  - ts: "2026-04-10T14:30:00Z"
    agent: test
    action: initial
---/meta
"""


class TestFrontmatter:
    def test_minimal(self, parser):
        doc = parser.parse(MINIMAL_DOX)
        assert doc.frontmatter.version == "1.0"
        assert doc.frontmatter.source == "test.pdf"

    def test_full(self, parser):
        doc = parser.parse(FULL_DOX)
        assert doc.frontmatter.version == "1.0"
        assert doc.frontmatter.pages == 10
        assert doc.frontmatter.lang == "en"


class TestHeadings:
    def test_h1(self, parser):
        doc = parser.parse(MINIMAL_DOX)
        headings = doc.headings()
        assert len(headings) >= 1
        assert headings[0].level == 1
        assert headings[0].text == "Hello World"

    def test_multiple_levels(self, parser):
        doc = parser.parse(FULL_DOX)
        headings = doc.headings()
        assert len(headings) == 2
        assert headings[0].level == 1
        assert headings[1].level == 2


class TestParagraphs:
    def test_basic(self, parser):
        doc = parser.parse(MINIMAL_DOX)
        paras = doc.paragraphs()
        assert len(paras) >= 1
        assert "paragraph" in paras[0].text


class TestTables:
    def test_table_parsing(self, parser):
        doc = parser.parse(FULL_DOX)
        tables = doc.tables()
        assert len(tables) == 1

        t = tables[0]
        assert t.table_id == "t1"
        assert t.caption == "Regional Sales"
        assert t.num_rows >= 3  # header + 2 data rows
        assert t.num_cols >= 3

    def test_table_header_detection(self, parser):
        doc = parser.parse(FULL_DOX)
        t = doc.tables()[0]
        headers = t.header_rows()
        data = t.data_rows()
        assert len(headers) >= 1
        assert len(data) >= 2
        assert headers[0].cells[0].text == "Region"


class TestCodeBlocks:
    def test_fenced(self, parser):
        doc = parser.parse(FULL_DOX)
        codes = [e for e in doc.elements if isinstance(e, CodeBlock)]
        assert len(codes) == 1
        assert codes[0].language == "python"
        assert "print" in codes[0].code

    def test_language_hints_with_non_word_characters(self, parser):
        text = """---dox
version: "1.0"
---

```typescript-react
const x = 1;
```

```c++
int main() { return 0; }
```
"""
        doc = parser.parse(text)
        codes = [e for e in doc.elements if isinstance(e, CodeBlock)]
        assert len(codes) == 2
        assert codes[0].language == "typescript-react"
        assert codes[1].language == "c++"


class TestMath:
    def test_math_block(self, parser):
        doc = parser.parse(FULL_DOX)
        maths = [e for e in doc.elements if isinstance(e, MathBlock)]
        assert len(maths) == 1
        assert "mc^2" in maths[0].expression


class TestFormFields:
    def test_checkbox(self, parser):
        doc = parser.parse(FULL_DOX)
        forms = [e for e in doc.elements if isinstance(e, FormField)]
        assert len(forms) == 1
        assert forms[0].field_name == "approved"
        assert forms[0].field_type.value == "checkbox"
        assert forms[0].value == "true"


class TestCharts:
    def test_chart(self, parser):
        doc = parser.parse(FULL_DOX)
        charts = [e for e in doc.elements if isinstance(e, Chart)]
        assert len(charts) == 1
        assert charts[0].chart_type == "bar"
        assert charts[0].data_ref == "t1"


class TestAnnotations:
    def test_handwriting(self, parser):
        doc = parser.parse(FULL_DOX)
        anns = [e for e in doc.elements if isinstance(e, Annotation)]
        assert len(anns) == 1
        assert anns[0].text == "OK"
        assert anns[0].confidence == 0.85


class TestFigures:
    def test_figure(self, parser):
        doc = parser.parse(FULL_DOX)
        figs = [e for e in doc.elements if isinstance(e, Figure)]
        assert len(figs) == 1
        assert figs[0].caption == "Revenue chart"
        assert figs[0].figure_id == "f1"


class TestFootnotes:
    def test_footnote(self, parser):
        doc = parser.parse(FULL_DOX)
        fns = [e for e in doc.elements if isinstance(e, Footnote)]
        assert len(fns) == 1
        assert fns[0].number == 1


class TestLists:
    def test_unordered(self, parser):
        doc = parser.parse(FULL_DOX)
        lists = [e for e in doc.elements if isinstance(e, ListBlock)]
        assert len(lists) == 1
        assert len(lists[0].items) == 3
        assert lists[0].items[0].text == "Item one"


class TestSpatialBlocks:
    def test_spatial_parsing(self, parser):
        doc = parser.parse(FULL_DOX)
        assert len(doc.spatial_blocks) == 1
        block = doc.spatial_blocks[0]
        assert block.page == 1
        assert block.grid_width == 1000
        assert len(block.annotations) >= 2

    def test_bbox_extraction(self, parser):
        doc = parser.parse(FULL_DOX)
        block = doc.spatial_blocks[0]
        ann = block.annotations[0]
        assert ann.bbox is not None
        assert ann.bbox.x1 == 45


class TestMetadata:
    def test_metadata_parsing(self, parser):
        doc = parser.parse(FULL_DOX)
        assert doc.metadata is not None
        assert doc.metadata.extracted_by == "test-parser"
        assert doc.metadata.confidence.overall == 0.97
        assert doc.metadata.confidence.elements.get("t1") == 0.99

    def test_provenance(self, parser):
        doc = parser.parse(FULL_DOX)
        prov = doc.metadata.provenance
        assert prov.source_hash == "sha256:abc123"
        assert len(prov.extraction_pipeline) == 2

    def test_version_history(self, parser):
        doc = parser.parse(FULL_DOX)
        vh = doc.metadata.version_history
        assert len(vh) == 1
        assert vh[0].agent == "test"


class TestRoundtrip:
    def test_parse_serialize_parse(self, parser):
        """Parse → serialize → parse should produce equivalent document."""
        from dox.serializer import DoxSerializer

        doc1 = parser.parse(FULL_DOX)
        serializer = DoxSerializer()
        text = serializer.serialize(doc1)
        doc2 = parser.parse(text)

        assert len(doc1.elements) == len(doc2.elements)
        assert doc1.frontmatter.version == doc2.frontmatter.version
        assert len(doc1.headings()) == len(doc2.headings())
        assert len(doc1.tables()) == len(doc2.tables())


class TestEdgeCases:
    def test_empty_doc(self, parser):
        doc = parser.parse("")
        assert doc.frontmatter.version == "1.0"
        assert len(doc.elements) == 0

    def test_markdown_only(self, parser):
        doc = parser.parse("# Just a heading\n\nA paragraph.\n")
        assert len(doc.headings()) == 1
        assert len(doc.paragraphs()) == 1

    def test_no_spatial_no_meta(self, parser):
        doc = parser.parse(MINIMAL_DOX)
        assert len(doc.spatial_blocks) == 0
        assert doc.metadata is None
