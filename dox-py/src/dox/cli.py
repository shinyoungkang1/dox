"""
dox CLI — parse, validate, convert, and inspect .dox documents.

Usage:
    dox parse report.dox                    # Parse and show summary
    dox validate report.dox                 # Run dox-lint
    dox convert report.dox --format html    # Convert to HTML
    dox convert report.dox --format json    # Convert to JSON
    dox convert report.dox --format md      # Convert to Markdown
    dox info report.dox                     # Show document info
    dox strip report.dox --layer spatial    # Strip Layer 1 or 2
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table as RichTable

from dox.converters import to_html, to_json, to_markdown
from dox.models.elements import Heading, Paragraph, Table
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.validator import DoxValidator

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="dox")
def main():
    """dox — Document Open eXchange Format CLI toolkit."""
    pass


@main.command()
@click.argument("file", type=click.Path(exists=True))
def parse(file: str):
    """Parse a .dox file and display a summary."""
    parser = DoxParser()
    doc = parser.parse_file(file)

    console.print(f"\n[bold]Parsed:[/bold] {file}")
    console.print(f"  Version: {doc.frontmatter.version}")
    console.print(f"  Source: {doc.frontmatter.source or '(none)'}")
    console.print(f"  Language: {doc.frontmatter.lang}")
    console.print(f"  Pages: {doc.frontmatter.pages or '(unknown)'}")
    console.print(f"  Elements: {len(doc.elements)}")

    # Element type breakdown
    type_counts: dict[str, int] = {}
    for el in doc.elements:
        name = type(el).__name__
        type_counts[name] = type_counts.get(name, 0) + 1

    if type_counts:
        t = RichTable(title="Element Breakdown")
        t.add_column("Type")
        t.add_column("Count", justify="right")
        for name, count in sorted(type_counts.items()):
            t.add_row(name, str(count))
        console.print(t)

    console.print(f"  Spatial blocks: {len(doc.spatial_blocks)}")
    console.print(f"  Has metadata: {'yes' if doc.metadata else 'no'}")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--threshold", "-t", default=0.90, help="Confidence threshold for warnings.")
def validate(file: str, threshold: float):
    """Validate a .dox file (dox-lint)."""
    parser = DoxParser()
    doc = parser.parse_file(file)

    validator = DoxValidator(confidence_threshold=threshold)
    result = validator.validate(doc)

    if result.is_valid:
        console.print(f"\n[green]✓[/green] {file} is valid")
    else:
        console.print(f"\n[red]✗[/red] {file} has issues")

    if result.issues:
        for issue in result.issues:
            if issue.severity.value == "error":
                console.print(f"  [red]ERROR[/red] {issue.message}")
            elif issue.severity.value == "warning":
                console.print(f"  [yellow]WARN[/yellow] {issue.message}")
            else:
                console.print(f"  [blue]INFO[/blue] {issue.message}")

    console.print(
        f"\n  {len(result.errors)} error(s), {len(result.warnings)} warning(s), "
        f"{len(result.issues) - len(result.errors) - len(result.warnings)} info(s)"
    )

    if not result.is_valid:
        sys.exit(1)


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(["html", "json", "md", "markdown", "dox"]),
    default="html",
    help="Output format.",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
@click.option("--standalone/--no-standalone", default=True, help="HTML: full page or fragment.")
def convert(file: str, fmt: str, output: str | None, standalone: bool):
    """Convert a .dox file to another format."""
    parser = DoxParser()
    doc = parser.parse_file(file)

    if fmt == "html":
        result = to_html(doc, standalone=standalone)
        ext = ".html"
    elif fmt == "json":
        result = to_json(doc)
        ext = ".json"
    elif fmt in ("md", "markdown"):
        result = to_markdown(doc)
        ext = ".md"
    elif fmt == "dox":
        serializer = DoxSerializer()
        result = serializer.serialize(doc)
        ext = ".dox"
    else:
        console.print(f"[red]Unknown format: {fmt}[/red]")
        sys.exit(1)

    if output:
        Path(output).write_text(result, encoding="utf-8")
        console.print(f"[green]Written to {output}[/green]")
    else:
        out_path = Path(file).with_suffix(ext)
        if out_path == Path(file):
            out_path = Path(file).with_suffix(f".converted{ext}")
        Path(out_path).write_text(result, encoding="utf-8")
        console.print(f"[green]Written to {out_path}[/green]")


@main.command()
@click.argument("file", type=click.Path(exists=True))
def info(file: str):
    """Show detailed document information."""
    parser = DoxParser()
    doc = parser.parse_file(file)

    console.print(f"\n[bold]Document Info:[/bold] {file}\n")

    # Frontmatter
    console.print("[bold]Frontmatter:[/bold]")
    for k, v in doc.frontmatter.to_dict().items():
        console.print(f"  {k}: {v}")

    # Headings (outline)
    headings = doc.headings()
    if headings:
        console.print("\n[bold]Document Outline:[/bold]")
        for h in headings:
            indent = "  " * h.level
            console.print(f"{indent}{'#' * h.level} {h.text}")

    # Tables
    tables = doc.tables()
    if tables:
        console.print(f"\n[bold]Tables:[/bold] {len(tables)}")
        for t in tables:
            tid = t.table_id or "(unnamed)"
            console.print(f"  {tid}: {t.num_rows} rows × {t.num_cols} cols")

    # Metadata
    if doc.metadata:
        console.print("\n[bold]Metadata:[/bold]")
        console.print(f"  Extracted by: {doc.metadata.extracted_by}")
        if doc.metadata.confidence.overall:
            console.print(f"  Overall confidence: {doc.metadata.confidence.overall}")
        flagged = doc.metadata.confidence.flagged_elements()
        if flagged:
            console.print(f"  [yellow]Flagged for review:[/yellow]")
            for eid, score in flagged.items():
                console.print(f"    {eid}: {score}")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--layer", "-l",
    type=click.Choice(["spatial", "metadata", "both"]),
    default="both",
    help="Which layer(s) to strip.",
)
@click.option("--output", "-o", type=click.Path(), default=None)
def strip(file: str, layer: str, output: str | None):
    """Strip optional layers from a .dox file."""
    parser = DoxParser()
    doc = parser.parse_file(file)

    include_spatial = layer not in ("spatial", "both")
    include_metadata = layer not in ("metadata", "both")

    if not include_spatial:
        doc.spatial_blocks = []
    if not include_metadata:
        doc.metadata = None

    serializer = DoxSerializer()
    result = serializer.serialize(
        doc,
        include_spatial=include_spatial,
        include_metadata=include_metadata,
    )

    out_path = output or file
    Path(out_path).write_text(result, encoding="utf-8")
    console.print(f"[green]Stripped {layer} layer(s) → {out_path}[/green]")


@main.command(name="diff")
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
@click.option("--ignore-spatial", is_flag=True, help="Ignore Layer 1 changes.")
@click.option("--ignore-metadata", is_flag=True, help="Ignore Layer 2 changes.")
def diff_cmd(file_a: str, file_b: str, ignore_spatial: bool, ignore_metadata: bool):
    """Compare two .dox files (dox-diff)."""
    from dox.diff import DoxDiff

    parser = DoxParser()
    doc_a = parser.parse_file(file_a)
    doc_b = parser.parse_file(file_b)

    differ = DoxDiff(ignore_spatial=ignore_spatial, ignore_metadata=ignore_metadata)
    result = differ.diff(doc_a, doc_b)

    if not result.has_changes:
        console.print(f"\n[green]No changes[/green] between {file_a} and {file_b}")
    else:
        console.print(f"\n[bold]Changes:[/bold] {result.summary()}")
        for change in result.changes:
            if change.change_type.value == "added":
                console.print(f"  [green]+[/green] {change.description}")
            elif change.change_type.value == "removed":
                console.print(f"  [red]-[/red] {change.description}")
            elif change.change_type.value == "modified":
                console.print(f"  [yellow]~[/yellow] {change.description}")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--strategy", "-s",
    type=click.Choice(["semantic", "by_heading", "by_element", "by_page", "fixed_size"]),
    default="semantic",
)
@click.option("--max-tokens", "-t", default=512, help="Max tokens per chunk.")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def chunk(file: str, strategy: str, max_tokens: int, json_output: bool):
    """Chunk a .dox file for RAG pipelines."""
    import json

    from dox.chunker import chunk_document

    parser = DoxParser()
    doc = parser.parse_file(file)
    chunks = chunk_document(doc, strategy=strategy, max_tokens=max_tokens)

    if json_output:
        output = [
            {"text": c.text, "metadata": c.metadata, "token_estimate": c.token_estimate}
            for c in chunks
        ]
        console.print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    else:
        console.print(f"\n[bold]Chunked {file}[/bold] — {len(chunks)} chunks (strategy: {strategy})")
        for i, c in enumerate(chunks):
            section = c.metadata.get("heading_path", "")
            types = ", ".join(c.metadata.get("element_types", []))
            console.print(
                f"  [{i+1}] ~{c.token_estimate} tokens | {types}"
                + (f" | {section}" if section else "")
            )
            if c.text:
                preview = c.text[:120].replace("\n", " ")
                console.print(f"      {preview}...")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
@click.option("--format", "-f", "fmt", type=click.Choice(["pdf", "html"]), default="html")
def render(file: str, output: str | None, fmt: str):
    """Render a .dox file to PDF or styled HTML (dox-render)."""
    from dox.renderer import DoxRenderer

    parser = DoxParser()
    doc = parser.parse_file(file)
    renderer = DoxRenderer()

    if fmt == "pdf":
        out_path = output or str(Path(file).with_suffix(".pdf"))
        try:
            renderer.to_pdf(doc, out_path)
            console.print(f"[green]Rendered PDF → {out_path}[/green]")
        except ImportError:
            console.print(
                "[red]WeasyPrint required for PDF.[/red] "
                "Install with: pip install 'dox-format[render]'"
            )
            sys.exit(1)
    else:
        out_path = output or str(Path(file).with_suffix(".rendered.html"))
        renderer.to_html_file(doc, out_path)
        console.print(f"[green]Rendered HTML → {out_path}[/green]")


@main.command()
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
def schema(output: str | None):
    """Output the .dox JSON Schema for external validation."""
    from dox.schema import schema_json

    text = schema_json()
    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]Schema written to {output}[/green]")
    else:
        console.print(text)


if __name__ == "__main__":
    main()
