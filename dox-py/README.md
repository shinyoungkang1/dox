<p align="center">
  <img src="https://img.shields.io/badge/format-.dox-0969da?style=for-the-badge&labelColor=1a1a2e" alt="format: .dox" />
  <img src="https://img.shields.io/badge/version-1.0.0-10b981?style=for-the-badge&labelColor=1a1a2e" alt="version: 1.0.0" />
  <img src="https://img.shields.io/badge/python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white&labelColor=1a1a2e" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/tests-705_passed-10b981?style=for-the-badge&labelColor=1a1a2e" alt="705 tests passed" />
  <img src="https://img.shields.io/badge/license-MIT-f59e0b?style=for-the-badge&labelColor=1a1a2e" alt="MIT License" />
</p>

<h1 align="center">
  <br>
  <code>.dox</code>
  <br>
  <sub>Document Open eXchange Format</sub>
</h1>

<p align="center">
  <strong>As readable as Markdown. As precise as PDF. As structured as JSON. As lightweight as plain text.</strong>
</p>

<p align="center">
  A 3-layer document format designed for the age of AI &mdash; where documents need to be<br>
  readable by humans, parseable by machines, and round-trippable between formats.
</p>

---

## The Problem

Every document format makes you choose:

| Format | Human-Readable | Layout Info | Structured Metadata | Token-Efficient |
|--------|:-:|:-:|:-:|:-:|
| **Markdown** | Yes | No | No | Yes |
| **PDF** | No | Yes | No | No |
| **DOCX** | No | Partial | No | No |
| **HTML** | Partial | CSS-based | No | No |
| **JSON** | No | Optional | Yes | No |
| **LaTeX** | Partial | Yes | No | No |

**`.dox` gives you all four.** One file. Three layers. Zero compromises.

---

## The Three Layers

```
Layer 0  CONTENT      Enhanced Markdown you can read in any text editor
Layer 1  SPATIAL      Bounding boxes that pin every element to a page grid
Layer 2  METADATA     Extraction provenance, confidence scores, version history
```

Layers 1 and 2 are **completely optional**. Strip them and you have a clean Markdown file. Keep them and you have pixel-perfect spatial fidelity with full provenance tracking.

```
---dox
version: "1.0"
source: annual-report-2025.pdf
pages: 42
lang: en
---

# Q3 Financial Results

Revenue increased by **15%** compared to last year, driven by
strong performance in the APAC region.

## Regional Sales

||| table id="t1" caption="Table 1: Regional Sales ($M)"
| Region   | Q3 2024 | Q3 2025 | Delta % |
|----------|---------|---------|---------|
| Americas | 105     | 120     | +14.3   |
| APAC     | 62      | 80      | +29.0   |
|||

$$E = mc^2$$ {math: latex}

::chart type="bar" data-ref="t1" x="Region" y="Q3 2025"::

---spatial page=1 grid=1000x1000
# Q3 Financial Results          @[45,62,520,95]
Revenue increased by **15%**... @[45,120,890,145]
||| table id="t1"               @[45,180,890,380]
---/spatial

---meta
extracted_by: docling-2.72.0 + granite-docling-258m
confidence:
  overall: 0.96
  elements:
    t1: 0.94
---/meta
```

**That's the whole format.** Open it in Vim. Read it in a browser. Feed it to an LLM. Convert it to DOCX. Every element carries its position on the page and its confidence score from extraction.

---

## Why `.dox`

**For RAG pipelines:** Built-in semantic chunker that never splits mid-table or mid-code-block. Heading hierarchy preserved as chunk metadata. Native LangChain and LlamaIndex adapters included.

**For document intelligence:** Every element carries bounding boxes and confidence scores. Flag low-confidence extractions for human review. Track which OCR engine produced what.

**For round-trip conversion:** Parse a PDF into `.dox`, edit it as Markdown, export back to DOCX/PDF/HTML. The spatial layer means you can reconstruct layout without guessing.

