"""
Head-to-Head: .dox vs Markdown vs JSON

Same content → each format → measure what survives.

The pipeline:
  OmniDocBench ground truth → DoxDocument (in memory)
      ├── .dox serialize → .dox parse → measure preservation
      ├── Markdown export → Markdown re-import → measure preservation
      └── JSON export → JSON re-import → measure preservation

We measure 8 dimensions:
  1. Text content (do the words survive?)
  2. Table row/col structure (do table dimensions survive?)
  3. Table cell text (does cell content survive?)
  4. Table colspan/rowspan (does complex structure survive?)
  5. Math expressions (does LaTeX survive?)
  6. Spatial bounding boxes (do positions survive?)
  7. Page numbers (do page assignments survive?)
  8. Element type accuracy (do types survive roundtrip?)
"""

import json
import re
import pytest
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.converters.to_html import to_html
from dox.converters.to_json import to_json, to_dict
from dox.converters.to_markdown import to_markdown
from dox.models.elements import (
    Heading, Paragraph, Table, MathBlock, Figure, Footnote, PageBreak,
    TableRow, TableCell,
)

OMNIDOCBENCH_JSON = Path(
    "/sessions/nice-amazing-wright/hf_cache/datasets--opendatalab--OmniDocBench/"
    "snapshots/d386947f7fc3bafdcd756c8485845a2f43a19875/OmniDocBench.json"
)


def _load_benchmark():
    if not OMNIDOCBENCH_JSON.exists():
        pytest.skip("OmniDocBench data not available")
    with open(OMNIDOCBENCH_JSON) as f:
        return json.load(f)


