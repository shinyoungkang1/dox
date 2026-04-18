"""
Real PDF Extraction Tests.

These tests run actual PDF extraction using PyMuPDF and verify the full
pipeline: PDF → extract → .dox → serialize → parse → convert.

This is the HONEST test suite — it shows what actually works and what
doesn't when starting from raw PDFs (not ground truth).
"""

import json
import pytest
from pathlib import Path

from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.converters.to_html import to_html
from dox.converters.to_json import to_json
from dox.converters.to_markdown import to_markdown
from dox.chunker import chunk_document, ChunkStrategy
from dox.merger import merge_document
from dox.models.elements import Heading, Paragraph, PageBreak, Figure

TEST_PDF = Path("/sessions/nice-amazing-wright/dox-project/test_report.pdf")


@pytest.fixture(scope="module")
def pdf_doc():
    if not TEST_PDF.exists():
        pytest.skip("Test PDF not available")
    from dox.exporters.pymupdf_exporter import pdf_to_dox
    return pdf_to_dox(TEST_PDF)


class TestPDFExtraction:
    """Test that real PDF extraction produces valid .dox."""

    def test_extracts_pages(self, pdf_doc):
        assert pdf_doc.frontmatter.pages == 3

    def test_extracts_headings(self, pdf_doc):
        headings = [e for e in pdf_doc.elements if isinstance(e, Heading)]
        assert len(headings) >= 2
        assert any("Financial" in h.text for h in headings)

    def test_extracts_paragraphs(self, pdf_doc):
        paras = [e for e in pdf_doc.elements if isinstance(e, Paragraph)]
        assert len(paras) >= 3

    def test_has_page_breaks(self, pdf_doc):
        breaks = [e for e in pdf_doc.elements if isinstance(e, PageBreak)]
        assert len(breaks) == 2  # 3 pages = 2 breaks

    def test_has_spatial_data(self, pdf_doc):
        assert len(pdf_doc.spatial_blocks) == 3  # One per page
        for block in pdf_doc.spatial_blocks:
            assert len(block.annotations) > 0
            for ann in block.annotations:
                if ann.bbox:
                    assert ann.bbox.x1 >= 0
                    assert ann.bbox.y1 >= 0

    def test_all_elements_have_page(self, pdf_doc):
        for el in pdf_doc.elements:
            if isinstance(el, PageBreak):
                continue
            assert el.page is not None, f"{type(el).__name__} missing page"

    def test_has_metadata(self, pdf_doc):
        assert pdf_doc.metadata is not None
        assert pdf_doc.metadata.extracted_by == "PyMuPDF"
        assert pdf_doc.metadata.confidence.overall == 0.7


class TestPDFPipeline:
    """Full pipeline on real extracted PDF."""

    def test_serialize_roundtrip(self, pdf_doc):
        text = DoxSerializer().serialize(pdf_doc)
        doc2 = DoxParser().parse(text)
        # Element count should be close
        drift = abs(len(doc2.elements) - len(pdf_doc.elements))
        assert drift <= 5, f"Element drift: {len(pdf_doc.elements)} → {len(doc2.elements)}"

    def test_to_html(self, pdf_doc):
        html = to_html(pdf_doc)
        assert "<!DOCTYPE html>" in html
        assert "Financial" in html

    def test_to_json(self, pdf_doc):
        j = to_json(pdf_doc)
        data = json.loads(j)
        assert "elements" in data
        assert len(data["elements"]) > 0

    def test_to_markdown(self, pdf_doc):
        md = to_markdown(pdf_doc)
        assert "Financial" in md
        assert len(md) > 100

    def test_chunk_semantic(self, pdf_doc):
        chunks = chunk_document(pdf_doc, strategy=ChunkStrategy.SEMANTIC)
        assert len(chunks) > 0
        for c in chunks:
            assert c.text.strip()

    def test_merge(self, pdf_doc):
        result = merge_document(pdf_doc)
        assert result.document is not None
        assert len(result.document.elements) > 0


class TestExtractionHonesty:
    """Honest assessment of what extraction CANNOT do."""

    def test_tables_not_structured(self, pdf_doc):
        """PyMuPDF basic extraction doesn't produce structured tables from plain text."""
        from dox.models.elements import Table
        tables = [e for e in pdf_doc.elements if isinstance(e, Table)]
        # Honest: basic PyMuPDF won't detect tables without ruled lines
        print(f"\nStructured tables detected: {len(tables)}")
        print("→ Basic PyMuPDF cannot detect tables from text alignment alone")
        print("→ Need vision model (GPT-4o, Qwen2-VL) or Docling for table detection")

    def test_math_not_latex(self, pdf_doc):
        """PyMuPDF cannot recover LaTeX from rendered equations."""
        from dox.models.elements import MathBlock
        math = [e for e in pdf_doc.elements if isinstance(e, MathBlock)]
        print(f"\nMath blocks detected: {len(math)}")
        print("→ PyMuPDF extracts rendered text, not LaTeX source")
        print("→ Need Nougat or vision model for LaTeX recovery")

    def test_extraction_quality_report(self, pdf_doc):
        """Print honest extraction quality summary."""
        from dox.models.elements import Table, MathBlock

        headings = [e for e in pdf_doc.elements if isinstance(e, Heading)]
        paras = [e for e in pdf_doc.elements if isinstance(e, Paragraph)]
        tables = [e for e in pdf_doc.elements if isinstance(e, Table)]
        math = [e for e in pdf_doc.elements if isinstance(e, MathBlock)]
        figures = [e for e in pdf_doc.elements if isinstance(e, Figure)]
        breaks = [e for e in pdf_doc.elements if isinstance(e, PageBreak)]

        print("\n" + "=" * 60)
        print("HONEST EXTRACTION QUALITY REPORT")
        print("=" * 60)
        print(f"Source: {pdf_doc.frontmatter.source}")
        print(f"Pages: {pdf_doc.frontmatter.pages}")
        print(f"Total elements: {len(pdf_doc.elements)}")
        print()
        print("WHAT WORKS:")
        print(f"  ✓ Text extraction:    {len(paras)} paragraphs")
        print(f"  ✓ Heading detection:  {len(headings)} headings (font-size heuristic)")
        print(f"  ✓ Page boundaries:    {len(breaks)} page breaks")
        print(f"  ✓ Spatial layout:     {sum(len(b.annotations) for b in pdf_doc.spatial_blocks)} bounding boxes")
        print(f"  ✓ Image detection:    {len(figures)} figures")
        print()
        print("WHAT DOESN'T WORK (with basic PyMuPDF):")
        print(f"  ✗ Table structure:    {len(tables)} detected (needs vision model)")
        print(f"  ✗ LaTeX recovery:     {len(math)} detected (needs Nougat/GPT-4o)")
        print(f"  ✗ Reading order:      approximate (block-based)")
        print(f"  ✗ Figure captions:    not linked to figures")
        print()
        print("WHERE .DOX ADDS VALUE:")
        print(f"  • Cross-page handling: PageBreak markers + merger")
        print(f"  • Spatial preservation: {sum(len(b.annotations) for b in pdf_doc.spatial_blocks)} bboxes maintained")
        print(f"  • Format flexibility: HTML, JSON, Markdown from one source")
        print(f"  • Chunking for RAG: semantic + by-page strategies")
        print(f"  • Confidence tracking: extraction quality metadata")
        print("=" * 60)
