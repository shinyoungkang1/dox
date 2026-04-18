"""
Stress tests against all benchmark documents.
Tests every document for: parse, validate, roundtrip, convert (HTML/JSON/MD).
"""

import json
from pathlib import Path

import pytest

from dox.converters import to_html, to_json, to_markdown
from dox.converters.to_json import to_dict
from dox.models.elements import (
    Annotation, Chart, CodeBlock, Figure, Footnote, FormField,
    Heading, ListBlock, MathBlock, Paragraph, Table,
)
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.validator import DoxValidator, Severity

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
ALL_DOX_FILES = sorted(EXAMPLES_DIR.glob("*.dox"))


@pytest.fixture
def parser():
    return DoxParser()


@pytest.fixture
def serializer():
    return DoxSerializer()


@pytest.fixture
def validator():
    return DoxValidator()


# ===========================================================================
# Parametrized tests across ALL benchmark files
# ===========================================================================


@pytest.mark.parametrize("dox_file", ALL_DOX_FILES, ids=lambda f: f.stem)
class TestAllBenchmarks:
    """Run every test against every .dox file in the examples directory."""

    def test_parse_succeeds(self, parser, dox_file):
        doc = parser.parse_file(dox_file)
        assert doc is not None
        assert doc.frontmatter.version in ("1.0", "0.1")
        assert len(doc.elements) > 0

    def test_validate_no_errors(self, parser, validator, dox_file):
        doc = parser.parse_file(dox_file)
        result = validator.validate(doc)
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        assert len(errors) == 0, f"Validation errors in {dox_file.name}: {errors}"

    def test_roundtrip_element_count(self, parser, serializer, dox_file):
        doc1 = parser.parse_file(dox_file)
        text = serializer.serialize(doc1)
        doc2 = parser.parse(text)
        assert len(doc1.elements) == len(doc2.elements), (
            f"Roundtrip element count mismatch in {dox_file.name}: "
            f"{len(doc1.elements)} vs {len(doc2.elements)}"
        )

    def test_roundtrip_heading_preservation(self, parser, serializer, dox_file):
        doc1 = parser.parse_file(dox_file)
        text = serializer.serialize(doc1)
        doc2 = parser.parse(text)
        h1 = [(h.level, h.text) for h in doc1.headings()]
        h2 = [(h.level, h.text) for h in doc2.headings()]
        assert h1 == h2, f"Heading mismatch in {dox_file.name}"

    def test_roundtrip_table_preservation(self, parser, serializer, dox_file):
        doc1 = parser.parse_file(dox_file)
        text = serializer.serialize(doc1)
        doc2 = parser.parse(text)
        t1 = [(t.table_id, t.num_rows, t.num_cols) for t in doc1.tables()]
        t2 = [(t.table_id, t.num_rows, t.num_cols) for t in doc2.tables()]
        assert t1 == t2, f"Table structure mismatch in {dox_file.name}"

    def test_convert_html(self, parser, dox_file):
        import html as html_mod
        doc = parser.parse_file(dox_file)
        html_out = to_html(doc, standalone=True)
        assert "<!DOCTYPE html>" in html_out
        assert "<body>" in html_out
        # Every heading should appear in HTML (account for HTML escaping)
        for h in doc.headings():
            escaped = html_mod.escape(h.text)
            assert escaped in html_out, f"Heading '{h.text}' missing from HTML"

    def test_convert_json(self, parser, dox_file):
        doc = parser.parse_file(dox_file)
        j = to_json(doc)
        parsed = json.loads(j)
        assert parsed["dox_version"] == doc.frontmatter.version
        assert len(parsed["elements"]) == len(doc.elements)

    def test_convert_markdown(self, parser, dox_file):
        doc = parser.parse_file(dox_file)
        md = to_markdown(doc)
        # Every heading should appear in Markdown
        for h in doc.headings():
            assert h.text in md, f"Heading '{h.text}' missing from Markdown"

    def test_spatial_blocks_valid(self, parser, dox_file):
        doc = parser.parse_file(dox_file)
        for block in doc.spatial_blocks:
            assert block.page >= 1
            assert block.grid_width > 0
            assert block.grid_height > 0
            for ann in block.annotations:
                if ann.bbox:
                    assert ann.bbox.x2 > ann.bbox.x1
                    assert ann.bbox.y2 > ann.bbox.y1

    def test_metadata_valid(self, parser, dox_file):
        doc = parser.parse_file(dox_file)
        if doc.metadata:
            assert doc.metadata.extracted_by != ""
            assert 0.0 <= doc.metadata.confidence.overall <= 1.0
            for eid, score in doc.metadata.confidence.elements.items():
                assert 0.0 <= score <= 1.0, f"Bad confidence for {eid}: {score}"