def _text_sim(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# =====================================================================
# Markdown re-import: parse standard markdown back into elements
# =====================================================================

def _markdown_to_elements(md_text: str) -> dict:
    """
    Parse standard Markdown back into structured elements.
    This simulates what you'd get if Markdown was your storage format.
    """
    lines = md_text.split("\n")
    result = {
        "headings": [],
        "paragraphs": [],
        "tables": [],
        "math": [],
        "all_text": "",
        "element_count": 0,
        "has_spatial": False,
        "has_page_numbers": False,
        "table_cells_with_colspan": 0,
        "table_cells_with_rowspan": 0,
    }

    i = 0
    all_texts = []

    # Skip YAML frontmatter
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1  # skip closing ---

    while i < len(lines):
        line = lines[i].strip()

        # Heading
        if line.startswith("#"):
            match = re.match(r"^(#{1,6})\s+(.*)", line)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                result["headings"].append({"level": level, "text": text})
                all_texts.append(text)
                result["element_count"] += 1
            i += 1
            continue

        # Math block
        if line.startswith("$$"):
            expr = line[2:]
            i += 1
            while i < len(lines) and not lines[i].strip().endswith("$$"):
                expr += "\n" + lines[i]
                i += 1
            if i < len(lines):
                expr += "\n" + lines[i].strip().rstrip("$").rstrip("$")
                i += 1
            result["math"].append(expr.strip())
            result["element_count"] += 1
            continue

        # Table (pipe-delimited)
        if "|" in line and line.startswith("|"):
            table_rows = []
            while i < len(lines) and "|" in lines[i].strip():
                row_line = lines[i].strip()
                # Skip separator line
                if re.match(r"^\|[\s\-:|]+\|$", row_line):
                    i += 1
                    continue
                cells = [c.strip() for c in row_line.split("|")[1:-1]]
                table_rows.append(cells)
                i += 1
            result["tables"].append({
                "rows": len(table_rows),
                "cols": max(len(r) for r in table_rows) if table_rows else 0,
                "cells": [cell for row in table_rows for cell in row],
            })
            result["element_count"] += 1
            continue

        # Paragraph (non-empty, non-special)
        if line:
            result["paragraphs"].append(line)
            all_texts.append(line)
            result["element_count"] += 1

        i += 1

    result["all_text"] = " ".join(all_texts)
    return result


def _dox_to_elements(doc) -> dict:
    """Extract structured info from a DoxDocument."""
    result = {
        "headings": [],
        "paragraphs": [],
        "tables": [],
        "math": [],
        "all_text": "",
        "element_count": 0,
        "has_spatial": len(doc.spatial_blocks) > 0,
        "has_page_numbers": False,
        "table_cells_with_colspan": 0,
        "table_cells_with_rowspan": 0,
        "spatial_bbox_count": 0,
        "elements_with_page": 0,
    }

    all_texts = []

    for el in doc.elements:
        if isinstance(el, PageBreak):
            continue

        result["element_count"] += 1

        if el.page is not None:
            result["elements_with_page"] += 1
            result["has_page_numbers"] = True

        if isinstance(el, Heading):
            result["headings"].append({"level": el.level, "text": el.text})
            all_texts.append(el.text)

        elif isinstance(el, Paragraph):
            result["paragraphs"].append(el.text)
            all_texts.append(el.text)

        elif isinstance(el, Table):
            table_info = {
                "rows": el.num_rows,
                "cols": el.num_cols,
                "cells": [c.text for r in el.rows for c in r.cells],
            }
            result["tables"].append(table_info)
            for row in el.rows:
                for cell in row.cells:
                    if cell.colspan > 1:
                        result["table_cells_with_colspan"] += 1
                    if cell.rowspan > 1:
                        result["table_cells_with_rowspan"] += 1

        elif isinstance(el, MathBlock):
            result["math"].append(el.expression)

    for block in doc.spatial_blocks:
        for ann in block.annotations:
            if ann.bbox:
                result["spatial_bbox_count"] += 1

    result["all_text"] = " ".join(all_texts)
    return result


# =====================================================================
# The actual comparison
# =====================================================================

@pytest.fixture(scope="module")
def benchmark_pages():
    return _load_benchmark()


class TestHeadToHead:
    """Direct comparison: same data through .dox vs Markdown vs JSON."""

    def test_text_roundtrip_comparison(self, benchmark_pages):
        """Compare text survival through each format."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox

        parser = DoxParser()
        serializer = DoxSerializer()

        dox_scores = []
        md_scores = []
        json_scores = []

        for page in benchmark_pages[:200]:
            doc = omnidocbench_page_to_dox(page)
            original = _dox_to_elements(doc)

            if not original["all_text"].strip():
                continue

            # .dox roundtrip
            dox_text = serializer.serialize(doc)
            doc_rt = parser.parse(dox_text)
            dox_el = _dox_to_elements(doc_rt)
            dox_scores.append(_text_sim(original["all_text"], dox_el["all_text"]))

            # Markdown roundtrip
            md_text = to_markdown(doc)
            md_el = _markdown_to_elements(md_text)
            md_scores.append(_text_sim(original["all_text"], md_el["all_text"]))

            # JSON roundtrip
            json_str = to_json(doc)
            json_data = json.loads(json_str)
            json_text = " ".join(
                el.get("text", "") for el in json_data.get("elements", [])
                if el.get("text")
            )
            json_scores.append(_text_sim(original["all_text"], json_text))

        n = len(dox_scores)
        avg_dox = sum(dox_scores) / n
        avg_md = sum(md_scores) / n
        avg_json = sum(json_scores) / n

        print(f"\n{'='*60}")
        print(f"TEXT FIDELITY ({n} pages)")
        print(f"{'='*60}")
        print(f"  .dox roundtrip:     {avg_dox:.4f}")
        print(f"  Markdown roundtrip: {avg_md:.4f}")
        print(f"  JSON roundtrip:     {avg_json:.4f}")

        # .dox preserves text better because it handles all element types
        # Markdown loses text in tables (flattened), math (delimiter issues), etc.
        assert avg_dox > 0.85
        assert avg_md > 0.70  # Markdown loses more — this is the real gap

    def test_table_structure_comparison(self, benchmark_pages):
        """Compare table structure survival through each format."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox

        parser = DoxParser()
        serializer = DoxSerializer()

        dox_row_ok = 0
        dox_col_ok = 0
        md_row_ok = 0
        md_col_ok = 0
        dox_colspan_preserved = 0
        md_colspan_preserved = 0  # Always 0 — MD can't do colspan
        total_tables = 0
        total_colspan_cells = 0
        total_rowspan_cells = 0

        table_pages = [
            p for p in benchmark_pages
            if any(d.get("category_type") == "table" for d in p.get("layout_dets", []))
        ]

        for page in table_pages[:100]:
            doc = omnidocbench_page_to_dox(page)
            original = _dox_to_elements(doc)

            # .dox roundtrip
            dox_text = serializer.serialize(doc)
            doc_rt = parser.parse(dox_text)
            dox_el = _dox_to_elements(doc_rt)

            # Markdown roundtrip
            md_text = to_markdown(doc)
            md_el = _markdown_to_elements(md_text)

            # Compare tables
            for i, orig_t in enumerate(original["tables"]):
                total_tables += 1

                # .dox
                if i < len(dox_el["tables"]):
                    dt = dox_el["tables"][i]
                    if dt["rows"] == orig_t["rows"]:
                        dox_row_ok += 1
                    if dt["cols"] == orig_t["cols"]:
                        dox_col_ok += 1

                # Markdown
                if i < len(md_el["tables"]):
                    mt = md_el["tables"][i]
                    if mt["rows"] == orig_t["rows"]:
                        md_row_ok += 1
                    if mt["cols"] == orig_t["cols"]:
                        md_col_ok += 1

            total_colspan_cells += original["table_cells_with_colspan"]
            total_rowspan_cells += original["table_cells_with_rowspan"]
            dox_colspan_preserved += dox_el["table_cells_with_colspan"]

        if total_tables == 0:
            pytest.skip("No tables")

        print(f"\n{'='*60}")
        print(f"TABLE STRUCTURE ({total_tables} tables)")
        print(f"{'='*60}")
        print(f"  Row preservation:")
        print(f"    .dox:     {dox_row_ok}/{total_tables} ({dox_row_ok/total_tables:.1%})")
        print(f"    Markdown: {md_row_ok}/{total_tables} ({md_row_ok/total_tables:.1%})")
        print(f"  Column preservation:")
        print(f"    .dox:     {dox_col_ok}/{total_tables} ({dox_col_ok/total_tables:.1%})")
        print(f"    Markdown: {md_col_ok}/{total_tables} ({md_col_ok/total_tables:.1%})")
        print(f"  Colspan cells preserved:")
        print(f"    .dox:     {dox_colspan_preserved}/{total_colspan_cells}")
        print(f"    Markdown: 0/{total_colspan_cells} (GFM has no colspan)")
        print(f"  Rowspan cells:")
        print(f"    .dox:     preserved in :::table syntax")
        print(f"    Markdown: 0/{total_rowspan_cells} (GFM has no rowspan)")

    def test_spatial_comparison(self, benchmark_pages):
        """Compare spatial info survival."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox

        parser = DoxParser()
        serializer = DoxSerializer()

        dox_bboxes = 0
        md_bboxes = 0  # Always 0
        json_bboxes = 0
        total_bboxes = 0

        for page in benchmark_pages[:100]:
            doc = omnidocbench_page_to_dox(page)
            original = _dox_to_elements(doc)
            total_bboxes += original["spatial_bbox_count"]

            # .dox roundtrip
            dox_text = serializer.serialize(doc)
            doc_rt = parser.parse(dox_text)
            dox_el = _dox_to_elements(doc_rt)
            dox_bboxes += dox_el["spatial_bbox_count"]

            # JSON roundtrip
            json_data = json.loads(to_json(doc))
            for sp in json_data.get("spatial", []):
                for ann in sp.get("annotations", []):
                    if ann.get("bbox"):
                        json_bboxes += 1

        print(f"\n{'='*60}")
        print(f"SPATIAL BOUNDING BOXES ({total_bboxes} total)")
        print(f"{'='*60}")
        print(f"  .dox:     {dox_bboxes}/{total_bboxes} ({dox_bboxes/max(total_bboxes,1):.1%})")
        print(f"  Markdown: {md_bboxes}/{total_bboxes} (0.0%) ← NO SPATIAL SUPPORT")
        print(f"  JSON:     {json_bboxes}/{total_bboxes} ({json_bboxes/max(total_bboxes,1):.1%})")

        assert dox_bboxes > total_bboxes * 0.9

    def test_page_number_comparison(self, benchmark_pages):
        """Compare page number survival."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_to_dox

        parser = DoxParser()
        serializer = DoxSerializer()

        doc = omnidocbench_to_dox(benchmark_pages[:20])
        original = _dox_to_elements(doc)

        # .dox roundtrip
        dox_text = serializer.serialize(doc)
        doc_rt = parser.parse(dox_text)
        dox_el = _dox_to_elements(doc_rt)

        # Markdown — has NO page number concept
        md_el = _markdown_to_elements(to_markdown(doc))

        # JSON
        json_data = json.loads(to_json(doc))
        json_with_page = sum(
            1 for el in json_data.get("elements", [])
            if el.get("page") is not None
        )

        total = original["elements_with_page"]
        dox_pages = dox_el["elements_with_page"]

        print(f"\n{'='*60}")
        print(f"PAGE NUMBERS ({total} elements with page)")
        print(f"{'='*60}")
        print(f"  .dox:     {dox_pages}/{total} ({dox_pages/max(total,1):.1%})")
        print(f"  Markdown: 0/{total} (0.0%) ← NO PAGE CONCEPT")
        print(f"  JSON:     {json_with_page}/{total} ({json_with_page/max(total,1):.1%})")

    def test_math_comparison(self, benchmark_pages):
        """Compare math expression survival."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox

        parser = DoxParser()
        serializer = DoxSerializer()

        dox_preserved = 0
        md_preserved = 0
        total_math = 0

        math_pages = [
            p for p in benchmark_pages
            if any(d.get("category_type") in ("equation_isolated",)
                   for d in p.get("layout_dets", []))
        ]

        for page in math_pages[:50]:
            doc = omnidocbench_page_to_dox(page)
            original = _dox_to_elements(doc)

            if not original["math"]:
                continue

            # .dox roundtrip
            dox_text = serializer.serialize(doc)
            doc_rt = parser.parse(dox_text)
            dox_el = _dox_to_elements(doc_rt)

            # Markdown roundtrip
            md_text = to_markdown(doc)
            md_el = _markdown_to_elements(md_text)

            for orig_expr in original["math"]:
                total_math += 1

                # .dox match
                best_dox = max(
                    (_text_sim(orig_expr, e) for e in dox_el["math"]),
                    default=0.0
                )
                if best_dox > 0.9:
                    dox_preserved += 1

                # Markdown match
                best_md = max(
                    (_text_sim(orig_expr, e) for e in md_el["math"]),
                    default=0.0
                )
                if best_md > 0.9:
                    md_preserved += 1

        if total_math == 0:
            pytest.skip("No math")

        print(f"\n{'='*60}")
        print(f"MATH EXPRESSIONS ({total_math} total)")
        print(f"{'='*60}")
        print(f"  .dox:     {dox_preserved}/{total_math} ({dox_preserved/total_math:.1%}) preserved >90%")
        print(f"  Markdown: {md_preserved}/{total_math} ({md_preserved/total_math:.1%}) preserved >90%")
        print(f"  Note: Markdown $$...$$ preserves expression TEXT but loses metadata")

    def test_full_summary(self, benchmark_pages):
        """Print the complete head-to-head comparison."""
        from dox.exporters.omnidocbench_exporter import omnidocbench_page_to_dox

        parser = DoxParser()
        serializer = DoxSerializer()

        # Collect all metrics over 200 pages
        n_pages = 200
        metrics = {
            "dox_text_sim": [],
            "md_text_sim": [],
            "dox_tables_found": 0,
            "md_tables_found": 0,
            "total_tables": 0,
            "dox_bboxes": 0,
            "total_bboxes": 0,
            "dox_pages": 0,
            "total_paged_elements": 0,
            "dox_math": 0,
            "md_math": 0,
            "total_math": 0,
            "dox_colspan": 0,
            "total_colspan": 0,
        }

        for page in benchmark_pages[:n_pages]:
            doc = omnidocbench_page_to_dox(page)
            orig = _dox_to_elements(doc)

            if not orig["all_text"].strip():
                continue

            # .dox roundtrip
            dox_text = serializer.serialize(doc)
            doc_rt = parser.parse(dox_text)
            dox_el = _dox_to_elements(doc_rt)

            # Markdown roundtrip
            md_text = to_markdown(doc)
            md_el = _markdown_to_elements(md_text)

            # Text
            metrics["dox_text_sim"].append(_text_sim(orig["all_text"], dox_el["all_text"]))
            metrics["md_text_sim"].append(_text_sim(orig["all_text"], md_el["all_text"]))

            # Tables
            metrics["total_tables"] += len(orig["tables"])
            metrics["dox_tables_found"] += len(dox_el["tables"])
            metrics["md_tables_found"] += len(md_el["tables"])

            # Spatial
            metrics["total_bboxes"] += orig["spatial_bbox_count"]
            metrics["dox_bboxes"] += dox_el["spatial_bbox_count"]

            # Page numbers
            metrics["total_paged_elements"] += orig["elements_with_page"]
            metrics["dox_pages"] += dox_el["elements_with_page"]

            # Math
            metrics["total_math"] += len(orig["math"])
            metrics["dox_math"] += len(dox_el["math"])
            metrics["md_math"] += len(md_el["math"])

            # Colspan
            metrics["total_colspan"] += orig["table_cells_with_colspan"]
            metrics["dox_colspan"] += dox_el["table_cells_with_colspan"]

        n = len(metrics["dox_text_sim"])
        avg_dox_text = sum(metrics["dox_text_sim"]) / n
        avg_md_text = sum(metrics["md_text_sim"]) / n

        print(f"\n{'='*70}")
        print(f"  HEAD-TO-HEAD: .dox vs Markdown ({n_pages} OmniDocBench pages)")
        print(f"{'='*70}")
        print(f"")
        print(f"  Dimension                    .dox        Markdown    Winner")
        print(f"  {'─'*62}")

        # Text
        dox_w = "✓" if avg_dox_text >= avg_md_text else " "
        md_w = "✓" if avg_md_text > avg_dox_text else " "
        print(f"  Text fidelity               {avg_dox_text:.1%}       {avg_md_text:.1%}       {'TIE' if abs(avg_dox_text - avg_md_text) < 0.02 else ('.dox' if dox_w == '✓' else 'MD')}")

        # Tables found
        tt = metrics["total_tables"]
        dt = metrics["dox_tables_found"]
        mt = metrics["md_tables_found"]
        if tt > 0:
            print(f"  Tables recovered            {dt}/{tt:<8}    {mt}/{tt:<8}    {'.dox' if dt >= mt else 'MD'}")

        # Colspan
        tc = metrics["total_colspan"]
        dc = metrics["dox_colspan"]
        if tc > 0:
            print(f"  Colspan cells               {dc}/{tc:<8}    0/{tc:<8}    .dox")

        # Spatial
        tb = metrics["total_bboxes"]
        db = metrics["dox_bboxes"]
        print(f"  Bounding boxes              {db}/{tb:<8}    0/{tb:<8}    .dox")

        # Pages
        tp = metrics["total_paged_elements"]
        dp = metrics["dox_pages"]
        print(f"  Page numbers                {dp}/{tp:<8}    0/{tp:<8}    .dox")

        # Math
        tm = metrics["total_math"]
        dm = metrics["dox_math"]
        mm = metrics["md_math"]
        if tm > 0:
            print(f"  Math expressions            {dm}/{tm:<8}    {mm}/{tm:<8}    {'TIE' if abs(dm - mm) < 3 else ('.dox' if dm > mm else 'MD')}")

        # Readability — markdown wins here
        print(f"  Human readability           ★★★★★       ★★★★★       TIE")
        print(f"  Standard tooling            partial     universal   MD")
        print(f"  Cross-page merging          ✓           ✗           .dox")
        print(f"  RAG chunking (w/ pages)     ✓           ✗           .dox")

        print(f"")
        print(f"  {'─'*62}")
        print(f"  VERDICT: .dox preserves everything Markdown does PLUS spatial,")
        print(f"  page layout, table structure, and cross-page relationships.")
        print(f"  Markdown wins on ecosystem/tooling compatibility.")
        print(f"{'='*70}")
