"""
Tests for cross-page element handling: PageBreak, table continuation,
paragraph merging, page assignment, and the DoxMerger utility.
"""

import pytest
from pathlib import Path

from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    BoundingBox,
    Heading,
    PageBreak,
    Paragraph,
    Table,
    TableCell,
    TableRow,
)
from dox.models.spatial import SpatialAnnotation, SpatialBlock
from dox.merger import DoxMerger, MergeConfig, merge_document

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# =====================================================================
# PageBreak Parsing & Serialization
# =====================================================================

class TestPageBreak:
    def test_parse_page_break(self):
        text = """---dox
version: '1.0'
source: test.pdf
---

## Chapter 1

Some text here.

---page-break from=1 to=2---

## Chapter 2

More text here.
"""
        doc = DoxParser().parse(text)
        page_breaks = [e for e in doc.elements if isinstance(e, PageBreak)]
        assert len(page_breaks) == 1
        assert page_breaks[0].from_page == 1
        assert page_breaks[0].to_page == 2

    def test_serialize_page_break(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Heading(level=1, text="Page 1"))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Heading(level=1, text="Page 2"))
        text = DoxSerializer().serialize(doc)
        assert "---page-break from=1 to=2---" in text

    def test_roundtrip_page_break(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Paragraph(text="Before break"))
        doc.add_element(PageBreak(from_page=3, to_page=4))
        doc.add_element(Paragraph(text="After break"))

        text = DoxSerializer().serialize(doc)
        doc2 = DoxParser().parse(text)
        pbs = [e for e in doc2.elements if isinstance(e, PageBreak)]
        assert len(pbs) == 1
        assert pbs[0].from_page == 3
        assert pbs[0].to_page == 4

    def test_multiple_page_breaks(self):
        text = """---dox
version: '1.0'
source: test.pdf
---

Text p1

---page-break from=1 to=2---

Text p2

---page-break from=2 to=3---

Text p3

---page-break from=3 to=4---

Text p4
"""
        doc = DoxParser().parse(text)
        pbs = [e for e in doc.elements if isinstance(e, PageBreak)]
        assert len(pbs) == 3
        assert [(pb.from_page, pb.to_page) for pb in pbs] == [(1, 2), (2, 3), (3, 4)]


# =====================================================================
# Table Continuation Parsing
# =====================================================================