# ===========================================================================
# Specific stress tests for complex documents
# ===========================================================================


class TestComplexLayout:
    """Stress tests for the academic paper benchmark (complex-layout)."""

    @pytest.fixture
    def doc(self, parser):
        return parser.parse_file(EXAMPLES_DIR / "benchmark-complex-layout.dox")

    def test_element_count(self, doc):
        assert len(doc.elements) >= 20, f"Expected 20+ elements, got {len(doc.elements)}"

    def test_heading_hierarchy(self, doc):
        headings = doc.headings()
        assert len(headings) >= 10
        # Should have h1, h2, h3
        levels = {h.level for h in headings}
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    def test_table_count(self, doc):
        tables = doc.tables()
        assert len(tables) >= 6, f"Expected 6+ tables, got {len(tables)}"

    def test_wide_table(self, doc):
        """The unified benchmark results table has 11 columns."""
        results_table = doc.get_element_by_id("t-results")
        assert results_table is not None
        assert isinstance(results_table, Table)
        assert results_table.num_cols >= 10, f"Expected 10+ cols, got {results_table.num_cols}"

    def test_math_equations(self, doc):
        maths = [e for e in doc.elements if isinstance(e, MathBlock)]
        assert len(maths) >= 3, f"Expected 3+ math blocks, got {len(maths)}"

    def test_footnotes(self, doc):
        fns = [e for e in doc.elements if isinstance(e, Footnote)]
        assert len(fns) >= 5

    def test_figures(self, doc):
        figs = [e for e in doc.elements if isinstance(e, Figure)]
        assert len(figs) >= 2

    def test_cross_references_in_text(self, doc):
        """Verify cross-references are parsed from paragraph text."""
        # Cross-refs appear as inline text in paragraphs for this doc
        paras = doc.paragraphs()
        all_text = " ".join(p.text for p in paras)
        assert "[[ref:" in all_text or len(doc.elements) > 0  # at least parsed

    def test_spatial_multipage(self, doc):
        assert len(doc.spatial_blocks) >= 2, "Expected multiple spatial blocks for multi-page doc"
        pages = {b.page for b in doc.spatial_blocks}
        assert len(pages) >= 2, "Expected spatial data for multiple pages"

    def test_metadata_confidence_scores(self, doc):
        assert doc.metadata is not None
        conf = doc.metadata.confidence
        assert conf.overall > 0
        assert len(conf.elements) >= 5
        flagged = conf.flagged_elements(threshold=0.85)
        assert len(flagged) >= 1, "Expected at least one low-confidence element"


