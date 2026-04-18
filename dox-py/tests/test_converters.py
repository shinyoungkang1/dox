"""Tests for .dox converters (Markdown, HTML, JSON)."""

import base64
import json
import zipfile
from io import BytesIO

import pytest

from dox.converters import to_docx_bytes, to_html, to_json, to_markdown, to_pdf_bytes
from dox.converters.to_json import to_dict
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import Figure
from dox.parsers.parser import DoxParser


SAMPLE = """---dox
version: "1.0"
source: test.pdf
---

# Test Document

A simple paragraph with **bold** text.

## Data

||| table id="t1" caption="Sales"
| Name  | Value |
|-------|-------|
| Alice | 100   |
| Bob   | 200   |
|||

```python
x = 42
```

- First item
- Second item

::form field="confirm" type="checkbox" value="true"::
"""


@pytest.fixture
def doc():
    return DoxParser().parse(SAMPLE)


class TestMarkdownConverter:
    def test_headings(self, doc):
        md = to_markdown(doc)
        assert "# Test Document" in md
        assert "## Data" in md

    def test_paragraph(self, doc):
        md = to_markdown(doc)
        assert "bold" in md

    def test_table(self, doc):
        md = to_markdown(doc)
        assert "Alice" in md
        assert "Bob" in md

    def test_code_block(self, doc):
        md = to_markdown(doc)
        assert "```python" in md
        assert "x = 42" in md

    def test_list(self, doc):
        md = to_markdown(doc)
        assert "- First item" in md

    def test_form_as_checkbox(self, doc):
        md = to_markdown(doc)
        assert "[x]" in md or "confirm" in md


class TestHTMLConverter:
    def test_standalone(self, doc):
        html = to_html(doc, standalone=True)
        assert "<!DOCTYPE html>" in html
        assert "<h1>" in html
        assert "Test Document" in html

    def test_fragment(self, doc):
        html = to_html(doc, standalone=False)
        assert "<!DOCTYPE" not in html
        assert "<h1>" in html

    def test_table_html(self, doc):
        html = to_html(doc)
        assert "<table" in html
        assert "<th>" in html
        assert "Alice" in html

    def test_code_html(self, doc):
        html = to_html(doc)
        assert "<pre>" in html
        assert "language-python" in html

    def test_bold_inline(self, doc):
        html = to_html(doc)
        assert "<strong>bold</strong>" in html

    def test_embedded_figure_uses_data_uri(self):
        doc = DoxDocument(
            frontmatter=Frontmatter(version="1.0"),
            elements=[
                Figure(
                    caption="Embedded",
                    source="",
                    image_data=_tiny_png_b64(),
                )
            ],
        )
        html = to_html(doc, standalone=False)
        assert "data:image/png;base64," in html


class TestBinaryFigureConverters:
    def test_docx_embeds_image_data(self):
        doc = DoxDocument(
            frontmatter=Frontmatter(version="1.0"),
            elements=[Figure(caption="Embedded", source="", image_data=_tiny_png_b64())],
        )
        data = to_docx_bytes(doc)
        with zipfile.ZipFile(BytesIO(data)) as zf:
            media_files = [name for name in zf.namelist() if name.startswith("word/media/")]
        assert media_files

    def test_pdf_accepts_image_data_only_figures(self):
        doc = DoxDocument(
            frontmatter=Frontmatter(version="1.0"),
            elements=[Figure(caption="Embedded", source="", image_data=_tiny_png_b64())],
        )
        data = to_pdf_bytes(doc)
        assert len(data) > 0


class TestJSONConverter:
    def test_valid_json(self, doc):
        j = to_json(doc)
        parsed = json.loads(j)
        assert "dox_version" in parsed
        assert "elements" in parsed

    def test_element_types(self, doc):
        d = to_dict(doc)
        types = {el["type"] for el in d["elements"]}
        assert "heading" in types
        assert "paragraph" in types
        assert "table" in types

    def test_table_structure(self, doc):
        d = to_dict(doc)
        tables = [e for e in d["elements"] if e["type"] == "table"]
        assert len(tables) == 1
        assert tables[0]["table_id"] == "t1"
        assert len(tables[0]["rows"]) >= 3

    def test_frontmatter(self, doc):
        d = to_dict(doc)
        assert d["frontmatter"]["source"] == "test.pdf"


def _tiny_png_b64() -> str:
    return (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk"
        "YGBgAAAABQABDQottAAAAABJRU5ErkJggg=="
    )