class TestTableContinuation:
    def test_parse_continuation_table(self):
        text = """---dox
version: '1.0'
source: report.pdf
---

||| table id="t1" pages="1-2"
| Name | Value |
|------|-------|
| A    | 10    |
| B    | 20    |
|||

---page-break from=1 to=2---

||| table id="t1_cont" continuation-of="t1"
| C    | 30    |
| D    | 40    |
|||
"""
        doc = DoxParser().parse(text)
        tables = [e for e in doc.elements if isinstance(e, Table)]
        assert len(tables) == 2
        assert tables[0].table_id == "t1"
        assert tables[0].page_range == (1, 2)
        assert tables[1].continuation_of == "t1"

    def test_roundtrip_continuation_table(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        t1 = Table(
            table_id="t1",
            page_range=(1, 3),
            rows=[
                TableRow(cells=[TableCell(text="A", is_header=True)], is_header=True),
                TableRow(cells=[TableCell(text="1")]),
            ],
        )
        t1.element_id = "t1"
        t2 = Table(
            table_id="t1_cont",
            continuation_of="t1",
            rows=[
                TableRow(cells=[TableCell(text="2")]),
            ],
        )
        doc.add_element(t1)
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(t2)

        text = DoxSerializer().serialize(doc)
        assert 'pages="1-3"' in text
        assert 'continuation-of="t1"' in text

        doc2 = DoxParser().parse(text)
        tables2 = [e for e in doc2.elements if isinstance(e, Table)]
        assert tables2[0].page_range == (1, 3)
        assert tables2[1].continuation_of == "t1"


# =====================================================================
# DoxMerger — Table Merging
# =====================================================================

class TestMergerTables:
    def test_merge_continuation_tables(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        t1 = Table(
            table_id="t1",
            rows=[
                TableRow(cells=[TableCell(text="Name", is_header=True), TableCell(text="Val", is_header=True)], is_header=True),
                TableRow(cells=[TableCell(text="A"), TableCell(text="1")]),
            ],
        )
        t1.element_id = "t1"
        t2 = Table(
            table_id="t1_cont",
            continuation_of="t1",
            page=2,
            rows=[
                TableRow(cells=[TableCell(text="B"), TableCell(text="2")]),
                TableRow(cells=[TableCell(text="C"), TableCell(text="3")]),
            ],
        )
        doc.add_element(t1)
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(t2)

        result = merge_document(doc)
        merged = result.document
        tables = [e for e in merged.elements if isinstance(e, Table)]
        assert len(tables) == 1  # continuation merged into parent
        assert tables[0].num_rows == 4  # 1 header + 1 data (orig) + 2 data (continuation)
        assert result.tables_merged == 1

    def test_merge_adjacent_tables_across_page_break(self):
        """Tables with same column count across a page break should merge."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        t1 = Table(
            page=1,
            rows=[
                TableRow(cells=[TableCell(text="A", is_header=True), TableCell(text="B", is_header=True)], is_header=True),
                TableRow(cells=[TableCell(text="1"), TableCell(text="2")]),
            ],
        )
        t2 = Table(
            page=2,
            rows=[
                # No header row — continuation
                TableRow(cells=[TableCell(text="3"), TableCell(text="4")]),
            ],
        )
        doc.add_element(t1)
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(t2)

        result = merge_document(doc)
        tables = [e for e in result.document.elements if isinstance(e, Table)]
        assert len(tables) == 1
        assert tables[0].num_rows == 3

    def test_no_merge_different_column_count(self):
        """Tables with different column counts should NOT merge."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        t1 = Table(
            page=1,
            rows=[
                TableRow(cells=[TableCell(text="A"), TableCell(text="B")]),
            ],
        )
        t2 = Table(
            page=2,
            rows=[
                TableRow(cells=[TableCell(text="X"), TableCell(text="Y"), TableCell(text="Z")]),
            ],
        )
        doc.add_element(t1)
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(t2)

        result = merge_document(doc)
        tables = [e for e in result.document.elements if isinstance(e, Table)]
        assert len(tables) == 2  # not merged


# =====================================================================
# DoxMerger — Paragraph Merging
# =====================================================================

class TestMergerParagraphs:
    def test_merge_split_paragraph(self):
        """Paragraph ending mid-sentence + PageBreak + continuation → merge."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Paragraph(text="The results showed that the treatment was effective in"))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Paragraph(text="reducing symptoms by 45% compared to the control group."))

        result = merge_document(doc)
        paras = [e for e in result.document.elements if isinstance(e, Paragraph)]
        assert len(paras) == 1
        assert "effective in reducing" in paras[0].text
        assert result.paragraphs_merged == 1

    def test_no_merge_complete_sentences(self):
        """Paragraphs ending with period should NOT merge."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Paragraph(text="This is a complete sentence."))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Paragraph(text="This is a new paragraph on page 2."))

        result = merge_document(doc)
        paras = [e for e in result.document.elements if isinstance(e, Paragraph)]
        assert len(paras) == 2  # not merged

    def test_merge_hyphenated_word(self):
        """Words broken by hyphen at page boundary → rejoined."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Paragraph(text="The pharma-"))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Paragraph(text="ceutical industry has grown rapidly"))

        result = merge_document(doc)
        paras = [e for e in result.document.elements if isinstance(e, Paragraph)]
        assert len(paras) == 1
        assert "pharmaceutical" in paras[0].text


# =====================================================================
# DoxMerger — Page Assignment
# =====================================================================

class TestMergerPageAssignment:
    def test_assign_pages_from_breaks(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Heading(level=1, text="Title"))
        doc.add_element(Paragraph(text="Intro text"))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Heading(level=2, text="Section"))
        doc.add_element(Paragraph(text="More text"))
        doc.add_element(PageBreak(from_page=2, to_page=3))
        doc.add_element(Paragraph(text="Final text"))

        result = merge_document(doc, merge_tables=False, merge_paragraphs=False)
        elems = [e for e in result.document.elements if not isinstance(e, PageBreak)]
        assert elems[0].page == 1  # Title
        assert elems[1].page == 1  # Intro text
        assert elems[2].page == 2  # Section
        assert elems[3].page == 2  # More text
        assert elems[4].page == 3  # Final text

    def test_assign_pages_from_spatial(self):
        """When no PageBreaks exist, infer pages from spatial blocks."""
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Heading(level=1, text="Introduction"))
        doc.add_element(Paragraph(text="The field of machine learning"))

        doc.spatial_blocks = [
            SpatialBlock(page=1, annotations=[
                SpatialAnnotation(line_text="Introduction", bbox=BoundingBox(10, 10, 200, 50)),
            ]),
            SpatialBlock(page=2, annotations=[
                SpatialAnnotation(line_text="The field of machine learning", bbox=BoundingBox(10, 10, 500, 50)),
            ]),
        ]

        result = merge_document(doc, merge_tables=False, merge_paragraphs=False)
        heading = [e for e in result.document.elements if isinstance(e, Heading)][0]
        para = [e for e in result.document.elements if isinstance(e, Paragraph)][0]
        assert heading.page == 1
        assert para.page == 2


# =====================================================================
# DoxMerger — Remove PageBreaks
# =====================================================================

class TestRemovePageBreaks:
    def test_remove(self):
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(version="1.0", source="test.pdf")
        doc.add_element(Paragraph(text="A"))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Paragraph(text="B"))

        result = merge_document(doc, remove_page_breaks=True)
        pbs = [e for e in result.document.elements if isinstance(e, PageBreak)]
        assert len(pbs) == 0
        assert result.page_breaks_removed == 1


# =====================================================================
# Complex Cross-Page Document Stress Test
# =====================================================================

class TestComplexCrossPage:
    """Simulate a realistic multi-page document extraction with splits."""

    def _build_complex_doc(self) -> DoxDocument:
        doc = DoxDocument()
        doc.frontmatter = Frontmatter(
            version="1.0", source="annual-report-2025.pdf", pages=5
        )

        # Page 1
        doc.add_element(Heading(level=1, text="Annual Financial Report 2025"))
        doc.add_element(Paragraph(text="This report summarizes the financial performance of Acme Corp for the fiscal year ending December 31, 2025."))

        # Table that starts on page 1 and continues on page 2
        t1 = Table(
            table_id="revenue_table",
            caption="Quarterly Revenue",
            page=1,
            page_range=(1, 2),
            rows=[
                TableRow(cells=[
                    TableCell(text="Quarter", is_header=True),
                    TableCell(text="Revenue ($M)", is_header=True),
                    TableCell(text="YoY Growth", is_header=True),
                ], is_header=True),
                TableRow(cells=[TableCell(text="Q1"), TableCell(text="125.3"), TableCell(text="+12%")]),
                TableRow(cells=[TableCell(text="Q2"), TableCell(text="138.7"), TableCell(text="+15%")]),
            ],
        )
        t1.element_id = "revenue_table"
        doc.add_element(t1)

        doc.add_element(PageBreak(from_page=1, to_page=2))

        # Continuation of table on page 2
        t1_cont = Table(
            table_id="revenue_table_p2",
            continuation_of="revenue_table",
            page=2,
            rows=[
                TableRow(cells=[TableCell(text="Q3"), TableCell(text="142.1"), TableCell(text="+18%")]),
                TableRow(cells=[TableCell(text="Q4"), TableCell(text="155.9"), TableCell(text="+22%")]),
            ],
        )
        doc.add_element(t1_cont)

        # Paragraph split across pages 2→3
        doc.add_element(Paragraph(text="The company's growth trajectory was driven by expansion into"))

        doc.add_element(PageBreak(from_page=2, to_page=3))

        doc.add_element(Paragraph(text="new markets in Southeast Asia and increased adoption of our SaaS platform."))

        # Page 3: Normal content
        doc.add_element(Heading(level=2, text="Operating Expenses"))
        doc.add_element(Paragraph(text="Operating expenses increased 8% year-over-year."))

        doc.add_element(PageBreak(from_page=3, to_page=4))

        # Page 4: Another split table
        t2 = Table(
            page=4,
            rows=[
                TableRow(cells=[
                    TableCell(text="Category", is_header=True),
                    TableCell(text="Amount", is_header=True),
                ], is_header=True),
                TableRow(cells=[TableCell(text="R&D"), TableCell(text="$45M")]),
                TableRow(cells=[TableCell(text="Sales"), TableCell(text="$32M")]),
            ],
        )
        doc.add_element(t2)

        doc.add_element(PageBreak(from_page=4, to_page=5))

        # Same-column table on page 5 without header = implicit continuation
        t3 = Table(
            page=5,
            rows=[
                TableRow(cells=[TableCell(text="G&A"), TableCell(text="$18M")]),
                TableRow(cells=[TableCell(text="Total"), TableCell(text="$95M")]),
            ],
        )
        doc.add_element(t3)

        return doc

    def test_merge_complex_doc(self):
        doc = self._build_complex_doc()
        result = merge_document(doc, remove_page_breaks=False)
        merged = result.document

        # Tables should be merged
        tables = [e for e in merged.elements if isinstance(e, Table)]
        assert len(tables) == 2  # revenue table + expenses table (both merged)

        # Revenue table: 1 header + 4 data rows
        revenue = [t for t in tables if t.table_id == "revenue_table"]
        assert len(revenue) == 1
        assert revenue[0].num_rows == 5

        # Expenses table: should have merged the continuation
        expenses = [t for t in tables if t.table_id != "revenue_table"]
        assert len(expenses) == 1
        assert expenses[0].num_rows == 5  # 1 header + 4 data

        # Paragraphs should be merged
        paras = [e for e in merged.elements if isinstance(e, Paragraph)]
        growth_para = [p for p in paras if "growth trajectory" in p.text]
        assert len(growth_para) == 1
        assert "new markets" in growth_para[0].text

    def test_page_assignment(self):
        doc = self._build_complex_doc()
        result = merge_document(doc, merge_tables=False, merge_paragraphs=False)
        merged = result.document

        headings = [e for e in merged.elements if isinstance(e, Heading)]
        assert headings[0].page == 1  # Annual Financial Report
        assert headings[1].page == 3  # Operating Expenses

    def test_roundtrip_after_merge(self):
        """Merged document should roundtrip cleanly."""
        doc = self._build_complex_doc()
        result = merge_document(doc, remove_page_breaks=True)
        merged = result.document

        text = DoxSerializer().serialize(merged)
        doc2 = DoxParser().parse(text)

        assert len(doc2.elements) == len(merged.elements)


# =====================================================================
# Existing benchmark documents — page break injection test
# =====================================================================

class TestBenchmarkWithPageBreaks:
    """Test that injecting page breaks into existing benchmarks doesn't break anything."""

    @pytest.mark.parametrize("filename", [
        "benchmark-complex-layout.dox",
        "benchmark-invoice.dox",
        "benchmark-nested-tables.dox",
    ])
    def test_inject_and_merge(self, filename):
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            pytest.skip(f"{filename} not found")

        doc = DoxParser().parse_file(filepath)
        original_count = len(doc.elements)

        # Inject page breaks every 5 elements
        new_elements = []
        page = 1
        for i, el in enumerate(doc.elements):
            if i > 0 and i % 5 == 0:
                new_elements.append(PageBreak(from_page=page, to_page=page + 1))
                page += 1
            new_elements.append(el)
        doc.elements = new_elements

        # Merge should assign pages and not crash
        result = merge_document(doc, merge_tables=False, merge_paragraphs=False)
        assert result.pages_assigned > 0

        # Remove page breaks and verify element count preserved
        result2 = merge_document(doc, merge_tables=False, merge_paragraphs=False, remove_page_breaks=True)
        non_pb = [e for e in result2.document.elements if not isinstance(e, PageBreak)]
        assert len(non_pb) == original_count