**For LLMs:** Token-efficient by design. A `.dox` file is 3-5x smaller than equivalent HTML or DOCX XML. The Markdown base layer is what LLMs already understand best.

---

## Quick Start

```bash
pip install dox-format
```

```python
from dox import DoxParser, DoxSerializer, DoxValidator

# Parse any .dox file
doc = DoxParser().parse_file("report.dox")

# Inspect it
print(doc.frontmatter.source)        # "annual-report-2025.pdf"
print(len(doc.elements))             # 14
print(doc.tables()[0].num_rows)      # 4

# Validate it
result = DoxValidator().validate(doc)
print(result.is_valid)               # True

# Serialize it back (round-trip)
text = DoxSerializer().serialize(doc)
```

### Convert to Any Format

```python
from dox.converters import to_html, to_json, to_markdown

html = to_html(doc, standalone=True)   # Full HTML page with styles
json_str = to_json(doc)                # Canonical structured JSON
md = to_markdown(doc)                  # Clean Markdown

# Binary formats (optional dependencies)
from dox.converters.to_docx import to_docx
from dox.converters.to_pdf import to_pdf

to_docx(doc, "report.docx")           # pip install 'dox-format[docx]'
to_pdf(doc, "report.pdf")             # pip install 'dox-format[pdf]'
```

`to_json()` is intended to be the canonical machine-readable representation of a `DoxDocument`, not a lightweight summary export.

### Chunk for RAG

```python
from dox.chunker import chunk_document

chunks = chunk_document(doc, strategy="semantic", max_tokens=512)
for chunk in chunks:
    print(chunk.text[:80])
    print(chunk.metadata["heading_path"])   # "Q3 Financial Results > Regional Sales"
    print(chunk.metadata["min_confidence"]) # 0.94

# One-liner to LangChain
from dox.chunker import to_langchain_documents
lc_docs = to_langchain_documents(chunks)

# Or LlamaIndex
from dox.chunker import to_llama_index_nodes
nodes = to_llama_index_nodes(chunks)
```

### Diff Two Documents

```python
from dox.diff import DoxDiff

result = DoxDiff().diff(doc_v1, doc_v2)
print(result.summary())  # "3 added, 1 removed, 2 modified"
for change in result.modified:
    print(change)         # [~] (Paragraph) Paragraph text changed
```

### CLI

```bash
dox parse report.dox                      # Summary with element breakdown
dox validate report.dox                   # Lint check (exit 1 on errors)
dox convert report.dox -f html            # Export to HTML/JSON/Markdown
dox convert report.dox -f json -o out.json
dox diff v1.dox v2.dox                    # Semantic diff
dox chunk report.dox -s semantic -t 512   # Chunk for RAG
dox strip report.dox --layer spatial      # Remove Layer 1/2
dox info report.dox                       # Document outline + metadata
dox render report.dox -f pdf              # Styled PDF output
```

---

## 16 Element Types

`.dox` supports every element you encounter in real-world documents:

| Element | Syntax | Use Case |
|---------|--------|----------|
| **Heading** | `# Text` through `###### Text` | Document structure |
| **Paragraph** | Plain text with **bold**, *italic*, `code`, [links] | Body content |
| **Table** | `\|\|\| table ... \|\|\|` with pipe rows | Data tables with colspan/rowspan |
| **CodeBlock** | ` ```lang ... ``` ` | Source code with syntax hints |
| **MathBlock** | `$$expression$$` | LaTeX math (inline + display) |
| **ListBlock** | `- item` / `1. item` / `- [x] item` | Lists, nested lists, task lists |
| **Blockquote** | `> text` | Quoted content |
| **HorizontalRule** | `---` / `***` / `___` | Thematic breaks |
| **Figure** | `![caption](source)` | Images with captions |
| **Footnote** | `[^1]: text` | Reference notes |
| **FormField** | `::form field="name" type="text"::` | Interactive fields |
| **Chart** | `::chart type="bar" data-ref="t1"::` | Declarative visualizations |
| **Annotation** | `::annotation type="handwriting"::` | OCR annotations |
| **CrossRef** | `[[ref:table:t1]]` | Internal references |
| **PageBreak** | `---page-break from=1 to=2---` | Page boundaries |
| **Table (cross-page)** | `continuation_of="t1"` | Tables spanning pages |

