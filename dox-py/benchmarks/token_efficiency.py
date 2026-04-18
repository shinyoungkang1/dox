"""
Token Efficiency Benchmark for .dox format.

Compares .dox file sizes (bytes and estimated tokens) against equivalent
HTML, JSON, and Markdown representations to validate the claim that
.dox is 3-5x smaller than HTML/DOCX XML.

Usage:
    python benchmarks/token_efficiency.py
    python benchmarks/token_efficiency.py --include-spatial
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dox.converters import to_html, to_json, to_markdown
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Annotation,
    Chart,
    CodeBlock,
    Figure,
    Footnote,
    FormField,
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
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer


def estimate_tokens(text: str) -> int:
    """Rough token estimate: words * 1.3 for English text."""
    return int(len(text.split()) * 1.3)


def build_synthetic_document(complexity: str = "medium") -> DoxDocument:
    """Build a synthetic document with realistic content for benchmarking."""
    elements = []

    if complexity == "small":
        # Simple doc: 1 heading, 2 paragraphs, 1 table
        elements.append(Heading(level=1, text="Quarterly Report"))
        elements.append(Paragraph(text=(
            "Revenue increased by 15% compared to last year, driven by "
            "strong performance in the APAC region. This was primarily due "
            "to new partnerships in Southeast Asia and expanding market share."
        )))
        elements.append(Table(
            table_id="t1",
            caption="Regional Sales ($M)",
            rows=[
                TableRow(is_header=True, cells=[
                    TableCell(text="Region", is_header=True),
                    TableCell(text="Q3 2024", is_header=True),
                    TableCell(text="Q3 2025", is_header=True),
                ]),
                TableRow(cells=[
                    TableCell(text="Americas"), TableCell(text="105"), TableCell(text="120"),
                ]),
                TableRow(cells=[
                    TableCell(text="APAC"), TableCell(text="62"), TableCell(text="80"),
                ]),
            ],
        ))
        elements.append(Paragraph(text="Operating margins improved to 22.3% from 19.8%."))

    elif complexity == "medium":
        # Moderate doc: headings, paragraphs, tables, code, math, lists
        elements.append(Heading(level=1, text="Technical Architecture Review"))
        elements.append(Paragraph(text=(
            "This document provides a comprehensive review of the system architecture "
            "including performance benchmarks, scalability analysis, and recommendations "
            "for the next fiscal quarter. All metrics were collected during the period "
            "from January 2026 through March 2026."
        )))

        elements.append(Heading(level=2, text="Performance Metrics"))
        elements.append(Table(
            table_id="perf_metrics",
            caption="System Performance Summary",
            rows=[
                TableRow(is_header=True, cells=[
                    TableCell(text="Metric", is_header=True),
                    TableCell(text="Q4 2025", is_header=True),
                    TableCell(text="Q1 2026", is_header=True),
                    TableCell(text="Change", is_header=True),
                    TableCell(text="Target", is_header=True),
                ]),
                *[TableRow(cells=[
                    TableCell(text=name),
                    TableCell(text=q4),
                    TableCell(text=q1),
                    TableCell(text=delta),
                    TableCell(text=target),
                ]) for name, q4, q1, delta, target in [
                    ("p50 Latency (ms)", "45", "38", "-15.6%", "<50"),
                    ("p99 Latency (ms)", "210", "185", "-11.9%", "<250"),
                    ("Throughput (rps)", "12,400", "15,200", "+22.6%", ">10,000"),
                    ("Error Rate", "0.12%", "0.08%", "-33.3%", "<0.1%"),
                    ("CPU Utilization", "68%", "72%", "+5.9%", "<80%"),
                    ("Memory (GB)", "14.2", "15.8", "+11.3%", "<20"),
                    ("Cache Hit Rate", "92.1%", "94.7%", "+2.8%", ">90%"),
                    ("DB Query Time (ms)", "8.3", "6.1", "-26.5%", "<10"),
                ]],
            ],
        ))

        elements.append(Heading(level=2, text="Algorithm Analysis"))
        elements.append(Paragraph(text=(
            "The core ranking algorithm was optimized using a hybrid approach "
            "combining collaborative filtering with content-based features. "
            "The time complexity was reduced from O(n^2) to O(n log n) through "
            "the introduction of an inverted index structure."
        )))
        elements.append(MathBlock(
            expression=r"\text{Score}(u,i) = \alpha \cdot CF(u,i) + (1-\alpha) \cdot CB(u,i)",
            display_mode=True,
        ))
        elements.append(CodeBlock(
            language="python",
            code=(
                "def compute_score(user_id: int, item_id: int, alpha: float = 0.7) -> float:\n"
                "    cf_score = collaborative_filter(user_id, item_id)\n"
                "    cb_score = content_based(user_id, item_id)\n"
                "    return alpha * cf_score + (1 - alpha) * cb_score\n"
            ),
        ))

        elements.append(Heading(level=2, text="Infrastructure"))
        elements.append(ListBlock(
            ordered=False,
            items=[
                ListItem(text="Kubernetes cluster: 24 nodes, auto-scaling enabled"),
                ListItem(text="Database: PostgreSQL 16 with read replicas"),
                ListItem(text="Cache: Redis Cluster, 6 nodes, 128GB total"),
                ListItem(text="CDN: CloudFront with 42 edge locations"),
                ListItem(text="Monitoring: Datadog APM + custom dashboards"),
            ],
        ))

        elements.append(Heading(level=2, text="Recommendations"))
        elements.append(Paragraph(text=(
            "Based on the analysis above, we recommend three key initiatives for Q2 2026: "
            "(1) migrate the search service to a dedicated Elasticsearch cluster, "
            "(2) implement connection pooling for the PostgreSQL read replicas, and "
            "(3) evaluate moving batch processing workloads to Apache Spark."
        )))

        elements.append(Footnote(number=1, text="All latency figures measured at the 50th and 99th percentiles."))
        elements.append(Footnote(number=2, text="Throughput measured under sustained load with 1000 concurrent users."))

    elif complexity == "large":
        # Large doc: many sections, tables, code blocks, mixed content
        elements.append(Heading(level=1, text="Annual Technical Report 2025-2026"))
        elements.append(Paragraph(text=(
            "This comprehensive report covers all major technical initiatives, "
            "performance outcomes, and strategic recommendations for the engineering "
            "organization. It encompasses data from 12 product teams, 847 services, "
            "and over 2.3 million daily active users across 14 global regions."
        )))

        for section_idx, section_title in enumerate([
            "Platform Performance",
            "Security Audit Results",
            "Data Pipeline Architecture",
            "Machine Learning Operations",
            "Developer Experience",
        ], 1):
            elements.append(Heading(level=2, text=section_title))
            elements.append(Paragraph(text=(
                f"Section {section_idx} of this report covers {section_title.lower()} "
                f"metrics and analysis. Key performance indicators were tracked across "
                f"all production environments, with automated alerting configured for "
                f"deviations beyond two standard deviations from baseline values."
            )))

            # Add a table for each section
            elements.append(Table(
                table_id=f"s{section_idx}_metrics",
                caption=f"{section_title} — Key Metrics",
                rows=[
                    TableRow(is_header=True, cells=[
                        TableCell(text="Metric", is_header=True),
                        TableCell(text="Baseline", is_header=True),
                        TableCell(text="Current", is_header=True),
                        TableCell(text="Status", is_header=True),
                    ]),
                    *[TableRow(cells=[
                        TableCell(text=f"Metric {j}"),
                        TableCell(text=f"{80 + j}%"),
                        TableCell(text=f"{85 + j}%"),
                        TableCell(text="On Track" if j % 2 == 0 else "At Risk"),
                    ]) for j in range(1, 7)],
                ],
            ))

            # Add subsections
            for sub_idx, sub_title in enumerate(["Analysis", "Action Items"], 1):
                elements.append(Heading(level=3, text=f"{section_title}: {sub_title}"))
                elements.append(Paragraph(text=(
                    f"Detailed {sub_title.lower()} for {section_title.lower()}. "
                    f"This subsection provides granular breakdowns of the metrics above, "
                    f"including regional splits, temporal patterns, and correlation analysis "
                    f"with external factors such as traffic spikes and deployment events."
                )))

            # Code block in some sections
            if section_idx % 2 == 0:
                elements.append(CodeBlock(
                    language="sql",
                    code=(
                        f"-- {section_title} query\n"
                        f"SELECT date_trunc('day', created_at) AS day,\n"
                        f"       COUNT(*) AS events,\n"
                        f"       AVG(latency_ms) AS avg_latency\n"
                        f"FROM metrics.{section_title.lower().replace(' ', '_')}\n"
                        f"WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'\n"
                        f"GROUP BY 1\n"
                        f"ORDER BY 1;\n"
                    ),
                ))

            # Math in some sections
            if section_idx % 3 == 0:
                elements.append(MathBlock(
                    expression=r"R^2 = 1 - \frac{SS_{res}}{SS_{tot}}",
                    display_mode=True,
                ))

        # KV pairs (invoice-like section)
        elements.append(Heading(level=2, text="Document Metadata"))
        for key, value in [
            ("Report ID", "TR-2026-Q1-001"),
            ("Classification", "Internal - Confidential"),
            ("Prepared By", "Engineering Excellence Team"),
            ("Review Status", "Approved"),
            ("Distribution", "Engineering Leadership, VP+"),
        ]:
            elements.append(KeyValuePair(key=key, value=value))

        elements.append(HorizontalRule())
        elements.append(Paragraph(text="End of report."))

    return DoxDocument(
        frontmatter=Frontmatter(
            version="1.0",
            source="benchmark-synthetic.pdf",
            pages={"small": 2, "medium": 8, "large": 42}.get(complexity, 8),
            lang="en",
            doc_type="report",
        ),
        elements=elements,
    )


def run_benchmark(doc: DoxDocument, label: str, include_spatial: bool = False) -> dict:
    """Run the benchmark for a single document and return results."""
    serializer = DoxSerializer()

    # Generate all representations
    dox_text = serializer.serialize(
        doc,
        include_spatial=include_spatial,
        include_metadata=False,
    )
    html_text = to_html(doc, standalone=True)
    html_fragment = to_html(doc, standalone=False)
    json_text = to_json(doc)
    md_text = to_markdown(doc)

    results = {}
    for fmt_name, text in [
        (".dox (Layer 0)", dox_text),
        ("HTML (standalone)", html_text),
        ("HTML (fragment)", html_fragment),
        ("JSON", json_text),
        ("Markdown", md_text),
    ]:
        byte_size = len(text.encode("utf-8"))
        tokens = estimate_tokens(text)
        results[fmt_name] = {
            "bytes": byte_size,
            "tokens": tokens,
            "lines": text.count("\n") + 1,
        }

    return results


def print_report(all_results: dict, include_spatial: bool):
    """Print a formatted benchmark report."""
    print("=" * 80)
    print("  .dox Token Efficiency Benchmark")
    print("=" * 80)
    print()

    for label, results in all_results.items():
        dox_bytes = results[".dox (Layer 0)"]["bytes"]
        dox_tokens = results[".dox (Layer 0)"]["tokens"]

        print(f"  Document: {label}")
        print(f"  {'Format':<25} {'Bytes':>10} {'Tokens':>10} {'Lines':>8} {'vs .dox':>10}")
        print(f"  {'-' * 63}")

        for fmt_name, data in results.items():
            ratio = data["bytes"] / dox_bytes if dox_bytes > 0 else 0
            ratio_str = f"{ratio:.2f}x" if fmt_name != ".dox (Layer 0)" else "1.00x"
            print(
                f"  {fmt_name:<25} {data['bytes']:>10,} {data['tokens']:>10,} "
                f"{data['lines']:>8,} {ratio_str:>10}"
            )
        print()

    # Summary
    print("-" * 80)
    print("  SUMMARY: Size Ratios vs .dox (Layer 0)")
    print("-" * 80)
    print(f"  {'Document':<25} {'HTML/dox':>12} {'JSON/dox':>12} {'MD/dox':>12}")
    print(f"  {'-' * 61}")

    for label, results in all_results.items():
        dox_bytes = results[".dox (Layer 0)"]["bytes"]
        html_ratio = results["HTML (standalone)"]["bytes"] / dox_bytes
        json_ratio = results["JSON"]["bytes"] / dox_bytes
        md_ratio = results["Markdown"]["bytes"] / dox_bytes
        print(f"  {label:<25} {html_ratio:>11.2f}x {json_ratio:>11.2f}x {md_ratio:>11.2f}x")

    print()

    # Token summary
    print("-" * 80)
    print("  SUMMARY: Token Ratios vs .dox (Layer 0)")
    print("-" * 80)
    print(f"  {'Document':<25} {'HTML/dox':>12} {'JSON/dox':>12} {'MD/dox':>12}")
    print(f"  {'-' * 61}")

    for label, results in all_results.items():
        dox_tokens = results[".dox (Layer 0)"]["tokens"]
        html_ratio = results["HTML (standalone)"]["tokens"] / dox_tokens if dox_tokens else 0
        json_ratio = results["JSON"]["tokens"] / dox_tokens if dox_tokens else 0
        md_ratio = results["Markdown"]["tokens"] / dox_tokens if dox_tokens else 0
        print(f"  {label:<25} {html_ratio:>11.2f}x {json_ratio:>11.2f}x {md_ratio:>11.2f}x")

    print()
    print("  NOTE: Token estimates use words * 1.3. Actual LLM tokenization may vary.")
    print("  HTML (standalone) includes full CSS. HTML (fragment) is body-only.")
    print("  .dox Layer 0 only — spatial/metadata layers add overhead but carry unique data.")
    print()


def main():
    parser_arg = argparse.ArgumentParser(description="Token efficiency benchmark for .dox")
    parser_arg.add_argument("--include-spatial", action="store_true", help="Include spatial layer in .dox output")
    args = parser_arg.parse_args()

    all_results = {}

    # Synthetic documents
    for complexity in ["small", "medium", "large"]:
        doc = build_synthetic_document(complexity)
        label = f"Synthetic ({complexity})"
        all_results[label] = run_benchmark(doc, label, include_spatial=args.include_spatial)

    # Real .dox files from examples/
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    dox_parser = DoxParser()
    for dox_file in sorted(examples_dir.glob("*.dox")):
        try:
            doc = dox_parser.parse_file(str(dox_file))
            label = dox_file.stem
            all_results[label] = run_benchmark(doc, label, include_spatial=args.include_spatial)
        except Exception as e:
            print(f"  SKIP {dox_file.name}: {e}")

    print_report(all_results, include_spatial=args.include_spatial)


if __name__ == "__main__":
    main()