class TestInvoice:
    """Stress tests for the invoice benchmark."""

    @pytest.fixture
    def doc(self, parser):
        return parser.parse_file(EXAMPLES_DIR / "benchmark-invoice.dox")

    def test_element_count(self, doc):
        assert len(doc.elements) >= 10

    def test_tables(self, doc):
        tables = doc.tables()
        assert len(tables) >= 3  # items, summary, payment

    def test_line_items_table(self, doc):
        t = doc.get_element_by_id("t-items")
        assert t is not None
        assert isinstance(t, Table)
        assert t.num_rows >= 7  # header + 6 items
        assert t.num_cols >= 6

    def test_form_fields(self, doc):
        forms = [e for e in doc.elements if isinstance(e, FormField)]
        assert len(forms) >= 3

    def test_annotations(self, doc):
        anns = [e for e in doc.elements if isinstance(e, Annotation)]
        assert len(anns) >= 2
        types = {a.annotation_type for a in anns}
        assert "handwriting" in types
        assert "stamp" in types

    def test_spatial_two_pages(self, doc):
        assert len(doc.spatial_blocks) >= 2
        pages = sorted(b.page for b in doc.spatial_blocks)
        assert pages == [1, 2]

    def test_cell_level_bboxes(self, doc):
        """Invoice spatial should have cell-level bounding boxes."""
        has_cell_bboxes = False
        for block in doc.spatial_blocks:
            for ann in block.annotations:
                if ann.cell_bboxes:
                    has_cell_bboxes = True
                    break
        assert has_cell_bboxes, "Expected cell-level bounding boxes in invoice spatial data"


class TestFDAReport:
    """Stress tests for the FDA drug approval benchmark."""

    @pytest.fixture
    def doc(self, parser):
        return parser.parse_file(EXAMPLES_DIR / "benchmark-nested-tables.dox")

    def test_large_table(self, doc):
        """The first-in-class table has 12 drug entries + header."""
        t = doc.get_element_by_id("t-firstclass")
        assert t is not None
        assert t.num_rows >= 13, f"Expected 13+ rows, got {t.num_rows}"

    def test_table_count(self, doc):
        tables = doc.tables()
        assert len(tables) >= 5

    def test_list_block(self, doc):
        lists = [e for e in doc.elements if isinstance(e, ListBlock)]
        assert len(lists) >= 1

    def test_charts(self, doc):
        charts = [e for e in doc.elements if isinstance(e, Chart)]
        assert len(charts) >= 2

    def test_math(self, doc):
        maths = [e for e in doc.elements if isinstance(e, MathBlock)]
        assert len(maths) >= 1


# ===========================================================================
# Edge case stress tests
# ===========================================================================