---

## Where `.dox` Fits

`.dox` is **not** a PDF library. It's a document interchange format that sits above extraction tools and below your application layer:

```
                        YOUR APPLICATION
                    RAG  |  Search  |  Editor
                         |         |
                    ┌────┴─────────┴────┐
                    │    .dox format     │   <-- this project
                    │  (read / write /   │
                    │   convert / chunk) │
                    └────┬─────────┬────┘
                         |         |
                    EXTRACTION BACKENDS
               PyMuPDF  |  Docling  |  Custom
                         |         |
                      SOURCE FILES
                  PDF  |  DOCX  |  Scans
```

### Comparison with Alternatives

| | `.dox` | Pandoc AST | Docling DoclingDocument | Unstructured Elements |
|---|---|---|---|---|
| **Standalone file format** | Yes (.dox files) | No (internal) | No (Python objects) | No (Python objects) |
| **Human-readable** | Yes (Markdown-based) | No (JSON AST) | No (API only) | No (API only) |
| **Spatial layout data** | Yes (Layer 1 bboxes) | No | Yes (DocItem) | Partial (coordinates) |
| **Confidence scores** | Yes (Layer 2) | No | Yes (per element) | Yes (per element) |
| **Round-trip fidelity** | Yes (parse / serialize) | Yes | No (one-way) | No (one-way) |
| **Built-in RAG chunker** | Yes (5 strategies) | No | No | Yes (1 strategy) |
| **Document diffing** | Yes (dox-diff) | No | No | No |
| **Format conversion** | HTML, JSON, MD, DOCX, PDF | 40+ formats | Limited | HTML, JSON |
| **CLI toolkit** | Yes (8 commands) | Yes | No | No |
| **Linter/validator** | Yes (dox-lint) | No | No | No |

### What `.dox` is Not

**Not a competitor to PyMuPDF.** PyMuPDF is a PDF extraction library. `.dox` actually *uses* PyMuPDF as one of its extraction backends (`pymupdf_exporter.py`). They're complementary.

**Not a competitor to Markdown.** `.dox` Layer 0 *is* Markdown — enhanced with tables, math, forms, and charts. Strip the optional layers and it's a valid `.md` file.

**Not trying to replace Pandoc.** Pandoc converts between 40+ formats with unmatched breadth. `.dox` is deeper, not wider — it adds spatial awareness and metadata that Pandoc doesn't track.

---

## Extraction Backends

Convert existing documents into `.dox` format:

```python
# From PDF via PyMuPDF
from dox.exporters.pymupdf_exporter import PymupdfExporter
doc = PymupdfExporter().export("report.pdf")

# From PDF/DOCX via IBM Docling
from dox.exporters.docling_exporter import DoclingExporter
doc = DoclingExporter().export("report.pdf")
```

---

## Architecture

```
src/dox/
├── models/
│   ├── elements.py        # 16 element dataclasses
│   ├── document.py        # DoxDocument (frontmatter + elements + spatial + meta)
│   ├── metadata.py        # Confidence, Provenance, VersionEntry
│   └── spatial.py         # SpatialBlock, SpatialAnnotation, BoundingBox
├── parsers/
│   └── parser.py          # .dox --> DoxDocument (all 3 layers)
├── serializer.py          # DoxDocument --> .dox (round-trip)
├── validator.py           # dox-lint (frontmatter, elements, spatial, metadata, xrefs)
├── diff.py                # dox-diff (content, structural, table, spatial, metadata)
├── chunker.py             # RAG chunker (5 strategies + LangChain/LlamaIndex adapters)
├── converters/
│   ├── to_html.py         # --> HTML with XSS prevention
│   ├── to_json.py         # --> structured JSON
│   ├── to_markdown.py     # --> clean Markdown
│   ├── to_docx.py         # --> Word (python-docx) with merged cells
│   └── to_pdf.py          # --> PDF (ReportLab) with merged cells
├── exporters/
│   ├── pymupdf_exporter.py    # PDF --> .dox via PyMuPDF
│   ├── docling_exporter.py    # PDF/DOCX --> .dox via IBM Docling
│   └── omnidocbench_exporter.py
├── renderer.py            # Styled HTML/PDF output (WeasyPrint)
└── cli.py                 # 8-command CLI toolkit
```

