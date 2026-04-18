"""Tests for the .dox validator (dox-lint)."""

import pytest
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    BoundingBox, Chart, Heading, PageBreak, Paragraph, Table, TableCell, TableRow,
)
from dox.models.metadata import Confidence, Metadata, Provenance
from dox.models.spatial import SpatialAnnotation, SpatialBlock
from dox.validator import DoxValidator, Severity


@pytest.fixture
def validator():
    return DoxValidator()


class TestFrontmatterValidation:
    def test_valid(self, validator):
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        result = validator.validate(doc)
        assert result.is_valid

    def test_missing_version(self, validator):
        doc = DoxDocument(frontmatter=Frontmatter(version=""))
        result = validator.validate(doc)
        assert not result.is_valid

    def test_unknown_version(self, validator):
        doc = DoxDocument(frontmatter=Frontmatter(version="99.0"))
        result = validator.validate(doc)
        assert any(i.severity == Severity.WARNING and "version" in i.message for i in result.issues)

    def test_invalid_page_count(self, validator):
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0", pages=0))
        result = validator.validate(doc)
        assert not result.is_valid


class TestElementValidation:
    def test_duplicate_ids(self, validator):
        doc = DoxDocument()
        doc.elements = [
            Heading(level=1, text="A", element_id="h1"),
            Heading(level=2, text="B", element_id="h1"),  # duplicate
        ]
        result = validator.validate(doc)
        assert any("Duplicate" in i.message for i in result.errors)

    def test_invalid_heading_level(self, validator):
        doc = DoxDocument()
        doc.elements = [Heading(level=7, text="Bad")]
        result = validator.validate(doc)
        assert not result.is_valid

    def test_empty_heading(self, validator):
        doc = DoxDocument()
        doc.elements = [Heading(level=1, text="")]
        result = validator.validate(doc)
        assert any("Empty heading" in i.message for i in result.warnings)

    def test_chart_bad_ref(self, validator):
        doc = DoxDocument()
        doc.elements = [Chart(data_ref="nonexistent")]
        result = validator.validate(doc)
        assert any("not found" in i.message for i in result.warnings)

    def test_page_break_invalid_range(self, validator):
        doc = DoxDocument()
        doc.elements = [PageBreak(from_page=2, to_page=2)]
        result = validator.validate(doc)
        assert any("advance forward" in i.message for i in result.errors)

    def test_page_break_with_generic_metadata_warns(self, validator):
        doc = DoxDocument()
        doc.elements = [PageBreak(from_page=1, to_page=2, page=1, element_id="pb-1")]
        result = validator.validate(doc)
        assert any("structural" in i.message for i in result.warnings)


class TestTableValidation:
    def test_empty_table(self, validator):
        doc = DoxDocument()
        doc.elements = [Table(table_id="t1")]
        result = validator.validate(doc)
        assert any("Empty table" in i.message for i in result.warnings)

    def test_uneven_columns(self, validator):
        doc = DoxDocument()
        doc.elements = [
            Table(
                table_id="t1",
                rows=[
                    TableRow(cells=[TableCell(text="a"), TableCell(text="b"), TableCell(text="c")]),
                    TableRow(cells=[TableCell(text="d"), TableCell(text="e")]),  # short row
                ],
            )
        ]
        result = validator.validate(doc)
        assert any("cells" in i.message for i in result.warnings)


class TestSpatialValidation:
    def test_negative_bbox(self, validator):
        doc = DoxDocument()
        doc.spatial_blocks = [
            SpatialBlock(
                page=1,
                annotations=[
                    SpatialAnnotation(
                        line_text="test",
                        bbox=BoundingBox(x1=-1, y1=0, x2=100, y2=100),
                    )
                ],
            )
        ]
        result = validator.validate(doc)
        assert any("negative" in i.message for i in result.errors)

    def test_bbox_exceeds_grid(self, validator):
        doc = DoxDocument()
        doc.spatial_blocks = [
            SpatialBlock(
                page=1,
                grid_width=1000,
                grid_height=1000,
                annotations=[
                    SpatialAnnotation(
                        line_text="test",
                        bbox=BoundingBox(x1=0, y1=0, x2=1500, y2=100),
                    )
                ],
            )
        ]
        result = validator.validate(doc)
        assert any("exceeds" in i.message for i in result.warnings)

    def test_zero_area_bbox(self, validator):
        doc = DoxDocument()
        doc.spatial_blocks = [
            SpatialBlock(
                page=1,
                annotations=[
                    SpatialAnnotation(
                        line_text="test",
                        bbox=BoundingBox(x1=100, y1=100, x2=100, y2=200),
                    )
                ],
            )
        ]
        result = validator.validate(doc)
        assert any("zero" in i.message.lower() for i in result.errors)


class TestMetadataValidation:
    def test_invalid_confidence(self, validator):
        doc = DoxDocument()
        doc.metadata = Metadata(
            confidence=Confidence(overall=1.5)
        )
        result = validator.validate(doc)
        assert any("confidence" in i.message.lower() for i in result.errors)

    def test_low_confidence_flagged(self, validator):
        doc = DoxDocument()
        doc.metadata = Metadata(
            confidence=Confidence(overall=0.97, elements={"t1": 0.85})
        )
        result = validator.validate(doc)
        assert any("flagged" in i.message.lower() and "t1" in i.message for i in result.issues)

    def test_missing_source_hash(self, validator):
        doc = DoxDocument()
        doc.metadata = Metadata(provenance=Provenance(source_hash=""))
        result = validator.validate(doc)
        assert any("source_hash" in i.message for i in result.warnings)
