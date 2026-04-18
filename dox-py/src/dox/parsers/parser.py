"""
Core .dox parser — reads a .dox string or file and produces a DoxDocument.

Parsing strategy:
  1. Extract and parse the ---dox ... --- frontmatter (YAML).
  2. Extract and parse ---spatial ... ---/spatial blocks (Layer 1).
  3. Extract and parse ---meta ... ---/meta blocks (Layer 2).
  4. Parse the remaining content as Layer 0 (enhanced Markdown).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Annotation,
    BoundingBox,
    Blockquote,
    Chart,
    CodeBlock,
    CrossRef,
    Element,
    Figure,
    Footnote,
    FormField,
    FormFieldType,
    Heading,
    HorizontalRule,
    KeyValuePair,
    ListBlock,
    ListItem,
    MathBlock,
    PageBreak,
    Paragraph,
    Table,
    TableCell,
    TableRow,
)
from dox.models.metadata import Metadata
from dox.models.spatial import SpatialAnnotation, SpatialBlock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---dox\s*\n(.*?)\n---\s*$", re.MULTILINE | re.DOTALL)
_SPATIAL_RE = re.compile(
    r"^---spatial\s+(.*?)\n(.*?)\n---/spatial\s*$", re.MULTILINE | re.DOTALL
)
_META_RE = re.compile(r"^---meta\s*\n(.*?)\n---/meta\s*$", re.MULTILINE | re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s*(.*)")
_TASK_LIST_RE = re.compile(r"^(\s*)([-*+])\s+\[([xX ])\]\s*(.*)")
_TABLE_START_RE = re.compile(r"^\|\|\|\s*table\s*(.*)?$")
_TABLE_END_RE = re.compile(r"^\|\|\|\s*$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
_SEPARATOR_RE = re.compile(r"^[\s|:-]+$")
_MATH_BLOCK_RE = re.compile(
    r"\$\$(.*?)\$\$\s*(\{([^}]*)\})?", re.DOTALL
)
_INLINE_BLOCK_RE = re.compile(r"^::(\w+)\s+(.*?)::\s*(\{[^}]*\})?\s*$")
_CODE_FENCE_START_RE = re.compile(r"^```(?:([^\s{]+))?(?:\s+(\{.*\}))?\s*$")
_CODE_FENCE_END_RE = re.compile(r"^```\s*$")
_CROSS_REF_RE = re.compile(r"^\[\[ref:([^\]]+)\]\]\s*(\{[^}]*\})?\s*$")
_FIGURE_RE = re.compile(
    r"^!\[((?:\\.|[^\]])*)\]\(((?:\\.|[^)])*)\)\s*(?:\{figure:\s*(.*?)\})?\s*$"
)
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^(\d+)\]:\s*(.+)$")
_BBOX_RE = re.compile(r"@\[(\d+),(\d+),(\d+),(\d+)\]")
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")
_HORIZONTAL_RULE_RE = re.compile(r"^([-*_])\s*(\1\s*)+$")
_PAGE_BREAK_RE = re.compile(r"^---page-break\s+from=(\d+)\s+to=(\d+)\s*---$")
_KV_RE = re.compile(r'^::kv\s+(.+?)::$')
_QUOTED_ATTR_RE = re.compile(r'([\w-]+)="((?:\\.|[^"\\])*)"')
_UNQUOTED_ATTR_RE = re.compile(r'([\w-]+)=([^\s]+)')

# Inline element metadata: {page: 3, id: "el-1", confidence: 0.95}
_ELEMENT_META_RE = re.compile(r'\s*\{([^}]*)\}\s*$')
_META_PAGE_RE = re.compile(r'page\s*[:=]\s*"?(?P<value>\d+)"?')
_META_ID_RE = re.compile(r'(?:^|[\s,])id\s*[:=]\s*"((?:\\.|[^"\\])*)"')
_META_CONFIDENCE_RE = re.compile(r'confidence\s*[:=]\s*"?(?P<value>[\d.]+)"?')
_META_READING_ORDER_RE = re.compile(r'reading_order\s*[:=]\s*"?(?P<value>\d+)"?')
_META_LANG_RE = re.compile(r'lang\s*[:=]\s*"((?:\\.|[^"\\])*)"')
_META_IS_FURNITURE_RE = re.compile(
    r'is_furniture\s*[:=]\s*"?(?P<value>true|false|1|0)"?',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Helper functions for safe type conversion
# ---------------------------------------------------------------------------

def _safe_int(val: str | int, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val: str | float, default: float | None = None) -> float | None:
    """Safely convert a value to float, returning default on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_bool(val: str | bool | None, default: bool = False) -> bool:
    """Safely convert a value to bool, returning default on failure."""
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    normalized = str(val).strip().strip('"').lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return default


