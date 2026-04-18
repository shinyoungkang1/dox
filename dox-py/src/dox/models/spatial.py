"""
Layer 1 spatial annotation model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dox.models.elements import BoundingBox


@dataclass
class SpatialAnnotation:
    """A single spatial annotation linking a content line to a bounding box."""
    line_text: str = ""
    bbox: BoundingBox | None = None
    cell_bboxes: list[BoundingBox] | None = None  # For table rows

    def __str__(self) -> str:
        parts = [self.line_text]
        if self.bbox:
            parts.append(f" {self.bbox}")
        if self.cell_bboxes:
            cells_str = ", ".join(str(c) for c in self.cell_bboxes)
            parts.append(f" cells=[{cells_str}]")
        return "".join(parts)


@dataclass
class SpatialBlock:
    """
    A ---spatial ... ---/spatial block describing one page's spatial layout.
    """
    page: int = 1
    grid_width: int = 1000
    grid_height: int = 1000
    annotations: list[SpatialAnnotation] = field(default_factory=list)
    dirty: bool = False

    @property
    def grid(self) -> str:
        return f"{self.grid_width}x{self.grid_height}"