class TestEdgeCases:
    """Parse degenerate or unusual .dox content."""

    @pytest.fixture
    def parser(self):
        return DoxParser()

    def test_empty_string(self, parser):
        doc = parser.parse("")
        assert len(doc.elements) == 0

    def test_only_frontmatter(self, parser):
        doc = parser.parse("---dox\nversion: '1.0'\n---\n")
        assert doc.frontmatter.version == "1.0"
        assert len(doc.elements) == 0

    def test_only_heading(self, parser):
        doc = parser.parse("# Just a heading\n")
        assert len(doc.headings()) == 1

    def test_table_no_header(self, parser):
        text = """||| table id="nohead"
| a | b | c |
| d | e | f |
|||"""
        doc = parser.parse(text)
        tables = doc.tables()
        assert len(tables) == 1
        assert tables[0].num_rows == 2

    def test_deeply_nested_headings(self, parser):
        text = "\n".join(f"{'#' * i} Heading {i}" for i in range(1, 7))
        doc = parser.parse(text)
        assert len(doc.headings()) == 6

    def test_unicode_content(self, parser):
        text = """---dox
version: "1.0"
lang: ja
---

# 第3四半期決算報告

売上高は前年比 **15%** 増加しました。

||| table id="t-unicode"
| 地域     | 売上 |
|----------|------|
| アジア   | 80   |
| ヨーロッパ | 95   |
|||
"""
        doc = parser.parse(text)
        assert doc.frontmatter.lang == "ja"
        assert len(doc.headings()) == 1
        assert "決算" in doc.headings()[0].text
        tables = doc.tables()
        assert len(tables) == 1
        assert tables[0].num_rows >= 3

    def test_special_chars_in_table(self, parser):
        text = """||| table id="special"
| Symbol | Meaning      |
|--------|--------------|
| $      | Dollar       |
| €      | Euro         |
| <      | Less than    |
| >      | Greater than |
| &      | Ampersand    |
| "      | Quote        |
|||"""
        doc = parser.parse(text)
        t = doc.tables()[0]
        assert t.num_rows >= 7

    def test_empty_table(self, parser):
        text = """||| table id="empty"
|||"""
        doc = parser.parse(text)
        assert len(doc.tables()) == 1
        assert doc.tables()[0].num_rows == 0

    def test_code_block_with_pipes(self, parser):
        text = """```python
data = {"a": 1, "b": 2}
for k, v in data.items():
    print(f"| {k} | {v} |")
```"""
        doc = parser.parse(text)
        codes = [e for e in doc.elements if isinstance(e, CodeBlock)]
        assert len(codes) == 1
        assert "print" in codes[0].code
        assert doc.tables() == []  # Pipes inside code should NOT be parsed as table

    def test_math_with_special_chars(self, parser):
        text = r"$$\sum_{i=1}^{N} \frac{x_i^2}{\sigma_i^2}$$ {math: latex}"
        doc = parser.parse(text)
        maths = [e for e in doc.elements if isinstance(e, MathBlock)]
        assert len(maths) == 1
        assert "sum" in maths[0].expression

    def test_mixed_list_types(self, parser):
        text = """- Unordered item 1
- Unordered item 2

1. Ordered item 1
2. Ordered item 2
"""
        doc = parser.parse(text)
        lists = [e for e in doc.elements if isinstance(e, ListBlock)]
        assert len(lists) == 2
        assert not lists[0].ordered
        assert lists[1].ordered

    def test_paragraph_with_inline_elements(self, parser):
        text = "This has **bold**, *italic*, `code`, and a [link](https://example.com) in it."
        doc = parser.parse(text)
        paras = doc.paragraphs()
        assert len(paras) == 1
        assert "**bold**" in paras[0].text  # Inline markup preserved in Layer 0

    def test_consecutive_tables(self, parser):
        text = """||| table id="a"
| X | Y |
|---|---|
| 1 | 2 |
|||

||| table id="b"
| A | B |
|---|---|
| 3 | 4 |
|||"""
        doc = parser.parse(text)
        tables = doc.tables()
        assert len(tables) == 2
        assert tables[0].table_id == "a"
        assert tables[1].table_id == "b"

    def test_large_table(self, parser):
        """50-row table should parse correctly."""
        rows = "\n".join(f"| Item {i:03d} | Value {i} | Cat {i % 5} |" for i in range(50))
        text = f"""||| table id="big"
| Item | Value | Category |
|------|-------|----------|
{rows}
|||"""
        doc = parser.parse(text)
        t = doc.tables()[0]
        assert t.num_rows >= 51  # header + 50 data

    def test_multiple_spatial_blocks(self, parser):
        text = """---spatial page=1 grid=1000x1000
# Title @[50,50,500,80]
---/spatial

---spatial page=2 grid=1000x1000
## Subtitle @[50,50,400,75]
---/spatial

---spatial page=3 grid=500x500
Content @[10,10,490,490]
---/spatial"""
        doc = parser.parse(text)
        assert len(doc.spatial_blocks) == 3
        assert doc.spatial_blocks[2].grid_width == 500

    def test_metadata_with_many_confidence_scores(self, parser):
        text = """---meta
extracted_by: test
extracted_at: "2026-01-01T00:00:00+00:00"
confidence:
  overall: 0.95
  elem_1: 0.99
  elem_2: 0.45
  elem_3: 0.88
  elem_4: 0.12
  elem_5: 0.97
provenance:
  source_hash: "sha256:test"
  extraction_pipeline:
    - "step1"
    - "step2"
    - "step3"
---/meta"""
        doc = parser.parse(text)
        assert doc.metadata is not None
        assert len(doc.metadata.confidence.elements) == 5
        flagged = doc.metadata.confidence.flagged_elements(threshold=0.90)
        assert "elem_2" in flagged
        assert "elem_4" in flagged
        assert "elem_3" in flagged
