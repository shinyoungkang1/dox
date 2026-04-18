"""Tests for the dox-render PDF and HTML renderer."""

import pytest
from pathlib import Path

from dox.parsers.parser import DoxParser
from dox.renderer import DoxRenderer

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def complex_doc():
    return DoxParser().parse_file(EXAMPLES_DIR / "benchmark-complex-layout.dox")


@pytest.fixture
def invoice_doc():
    return DoxParser().parse_file(EXAMPLES_DIR / "benchmark-invoice.dox")


@pytest.fixture
def minimal_doc():
    return DoxParser().parse_file(EXAMPLES_DIR / "minimal.dox")


@pytest.fixture
def renderer():
    return DoxRenderer()


class TestHTMLRendering:
    def test_produces_html(self, renderer, complex_doc):
        html = renderer.to_html_string(complex_doc)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_includes_css(self, renderer, complex_doc):
        html = renderer.to_html_string(complex_doc)
        assert "<style>" in html
        assert "@page" in html

    def test_includes_title(self, renderer, complex_doc):
        html = renderer.to_html_string(complex_doc)
        assert "<title>" in html

    def test_lang_attribute(self, renderer, complex_doc):
        html = renderer.to_html_string(complex_doc)
        assert f'lang="{complex_doc.frontmatter.lang}"' in html

    def test_contains_headings(self, renderer, complex_doc):
        html = renderer.to_html_string(complex_doc)
        assert "<h1" in html or "<h2" in html

    def test_contains_tables(self, renderer, invoice_doc):
        html = renderer.to_html_string(invoice_doc)
        assert "<table" in html

    def test_minimal_doc(self, renderer, minimal_doc):
        html = renderer.to_html_string(minimal_doc)
        assert "<!DOCTYPE html>" in html
        assert len(html) > 200

    def test_custom_css(self, complex_doc):
        custom = "body { font-size: 14pt; color: red; }"
        r = DoxRenderer(css=custom)
        html = r.to_html_string(complex_doc)
        assert "font-size: 14pt" in html
        assert "color: red" in html


class TestHTMLFileOutput:
    def test_writes_file(self, renderer, complex_doc, tmp_path):
        out = tmp_path / "test.html"
        result = renderer.to_html_file(complex_doc, out)
        assert result.exists()
        content = result.read_text()
        assert "<!DOCTYPE html>" in content

    def test_invoice_file(self, renderer, invoice_doc, tmp_path):
        out = tmp_path / "invoice.html"
        result = renderer.to_html_file(invoice_doc, out)
        assert result.exists()
        assert result.stat().st_size > 500


class TestPDFRendering:
    """PDF tests - only run if WeasyPrint is installed."""

    def test_pdf_import_error(self, renderer, minimal_doc, tmp_path):
        """Without WeasyPrint, to_pdf should raise ImportError."""
        try:
            from weasyprint import HTML  # noqa: F401
            pytest.skip("WeasyPrint is installed — skipping import error test")
        except ImportError:
            with pytest.raises(ImportError, match="WeasyPrint"):
                renderer.to_pdf(minimal_doc, tmp_path / "test.pdf")

    def test_pdf_bytes_import_error(self, renderer, minimal_doc):
        try:
            from weasyprint import HTML  # noqa: F401
            pytest.skip("WeasyPrint is installed — skipping import error test")
        except ImportError:
            with pytest.raises(ImportError, match="WeasyPrint"):
                renderer.to_pdf_bytes(minimal_doc)


class TestAllBenchmarkDocs:
    """Ensure renderer doesn't crash on any benchmark document."""

    @pytest.mark.parametrize("filename", [
        "benchmark-complex-layout.dox",
        "benchmark-invoice.dox",
        "benchmark-nested-tables.dox",
        "minimal.dox",
        "financial-report.dox",
    ])
    def test_render_html_string(self, renderer, filename):
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            pytest.skip(f"{filename} not found")
        doc = DoxParser().parse_file(filepath)
        html = renderer.to_html_string(doc)
        assert "<!DOCTYPE html>" in html
        assert len(html) > 100

    @pytest.mark.parametrize("filename", [
        "benchmark-complex-layout.dox",
        "benchmark-invoice.dox",
        "benchmark-nested-tables.dox",
        "minimal.dox",
    ])
    def test_render_html_file(self, renderer, filename, tmp_path):
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            pytest.skip(f"{filename} not found")
        doc = DoxParser().parse_file(filepath)
        out = tmp_path / f"{filename}.html"
        result = renderer.to_html_file(doc, out)
        assert result.exists()
        assert result.stat().st_size > 0
