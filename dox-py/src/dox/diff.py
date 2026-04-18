"""
dox-diff — Semantic and structural diff for .dox documents.

Compares two DoxDocument instances and reports:
  - Content changes (text edits in headings, paragraphs)
  - Structural changes (added/removed/moved elements)
  - Table changes (cell-level diffs)
  - Spatial changes (bounding box shifts)
  - Metadata changes (confidence, provenance)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dox.models.document import DoxDocument
from dox.models.elements import (
    Element,
    Heading,
    Paragraph,
    Table,
    CodeBlock,
    MathBlock,
    FormField,
)


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"
    UNCHANGED = "unchanged"


@dataclass
class ElementChange:
    """A single change between two documents."""
    change_type: ChangeType
    element_type: str
    description: str
    old_value: str | None = None
    new_value: str | None = None
    element_id: str | None = None
    layer: int = 0  # 0=content, 1=spatial, 2=metadata

    def __str__(self) -> str:
        prefix = {
            ChangeType.ADDED: "+",
            ChangeType.REMOVED: "-",
            ChangeType.MODIFIED: "~",
            ChangeType.MOVED: "→",
            ChangeType.UNCHANGED: "=",
        }[self.change_type]
        return f"[{prefix}] ({self.element_type}) {self.description}"


@dataclass
class DiffResult:
    """Complete diff between two .dox documents."""
    changes: list[ElementChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(c.change_type != ChangeType.UNCHANGED for c in self.changes)

    @property
    def added(self) -> list[ElementChange]:
        return [c for c in self.changes if c.change_type == ChangeType.ADDED]

    @property
    def removed(self) -> list[ElementChange]:
        return [c for c in self.changes if c.change_type == ChangeType.REMOVED]

    @property
    def modified(self) -> list[ElementChange]:
        return [c for c in self.changes if c.change_type == ChangeType.MODIFIED]

    def summary(self) -> str:
        if not self.has_changes:
            return "No changes detected."
        parts = []
        if self.added:
            parts.append(f"{len(self.added)} added")
        if self.removed:
            parts.append(f"{len(self.removed)} removed")
        if self.modified:
            parts.append(f"{len(self.modified)} modified")
        return ", ".join(parts)

    def __str__(self) -> str:
        if not self.has_changes:
            return "No changes."
        lines = [f"Changes: {self.summary()}"]
        for change in self.changes:
            if change.change_type != ChangeType.UNCHANGED:
                lines.append(f"  {change}")
        return "\n".join(lines)


class DoxDiff:
    """
    Compare two DoxDocuments and produce a structured diff.

    Usage:
        differ = DoxDiff()
        result = differ.diff(doc_old, doc_new)
        print(result)
        for change in result.modified:
            print(change)
    """

    def __init__(self, ignore_spatial: bool = False, ignore_metadata: bool = False):
        self.ignore_spatial = ignore_spatial
        self.ignore_metadata = ignore_metadata

    def diff(self, old: DoxDocument, new: DoxDocument) -> DiffResult:
        result = DiffResult()

        # Frontmatter diff
        self._diff_frontmatter(old, new, result)

        # Element diff (Layer 0)
        self._diff_elements(old, new, result)

        # Spatial diff (Layer 1)
        if not self.ignore_spatial:
            self._diff_spatial(old, new, result)

        # Metadata diff (Layer 2)
        if not self.ignore_metadata:
            self._diff_metadata(old, new, result)

        return result

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def _diff_frontmatter(self, old: DoxDocument, new: DoxDocument, result: DiffResult) -> None:
        old_fm = old.frontmatter.to_dict()
        new_fm = new.frontmatter.to_dict()

        for key in set(old_fm.keys()) | set(new_fm.keys()):
            old_val = old_fm.get(key)
            new_val = new_fm.get(key)
            if old_val != new_val:
                result.changes.append(ElementChange(
                    change_type=ChangeType.MODIFIED,
                    element_type="frontmatter",
                    description=f"frontmatter.{key}: {old_val!r} → {new_val!r}",
                    old_value=str(old_val),
                    new_value=str(new_val),
                ))

    # ------------------------------------------------------------------
    # Elements (Layer 0)
    # ------------------------------------------------------------------

    def _diff_elements(self, old: DoxDocument, new: DoxDocument, result: DiffResult) -> None:
        old_elements = old.elements
        new_elements = new.elements

        # Build ID-based index for matching
        old_by_id = {self._element_key(e, i): e for i, e in enumerate(old_elements)}
        new_by_id = {self._element_key(e, i): e for i, e in enumerate(new_elements)}

        old_keys = set(old_by_id.keys())
        new_keys = set(new_by_id.keys())

        # Removed elements
        for key in old_keys - new_keys:
            el = old_by_id[key]
            result.changes.append(ElementChange(
                change_type=ChangeType.REMOVED,
                element_type=type(el).__name__,
                description=f"Removed: {self._element_summary(el)}",
                old_value=self._element_summary(el),
                element_id=getattr(el, "element_id", None),
                layer=0,
            ))

        # Added elements
        for key in new_keys - old_keys:
            el = new_by_id[key]
            result.changes.append(ElementChange(
                change_type=ChangeType.ADDED,
                element_type=type(el).__name__,
                description=f"Added: {self._element_summary(el)}",
                new_value=self._element_summary(el),
                element_id=getattr(el, "element_id", None),
                layer=0,
            ))

        # Modified elements (same key, different content)
        for key in old_keys & new_keys:
            old_el = old_by_id[key]
            new_el = new_by_id[key]
            changes = self._compare_elements(old_el, new_el)
            result.changes.extend(changes)

    def _compare_elements(self, old: Element, new: Element) -> list[ElementChange]:
        changes: list[ElementChange] = []
        etype = type(old).__name__
        eid = getattr(old, "element_id", None) or getattr(old, "table_id", None)

        if isinstance(old, Heading) and isinstance(new, Heading):
            if old.text != new.text:
                changes.append(ElementChange(
                    change_type=ChangeType.MODIFIED,
                    element_type=etype,
                    description=f"Heading text changed: '{old.text}' → '{new.text}'",
                    old_value=old.text,
                    new_value=new.text,
                    element_id=eid,
                    layer=0,
                ))
            if old.level != new.level:
                changes.append(ElementChange(
                    change_type=ChangeType.MODIFIED,
                    element_type=etype,
                    description=f"Heading level changed: h{old.level} → h{new.level}",
                    old_value=str(old.level),
                    new_value=str(new.level),
                    element_id=eid,
                    layer=0,
                ))

        elif isinstance(old, Paragraph) and isinstance(new, Paragraph):
            if old.text != new.text:
                changes.append(ElementChange(
                    change_type=ChangeType.MODIFIED,
                    element_type=etype,
                    description=f"Paragraph text changed",
                    old_value=old.text[:100],
                    new_value=new.text[:100],
                    element_id=eid,
                    layer=0,
                ))

        elif isinstance(old, Table) and isinstance(new, Table):
            changes.extend(self._diff_table(old, new))

        elif isinstance(old, CodeBlock) and isinstance(new, CodeBlock):
            if old.code != new.code:
                changes.append(ElementChange(
                    change_type=ChangeType.MODIFIED,
                    element_type=etype,
                    description="Code block changed",
                    element_id=eid,
                    layer=0,
                ))

        return changes

    def _diff_table(self, old: Table, new: Table) -> list[ElementChange]:
        changes: list[ElementChange] = []
        tid = old.table_id or new.table_id

        if old.num_rows != new.num_rows:
            changes.append(ElementChange(
                change_type=ChangeType.MODIFIED,
                element_type="Table",
                description=f"Table '{tid}' row count: {old.num_rows} → {new.num_rows}",
                element_id=tid,
                layer=0,
            ))

        if old.num_cols != new.num_cols:
            changes.append(ElementChange(
                change_type=ChangeType.MODIFIED,
                element_type="Table",
                description=f"Table '{tid}' col count: {old.num_cols} → {new.num_cols}",
                element_id=tid,
                layer=0,
            ))

        # Cell-level comparison
        min_rows = min(len(old.rows), len(new.rows))
        for r in range(min_rows):
            old_row = old.rows[r]
            new_row = new.rows[r]
            min_cells = min(len(old_row.cells), len(new_row.cells))
            for c in range(min_cells):
                if old_row.cells[c].text != new_row.cells[c].text:
                    changes.append(ElementChange(
                        change_type=ChangeType.MODIFIED,
                        element_type="TableCell",
                        description=(
                            f"Table '{tid}' [{r},{c}]: "
                            f"'{old_row.cells[c].text}' → '{new_row.cells[c].text}'"
                        ),
                        old_value=old_row.cells[c].text,
                        new_value=new_row.cells[c].text,
                        element_id=tid,
                        layer=0,
                    ))

        return changes

    # ------------------------------------------------------------------
    # Spatial (Layer 1)
    # ------------------------------------------------------------------

    def _diff_spatial(self, old: DoxDocument, new: DoxDocument, result: DiffResult) -> None:
        old_pages = {b.page for b in old.spatial_blocks}
        new_pages = {b.page for b in new.spatial_blocks}

        for page in old_pages - new_pages:
            result.changes.append(ElementChange(
                change_type=ChangeType.REMOVED,
                element_type="SpatialBlock",
                description=f"Spatial data removed for page {page}",
                layer=1,
            ))

        for page in new_pages - old_pages:
            result.changes.append(ElementChange(
                change_type=ChangeType.ADDED,
                element_type="SpatialBlock",
                description=f"Spatial data added for page {page}",
                layer=1,
            ))

    # ------------------------------------------------------------------
    # Metadata (Layer 2)
    # ------------------------------------------------------------------

    def _diff_metadata(self, old: DoxDocument, new: DoxDocument, result: DiffResult) -> None:
        if old.metadata is None and new.metadata is None:
            return
        if old.metadata is None:
            result.changes.append(ElementChange(
                change_type=ChangeType.ADDED,
                element_type="Metadata",
                description="Metadata block added",
                layer=2,
            ))
            return
        if new.metadata is None:
            result.changes.append(ElementChange(
                change_type=ChangeType.REMOVED,
                element_type="Metadata",
                description="Metadata block removed",
                layer=2,
            ))
            return

        # Confidence changes
        old_conf = old.metadata.confidence.elements
        new_conf = new.metadata.confidence.elements
        for key in set(old_conf.keys()) | set(new_conf.keys()):
            old_score = old_conf.get(key)
            new_score = new_conf.get(key)
            if old_score != new_score:
                result.changes.append(ElementChange(
                    change_type=ChangeType.MODIFIED,
                    element_type="Confidence",
                    description=f"Confidence '{key}': {old_score} → {new_score}",
                    element_id=key,
                    layer=2,
                ))

        # Version history
        old_vh_len = len(old.metadata.version_history)
        new_vh_len = len(new.metadata.version_history)
        if new_vh_len > old_vh_len:
            for entry in new.metadata.version_history[old_vh_len:]:
                result.changes.append(ElementChange(
                    change_type=ChangeType.ADDED,
                    element_type="VersionEntry",
                    description=f"New version entry: {entry.agent} — {entry.action}",
                    layer=2,
                ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _element_key(element: Element, index: int) -> str:
        """Generate a stable key for matching elements across documents."""
        eid = getattr(element, "element_id", None)
        if eid:
            return f"{type(element).__name__}:{eid}"
        if isinstance(element, Table) and element.table_id:
            return f"Table:{element.table_id}"
        if isinstance(element, Heading):
            return f"Heading:{element.level}:{element.text}"
        return f"{type(element).__name__}:{index}"

    @staticmethod
    def _element_summary(element: Element) -> str:
        if isinstance(element, Heading):
            return f"{'#' * element.level} {element.text}"
        elif isinstance(element, Paragraph):
            return element.text[:80] + ("..." if len(element.text) > 80 else "")
        elif isinstance(element, Table):
            return f"Table({element.table_id or 'unnamed'}, {element.num_rows}×{element.num_cols})"
        return type(element).__name__