def _unescape_escaped_text(val: str | None) -> str:
    """Unescape backslash-escaped text used in attributes and markdown spans."""
    if not val:
        return ""
    out: list[str] = []
    escaping = False
    for ch in val:
        if escaping:
            out.append(ch)
            escaping = False
        elif ch == "\\":
            escaping = True
        else:
            out.append(ch)
    if escaping:
        out.append("\\")
    return "".join(out)


def _parse_meta_string(meta_str: str) -> dict:
    """Parse metadata from either key: value or key=\"value\" style annotations."""
    meta: dict = {}

    pm = _META_PAGE_RE.search(meta_str)
    if pm:
        meta["page"] = _safe_int(pm.group("value"))

    im = _META_ID_RE.search(meta_str)
    if im:
        meta["element_id"] = _unescape_escaped_text(im.group(1))

    cm = _META_CONFIDENCE_RE.search(meta_str)
    if cm:
        conf_val = _safe_float(cm.group("value"))
        if conf_val is not None:
            meta["confidence"] = conf_val

    rom = _META_READING_ORDER_RE.search(meta_str)
    if rom:
        meta["reading_order"] = _safe_int(rom.group("value"))

    lm = _META_LANG_RE.search(meta_str)
    if lm:
        meta["lang"] = _unescape_escaped_text(lm.group(1))

    fm = _META_IS_FURNITURE_RE.search(meta_str)
    if fm:
        meta["is_furniture"] = _safe_bool(fm.group("value"))

    return meta


def _extract_element_meta(text: str) -> tuple[str, dict]:
    """Extract trailing {page: N, id: "..."} style metadata from text.

    Returns (clean_text, meta_dict) where meta_dict may contain
    canonical element metadata fields.
    """
    meta: dict = {}
    m = _ELEMENT_META_RE.search(text)
    if not m:
        return text, meta

    meta_str = m.group(1)
    meta = _parse_meta_string(meta_str)
    if not meta:
        return text, meta

    clean = text[:m.start()]
    return clean, meta


def _apply_meta(element: Element, meta: dict) -> None:
    """Apply extracted metadata to an element."""
    if 'page' in meta:
        element.page = meta['page']
    if 'element_id' in meta:
        element.element_id = meta['element_id']
    if 'confidence' in meta:
        element.confidence = meta['confidence']
    if 'reading_order' in meta:
        element.reading_order = meta['reading_order']
    if 'lang' in meta:
        element.lang = meta['lang']
    if 'is_furniture' in meta:
        element.is_furniture = meta['is_furniture']

# Table attribute patterns
_TABLE_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _parse_attrs(attrs_str: str) -> dict[str, str]:
    """Parse key="value" pairs from an attributes string."""
    attrs: dict[str, str] = {}
    for m in _QUOTED_ATTR_RE.finditer(attrs_str):
        attrs[m.group(1)] = _unescape_escaped_text(m.group(2))
    for m in _UNQUOTED_ATTR_RE.finditer(attrs_str):
        key = m.group(1)
        val = _unescape_escaped_text(m.group(2).strip('"'))
        if key not in attrs:
            attrs[key] = val
    return attrs


