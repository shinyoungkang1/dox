"""Tests for the dox-diff semantic document comparison tool."""

import pytest
from copy import deepcopy
from pathlib import Path

from dox.parsers.parser import DoxParser
from dox.diff import DoxDiff, DiffResult, ChangeType, ElementChange
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import Heading, Paragraph, Table, TableRow, TableCell, CodeBlock
from dox.models.metadata import Metadata, Confidence, Provenance, VersionEntry
from dox.models.spatial import SpatialBlock

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


class TestIdenticalDocuments:
    def test_no_changes(self, complex_doc):
        result = DoxDiff().diff(complex_doc, complex_doc)
        assert not result.has_changes

    def test_no_changes_minimal(self, minimal_doc):
        result = DoxDiff().diff(minimal_doc, minimal_doc)
        assert not result.has_changes

    def test_no_changes_invoice(self, invoice_doc):
        result = DoxDiff().diff(invoice_doc, invoice_doc)
        assert not result.has_changes


class TestFrontmatterDiff:
    def test_version_change(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        modified.frontmatter.version = "0.2.0"
        result = DoxDiff().diff(minimal_doc, modified)
        assert result.has_changes
        assert any("version" in c.description for c in result.modified)

    def test_lang_change(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        modified.frontmatter.lang = "fr"
        result = DoxDiff().diff(minimal_doc, modified)
        assert result.has_changes


class TestElementDiff:
    def test_heading_text_change(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        for el in modified.elements:
            if isinstance(el, Heading):
                el.text = "Changed Heading"
                break
        result = DoxDiff().diff(minimal_doc, modified)
        assert result.has_changes
        # Heading key includes text, so text change = remove old + add new
        assert len(result.added) > 0 or len(result.removed) > 0

    def test_heading_level_change(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        for el in modified.elements:
            if isinstance(el, Heading):
                el.level = el.level + 1
                break
        result = DoxDiff().diff(minimal_doc, modified)
        assert result.has_changes

    def test_paragraph_text_change(self, complex_doc):
        modified = deepcopy(complex_doc)
        for el in modified.elements:
            if isinstance(el, Paragraph):
                el.text = "Completely different text here."
                break
        result = DoxDiff().diff(complex_doc, modified)
        assert result.has_changes

    def test_added_element(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        modified.elements.append(Paragraph(text="Brand new paragraph."))
        result = DoxDiff().diff(minimal_doc, modified)
        assert result.has_changes
        assert len(result.added) > 0

    def test_removed_element(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        if len(modified.elements) > 1:
            modified.elements.pop()
        result = DoxDiff().diff(minimal_doc, modified)
        assert result.has_changes
        assert len(result.removed) > 0


class TestTableDiff:
    def test_cell_change(self, invoice_doc):
        modified = deepcopy(invoice_doc)
        tables = [el for el in modified.elements if isinstance(el, Table)]
        if tables and tables[0].rows:
            tables[0].rows[0].cells[0].text = "CHANGED"
        result = DoxDiff().diff(invoice_doc, modified)
        assert result.has_changes
        assert any("TableCell" in c.element_type for c in result.changes)

    def test_row_count_change(self, invoice_doc):
        modified = deepcopy(invoice_doc)
        tables = [el for el in modified.elements if isinstance(el, Table)]
        if tables and len(tables[0].rows) > 1:
            tables[0].rows.append(deepcopy(tables[0].rows[-1]))
        result = DoxDiff().diff(invoice_doc, modified)
        assert result.has_changes


class TestSpatialDiff:
    def test_spatial_removed(self, complex_doc):
        modified = deepcopy(complex_doc)
        if modified.spatial_blocks:
            modified.spatial_blocks = modified.spatial_blocks[:1]
        result = DoxDiff().diff(complex_doc, modified)
        if len(complex_doc.spatial_blocks) > 1:
            assert result.has_changes

    def test_ignore_spatial(self, complex_doc):
        modified = deepcopy(complex_doc)
        modified.spatial_blocks = []
        differ = DoxDiff(ignore_spatial=True)
        result = differ.diff(complex_doc, modified)
        spatial_changes = [c for c in result.changes if c.layer == 1]
        assert len(spatial_changes) == 0


class TestMetadataDiff:
    def test_metadata_removed(self, complex_doc):
        modified = deepcopy(complex_doc)
        if modified.metadata:
            modified.metadata = None
            result = DoxDiff().diff(complex_doc, modified)
            assert result.has_changes
            assert any(c.element_type == "Metadata" for c in result.removed)

    def test_metadata_added(self, minimal_doc):
        modified = deepcopy(minimal_doc)
        if modified.metadata is None:
            modified.metadata = Metadata(
                extracted_by="test",
                confidence=Confidence(),
                provenance=Provenance(
                    source_hash="abc123",
                    extraction_pipeline=["test-tool v1.0"],
                ),
                version_history=[],
            )
            result = DoxDiff().diff(minimal_doc, modified)
            assert result.has_changes

    def test_ignore_metadata(self, complex_doc):
        modified = deepcopy(complex_doc)
        modified.metadata = None
        differ = DoxDiff(ignore_metadata=True)
        result = differ.diff(complex_doc, modified)
        meta_changes = [c for c in result.changes if c.layer == 2]
        assert len(meta_changes) == 0

    def test_confidence_change(self, complex_doc):
        if complex_doc.metadata and complex_doc.metadata.confidence.elements:
            modified = deepcopy(complex_doc)
            key = next(iter(modified.metadata.confidence.elements))
            modified.metadata.confidence.elements[key] = 0.01
            result = DoxDiff().diff(complex_doc, modified)
            assert result.has_changes
            assert any("Confidence" in c.element_type for c in result.changes)


class TestDiffResult:
    def test_summary_no_changes(self):
        result = DiffResult()
        assert "No changes" in result.summary()

    def test_summary_with_changes(self):
        result = DiffResult(changes=[
            ElementChange(ChangeType.ADDED, "Paragraph", "Added para"),
            ElementChange(ChangeType.REMOVED, "Heading", "Removed heading"),
            ElementChange(ChangeType.MODIFIED, "Table", "Modified table"),
        ])
        summary = result.summary()
        assert "1 added" in summary
        assert "1 removed" in summary
        assert "1 modified" in summary

    def test_str_output(self):
        result = DiffResult(changes=[
            ElementChange(ChangeType.ADDED, "Paragraph", "Added new text"),
        ])
        text = str(result)
        assert "Added new text" in text


class TestBenchmarkRoundtripDiff:
    """Ensure parsed → serialized → re-parsed documents diff as identical."""

    @pytest.mark.parametrize("filename", [
        "benchmark-complex-layout.dox",
        "benchmark-invoice.dox",
        "benchmark-nested-tables.dox",
        "minimal.dox",
    ])
    def test_roundtrip_no_diff(self, filename):
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            pytest.skip(f"{filename} not found")
        parser = DoxParser()
        from dox.serializer import DoxSerializer
        doc = parser.parse_file(filepath)
        text = DoxSerializer().serialize(doc)
        doc2 = parser.parse(text)
        result = DoxDiff().diff(doc, doc2)
        # Roundtrip should produce minimal or no changes
        # (some metadata timestamp drift is acceptable)
        content_changes = [c for c in result.changes if c.layer == 0]
        assert len(content_changes) == 0, f"Content changes in roundtrip: {content_changes}"
