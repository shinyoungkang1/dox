"""
dox-render — Render .dox documents to PDF and HTML.

Uses WeasyPrint (CSS Paged Media) as the PDF backend. Falls back to HTML-only
if WeasyPrint is not installed.

Usage:
    from dox.renderer import DoxRenderer

    renderer = DoxRenderer()
    renderer.to_pdf(doc, "output.pdf")
    renderer.to_html_file(doc, "output.html")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dox.converters.to_html import to_html
from dox.models.document import DoxDocument


# Enhanced CSS for PDF rendering
_PDF_CSS = """
@page {
    size: A4;
    margin: 2.5cm 2cm;
    @top-center {
        content: string(doc-title);
        font-size: 9pt;
        color: #888;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #888;
    }
}

@page :first {
    @top-center { content: none; }
}

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
    max-width: none;
    margin: 0;
    padding: 0;
}

h1 {
    string-set: doc-title content();
    font-size: 22pt;
    font-weight: 700;
    margin-top: 0;
    margin-bottom: 12pt;
    color: #111;
    page-break-after: avoid;
}

h2 {
    font-size: 16pt;
    font-weight: 600;
    margin-top: 18pt;
    margin-bottom: 8pt;
    color: #222;
    page-break-after: avoid;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4pt;
}

h3 {
    font-size: 13pt;
    font-weight: 600;
    margin-top: 14pt;
    margin-bottom: 6pt;
    color: #333;
    page-break-after: avoid;
}

h4, h5, h6 {
    font-size: 11pt;
    font-weight: 600;
    margin-top: 10pt;
    margin-bottom: 4pt;
    page-break-after: avoid;
}

p {
    margin: 0 0 8pt 0;
    text-align: justify;
    orphans: 3;
    widows: 3;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 10pt 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

caption {
    font-style: italic;
    font-size: 9pt;
    color: #555;
    text-align: left;
    margin-bottom: 4pt;
    caption-side: top;
}

th {
    background: #f0f0f0;
    font-weight: 600;
    text-align: left;
    padding: 5pt 6pt;
    border: 0.5pt solid #ccc;
}

td {
    padding: 4pt 6pt;
    border: 0.5pt solid #ddd;
    vertical-align: top;
}

tr:nth-child(even) td {
    background: #fafafa;
}

pre {
    background: #f5f5f5;
    border: 0.5pt solid #ddd;
    border-radius: 3pt;
    padding: 8pt;
    font-family: 'SF Mono', Menlo, Consolas, monospace;
    font-size: 9pt;
    line-height: 1.4;
    overflow-x: auto;
    page-break-inside: avoid;
    white-space: pre-wrap;
    word-wrap: break-word;
}

code {
    font-family: 'SF Mono', Menlo, Consolas, monospace;
    font-size: 9pt;
    background: #f0f0f0;
    padding: 1pt 3pt;
    border-radius: 2pt;
}

pre code {
    background: none;
    padding: 0;
}

ul, ol {
    margin: 4pt 0 8pt 0;
    padding-left: 20pt;
}

li {
    margin-bottom: 3pt;
}

.math-block, .math-inline {
    font-family: 'Times New Roman', serif;
    font-style: italic;
}

.math-block {
    display: block;
    text-align: center;
    margin: 8pt 0;
    font-size: 11pt;
}

.dox-chart {
    background: #f0f4ff;
    border: 0.5pt dashed #4a90d9;
    padding: 12pt;
    border-radius: 3pt;
    text-align: center;
    color: #666;
    font-style: italic;
    margin: 8pt 0;
}

.dox-annotation {
    background: #fff3cd;
    padding: 1pt 3pt;
    border-radius: 2pt;
    font-style: italic;
}

mark.dox-annotation {
    background: #fff3cd;
}

figure {
    margin: 10pt 0;
    text-align: center;
    page-break-inside: avoid;
}

figcaption {
    font-style: italic;
    font-size: 9pt;
    color: #666;
    margin-top: 4pt;
}

.footnote {
    font-size: 8.5pt;
    color: #555;
    border-top: 0.5pt solid #ddd;
    padding-top: 4pt;
    margin-top: 10pt;
}

strong {
    font-weight: 700;
}

a {
    color: #2563eb;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

.dox-ref {
    color: #2563eb;
    font-style: italic;
}

blockquote {
    border-left: 3pt solid #ddd;
    margin: 8pt 0;
    padding: 4pt 0 4pt 12pt;
    color: #555;
}
"""


class DoxRenderer:
    """
    Render .dox documents to PDF and HTML files.

    Usage:
        renderer = DoxRenderer()
        renderer.to_pdf(doc, "output.pdf")
        renderer.to_html_file(doc, "output.html", css=custom_css)
    """

    def __init__(self, css: str | None = None):
        self.css = css or _PDF_CSS

    def to_html_string(self, doc: DoxDocument) -> str:
        """Render to HTML string with PDF-quality styling."""
        raw_html = to_html(doc, standalone=False)
        title = ""
        for el in doc.elements:
            from dox.models.elements import Heading
            if isinstance(el, Heading) and el.level == 1:
                title = el.text
                break

        return f"""<!DOCTYPE html>
<html lang="{doc.frontmatter.lang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
{self.css}
</style>
</head>
<body>
{raw_html}
</body>
</html>"""

    def to_html_file(self, doc: DoxDocument, output_path: str | Path) -> Path:
        """Render to an HTML file."""
        path = Path(output_path)
        html = self.to_html_string(doc)
        path.write_text(html, encoding="utf-8")
        return path

    def to_pdf(self, doc: DoxDocument, output_path: str | Path) -> Path:
        """
        Render to PDF using WeasyPrint.

        Raises:
            ImportError: If WeasyPrint is not installed.
        """
        try:
            from weasyprint import HTML  # type: ignore
        except ImportError:
            raise ImportError(
                "WeasyPrint is required for PDF rendering. "
                "Install with: pip install 'dox-format[render]'"
            )

        path = Path(output_path)
        html_string = self.to_html_string(doc)
        HTML(string=html_string).write_pdf(str(path))
        return path

    def to_pdf_bytes(self, doc: DoxDocument) -> bytes:
        """Render to PDF and return as bytes."""
        try:
            from weasyprint import HTML  # type: ignore
        except ImportError:
            raise ImportError(
                "WeasyPrint is required for PDF rendering. "
                "Install with: pip install 'dox-format[render]'"
            )

        html_string = self.to_html_string(doc)
        return HTML(string=html_string).write_pdf()
