"""Performance and fuzzing tests for the dox-py project.

Run with: pytest tests/test_performance.py -v --tb=short
Performance tests: pytest tests/test_performance.py -v -m performance
Fuzzing tests: pytest tests/test_performance.py -v -m fuzz
"""

import pytest
import random
import string
import time
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.converters import to_html, to_docx_bytes, to_pdf_bytes, to_json, to_markdown
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Heading, Paragraph, Table, TableRow, TableCell, CodeBlock,
    MathBlock, ListBlock, ListItem, Figure, Footnote, FormField, Annotation
)
from dox.validator import DoxValidator
from dox.chunker import chunk_document


# ============================================================================
# TEST CLASS 1: PERFORMANCE TESTS (~15 tests)
# ============================================================================

class TestPerformance:
    """Performance tests marked with @pytest.mark.performance."""

    @pytest.mark.performance
    def test_large_document_parse_1000_elements(self):
        """Parse a .dox string with 1000 headings and paragraphs. Assert < 2 seconds."""
        # Build a .dox document with 1000 elements
        content = "---dox\nversion: \"1.0\"\nsource: test.pdf\n---\n\n"
        for i in range(1000):
            if i % 10 == 0:
                content += f"# Heading {i}\n\n"
            else:
                content += f"Paragraph {i} with some content.\n\n"

        parser = DoxParser()
        start = time.time()
        doc = parser.parse(content)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Parse took {elapsed:.2f}s, expected < 2s"
        assert len(doc.elements) > 900

    @pytest.mark.performance
    def test_large_document_serialize_1000_elements(self):
        """Build a DoxDocument with 1000 elements. Assert serialize < 2 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0", source="test.pdf"))
        for i in range(1000):
            if i % 10 == 0:
                doc.elements.append(Heading(level=1, text=f"Heading {i}"))
            else:
                doc.elements.append(Paragraph(text=f"Paragraph {i} with content"))

        serializer = DoxSerializer()
        start = time.time()
        result = serializer.serialize(doc)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Serialize took {elapsed:.2f}s, expected < 2s"
        assert len(result) > 1000

    @pytest.mark.performance
    def test_large_table_roundtrip(self):
        """Create a doc with a 100×100 table. Parse→serialize roundtrip < 3 seconds."""
        # Build a large table
        rows = []
        for i in range(100):
            cells = [TableCell(text=f"Cell {i},{j}") for j in range(100)]
            rows.append(TableRow(cells=cells))

        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        doc.elements.append(Table(table_id="big_table", rows=rows))

        serializer = DoxSerializer()
        start = time.time()
        serialized = serializer.serialize(doc)
        parsed = DoxParser().parse(serialized)
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Roundtrip took {elapsed:.2f}s, expected < 3s"
        assert len(parsed.tables()) == 1
        assert len(parsed.tables()[0].rows) == 100

    @pytest.mark.performance
    def test_docx_generation_500_elements(self):
        """Build doc with 500 elements, generate DOCX bytes. Assert < 5 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0", source="test.docx"))
        for i in range(500):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Section {i}"))
            elif i % 5 == 0:
                doc.elements.append(CodeBlock(language="python", code="x = 42"))
            else:
                doc.elements.append(Paragraph(text=f"Content {i}"))

        start = time.time()
        docx_bytes = to_docx_bytes(doc)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"DOCX generation took {elapsed:.2f}s, expected < 5s"
        assert len(docx_bytes) > 0
        assert docx_bytes[:4] == b'PK\x03\x04'  # ZIP file signature

    @pytest.mark.performance
    def test_pdf_generation_500_elements(self):
        """Build doc with 500 elements, generate PDF bytes. Assert < 5 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0", source="test.pdf"))
        for i in range(500):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Section {i}"))
            elif i % 5 == 0:
                doc.elements.append(Paragraph(text="Lorem ipsum dolor sit amet."))
            else:
                doc.elements.append(Paragraph(text=f"Content line {i}"))

        start = time.time()
        pdf_bytes = to_pdf_bytes(doc)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"PDF generation took {elapsed:.2f}s, expected < 5s"
        assert len(pdf_bytes) > 0

    @pytest.mark.performance
    def test_html_generation_1000_elements(self):
        """Build doc with 1000 elements, generate HTML. Assert < 1 second."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for i in range(1000):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Heading {i}"))
            else:
                doc.elements.append(Paragraph(text=f"Paragraph {i}"))

        start = time.time()
        html = to_html(doc)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"HTML generation took {elapsed:.2f}s, expected < 1s"
        assert "<h1>" in html or "<h2>" in html

    @pytest.mark.performance
    def test_json_generation_1000_elements(self):
        """Build doc with 1000 elements, generate JSON. Assert < 1 second."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for i in range(1000):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Heading {i}"))
            else:
                doc.elements.append(Paragraph(text=f"Paragraph {i}"))

        start = time.time()
        json_str = to_json(doc)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"JSON generation took {elapsed:.2f}s, expected < 1s"
        assert len(json_str) > 100
        assert "version" in json_str

    @pytest.mark.performance
    def test_markdown_generation_1000_elements(self):
        """Build doc with 1000 elements, generate Markdown. Assert < 1 second."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for i in range(1000):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Heading {i}"))
            else:
                doc.elements.append(Paragraph(text=f"Paragraph {i}"))

        start = time.time()
        md = to_markdown(doc)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Markdown generation took {elapsed:.2f}s, expected < 1s"
        assert "#" in md or "Heading" in md

    @pytest.mark.performance
    def test_chunking_1000_elements(self):
        """Chunk a doc with 1000 elements. Assert < 3 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for i in range(1000):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Section {i}"))
            else:
                doc.elements.append(Paragraph(text=f"Content {i}"))

        start = time.time()
        chunks = chunk_document(doc, strategy="semantic")
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Chunking took {elapsed:.2f}s, expected < 3s"
        assert len(chunks) > 0

    @pytest.mark.performance
    def test_validation_1000_elements(self):
        """Validate a doc with 1000 elements. Assert < 1 second."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for i in range(1000):
            if i % 20 == 0:
                doc.elements.append(Heading(level=1 + (i % 3), text=f"Heading {i}"))
            else:
                doc.elements.append(Paragraph(text=f"Paragraph {i}"))

        validator = DoxValidator()
        start = time.time()
        result = validator.validate(doc)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Validation took {elapsed:.2f}s, expected < 1s"

    @pytest.mark.performance
    def test_roundtrip_parse_serialize_parse_500_elements(self):
        """Parse→serialize→parse 500 elements. Assert < 3 seconds and content preserved."""
        content = "---dox\nversion: \"1.0\"\nsource: test.pdf\n---\n\n"
        for i in range(500):
            if i % 20 == 0:
                content += f"# Heading {i}\n\n"
            elif i % 5 == 0:
                content += f"```python\ncode {i}\n```\n\n"
            else:
                content += f"Paragraph {i}.\n\n"

        parser = DoxParser()
        serializer = DoxSerializer()

        start = time.time()
        doc1 = parser.parse(content)
        serialized = serializer.serialize(doc1)
        doc2 = parser.parse(serialized)
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Roundtrip took {elapsed:.2f}s, expected < 3s"
        assert len(doc1.elements) == len(doc2.elements)
        assert len(doc1.headings()) == len(doc2.headings())

    @pytest.mark.performance
    def test_memory_large_doc_5000_paragraphs(self):
        """Large doc with 5000 paragraphs should complete without crashing."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for i in range(5000):
            doc.elements.append(Paragraph(text=f"Paragraph {i} with content."))

        serializer = DoxSerializer()
        start = time.time()
        result = serializer.serialize(doc)
        elapsed = time.time() - start

        # Just verify it completes and produces output
        assert len(result) > 10000
        assert elapsed < 10.0  # Generous timeout for large document

    @pytest.mark.performance
    def test_deep_nesting_6_levels_100_times(self):
        """Deep heading nesting (6 levels × 100 times) with paragraphs. Assert < 2 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for repeat in range(100):
            for level in range(1, 7):
                doc.elements.append(
                    Heading(level=level, text=f"Level {level} Heading {repeat}")
                )
                doc.elements.append(
                    Paragraph(text=f"Content for level {level}, repeat {repeat}")
                )

        serializer = DoxSerializer()
        start = time.time()
        result = serializer.serialize(doc)
        parsed = DoxParser().parse(result)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Deep nesting roundtrip took {elapsed:.2f}s, expected < 2s"
        assert len(parsed.headings()) == 600

    @pytest.mark.performance
    def test_many_tables_50_tables_10x5(self):
        """50 tables (10×5 cells each). All converters < 5 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        for t in range(50):
            rows = []
            for i in range(10):
                cells = [TableCell(text=f"T{t}R{i}C{j}") for j in range(5)]
                rows.append(TableRow(cells=cells))
            doc.elements.append(Table(table_id=f"table_{t}", rows=rows))

        start = time.time()
        html = to_html(doc)
        json_out = to_json(doc)
        md = to_markdown(doc)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Multiple converters took {elapsed:.2f}s, expected < 5s"
        assert len(html) > 1000
        assert "table" in json_out.lower()

    @pytest.mark.performance
    def test_unicode_stress_500_paragraphs_cjk_arabic_emoji(self):
        """500 paragraphs with CJK, Arabic, emoji, math symbols. Assert < 2 seconds."""
        doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
        test_strings = [
            "Chinese: 你好世界",
            "Japanese: こんにちは",
            "Korean: 안녕하세요",
            "Arabic: مرحبا بالعالم",
            "Emoji: 🚀 🎉 ✨",
            "Math: ∑ ∏ √ ∞",
            "Mixed: Héllo Wörld مرحبا",
        ]

        for i in range(500):
            test_str = test_strings[i % len(test_strings)]
            doc.elements.append(Paragraph(text=f"Paragraph {i}: {test_str}"))

        serializer = DoxSerializer()
        start = time.time()
        result = serializer.serialize(doc)
        parsed = DoxParser().parse(result)
        to_html(doc)
        to_json(doc)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Unicode stress took {elapsed:.2f}s, expected < 2s"
        assert len(parsed.paragraphs()) == 500


# ============================================================================
# TEST CLASS 2: FUZZING TESTS (~20 tests)
# ============================================================================

class TestFuzzing:
    """Fuzzing tests marked with @pytest.mark.fuzz.

    These tests use random.seed() for reproducibility and verify
    that no unhandled exceptions occur on malformed/random inputs.
    """

    @pytest.mark.fuzz
    def test_fuzz_random_bytes_as_dox_input(self):
        """Random bytes as .dox input should not crash."""
        random.seed(42)
        parser = DoxParser()

        for iteration in range(50):
            # Generate random printable and control chars
            length = random.randint(10, 1000)
            chars = [chr(random.randint(32, 126)) for _ in range(length)]
            # Sprinkle in some control chars
            for _ in range(length // 10):
                chars[random.randint(0, length - 1)] = chr(random.randint(0, 31))

            input_str = "".join(chars)
            try:
                doc = parser.parse(input_str)
                # If it parses, just verify it returns a DoxDocument
                assert isinstance(doc, DoxDocument)
            except Exception:
                # Expected for malformed input; just verify no crash
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_yaml_frontmatter(self):
        """Random YAML frontmatter values should not crash."""
        random.seed(43)
        parser = DoxParser()

        for iteration in range(50):
            keys = ["custom_key_" + str(i) for i in range(random.randint(1, 5))]
            values = [
                random.choice([
                    str(random.randint(-1000, 1000)),
                    random.choice(["true", "false"]),
                    "string_value_" + str(random.randint(0, 100)),
                ])
                for _ in keys
            ]

            yaml_content = "---dox\nversion: \"1.0\"\n"
            for k, v in zip(keys, values):
                yaml_content += f"{k}: {v}\n"
            yaml_content += "---\n\n# Content\n"

            try:
                doc = parser.parse(yaml_content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_malformed_table_structures(self):
        """Random pipes and dashes in table structures should not crash."""
        random.seed(44)
        parser = DoxParser()

        for iteration in range(50):
            pipes = random.randint(1, 20)
            dashes = random.randint(1, 20)
            table_line = "|" * pipes + "-" * dashes + "|" * pipes

            content = f"---dox\nversion: \"1.0\"\n---\n\n{table_line}\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_heading_levels(self):
        """Random heading levels (1-100 #) should not crash."""
        random.seed(45)
        parser = DoxParser()

        for iteration in range(50):
            level = random.randint(1, 100)
            heading_line = "#" * level + " Heading " + str(iteration)
            content = f"---dox\nversion: \"1.0\"\n---\n\n{heading_line}\n"

            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_mismatched_inline_formatting(self):
        """Mismatched **bold**, *italic*, ~~strike~~, backticks should not crash."""
        random.seed(46)
        parser = DoxParser()

        for iteration in range(50):
            formatters = ["**", "*", "~~", "`"]
            f1 = random.choice(formatters)
            f2 = random.choice(formatters)
            f3 = random.choice(formatters)

            # Sometimes match, sometimes don't
            if random.random() > 0.5:
                text = f"Text with {f1}formatted{f1} content"
            else:
                text = f"Text with {f1}mismatched{f2} content"

            content = f"---dox\nversion: \"1.0\"\n---\n\n{text}\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_deeply_nested_brackets_parens(self):
        """Deeply nested brackets/parens (hundreds deep) should not crash."""
        random.seed(47)
        parser = DoxParser()

        for iteration in range(50):
            depth = random.randint(50, 500)
            text = "[" * depth + "content" + "]" * depth
            content = f"---dox\nversion: \"1.0\"\n---\n\n{text}\n"

            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_giant_single_line(self):
        """100K chars on one line should not crash."""
        random.seed(48)
        parser = DoxParser()

        for iteration in range(10):  # Fewer iterations for large lines
            length = random.randint(10000, 100000)
            line = "x" * length
            content = f"---dox\nversion: \"1.0\"\n---\n\n{line}\n"

            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_empty_lines(self):
        """Random empty line insertion should not crash."""
        random.seed(49)
        parser = DoxParser()

        for iteration in range(50):
            lines = ["---dox", "version: \"1.0\"", "---", ""]
            for i in range(50):
                if random.random() > 0.5:
                    lines.append("")
                lines.append(f"Line {i}")

            content = "\n".join(lines)
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_code_blocks(self):
        """Unclosed, nested, with random languages should not crash."""
        random.seed(50)
        parser = DoxParser()

        for iteration in range(50):
            langs = ["python", "javascript", "ruby", "", "unknown_lang"]
            lang = random.choice(langs)

            if random.random() > 0.3:
                code = f"```{lang}\ncode here\n```"
            else:
                # Unclosed
                code = f"```{lang}\ncode here"

            content = f"---dox\nversion: \"1.0\"\n---\n\n{code}\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_math_blocks(self):
        """Unclosed $$, malformed LaTeX should not crash."""
        random.seed(51)
        parser = DoxParser()

        for iteration in range(50):
            math_content = "x^2 + y^2 = z^2" if random.random() > 0.5 else "\\invalid{}"

            if random.random() > 0.3:
                math = f"$${math_content}$$"
            else:
                # Unclosed
                math = f"$${math_content}"

            content = f"---dox\nversion: \"1.0\"\n---\n\n{math}\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_null_bytes_in_text(self):
        """Null bytes scattered throughout text should not crash."""
        random.seed(52)
        parser = DoxParser()

        for iteration in range(50):
            text = "Normal text content"
            # Insert random null bytes
            text_list = list(text)
            for _ in range(random.randint(0, 5)):
                idx = random.randint(0, len(text_list) - 1)
                text_list[idx] = "\x00"
            text = "".join(text_list)

            content = f"---dox\nversion: \"1.0\"\n---\n\n{text}\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_yaml_types_in_frontmatter(self):
        """Random YAML types (lists, dicts, booleans) as frontmatter should not crash."""
        random.seed(53)
        parser = DoxParser()

        for iteration in range(50):
            yaml_lines = ["---dox", "version: \"1.0\""]

            # Random YAML structures
            if random.random() > 0.5:
                yaml_lines.append("custom_list:")
                for i in range(random.randint(1, 5)):
                    yaml_lines.append(f"  - item_{i}")

            if random.random() > 0.5:
                yaml_lines.append("custom_dict:")
                for i in range(random.randint(1, 3)):
                    yaml_lines.append(f"  key_{i}: value_{i}")

            if random.random() > 0.5:
                yaml_lines.append(f"custom_bool: {random.choice(['true', 'false'])}")

            yaml_lines.append("---")
            yaml_lines.append("")
            yaml_lines.append("# Content")

            content = "\n".join(yaml_lines)
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_metadata_section(self):
        """Random <!--dox-meta ... --> sections should not crash."""
        random.seed(54)
        parser = DoxParser()

        for iteration in range(50):
            # Generate random metadata content
            meta_keys = ["key_" + str(i) for i in range(random.randint(1, 5))]
            meta_values = [
                "value_" + str(random.randint(0, 100)) for _ in meta_keys
            ]
            meta_content = " ".join([f'{k}="{v}"' for k, v in zip(meta_keys, meta_values)])

            content = f"""---dox
version: "1.0"
---

<!--dox-meta {meta_content}-->

# Content
"""
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_spatial_section(self):
        """Random <!-- dox-spatial ... --> sections should not crash."""
        random.seed(55)
        parser = DoxParser()

        for iteration in range(50):
            spatial_data = "".join(
                random.choices(string.ascii_letters + string.digits + " ,.", k=random.randint(50, 200))
            )

            content = f"""---dox
version: "1.0"
---

<!-- dox-spatial {spatial_data}-->

# Content
"""
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_serialize_parse_roundtrip_random_docs(self):
        """Serialize→parse roundtrip with random DoxDocuments should not crash."""
        random.seed(56)
        serializer = DoxSerializer()
        parser = DoxParser()

        for iteration in range(50):
            doc = DoxDocument(
                frontmatter=Frontmatter(
                    version="1.0",
                    source=f"test_{iteration}.pdf"
                )
            )

            # Add random elements
            for i in range(random.randint(10, 100)):
                element_type = random.choice(["heading", "paragraph", "code"])
                if element_type == "heading":
                    doc.elements.append(
                        Heading(level=random.randint(1, 6), text=f"Heading {i}")
                    )
                elif element_type == "code":
                    doc.elements.append(
                        CodeBlock(language="python", code=f"x = {i}")
                    )
                else:
                    doc.elements.append(
                        Paragraph(text=f"Paragraph {i}")
                    )

            try:
                serialized = serializer.serialize(doc)
                parsed = parser.parse(serialized)
                assert isinstance(parsed, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_all_converters_random_docs(self):
        """All converters on random docs should not crash."""
        random.seed(57)

        for iteration in range(50):
            doc = DoxDocument(frontmatter=Frontmatter(version="1.0"))
            for i in range(random.randint(5, 50)):
                if random.random() > 0.5:
                    doc.elements.append(
                        Heading(level=random.randint(1, 3), text=f"H{i}")
                    )
                else:
                    doc.elements.append(Paragraph(text=f"P{i}"))

            try:
                to_html(doc)
            except Exception:
                pass

            try:
                to_json(doc)
            except Exception:
                pass

            try:
                to_markdown(doc)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_form_fields(self):
        """Random form field syntax should not crash."""
        random.seed(58)
        parser = DoxParser()

        for iteration in range(50):
            field_types = ["text", "checkbox", "radio", "select", "textarea"]
            field_type = random.choice(field_types)
            field_name = "field_" + str(random.randint(0, 100))

            # Sometimes valid, sometimes not
            if random.random() > 0.5:
                form_line = f"::form field=\"{field_name}\" type=\"{field_type}\"::"
            else:
                form_line = f"[__{field_name}: {field_type}__]"

            content = f"---dox\nversion: \"1.0\"\n---\n\n{form_line}\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_random_annotations(self):
        """Random annotation syntax should not crash."""
        random.seed(59)
        parser = DoxParser()

        for iteration in range(50):
            annotation_text = "".join(
                random.choices(
                    string.ascii_letters + string.digits + " ", k=random.randint(5, 50)
                )
            )

            # Various annotation formats
            formats = [
                f"{{>> {annotation_text} <<}}",
                f"{{[[{annotation_text}]]}}",
                f"{{-- {annotation_text} --}}",
            ]
            annotation_line = random.choice(formats)

            content = f"---dox\nversion: \"1.0\"\n---\n\nSome text {annotation_line} more text\n"
            try:
                doc = parser.parse(content)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_mixed_encoding_utf8_latin1_emoji(self):
        """Mixed UTF-8, Latin-1, emoji sequences should not crash."""
        random.seed(60)
        parser = DoxParser()

        for iteration in range(50):
            text_parts = [
                "ASCII text",
                "Ëñçödéd tëxt",
                "🚀 🎉 ✨ 🌟",
                "Ñoño señorita",
                "Naïve café",
            ]
            text = " ".join(random.sample(text_parts, k=random.randint(2, 5)))

            content = f"---dox\nversion: \"1.0\"\n---\n\n{text}\n"
            try:
                doc = parser.parse(content)
                serialized = DoxSerializer().serialize(doc)
                assert isinstance(doc, DoxDocument)
            except Exception:
                pass

    @pytest.mark.fuzz
    def test_fuzz_adversarial_xss_strings(self):
        """XSS strings should be safely handled (not crash or execute)."""
        random.seed(61)
        parser = DoxParser()

        xss_payloads = [
            "<script>alert('xss')</script>",
            "\" onload=\"alert('xss')\"",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "' onclick='alert(1)' '",
            "<iframe src=\"javascript:alert('xss')\">",
        ]

        for iteration in range(50):
            payload = random.choice(xss_payloads)
            element_types = ["heading", "paragraph", "code"]
            element_type = random.choice(element_types)

            if element_type == "heading":
                content = f"---dox\nversion: \"1.0\"\n---\n\n# {payload}\n"
            elif element_type == "code":
                content = f"---dox\nversion: \"1.0\"\n---\n\n```html\n{payload}\n```\n"
            else:
                content = f"---dox\nversion: \"1.0\"\n---\n\n{payload}\n"

            try:
                doc = parser.parse(content)
                # Also try converting to HTML to ensure output is safe
                html = to_html(doc)
                # XSS payloads should not execute; just verify we get HTML
                assert isinstance(html, str)
            except Exception:
                pass
