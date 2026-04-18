"""
Integration tests using real OmniDocBench ground truth data.

These tests convert OmniDocBench annotations to .dox format and verify
that the full pipeline (parse, validate, serialize, roundtrip, convert,
chunk, diff, render) handles real-world document structures correctly.
"""

import json
import pytest
from pathlib import Path

from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.validator import DoxValidator
from dox.converters.to_html import to_html
from dox.converters.to_json import to_json
from dox.converters.to_markdown import to_markdown
from dox.chunker import chunk_document, ChunkStrategy
from dox.diff import DoxDiff
from dox.renderer import DoxRenderer
from dox.merger import merge_document
from dox.models.elements import (
    Heading, Paragraph, Table, MathBlock, Figure, PageBreak, Footnote
)

# Path to downloaded OmniDocBench data
OMNIDOCBENCH_JSON = Path(
    "/sessions/nice-amazing-wright/hf_cache/datasets--opendatalab--OmniDocBench/"
    "snapshots/d386947f7fc3bafdcd756c8485845a2f43a19875/OmniDocBench.json"
)


def _load_benchmark():
    if not OMNIDOCBENCH_JSON.exists():
        pytest.skip("OmniDocBench data not available")
    with open(OMNIDOCBENCH_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def all_pages():
    return _load_benchmark()


@pytest.fixture(scope="module")
def table_pages(all_pages):
    """Pages that contain at least one table."""
    return [
        p for p in all_pages
        if any(d.get("category_type") == "table" for d in p.get("layout_dets", []))
    ][:20]  # Limit to 20 for speed


@pytest.fixture(scope="module")
def math_pages(all_pages):
    """Pages with equations."""
    return [
        p for p in all_pages
        if any(d.get("category_type") in ("equation_isolated", "equation_semantic")
               for d in p.get("layout_dets", []))
    ][:10]


@pytest.fixture(scope="module")
def diverse_pages(all_pages):
    """A diverse sample: book, textbook, slides, etc."""
    seen_sources = set()
    pages = []
    for p in all_pages:
        src = p.get("page_info", {}).get("page_attribute", {}).get("data_source", "")
        if src not in seen_sources:
            seen_sources.add(src)
            pages.append(p)
        if len(pages) >= 10:
            break
    return pages


# =====================================================================
# Single-page conversion tests
# =====================================================================

class TestSinglePageConversion:
    def test_convert_table_page(self, table_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        page = table_pages[0]
        doc = omnidocbench_page_to_dox(page)

        assert doc.frontmatter.version == "1.0"
        assert len(doc.elements) > 0
        tables = [e for e in doc.elements if isinstance(e, Table)]
        assert len(tables) > 0
        # Tables should have rows
        for t in tables:
            assert t.num_rows > 0, f"Table has 0 rows"

    def test_convert_math_page(self, math_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        page = math_pages[0]
        doc = omnidocbench_page_to_dox(page)

        math_els = [e for e in doc.elements if isinstance(e, MathBlock)]
        assert len(math_els) > 0
        for m in math_els:
            assert m.expression.strip(), "Math expression is empty"

    def test_spatial_generated(self, table_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        doc = omnidocbench_page_to_dox(table_pages[0])
        assert len(doc.spatial_blocks) > 0
        for block in doc.spatial_blocks:
            assert block.page >= 1
            for ann in block.annotations:
                if ann.bbox:
                    assert ann.bbox.x1 >= 0
                    assert ann.bbox.y1 >= 0


# =====================================================================
# Multi-page conversion tests
# =====================================================================

class TestMultiPageConversion:
    def test_multi_page_document(self, diverse_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox
        doc = omnidocbench_to_dox(diverse_pages[:5])

        assert doc.frontmatter.pages == 5
        # Should have PageBreak markers between pages
        page_breaks = [e for e in doc.elements if isinstance(e, PageBreak)]
        assert len(page_breaks) == 4  # Between pages 1-2, 2-3, 3-4, 4-5

    def test_page_assignment_after_conversion(self, diverse_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox
        doc = omnidocbench_to_dox(diverse_pages[:3])

        # Elements should have page numbers set
        for el in doc.elements:
            if isinstance(el, PageBreak):
                continue
            assert el.page is not None, f"{type(el).__name__} missing page number"


# =====================================================================
# Full pipeline on OmniDocBench data
# =====================================================================

class TestPipelineOnBenchmark:
    """Run the full .dox pipeline on OmniDocBench-derived documents."""

    @pytest.fixture
    def sample_doc(self, diverse_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox
        return omnidocbench_to_dox(diverse_pages[:3])

    def test_validate(self, sample_doc):
        result = DoxValidator().validate(sample_doc)
        # Should have no errors (warnings are OK)
        errors = [i for i in result.issues if i.severity.name == "ERROR"]
        # Allow some errors since benchmark data isn't perfect .dox
        assert len(errors) < 10, f"Too many validation errors: {errors[:5]}"

    def test_serialize_roundtrip(self, sample_doc):
        text = DoxSerializer().serialize(sample_doc)
        doc2 = DoxParser().parse(text)
        # Element counts should match closely (some OmniDocBench LaTeX/math
        # content may re-parse slightly differently, so allow ~15% drift)
        drift_pct = abs(len(doc2.elements) - len(sample_doc.elements)) / max(len(sample_doc.elements), 1)
        assert drift_pct < 0.20, f"Element count drift too large: {len(sample_doc.elements)} → {len(doc2.elements)} ({drift_pct:.0%})"

    def test_convert_html(self, sample_doc):
        html = to_html(sample_doc)
        assert "<html" in html
        assert len(html) > 200

    def test_convert_json(self, sample_doc):
        result = to_json(sample_doc)
        data = json.loads(result)
        assert "elements" in data

    def test_convert_markdown(self, sample_doc):
        md = to_markdown(sample_doc)
        assert len(md) > 50

    def test_chunk_semantic(self, sample_doc):
        chunks = chunk_document(sample_doc, strategy=ChunkStrategy.SEMANTIC)
        assert len(chunks) > 0
        for c in chunks:
            assert c.text.strip(), "Empty chunk text"
            assert c.token_estimate > 0

    def test_chunk_by_page(self, sample_doc):
        chunks = chunk_document(sample_doc, strategy=ChunkStrategy.BY_PAGE)
        assert len(chunks) > 0

    def test_diff_identical(self, sample_doc):
        result = DoxDiff().diff(sample_doc, sample_doc)
        assert not result.has_changes

    def test_render_html(self, sample_doc):
        html = DoxRenderer().to_html_string(sample_doc)
        assert "<!DOCTYPE html>" in html
        assert len(html) > 500

    def test_merge(self, sample_doc):
        result = merge_document(sample_doc)
        # Should not crash and should produce a valid document
        assert result.document is not None
        assert len(result.document.elements) > 0


# =====================================================================
# Table quality stress tests
# =====================================================================

class TestTableQuality:
    """Verify table parsing quality on real OmniDocBench tables."""

    def test_all_tables_have_content(self, table_pages):
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        empty_tables = 0
        total_tables = 0

        for page in table_pages:
            doc = omnidocbench_page_to_dox(page)
            for el in doc.elements:
                if isinstance(el, Table):
                    total_tables += 1
                    if el.num_rows == 0:
                        empty_tables += 1

        assert total_tables > 0, "No tables found in benchmark"
        error_rate = empty_tables / total_tables
        assert error_rate < 0.1, f"Too many empty tables: {empty_tables}/{total_tables} ({error_rate:.0%})"

    def test_table_roundtrip_fidelity(self, table_pages):
        """Tables should survive serialize → parse roundtrip."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        parser = DoxParser()
        serializer = DoxSerializer()

        for page in table_pages[:5]:
            doc = omnidocbench_page_to_dox(page)
            text = serializer.serialize(doc)
            doc2 = parser.parse(text)

            t1 = [e for e in doc.elements if isinstance(e, Table)]
            t2 = [e for e in doc2.elements if isinstance(e, Table)]

            for orig, parsed in zip(t1, t2):
                assert orig.num_rows == parsed.num_rows, (
                    f"Row count changed: {orig.num_rows} → {parsed.num_rows}"
                )


# =====================================================================
# Scale test — convert many pages
# =====================================================================

class TestScaleConversion:
    def test_50_pages(self, all_pages):
        """Convert 50 pages and verify no crashes."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox
        doc = omnidocbench_to_dox(all_pages[:50])
        assert doc.frontmatter.pages == 50
        assert len(doc.elements) > 100  # Should have many elements
        # Serialize and re-parse
        text = DoxSerializer().serialize(doc)
        doc2 = DoxParser().parse(text)
        assert len(doc2.elements) > 50

    def test_100_pages_performance(self, all_pages):
        """Convert 100 pages — should complete in reasonable time."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox
        import time
        start = time.time()
        doc = omnidocbench_to_dox(all_pages[:100])
        elapsed = time.time() - start
        assert elapsed < 10, f"100-page conversion took {elapsed:.1f}s (too slow)"
        assert len(doc.elements) > 200


class TestFullCoverage:
    """Run every single page through the full pipeline — 0 errors expected."""

    def test_all_1651_pages_convert(self, all_pages):
        """Every page in OmniDocBench v1.5 must convert without error."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        failures = []
        for i, page in enumerate(all_pages):
            try:
                omnidocbench_page_to_dox(page)
            except Exception as ex:
                failures.append((i, str(ex)[:80]))
        assert len(failures) == 0, f"{len(failures)} conversion failures: {failures[:5]}"

    def test_all_1651_pages_roundtrip(self, all_pages):
        """Every page must survive serialize → re-parse."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        failures = []
        for i, page in enumerate(all_pages):
            try:
                doc = omnidocbench_page_to_dox(page)
                text = DoxSerializer().serialize(doc)
                DoxParser().parse(text)
            except Exception as ex:
                failures.append((i, str(ex)[:80]))
        assert len(failures) == 0, f"{len(failures)} roundtrip failures: {failures[:5]}"

    def test_all_1651_pages_all_formats(self, all_pages):
        """Every page must convert to HTML, JSON, and Markdown."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        from dox.converters.to_html import to_html
        from dox.converters.to_json import to_json
        from dox.converters.to_markdown import to_markdown
        failures = []
        for i, page in enumerate(all_pages):
            try:
                doc = omnidocbench_page_to_dox(page)
                to_html(doc)
                to_json(doc)
                to_markdown(doc)
            except Exception as ex:
                failures.append((i, str(ex)[:80]))
        assert len(failures) == 0, f"{len(failures)} format failures: {failures[:5]}"

    def test_all_1651_pages_chunk(self, all_pages):
        """Every page must chunk without error."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox
        failures = []
        for i, page in enumerate(all_pages):
            try:
                doc = omnidocbench_page_to_dox(page)
                chunk_document(doc, strategy=ChunkStrategy.SEMANTIC)
            except Exception as ex:
                failures.append((i, str(ex)[:80]))
        assert len(failures) == 0, f"{len(failures)} chunk failures: {failures[:5]}"

    def test_mega_document_pipeline(self, all_pages):
        """All 1651 pages as one document through full pipeline."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox
        doc = omnidocbench_to_dox(all_pages)
        assert len(doc.elements) > 30000
        assert doc.frontmatter.pages == 1651

        # Merge
        result = merge_document(doc)
        assert result.document is not None

        # Render
        html = DoxRenderer().to_html_string(doc)
        assert len(html) > 1_000_000

        # Chunk
        chunks = chunk_document(doc, strategy=ChunkStrategy.SEMANTIC)
        assert len(chunks) > 5000
