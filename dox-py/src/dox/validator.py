"""
DoxValidator (dox-lint) — validate .dox documents for correctness.

Checks:
  - Frontmatter: required fields, version compatibility
  - Layer 0: well-formed tables, valid element syntax
  - Layer 1: bounding box ranges, grid consistency
  - Layer 2: confidence ranges, required provenance fields
  - Cross-references: all [[ref:...]] targets exist
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dox.models.document import DoxDocument
from dox.models.elements import (
    Chart,
    CrossRef,
    Element,
    FormField,
    Heading,
    PageBreak,
    Table,
)
from dox.models.spatial import SpatialBlock


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    severity: Severity
    message: str
    element_id: str | None = None
    layer: int | None = None  # 0, 1, or 2

    def __str__(self) -> str:
        prefix = f"[{self.severity.value.upper()}]"
        loc = f" (Layer {self.layer})" if self.layer is not None else ""
        eid = f" [{self.element_id}]" if self.element_id else ""
        return f"{prefix}{loc}{eid} {self.message}"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    def __str__(self) -> str:
        if not self.issues:
            return "Valid .dox document (no issues found)"
        lines = [f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"]
        for issue in self.issues:
            lines.append(f"  {issue}")
        return "\n".join(lines)


class DoxValidator:
    """
    Validate a DoxDocument against the .dox specification.

    Usage:
        validator = DoxValidator()
        result = validator.validate(doc)
        if not result.is_valid:
            print(result)
    """

    def __init__(self, confidence_threshold: float = 0.90):
        # Clamp confidence_threshold to valid range [0.0, 1.0]
        if confidence_threshold < 0.0:
            self.confidence_threshold = 0.0
        elif confidence_threshold > 1.0:
            self.confidence_threshold = 1.0
        else:
            self.confidence_threshold = confidence_threshold

    def validate(self, doc: DoxDocument) -> ValidationResult:
        result = ValidationResult()
        self._validate_frontmatter(doc, result)
        self._validate_elements(doc, result)
        self._validate_spatial(doc, result)
        self._validate_metadata(doc, result)
        self._validate_cross_refs(doc, result)
        return result

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def _validate_frontmatter(self, doc: DoxDocument, result: ValidationResult) -> None:
        fm = doc.frontmatter
        if not fm.version:
            result.issues.append(
                ValidationIssue(Severity.ERROR, "Missing frontmatter version", layer=0)
            )
        elif fm.version not in ("1.0", "0.1"):
            result.issues.append(
                ValidationIssue(
                    Severity.WARNING,
                    f"Unknown .dox version: {fm.version}",
                    layer=0,
                )
            )
        if fm.pages is not None and fm.pages < 1:
            result.issues.append(
                ValidationIssue(Severity.ERROR, "Page count must be >= 1", layer=0)
            )

    # ------------------------------------------------------------------
    # Elements (Layer 0)
    # ------------------------------------------------------------------

    def _validate_elements(self, doc: DoxDocument, result: ValidationResult) -> None:
        seen_ids: set[str] = set()

        for element in doc.elements:
            eid = self._get_element_id(element)

            # Check duplicate IDs
            if eid:
                if eid in seen_ids:
                    result.issues.append(
                        ValidationIssue(
                            Severity.ERROR,
                            f"Duplicate element ID: {eid}",
                            element_id=eid,
                            layer=0,
                        )
                    )
                seen_ids.add(eid)

            # Type-specific validation
            if isinstance(element, Heading):
                if element.level < 1 or element.level > 6:
                    result.issues.append(
                        ValidationIssue(
                            Severity.ERROR,
                            f"Heading level must be 1-6, got {element.level}",
                            layer=0,
                        )
                    )
                if not element.text.strip():
                    result.issues.append(
                        ValidationIssue(Severity.WARNING, "Empty heading text", layer=0)
                    )

            elif isinstance(element, Table):
                self._validate_table(element, result)

            elif isinstance(element, FormField):
                if not element.field_name:
                    result.issues.append(
                        ValidationIssue(
                            Severity.WARNING, "Form field missing field name", layer=0
                        )
                    )

            elif isinstance(element, Chart):
                if element.data_ref and not doc.get_element_by_id(element.data_ref):
                    result.issues.append(
                        ValidationIssue(
                            Severity.WARNING,
                            f"Chart data-ref '{element.data_ref}' not found",
                            element_id=eid,
                            layer=0,
                        )
                    )

            elif isinstance(element, PageBreak):
                self._validate_page_break(element, result)

    def _validate_table(self, table: Table, result: ValidationResult) -> None:
        eid = table.table_id or table.element_id
        if not table.rows:
            result.issues.append(
                ValidationIssue(
                    Severity.WARNING, "Empty table (no rows)", element_id=eid, layer=0
                )
            )
            return

        expected_cols = table.num_cols
        for i, row in enumerate(table.rows):
            row_width = sum(max(1, cell.colspan) for cell in row.cells)
            if row_width != expected_cols:
                result.issues.append(
                    ValidationIssue(
                        Severity.WARNING,
                        f"Table row {i} has semantic width {row_width} ({len(row.cells)} cells), expected {expected_cols}",
                        element_id=eid,
                        layer=0,
                    )
                )

    def _validate_page_break(self, page_break: PageBreak, result: ValidationResult) -> None:
        if page_break.from_page < 1 or page_break.to_page < 1:
            result.issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    f"PageBreak pages must be >= 1, got from={page_break.from_page}, to={page_break.to_page}",
                    layer=0,
                )
            )
        elif page_break.to_page <= page_break.from_page:
            result.issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    f"PageBreak must advance forward, got from={page_break.from_page}, to={page_break.to_page}",
                    layer=0,
                )
            )

        carries_generic_meta = any(
            [
                page_break.element_id,
                page_break.bbox is not None,
                page_break.confidence is not None,
                page_break.page is not None,
                page_break.reading_order is not None,
                page_break.lang is not None,
                page_break.is_furniture,
            ]
        )
        if carries_generic_meta:
            result.issues.append(
                ValidationIssue(
                    Severity.WARNING,
                    "PageBreak is structural and should not carry generic element metadata",
                    layer=0,
                )
            )

    # ------------------------------------------------------------------
    # Spatial (Layer 1)
    # ------------------------------------------------------------------

    def _validate_spatial(self, doc: DoxDocument, result: ValidationResult) -> None:
        for block in doc.spatial_blocks:
            if block.page < 1:
                result.issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        f"Spatial block page must be >= 1, got {block.page}",
                        layer=1,
                    )
                )
            self._validate_spatial_block(block, result)

    def _validate_spatial_block(
        self, block: SpatialBlock, result: ValidationResult
    ) -> None:
        for ann in block.annotations:
            if ann.bbox:
                self._validate_bbox(
                    ann.bbox, block.grid_width, block.grid_height, result
                )
            if ann.cell_bboxes:
                for cb in ann.cell_bboxes:
                    self._validate_bbox(cb, block.grid_width, block.grid_height, result)

    def _validate_bbox(
        self,
        bbox,
        grid_w: int,
        grid_h: int,
        result: ValidationResult,
    ) -> None:
        if bbox.x1 < 0 or bbox.y1 < 0:
            result.issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    f"Bounding box has negative coordinates: {bbox}",
                    layer=1,
                )
            )
        if bbox.x2 > grid_w or bbox.y2 > grid_h:
            result.issues.append(
                ValidationIssue(
                    Severity.WARNING,
                    f"Bounding box exceeds grid ({grid_w}x{grid_h}): {bbox}",
                    layer=1,
                )
            )
        if bbox.x1 >= bbox.x2 or bbox.y1 >= bbox.y2:
            result.issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    f"Bounding box has zero or negative area: {bbox}",
                    layer=1,
                )
            )

    # ------------------------------------------------------------------
    # Metadata (Layer 2)
    # ------------------------------------------------------------------

    def _validate_metadata(self, doc: DoxDocument, result: ValidationResult) -> None:
        if not doc.metadata:
            return

        meta = doc.metadata
        conf = meta.confidence

        if conf.overall < 0 or conf.overall > 1:
            result.issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    f"Overall confidence must be 0-1, got {conf.overall}",
                    layer=2,
                )
            )

        for eid, score in conf.elements.items():
            if score < 0 or score > 1:
                result.issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        f"Confidence for '{eid}' must be 0-1, got {score}",
                        element_id=eid,
                        layer=2,
                    )
                )
            if score < self.confidence_threshold:
                result.issues.append(
                    ValidationIssue(
                        Severity.INFO,
                        f"Low confidence ({score}) for '{eid}' — flagged for review",
                        element_id=eid,
                        layer=2,
                    )
                )

        if not meta.provenance.source_hash:
            result.issues.append(
                ValidationIssue(
                    Severity.WARNING, "Missing source_hash in provenance", layer=2
                )
            )

    # ------------------------------------------------------------------
    # Cross-references
    # ------------------------------------------------------------------

    def _validate_cross_refs(self, doc: DoxDocument, result: ValidationResult) -> None:
        for element in doc.elements:
            if isinstance(element, CrossRef):
                target = doc.get_element_by_id(element.ref_id)
                if not target:
                    result.issues.append(
                        ValidationIssue(
                            Severity.WARNING,
                            f"Unresolved cross-reference: [[ref:{element.ref_type}:{element.ref_id}]]",
                            layer=0,
                        )
                    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_element_id(element: Element) -> str | None:
        if element.element_id:
            return element.element_id
        if isinstance(element, Table) and element.table_id:
            return element.table_id
        return None