---

## Security

Built for production from day one:

- **XSS prevention** — URL scheme allowlisting on all links (`http`, `https`, `mailto`, `#` only). No `javascript:` URIs ever reach the output.
- **HTML entity escaping** — All user content escaped in attributes and text nodes.
- **Safe type conversion** — Integer/float parsing with fallbacks, never crashes on malformed input.
- **YAML error handling** — Malformed metadata blocks produce warnings, not exceptions.
- **Input validation** — Dataclass `__post_init__` validators on colspan, rowspan, footnote numbers, list indices.

---

## Test Suite

705 tests across 9 test modules, running in ~25 seconds:

| Module | Tests | What It Covers |
|--------|------:|----------------|
| Core tests | 322 | Parser, serializer, models, converters, round-trip fidelity |
| Stress tests | 66 | 1000+ element documents, deeply nested structures, edge cases |
| Error handling | 51 | Malformed input, missing fields, invalid values, graceful degradation |
| Real-world docs | 31 | Financial reports, invoices, academic papers, contracts |
| CLI tests | 107 | All 8 commands (parse, validate, convert, info, strip, diff, chunk, render) |
| Docling exporter | 58 | Mocked Docling API integration |
| Performance + fuzz | 35 | Benchmarks + robustness against random/malformed input |
| v1 features | 35 | Blockquotes, horizontal rules, task lists, TOC, statistics |

---

## Installation

```bash
# Core (parsing, validation, HTML/JSON/Markdown conversion)
pip install dox-format

# With Word export
pip install 'dox-format[docx]'

# With PDF export
pip install 'dox-format[pdf]'

# Everything
pip install 'dox-format[all]'

# Development
pip install 'dox-format[dev]'
```

Requires **Python 3.10+**. Core dependencies: `pyyaml`, `markdown-it-py`, `rich`, `click`.

---

## The Moat

1. **Three layers in one file.** No other format combines human-readable content, pixel-level spatial layout, and extraction metadata in a single text file. This is the core innovation.

2. **Markdown-native.** The base layer is enhanced Markdown. Every LLM already speaks it. Every developer can read it. Every text editor can open it. The adoption barrier is nearly zero.

3. **RAG-first design.** The built-in chunker is structure-aware — it never splits a table or code block across chunks. Heading paths flow into chunk metadata. Confidence scores let you filter low-quality extractions before they hit your vector store.

4. **Round-trip fidelity.** Parse a `.dox` file, modify it programmatically, serialize it back — nothing is lost. This makes `.dox` suitable as a working format, not just an export target.

5. **Extraction-agnostic.** PyMuPDF, Docling, or your own custom pipeline — `.dox` doesn't care how content was extracted. It's the neutral interchange layer.

6. **Production-hardened.** 705 tests. XSS prevention. Input validation. Graceful error handling. Fuzz-tested. This isn't a proof of concept.

---

## Contributing

```bash
git clone https://github.com/deepsearch-ai/dox.git
cd dox/dox-py
pip install -e '.[dev]'
pytest                     # Run all 705 tests
ruff check src/            # Lint
mypy src/                  # Type check
```

---

## License

MIT — use it however you want.

---

<p align="center">
  <strong><code>.dox</code></strong> — because documents deserve better than XML soup.
</p>