class DoxParser:
    """
    Parse .dox format text into a DoxDocument.

    Usage:
        parser = DoxParser()
        doc = parser.parse(text)
        doc = parser.parse_file("report.dox")
    """

    def parse_file(self, path: str | Path) -> DoxDocument:
        """Parse a .dox file from disk."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError as e:
            logger.warning(f"File not found: {path}")
            raise
        except UnicodeDecodeError as e:
            logger.warning(f"Unicode decode error reading {path}: {e}")
            raise
        return self.parse(text)

    def parse(self, text: str) -> DoxDocument:
        """Parse a .dox string into a DoxDocument."""
        doc = DoxDocument()

        # 1. Frontmatter
        text = self._parse_frontmatter(text, doc)

        # 2. Spatial blocks (Layer 1)
        text = self._parse_spatial_blocks(text, doc)

        # 3. Metadata block (Layer 2)
        text = self._parse_metadata(text, doc)

        # 4. Content (Layer 0)
        self._parse_content(text, doc)

        return doc

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------

    def _parse_frontmatter(self, text: str, doc: DoxDocument) -> str:
        match = _FRONTMATTER_RE.search(text)
        if match:
            try:
                raw = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError as e:
                logger.warning(f"YAML parse error in frontmatter: {e}. Using empty frontmatter.")
                raw = {}
            doc.frontmatter = Frontmatter.from_dict(raw)
            text = text[: match.start()] + text[match.end() :]
        return text

    # ------------------------------------------------------------------
    # Spatial blocks (Layer 1)
    # ------------------------------------------------------------------

    def _parse_spatial_blocks(self, text: str, doc: DoxDocument) -> str:
        for match in _SPATIAL_RE.finditer(text):
            header = match.group(1)
            body = match.group(2)
            block = self._parse_spatial_header(header)
            block.annotations = self._parse_spatial_body(body)
            doc.spatial_blocks.append(block)
        text = _SPATIAL_RE.sub("", text)
        return text

    def _parse_spatial_header(self, header: str) -> SpatialBlock:
        block = SpatialBlock()
        parts = header.split()
        for part in parts:
            if part.startswith("page="):
                page_val = _safe_int(part.split("=", 1)[1])
                if page_val is not None:
                    block.page = page_val
            elif part.startswith("grid="):
                grid = part.split("=", 1)[1]
                if "x" in grid:
                    w, h = grid.split("x")
                    w_val = _safe_int(w)
                    h_val = _safe_int(h)
                    if w_val is not None:
                        block.grid_width = w_val
                    if h_val is not None:
                        block.grid_height = h_val
        return block

    def _parse_spatial_body(self, body: str) -> list[SpatialAnnotation]:
        annotations = []
        for line in body.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            ann = SpatialAnnotation()
            bbox_match = _BBOX_RE.search(line)
            if bbox_match:
                x1 = _safe_int(bbox_match.group(1))
                y1 = _safe_int(bbox_match.group(2))
                x2 = _safe_int(bbox_match.group(3))
                y2 = _safe_int(bbox_match.group(4))
                if all(v is not None for v in [x1, y1, x2, y2]):
                    ann.bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                ann.line_text = line[: bbox_match.start()].strip()
            else:
                ann.line_text = line

            # Parse cell-level bboxes (greedy to capture all nested @[...] entries)
            cells_match = re.search(r"cells=\[(.+)\]\s*$", line)
            if cells_match:
                cell_bboxes = []
                for cm in _BBOX_RE.finditer(cells_match.group(1)):
                    x1 = _safe_int(cm.group(1))
                    y1 = _safe_int(cm.group(2))
                    x2 = _safe_int(cm.group(3))
                    y2 = _safe_int(cm.group(4))
                    if all(v is not None for v in [x1, y1, x2, y2]):
                        cell_bboxes.append(BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2))
                ann.cell_bboxes = cell_bboxes

            annotations.append(ann)
        return annotations

    # ------------------------------------------------------------------
    # Metadata (Layer 2)
    # ------------------------------------------------------------------

    def _parse_metadata(self, text: str, doc: DoxDocument) -> str:
        match = _META_RE.search(text)
        if match:
            try:
                raw = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError as e:
                logger.warning(f"YAML parse error in metadata: {e}. Using empty metadata.")
                raw = {}
            doc.metadata = Metadata.from_dict(raw)
            text = text[: match.start()] + text[match.end() :]
        return text

    # ------------------------------------------------------------------
    # Content (Layer 0)
    # ------------------------------------------------------------------

    def _parse_content(self, text: str, doc: DoxDocument) -> None:
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                i += 1
                continue

            # Horizontal rules (must check before page breaks since they can look similar)
            if _HORIZONTAL_RULE_RE.match(stripped):
                # Make sure it's not a page break (which starts with ---)
                if not stripped.startswith("---page-break"):
                    doc.add_element(HorizontalRule())
                    i += 1
                    continue

            # Page breaks
            pb_match = _PAGE_BREAK_RE.match(stripped)
            if pb_match:
                from_page = _safe_int(pb_match.group(1))
                to_page = _safe_int(pb_match.group(2))
                doc.add_element(PageBreak(from_page=from_page, to_page=to_page))
                i += 1
                continue

            # Headings
            heading_match = _HEADING_RE.match(stripped)
            if heading_match:
                raw_text = heading_match.group(2).strip()
                clean_text, meta = _extract_element_meta(raw_text)
                el = Heading(
                    level=len(heading_match.group(1)),
                    text=clean_text.strip(),
                )
                _apply_meta(el, meta)
                self._extract_inline_bbox(stripped, el)
                doc.add_element(el)
                i += 1
                continue

            # Code blocks
            code_match = _CODE_FENCE_START_RE.match(stripped)
            if code_match:
                lang = code_match.group(1) or None
                meta_group = code_match.group(2) or ""
                meta = _parse_meta_string(meta_group[1:-1]) if meta_group.startswith("{") else {}
                code_lines = []
                i += 1
                while i < len(lines) and not _CODE_FENCE_END_RE.match(lines[i].strip()):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                el = CodeBlock(code="\n".join(code_lines), language=lang)
                _apply_meta(el, meta)
                doc.add_element(el)
                continue

            # Table blocks
            table_match = _TABLE_START_RE.match(stripped)
            if table_match:
                attrs_str = table_match.group(1) or ""
                table = self._parse_table_block(lines, i, attrs_str)
                # Advance past the table
                i += 1
                while i < len(lines) and not _TABLE_END_RE.match(lines[i].strip()):
                    i += 1
                i += 1  # skip closing |||
                doc.add_element(table)
                continue

            # Inline blocks: ::type attrs::
            inline_match = _INLINE_BLOCK_RE.match(stripped)
            if inline_match:
                el = self._parse_inline_block(
                    inline_match.group(1), inline_match.group(2), inline_match.group(3)
                )
                if el:
                    doc.add_element(el)
                i += 1
                continue

            # Cross-reference
            cross_ref_match = _CROSS_REF_RE.match(stripped)
            if cross_ref_match:
                ref_target = cross_ref_match.group(1)
                ref_parts = ref_target.split(":", 1)
                ref_type = ref_parts[0] if len(ref_parts) == 2 else ""
                ref_id = ref_parts[1] if len(ref_parts) == 2 else ref_target
                meta_group = cross_ref_match.group(2) or ""
                meta = _parse_meta_string(meta_group[1:-1]) if meta_group.startswith("{") else {}
                el = CrossRef(ref_type=ref_type, ref_id=ref_id)
                _apply_meta(el, meta)
                doc.add_element(el)
                i += 1
                continue

            # Figure
            fig_match = _FIGURE_RE.match(stripped)
            if fig_match:
                fig_meta_str = fig_match.group(3) or ""
                fig_attrs = _parse_attrs(fig_meta_str)
                fig_meta = _parse_meta_string(fig_meta_str)
                el = Figure(
                    caption=_unescape_escaped_text(fig_match.group(1)),
                    source=_unescape_escaped_text(fig_match.group(2)),
                    figure_id=fig_attrs.get("id"),
                    image_type=fig_attrs.get("image_type") or fig_attrs.get("image-type"),
                    image_data=fig_attrs.get("image_data") or fig_attrs.get("image-data"),
                )
                fig_meta.pop("element_id", None)
                eid_match = re.search(r'eid\s*[:=]\s*"((?:\\.|[^"\\])*)"', fig_meta_str)
                if "eid" in fig_attrs:
                    el.element_id = fig_attrs["eid"]
                elif eid_match:
                    el.element_id = _unescape_escaped_text(eid_match.group(1))
                _apply_meta(el, fig_meta)
                doc.add_element(el)
                i += 1
                continue

            # Footnote definition
            fn_match = _FOOTNOTE_DEF_RE.match(stripped)
            if fn_match:
                fn_text = fn_match.group(2)
                clean_fn, fn_meta = _extract_element_meta(fn_text)
                fn_num = _safe_int(fn_match.group(1))
                if fn_num is not None:
                    el = Footnote(number=fn_num, text=clean_fn.strip())
                    _apply_meta(el, fn_meta)
                    doc.add_element(el)
                i += 1
                continue

            # List blocks
            list_match = _LIST_RE.match(stripped)
            if list_match:
                items, i = self._parse_list(lines, i)
                ordered = bool(re.match(r"\d+\.", list_match.group(2)))
                doc.add_element(ListBlock(items=items, ordered=ordered))
                continue

            # Math block - check for multi-line first ($$...$$)
            if stripped == "$$":
                # Multi-line math block
                math_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() != "$$":
                    math_lines.append(lines[i])
                    i += 1
                if i < len(lines) and lines[i].strip() == "$$":
                    i += 1  # skip closing $$
                expression = "\n".join(math_lines).strip()
                el = MathBlock(expression=expression, display_mode=True)
                doc.add_element(el)
                continue

            # Math block (standalone line with inline $$ ... $$)
            math_match = _MATH_BLOCK_RE.match(stripped)
            if math_match:
                display_mode = True
                page = None
                element_id = None
                confidence = None
                hint_str = math_match.group(3) if math_match.group(2) else ""
                if hint_str:
                    if "latex" in hint_str:
                        display_mode = True
                    pm = _META_PAGE_RE.search(hint_str)
                    if pm:
                        page = _safe_int(pm.group(1))
                    im = _META_ID_RE.search(hint_str)
                    if im:
                        element_id = im.group(1)
                    cm = _META_CONFIDENCE_RE.search(hint_str)
                    if cm:
                        confidence = _safe_float(cm.group(1))
                el = MathBlock(
                    expression=math_match.group(1).strip(),
                    display_mode=display_mode,
                    page=page,
                    element_id=element_id,
                    confidence=confidence,
                )
                doc.add_element(el)
                i += 1
                continue

            # Blockquotes (collect consecutive > lines)
            blockquote_match = _BLOCKQUOTE_RE.match(stripped)
            if blockquote_match:
                blockquote_lines = []
                while i < len(lines):
                    bq_line = lines[i].strip()
                    bq_match = _BLOCKQUOTE_RE.match(bq_line)
                    if not bq_match:
                        break
                    blockquote_lines.append(bq_match.group(1))
                    i += 1
                if blockquote_lines:
                    text_content = " ".join(blockquote_lines)
                    clean_text, meta = _extract_element_meta(text_content)
                    el = Blockquote(text=clean_text.strip())
                    _apply_meta(el, meta)
                    doc.add_element(el)
                continue

            # Default: paragraph (collect consecutive non-blank, non-special lines)
            para_lines = []
            while i < len(lines):
                ln = lines[i].strip()
                if not ln:
                    break
                if (
                    _HEADING_RE.match(ln)
                    or _BLOCKQUOTE_RE.match(ln)
                    or _TABLE_START_RE.match(ln)
                    or _CODE_FENCE_START_RE.match(ln)
                    or _INLINE_BLOCK_RE.match(ln)
                    or _CROSS_REF_RE.match(ln)
                    or _FIGURE_RE.match(ln)
                    or _FOOTNOTE_DEF_RE.match(ln)
                    or _LIST_RE.match(ln)
                    or _PAGE_BREAK_RE.match(ln)
                    or _MATH_BLOCK_RE.match(ln)
                ):
                    break
                para_lines.append(ln)
                i += 1
            if para_lines:
                text_content = " ".join(para_lines)
                clean_text, meta = _extract_element_meta(text_content)
                el = Paragraph(text=clean_text.strip())
                _apply_meta(el, meta)
                doc.add_element(el)
                continue

            i += 1

    # ------------------------------------------------------------------
    # Table parsing
    # ------------------------------------------------------------------

    def _parse_table_block(self, lines: list[str], start: int, attrs_str: str) -> Table:
        attrs = _parse_attrs(attrs_str)
        table = Table(
            table_id=attrs.get("id"),
            caption=attrs.get("caption"),
            nested=_safe_bool(attrs.get("nested"), default="nested" in attrs),
            continuation_of=attrs.get("continuation-of"),
        )
        # Parse pages="3-5" attribute
        pages_str = attrs.get("pages")
        if pages_str and "-" in pages_str:
            parts = pages_str.split("-", 1)
            try:
                table.page_range = (int(parts[0]), int(parts[1]))
            except ValueError:
                pass
        table.element_id = attrs.get("eid") or table.table_id
        if "page" in attrs:
            table.page = _safe_int(attrs["page"])
        if "confidence" in attrs:
            table.confidence = _safe_float(attrs["confidence"])
        if "reading_order" in attrs:
            table.reading_order = _safe_int(attrs["reading_order"])
        if "lang" in attrs:
            table.lang = attrs["lang"]
        if "is_furniture" in attrs:
            table.is_furniture = _safe_bool(attrs["is_furniture"])

        i = start + 1
        header_passed = False
        while i < len(lines):
            stripped = lines[i].strip()
            if _TABLE_END_RE.match(stripped):
                break

            # Separator row
            if _SEPARATOR_RE.match(stripped) and "|" in stripped:
                header_passed = True
                i += 1
                continue

            row_match = _TABLE_ROW_RE.match(stripped)
            if row_match:
                cell_texts = [c.strip() for c in row_match.group(1).split("|")]
                cells = []
                for t in cell_texts:
                    colspan = 1
                    rowspan = 1
                    # Extract {cs=N rs=N} span annotations
                    span_match = re.search(r'\{((?:cs=\d+\s*)?(?:rs=\d+\s*)?)\}\s*$', t)
                    if span_match:
                        span_str = span_match.group(1)
                        cs_m = re.search(r'cs=(\d+)', span_str)
                        rs_m = re.search(r'rs=(\d+)', span_str)
                        if cs_m:
                            cs_val = _safe_int(cs_m.group(1))
                            if cs_val is not None and cs_val > 0:
                                colspan = cs_val
                        if rs_m:
                            rs_val = _safe_int(rs_m.group(1))
                            if rs_val is not None and rs_val > 0:
                                rowspan = rs_val
                        t = t[:span_match.start()].strip()
                    cells.append(TableCell(
                        text=t,
                        is_header=not header_passed,
                        colspan=colspan,
                        rowspan=rowspan,
                    ))
                row = TableRow(cells=cells, is_header=not header_passed)
                table.rows.append(row)

            i += 1

        return table

    # ------------------------------------------------------------------
    # Inline block parsing
    # ------------------------------------------------------------------

    def _parse_inline_block(
        self,
        block_type: str,
        attrs_str: str,
        meta_group: str | None = None,
    ) -> Element | None:
        attrs = _parse_attrs(attrs_str)
        meta = _parse_meta_string(meta_group[1:-1]) if meta_group and meta_group.startswith("{") else {}
        element: Element | None = None

        if block_type == "form":
            ft_str = attrs.get("type", "text")
            try:
                ft = FormFieldType(ft_str)
            except ValueError:
                ft = FormFieldType.TEXT
            element = FormField(
                field_name=attrs.get("field", ""),
                field_type=ft,
                value=attrs.get("value", ""),
            )
        elif block_type == "chart":
            element = Chart(
                chart_type=attrs.get("type", "bar"),
                data_ref=attrs.get("data-ref"),
                x_field=attrs.get("x"),
                y_field=attrs.get("y"),
                extra={k: v for k, v in attrs.items() if k not in {"type", "data-ref", "x", "y"}},
            )
        elif block_type == "annotation":
            confidence = None
            if "confidence" in attrs:
                confidence = _safe_float(attrs["confidence"])
            element = Annotation(
                annotation_type=attrs.get("type", "handwriting"),
                text=attrs.get("text", ""),
                confidence=confidence,
            )
        elif block_type == "kv":
            element = KeyValuePair(
                key=attrs.get("key", ""),
                value=attrs.get("value", ""),
            )
        if element is not None:
            _apply_meta(element, meta)
        return element

    # ------------------------------------------------------------------
    # List parsing
    # ------------------------------------------------------------------

    def _parse_list(self, lines: list[str], start: int) -> tuple[list[ListItem], int]:
        items: list[ListItem] = []
        i = start
        base_indent = None

        while i < len(lines):
            line = lines[i]

            # Try task-list pattern first
            task_match = _TASK_LIST_RE.match(line)
            if task_match:
                indent = len(task_match.group(1))
                checkbox = task_match.group(3)
                text = task_match.group(4)
                checked = checkbox.lower() == 'x'

                # Set base indentation from first item
                if base_indent is None:
                    base_indent = indent

                # If indentation decreased, we've left the list
                if indent < base_indent:
                    break

                # Check if this is a top-level item or child
                if indent == base_indent:
                    # Top-level item
                    item = ListItem(text=text, children=[], checked=checked)
                    items.append(item)
                elif indent > base_indent and items:
                    # Child item - add to last item's children (2-level nesting)
                    child_item = ListItem(text=text, checked=checked)
                    items[-1].children.append(child_item)

                i += 1
                continue

            # Try regular list pattern
            match = _LIST_RE.match(line)
            if not match:
                break

            indent = len(match.group(1))
            text = match.group(3)

            # Set base indentation from first item
            if base_indent is None:
                base_indent = indent

            # If indentation decreased, we've left the list
            if indent < base_indent:
                break

            # Check if this is a top-level item or child
            if indent == base_indent:
                # Top-level item
                item = ListItem(text=text, children=[])
                items.append(item)
            elif indent > base_indent and items:
                # Child item - add to last item's children (2-level nesting)
                child_item = ListItem(text=text)
                items[-1].children.append(child_item)

            i += 1

        return items, i

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_inline_bbox(self, text: str, element: Element) -> None:
        match = _BBOX_RE.search(text)
        if match:
            x1 = _safe_int(match.group(1))
            y1 = _safe_int(match.group(2))
            x2 = _safe_int(match.group(3))
            y2 = _safe_int(match.group(4))
            if all(v is not None for v in [x1, y1, x2, y2]):
                element.bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
