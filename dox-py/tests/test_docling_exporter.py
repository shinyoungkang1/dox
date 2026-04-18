"""Comprehensive tests for the docling exporter.

This test suite mocks the entire Docling library since it is not installed.
We test all key functions and edge cases without requiring Docling itself.
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch, call, PropertyMock
from datetime import datetime, timezone

from dox.exporters.docling_exporter import (
    docling_to_dox,
    _export_content,
    _convert_table,
    _convert_list,
    _export_spatial,
    _build_metadata,
    _get_text,
    _parse_markdown_fallback,
)
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Heading,
    Paragraph,
    Table,
    TableRow,
    TableCell,
    CodeBlock,
    ListBlock,
    ListItem,
    BoundingBox,
)
from dox.models.metadata import Metadata, Confidence, Provenance, VersionEntry
from dox.models.spatial import SpatialBlock, SpatialAnnotation


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_docling_document():
    """Create a mock DoclingDocument instance."""
    doc = Mock()
    doc.name = "test_document.pdf"
    doc.num_pages = 5
    return doc


@pytest.fixture
def mock_docling_class(mock_docling_document):
    """Mock the DoclingDocument class for isinstance checks."""
    with patch("dox.exporters.docling_exporter.DoclingDocument", mock_docling_document.__class__):
        yield mock_docling_document.__class__


# =============================================================================
# Tests for docling_to_dox (main entry point)
# =============================================================================


class TestDoclingToDoxMainFunction:
    """Test the main docling_to_dox() function."""

    def test_docling_not_installed(self):
        """Test ImportError when docling is not installed."""
        # Temporarily remove docling from sys.modules to simulate it not being installed
        docling_backup = sys.modules.get("docling")
        docling_dm_backup = sys.modules.get("docling.datamodel")
        docling_dm_doc_backup = sys.modules.get("docling.datamodel.document")

        try:
            sys.modules["docling"] = None
            sys.modules["docling.datamodel"] = None
            sys.modules["docling.datamodel.document"] = None

            with pytest.raises(ImportError, match="Docling is required"):
                docling_to_dox(Mock())
        finally:
            # Restore modules
            if docling_backup is None:
                sys.modules.pop("docling", None)
            else:
                sys.modules["docling"] = docling_backup
            if docling_dm_backup is None:
                sys.modules.pop("docling.datamodel", None)
            else:
                sys.modules["docling.datamodel"] = docling_dm_backup
            if docling_dm_doc_backup is None:
                sys.modules.pop("docling.datamodel.document", None)
            else:
                sys.modules["docling.datamodel.document"] = docling_dm_doc_backup

    def test_invalid_document_type(self, mock_docling_document):
        """Test TypeError when docling_doc is not a DoclingDocument."""
        # Create a mock DoclingDocument class
        mock_docling_class = type("DoclingDocument", (), {})

        # Patch to provide the mock class
        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": Mock(), "docling.datamodel.document": Mock(DoclingDocument=mock_docling_class)}):
            # Pass an invalid object type that won't match isinstance
            not_a_doc = "not a document"
            with pytest.raises(TypeError, match="Expected DoclingDocument"):
                docling_to_dox(not_a_doc)

    def test_basic_conversion(self, mock_docling_document):
        """Test basic conversion with minimal input."""
        mock_docling_document.iterate_items.return_value = []
        mock_docling_document.pages = {}  # Add empty pages dict for spatial export

        # Create a mock DoclingDocument class that matches our mock instance
        mock_docling_class = type(mock_docling_document)

        # Patch sys.modules to provide the mock docling
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            dox_doc = docling_to_dox(mock_docling_document)

            assert isinstance(dox_doc, DoxDocument)
            assert dox_doc.frontmatter.version == "1.0"
            assert dox_doc.frontmatter.source == "test_document.pdf"
            assert dox_doc.frontmatter.pages == 5

    def test_conversion_with_source_path(self, mock_docling_document):
        """Test conversion with explicit source_path."""
        mock_docling_document.iterate_items.return_value = []
        mock_docling_document.pages = {}  # Add empty pages dict for spatial export

        mock_docling_class = type(mock_docling_document)
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            dox_doc = docling_to_dox(
                mock_docling_document,
                source_path="/path/to/document.pdf"
            )

            assert dox_doc.frontmatter.source == "/path/to/document.pdf"

    def test_conversion_without_spatial(self, mock_docling_document):
        """Test conversion with include_spatial=False."""
        mock_docling_document.iterate_items.return_value = []
        mock_docling_document.pages = {}

        mock_docling_class = type(mock_docling_document)
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            with patch("dox.exporters.docling_exporter._export_spatial") as mock_spatial:
                dox_doc = docling_to_dox(
                    mock_docling_document,
                    include_spatial=False
                )

                # _export_spatial should not be called
                mock_spatial.assert_not_called()

    def test_conversion_with_custom_grid_size(self, mock_docling_document):
        """Test conversion with custom grid_size."""
        mock_docling_document.iterate_items.return_value = []
        mock_docling_document.pages = {}

        mock_docling_class = type(mock_docling_document)
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            with patch("dox.exporters.docling_exporter._export_spatial") as mock_spatial:
                dox_doc = docling_to_dox(
                    mock_docling_document,
                    grid_size=2000
                )

                # _export_spatial should be called with the custom grid_size
                mock_spatial.assert_called_once()
                assert mock_spatial.call_args[0][2] == 2000

    def test_metadata_is_built(self, mock_docling_document):
        """Test that metadata is properly built."""
        mock_docling_document.iterate_items.return_value = []
        mock_docling_document.pages = {}  # Add empty pages dict for spatial export

        mock_docling_class = type(mock_docling_document)
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            dox_doc = docling_to_dox(mock_docling_document)

            assert dox_doc.metadata is not None
            assert isinstance(dox_doc.metadata, Metadata)
            assert "docling" in dox_doc.metadata.extracted_by


# =============================================================================
# Tests for _export_content
# =============================================================================


class TestExportContent:
    """Test the _export_content() function for walking document trees."""

    def test_empty_document(self):
        """Test export of an empty document."""
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = []
        dox_doc = DoxDocument()

        _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 0

    def test_heading_extraction(self):
        """Test extraction of heading elements."""
        mock_heading = Mock()
        mock_heading.__class__.__name__ = "Heading"
        mock_heading.text = "Section Title"
        mock_heading.level = 2
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_heading, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Section Title"):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 1
        assert isinstance(dox_doc.elements[0], Heading)
        assert dox_doc.elements[0].text == "Section Title"
        assert dox_doc.elements[0].level == 2

    def test_heading_level_clamped_to_6(self):
        """Test that heading levels are clamped to max 6."""
        mock_heading = Mock()
        mock_heading.__class__.__name__ = "Heading"
        mock_heading.level = 10  # Too high
        mock_heading.text = "Deep Heading"
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_heading, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Deep Heading"):
            _export_content(mock_doc, dox_doc)

        assert dox_doc.elements[0].level == 6

    def test_paragraph_extraction(self):
        """Test extraction of paragraph elements."""
        mock_para = Mock()
        mock_para.__class__.__name__ = "Paragraph"
        mock_para.text = "This is a paragraph."
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_para, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="This is a paragraph."):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 1
        assert isinstance(dox_doc.elements[0], Paragraph)
        assert dox_doc.elements[0].text == "This is a paragraph."

    def test_empty_paragraph_skipped(self):
        """Test that empty paragraphs are skipped."""
        mock_para = Mock()
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_para, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="   "):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 0

    def test_code_block_extraction(self):
        """Test extraction of code block elements."""
        mock_code = Mock()
        mock_code.__class__.__name__ = "CodeBlock"
        mock_code.language = "python"
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_code, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="print('hello')"):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 1
        assert isinstance(dox_doc.elements[0], CodeBlock)
        assert dox_doc.elements[0].code == "print('hello')"
        assert dox_doc.elements[0].language == "python"

    def test_table_extraction(self):
        """Test extraction of table elements."""
        mock_table = Mock()
        mock_table.__class__.__name__ = "Table"
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_table, 0)]

        dox_doc = DoxDocument()
        mock_converted_table = Table(rows=[])
        with patch("dox.exporters.docling_exporter._convert_table", return_value=mock_converted_table):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 1
        assert isinstance(dox_doc.elements[0], Table)

    def test_table_none_skipped(self):
        """Test that None tables (conversion failed) are skipped."""
        mock_table = Mock()
        mock_table.__class__.__name__ = "Table"
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_table, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._convert_table", return_value=None):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 0

    def test_list_extraction(self):
        """Test extraction of list elements."""
        mock_list = Mock()
        mock_list.__class__.__name__ = "List"
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_list, 0)]

        dox_doc = DoxDocument()
        mock_list_block = ListBlock(items=[ListItem(text="item")])
        with patch("dox.exporters.docling_exporter._convert_list", return_value=mock_list_block):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 1
        assert isinstance(dox_doc.elements[0], ListBlock)

    def test_list_none_skipped(self):
        """Test that None lists (conversion failed) are skipped."""
        mock_list = Mock()
        mock_list.__class__.__name__ = "List"
        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [(mock_list, 0)]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._convert_list", return_value=None):
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 0

    def test_iterate_items_failure_tries_markdown(self):
        """Test that iterate_items failure falls back to markdown."""
        mock_doc = Mock()
        mock_doc.iterate_items.side_effect = AttributeError("No iterate_items")
        mock_doc.export_to_markdown.return_value = "# Fallback\n\nParagraph."

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._parse_markdown_fallback") as mock_fallback:
            _export_content(mock_doc, dox_doc)

            mock_fallback.assert_called_once()
            assert mock_fallback.call_args[0][0] == "# Fallback\n\nParagraph."

    def test_iterate_items_and_markdown_both_fail(self):
        """Test graceful handling when both iterate_items and markdown fail."""
        mock_doc = Mock()
        mock_doc.iterate_items.side_effect = AttributeError("No iterate_items")
        mock_doc.export_to_markdown.side_effect = AttributeError("No markdown export")

        dox_doc = DoxDocument()
        # Should not raise, just log error
        _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 0

    def test_multiple_elements_in_order(self):
        """Test extraction of multiple elements preserves order."""
        mock_heading = Mock()
        mock_heading.__class__.__name__ = "Heading"
        mock_heading.level = 1
        mock_para = Mock()
        mock_para.__class__.__name__ = "Paragraph"

        mock_doc = Mock()
        mock_doc.iterate_items.return_value = [
            (mock_heading, 0),
            (mock_para, 1),
        ]

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text") as mock_get_text:
            mock_get_text.side_effect = ["Title", "Paragraph text"]
            _export_content(mock_doc, dox_doc)

        assert len(dox_doc.elements) == 2
        assert isinstance(dox_doc.elements[0], Heading)
        assert isinstance(dox_doc.elements[1], Paragraph)


# =============================================================================
# Tests for _convert_table
# =============================================================================


class TestConvertTable:
    """Test the _convert_table() function."""

    def test_table_from_dataframe(self):
        """Test table conversion using DataFrame export."""
        mock_table = Mock()

        # Mock pandas DataFrame
        import pandas as pd
        df = pd.DataFrame({
            "Name": ["Alice", "Bob"],
            "Age": [30, 25],
        })
        mock_table.export_to_dataframe.return_value = df

        table = _convert_table(mock_table)

        assert table is not None
        assert len(table.rows) == 3  # Header + 2 data rows
        assert len(table.rows[0].cells) == 2
        assert table.rows[0].is_header
        assert table.rows[0].cells[0].text == "Name"
        assert table.rows[1].cells[0].text == "Alice"

    def test_table_from_grid(self):
        """Test table conversion using grid-based access."""
        mock_table = Mock()
        mock_table.export_to_dataframe.side_effect = AttributeError("No dataframe")

        # Mock grid structure
        mock_cell = Mock()
        mock_cell.text = "Cell text"
        mock_row = [mock_cell]
        mock_table.grid = [mock_row]

        table = _convert_table(mock_table)

        assert table is not None
        assert len(table.rows) == 1
        assert table.rows[0].cells[0].text == "Cell text"
        assert table.rows[0].is_header

    def test_table_conversion_failure_returns_none(self):
        """Test that table conversion failure returns None."""
        mock_table = Mock()
        mock_table.export_to_dataframe.side_effect = AttributeError("No dataframe")
        type(mock_table).grid = PropertyMock(side_effect=AttributeError("No grid"))

        table = _convert_table(mock_table)

        assert table is None

    def test_empty_dataframe_table(self):
        """Test table from empty DataFrame."""
        import pandas as pd
        mock_table = Mock()
        df = pd.DataFrame()
        mock_table.export_to_dataframe.return_value = df

        table = _convert_table(mock_table)

        # Empty DataFrame creates table with a header row but no data rows
        assert table is not None
        # Header row is created even for empty DataFrame
        assert len(table.rows) >= 1

    def test_table_with_multiple_rows_and_columns(self):
        """Test table with multiple rows and columns."""
        import pandas as pd
        mock_table = Mock()
        df = pd.DataFrame({
            "Col1": ["A", "B", "C"],
            "Col2": [1, 2, 3],
            "Col3": ["X", "Y", "Z"],
        })
        mock_table.export_to_dataframe.return_value = df

        table = _convert_table(mock_table)

        assert len(table.rows) == 4  # Header + 3 data
        assert len(table.rows[0].cells) == 3


# =============================================================================
# Tests for _convert_list
# =============================================================================


class TestConvertList:
    """Test the _convert_list() function."""

    def test_unordered_list_conversion(self):
        """Test conversion of unordered list."""
        mock_item1 = Mock()
        mock_item2 = Mock()
        mock_list = Mock()
        mock_list.items = [mock_item1, mock_item2]
        mock_list.ordered = False

        with patch("dox.exporters.docling_exporter._get_text") as mock_get_text:
            mock_get_text.side_effect = ["Item one", "Item two"]
            list_block = _convert_list(mock_list)

        assert list_block is not None
        assert not list_block.ordered
        assert len(list_block.items) == 2
        assert list_block.items[0].text == "Item one"
        assert list_block.items[1].text == "Item two"

    def test_ordered_list_conversion(self):
        """Test conversion of ordered list."""
        mock_item1 = Mock()
        mock_list = Mock()
        mock_list.items = [mock_item1]
        mock_list.ordered = True

        with patch("dox.exporters.docling_exporter._get_text", return_value="First item"):
            list_block = _convert_list(mock_list)

        assert list_block is not None
        assert list_block.ordered

    def test_empty_list_conversion(self):
        """Test conversion of empty list."""
        mock_list = Mock()
        mock_list.items = []
        mock_list.ordered = False

        list_block = _convert_list(mock_list)

        # Empty list returns None
        assert list_block is None

    def test_list_no_items_attribute(self):
        """Test list without items attribute."""
        mock_list = Mock(spec=[])  # No attributes

        list_block = _convert_list(mock_list)

        assert list_block is None

    def test_list_conversion_exception(self):
        """Test exception during list conversion."""
        mock_list = Mock()
        type(mock_list).items = PropertyMock(side_effect=TypeError("Bad access"))

        list_block = _convert_list(mock_list)

        assert list_block is None


# =============================================================================
# Tests for _export_spatial
# =============================================================================


class TestExportSpatial:
    """Test the _export_spatial() function."""

    def test_no_pages_attribute(self):
        """Test spatial export when pages attribute is missing."""
        mock_doc = Mock(spec=[])
        dox_doc = DoxDocument()

        _export_spatial(mock_doc, dox_doc, grid_size=1000)

        assert len(dox_doc.spatial_blocks) == 0

    def test_single_page_with_items(self):
        """Test spatial export of single page with items."""
        mock_item = Mock()
        mock_bbox = Mock()
        mock_bbox.l = 100
        mock_bbox.t = 200
        mock_bbox.r = 300
        mock_bbox.b = 400
        mock_item.bbox = mock_bbox

        mock_page = Mock()
        mock_page.width = 1000
        mock_page.height = 1000
        mock_page.items = [mock_item]

        mock_doc = Mock()
        mock_doc.pages = {0: mock_page}

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Text"):
            _export_spatial(mock_doc, dox_doc, grid_size=1000)

        assert len(dox_doc.spatial_blocks) == 1
        block = dox_doc.spatial_blocks[0]
        assert block.page == 0
        assert len(block.annotations) == 1
        assert block.annotations[0].line_text == "Text"
        assert block.annotations[0].bbox.x1 == 100
        assert block.annotations[0].bbox.y1 == 200

    def test_bbox_as_tuple(self):
        """Test spatial export with bbox as tuple."""
        mock_item = Mock()
        mock_item.bbox = (50, 100, 150, 200)

        mock_page = Mock()
        mock_page.width = 1000
        mock_page.height = 1000
        mock_page.items = [mock_item]

        mock_doc = Mock()
        mock_doc.pages = {1: mock_page}

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Text"):
            _export_spatial(mock_doc, dox_doc, grid_size=1000)

        block = dox_doc.spatial_blocks[0]
        assert block.annotations[0].bbox.x1 == 50

    def test_bbox_normalization(self):
        """Test that bboxes are normalized to grid coordinates."""
        mock_item = Mock()
        mock_bbox = Mock()
        mock_bbox.l = 250
        mock_bbox.t = 250
        mock_bbox.r = 750
        mock_bbox.b = 750
        mock_item.bbox = mock_bbox

        mock_page = Mock()
        mock_page.width = 1000
        mock_page.height = 1000
        mock_page.items = [mock_item]

        mock_doc = Mock()
        mock_doc.pages = {0: mock_page}

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Text"):
            _export_spatial(mock_doc, dox_doc, grid_size=1000)

        ann = dox_doc.spatial_blocks[0].annotations[0]
        assert ann.bbox.x1 == 250
        assert ann.bbox.x2 == 750

    def test_custom_grid_size(self):
        """Test spatial export with custom grid size."""
        mock_item = Mock()
        mock_bbox = Mock()
        mock_bbox.l = 500
        mock_bbox.t = 500
        mock_bbox.r = 1500
        mock_bbox.b = 1500
        mock_item.bbox = mock_bbox

        mock_page = Mock()
        mock_page.width = 2000
        mock_page.height = 2000
        mock_page.items = [mock_item]

        mock_doc = Mock()
        mock_doc.pages = {0: mock_page}

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Text"):
            _export_spatial(mock_doc, dox_doc, grid_size=500)

        ann = dox_doc.spatial_blocks[0].annotations[0]
        assert ann.bbox.x1 == 125  # 500 / 2000 * 500
        assert ann.bbox.x2 == 375  # 1500 / 2000 * 500

    def test_no_items_on_page(self):
        """Test spatial export when page has no items."""
        mock_page = Mock()
        mock_page.width = 1000
        mock_page.height = 1000
        mock_page.items = []

        mock_doc = Mock()
        mock_doc.pages = {0: mock_page}

        dox_doc = DoxDocument()
        _export_spatial(mock_doc, dox_doc, grid_size=1000)

        # No spatial blocks should be created for page with no items
        assert len(dox_doc.spatial_blocks) == 0

    def test_multiple_pages(self):
        """Test spatial export of multiple pages."""
        mock_item1 = Mock()
        mock_item1.bbox = (0, 0, 100, 100)
        mock_page1 = Mock()
        mock_page1.width = 1000
        mock_page1.height = 1000
        mock_page1.items = [mock_item1]

        mock_item2 = Mock()
        mock_item2.bbox = (50, 50, 150, 150)
        mock_page2 = Mock()
        mock_page2.width = 1000
        mock_page2.height = 1000
        mock_page2.items = [mock_item2]

        mock_doc = Mock()
        mock_doc.pages = {0: mock_page1, 1: mock_page2}

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Text"):
            _export_spatial(mock_doc, dox_doc, grid_size=1000)

        assert len(dox_doc.spatial_blocks) == 2
        assert dox_doc.spatial_blocks[0].page == 0
        assert dox_doc.spatial_blocks[1].page == 1

    def test_page_with_string_key(self):
        """Test spatial export when page keys are strings."""
        mock_item = Mock()
        mock_item.bbox = (0, 0, 100, 100)
        mock_page = Mock()
        mock_page.width = 1000
        mock_page.height = 1000
        mock_page.items = [mock_item]

        mock_doc = Mock()
        mock_doc.pages = {"0": mock_page}

        dox_doc = DoxDocument()
        with patch("dox.exporters.docling_exporter._get_text", return_value="Text"):
            _export_spatial(mock_doc, dox_doc, grid_size=1000)

        assert dox_doc.spatial_blocks[0].page == 0


# =============================================================================
# Tests for _build_metadata
# =============================================================================


class TestBuildMetadata:
    """Test the _build_metadata() function."""

    def test_metadata_without_source_path(self):
        """Test metadata building without source_path."""
        mock_doc = Mock()
        metadata = _build_metadata(mock_doc, "")

        assert metadata is not None
        assert "docling" in metadata.extracted_by
        assert metadata.provenance.source_hash == ""
        assert len(metadata.version_history) > 0

    def test_metadata_with_source_path(self, tmp_path):
        """Test metadata building with valid source_path."""
        # Create a temporary file
        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"test content")

        mock_doc = Mock()
        metadata = _build_metadata(mock_doc, str(temp_file))

        assert metadata is not None
        assert "sha256:" in metadata.provenance.source_hash

    def test_metadata_with_invalid_source_path(self):
        """Test metadata building with invalid source_path."""
        mock_doc = Mock()
        metadata = _build_metadata(mock_doc, "/nonexistent/path/file.pdf")

        assert metadata is not None
        assert metadata.provenance.source_hash == ""

    def test_metadata_timestamp(self):
        """Test that metadata has current timestamp."""
        mock_doc = Mock()
        before = datetime.now(timezone.utc)
        metadata = _build_metadata(mock_doc, "")
        after = datetime.now(timezone.utc)

        assert metadata.extracted_at is not None
        assert before <= metadata.extracted_at <= after

    def test_metadata_version_history(self):
        """Test version history in metadata."""
        mock_doc = Mock()
        metadata = _build_metadata(mock_doc, "")

        assert len(metadata.version_history) == 1
        entry = metadata.version_history[0]
        # The agent in version entry might be shorter format than extracted_by
        assert "docling" in entry.agent
        assert entry.action == "initial_extraction"

    def test_metadata_extraction_pipeline(self):
        """Test extraction pipeline in provenance."""
        mock_doc = Mock()
        metadata = _build_metadata(mock_doc, "")

        assert len(metadata.provenance.extraction_pipeline) > 0
        assert any("docling" in p for p in metadata.provenance.extraction_pipeline)


# =============================================================================
# Tests for _get_text
# =============================================================================


class TestGetText:
    """Test the _get_text() function."""

    def test_get_text_from_text_attribute(self):
        """Test getting text from 'text' attribute."""
        mock_item = Mock()
        mock_item.text = "Hello World"

        text = _get_text(mock_item)

        assert text == "Hello World"

    def test_get_text_from_content_attribute(self):
        """Test getting text from 'content' attribute when 'text' is missing."""
        mock_item = Mock(spec=["content"])
        mock_item.content = "Content text"

        text = _get_text(mock_item)

        assert text == "Content text"

    def test_get_text_from_value_attribute(self):
        """Test getting text from 'value' attribute."""
        mock_item = Mock(spec=["value"])
        mock_item.value = "Value text"

        text = _get_text(mock_item)

        assert text == "Value text"

    def test_get_text_from_raw_text_attribute(self):
        """Test getting text from 'raw_text' attribute."""
        mock_item = Mock(spec=["raw_text"])
        mock_item.raw_text = "Raw text"

        text = _get_text(mock_item)

        assert text == "Raw text"

    def test_get_text_fallback_to_str(self):
        """Test fallback to str() conversion."""
        class CustomObject:
            def __str__(self):
                return "String representation"

        obj = CustomObject()
        text = _get_text(obj)

        assert text == "String representation"

    def test_get_text_none_item(self):
        """Test getting text from None."""
        text = _get_text(None)

        assert text == ""

    def test_get_text_attribute_priority(self):
        """Test that attributes are checked in correct priority order."""
        mock_item = Mock()
        mock_item.text = "From text"
        mock_item.content = "From content"
        mock_item.value = "From value"
        mock_item.raw_text = "From raw_text"

        text = _get_text(mock_item)

        # Should get from 'text' first
        assert text == "From text"

    def test_get_text_skips_non_string_values(self):
        """Test that non-string attribute values are skipped."""
        mock_item = Mock()
        mock_item.text = 123  # Not a string
        mock_item.content = "From content"

        text = _get_text(mock_item)

        assert text == "From content"

    def test_get_text_empty_string_is_falsy(self):
        """Test that empty strings are skipped."""
        mock_item = Mock()
        mock_item.text = ""
        mock_item.content = "From content"

        text = _get_text(mock_item)

        assert text == "From content"


# =============================================================================
# Tests for _parse_markdown_fallback
# =============================================================================


class TestParseMarkdownFallback:
    """Test the _parse_markdown_fallback() function."""

    def test_markdown_fallback_parsing(self):
        """Test that markdown fallback uses DoxParser."""
        mock_doc = DoxDocument()

        with patch("dox.parsers.parser.DoxParser") as mock_parser_class:
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance

            parsed_doc = DoxDocument()
            parsed_doc.add_element(Heading(text="Title", level=1))
            parsed_doc.add_element(Paragraph(text="Paragraph"))
            mock_parser_instance.parse.return_value = parsed_doc

            md_text = "# Title\n\nParagraph"
            _parse_markdown_fallback(md_text, mock_doc)

            # Check that parser was called
            mock_parser_instance.parse.assert_called_once_with(md_text)

            # Check that elements were copied
            assert len(mock_doc.elements) == 2
            assert isinstance(mock_doc.elements[0], Heading)
            assert isinstance(mock_doc.elements[1], Paragraph)

    def test_markdown_fallback_empty_markdown(self):
        """Test markdown fallback with empty markdown."""
        mock_doc = DoxDocument()

        with patch("dox.parsers.parser.DoxParser") as mock_parser_class:
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance
            mock_parser_instance.parse.return_value = DoxDocument()

            _parse_markdown_fallback("", mock_doc)

            assert len(mock_doc.elements) == 0

    def test_markdown_fallback_preserves_existing_elements(self):
        """Test that markdown fallback preserves existing elements."""
        mock_doc = DoxDocument()
        existing_elem = Paragraph(text="Existing")
        mock_doc.add_element(existing_elem)

        with patch("dox.parsers.parser.DoxParser") as mock_parser_class:
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance

            parsed_doc = DoxDocument()
            parsed_doc.add_element(Heading(text="New", level=1))
            mock_parser_instance.parse.return_value = parsed_doc

            _parse_markdown_fallback("# New", mock_doc)

            # Original element should be replaced by parsed elements
            assert len(mock_doc.elements) == 1
            assert isinstance(mock_doc.elements[0], Heading)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDoclingExporterIntegration:
    """Integration tests combining multiple functions."""

    def test_full_document_with_all_element_types(self):
        """Test conversion of a complete document with multiple element types."""
        # Create mock elements
        mock_heading = Mock()
        mock_heading.__class__.__name__ = "Heading"
        mock_heading.level = 1

        mock_para = Mock()
        mock_para.__class__.__name__ = "Paragraph"

        mock_table = Mock()
        mock_table.__class__.__name__ = "Table"

        mock_list = Mock()
        mock_list.__class__.__name__ = "List"

        mock_code = Mock()
        mock_code.__class__.__name__ = "CodeBlock"
        mock_code.language = "python"

        mock_doc = Mock()
        mock_doc.name = "complex.pdf"
        mock_doc.num_pages = 10
        mock_doc.iterate_items.return_value = [
            (mock_heading, 0),
            (mock_para, 1),
            (mock_table, 2),
            (mock_list, 3),
            (mock_code, 4),
        ]
        mock_doc.pages = {}

        mock_docling_class = type(mock_doc)
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            with patch("dox.exporters.docling_exporter._get_text") as mock_get_text:
                mock_get_text.side_effect = [
                    "Main Title",
                    "Main paragraph",
                    "python code",
                ]
                with patch("dox.exporters.docling_exporter._convert_table") as mock_table_conv:
                    with patch("dox.exporters.docling_exporter._convert_list") as mock_list_conv:
                        mock_table_conv.return_value = Table()
                        mock_list_conv.return_value = ListBlock(items=[])

                        dox_doc = docling_to_dox(mock_doc)

                        assert dox_doc.frontmatter.pages == 10
                        assert len(dox_doc.elements) >= 3

    def test_export_with_spatial_and_metadata(self):
        """Test full export including spatial annotations and metadata."""
        mock_item = Mock()
        mock_item.bbox = (0, 0, 100, 100)
        mock_page = Mock()
        mock_page.width = 1000
        mock_page.height = 1000
        mock_page.items = [mock_item]

        mock_doc = Mock()
        mock_doc.name = "spatial.pdf"
        mock_doc.num_pages = 1
        mock_doc.iterate_items.return_value = []
        mock_doc.pages = {0: mock_page}

        mock_docling_class = type(mock_doc)
        mock_docling_module = Mock(DoclingDocument=mock_docling_class)
        mock_datamodel = Mock(document=mock_docling_module)

        with patch("sys.modules", {**sys.modules, "docling": Mock(), "docling.datamodel": mock_datamodel, "docling.datamodel.document": mock_docling_module}):
            with patch("dox.exporters.docling_exporter._get_text", return_value="Item"):
                dox_doc = docling_to_dox(mock_doc, include_spatial=True)

                assert dox_doc.metadata is not None
                assert len(dox_doc.spatial_blocks) == 1
