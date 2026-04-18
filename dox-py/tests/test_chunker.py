"""Tests for the RAG chunker."""

import pytest
from pathlib import Path

from dox.chunker import DoxChunker, ChunkConfig, ChunkStrategy, chunk_document
from dox.parsers.parser import DoxParser

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def complex_doc():
    return DoxParser().parse_file(EXAMPLES_DIR / "benchmark-complex-layout.dox")


@pytest.fixture
def invoice_doc():
    return DoxParser().parse_file(EXAMPLES_DIR / "benchmark-invoice.dox")


@pytest.fixture
def minimal_doc():
    return DoxParser().parse_file(EXAMPLES_DIR / "minimal.dox")


class TestSemanticChunking:
    def test_produces_chunks(self, complex_doc):
        chunks = chunk_document(complex_doc, strategy="semantic")
        assert len(chunks) > 0

    def test_no_empty_chunks(self, complex_doc):
        chunks = chunk_document(complex_doc, strategy="semantic")
        for c in chunks:
            assert c.text.strip(), f"Empty chunk found: {c.metadata}"

    def test_metadata_present(self, complex_doc):
        chunks = chunk_document(complex_doc, strategy="semantic")
        for c in chunks:
            assert "source" in c.metadata
            assert "element_types" in c.metadata

    def test_heading_path(self, complex_doc):
        chunks = chunk_document(complex_doc, strategy="semantic")
        paths = [c.metadata.get("heading_path", "") for c in chunks]
        assert any("Background" in p or "Architecture" in p or "Results" in p for p in paths)

    def test_table_gets_own_chunk(self, complex_doc):
        chunks = chunk_document(complex_doc, strategy="semantic", max_tokens=256)
        table_chunks = [c for c in chunks if "Table" in c.metadata.get("element_types", [])]
        assert len(table_chunks) > 0

    def test_max_tokens_respected(self, complex_doc):
        chunks = chunk_document(complex_doc, strategy="semantic", max_tokens=256)
        for c in chunks:
            # Allow some slack (tables can be larger than max_tokens)
            if "Table" not in c.metadata.get("element_types", []):
                assert c.token_estimate < 400, f"Chunk too large: {c.token_estimate} tokens"


class TestByHeadingChunking:
    def test_produces_chunks(self, complex_doc):
        config = ChunkConfig(strategy=ChunkStrategy.BY_HEADING, heading_level_split=2)
        chunks = DoxChunker(config).chunk(complex_doc)
        assert len(chunks) > 3  # Should split at each h2

    def test_section_names(self, complex_doc):
        config = ChunkConfig(strategy=ChunkStrategy.BY_HEADING, heading_level_split=2)
        chunks = DoxChunker(config).chunk(complex_doc)
        sections = [c.metadata.get("section", "") for c in chunks]
        assert any("Background" in s for s in sections)


class TestByElementChunking:
    def test_one_per_element(self, minimal_doc):
        chunks = chunk_document(minimal_doc, strategy="by_element")
        assert len(chunks) == len(minimal_doc.elements)


class TestConvenienceFunction:
    def test_default(self, complex_doc):
        chunks = chunk_document(complex_doc)
        assert len(chunks) > 0

    def test_all_strategies(self, minimal_doc):
        for strategy in ["semantic", "by_heading", "by_element", "fixed_size"]:
            chunks = chunk_document(minimal_doc, strategy=strategy)
            assert len(chunks) > 0, f"Strategy {strategy} produced 0 chunks"


class TestChunkMetadata:
    def test_table_ids(self, invoice_doc):
        chunks = chunk_document(invoice_doc, strategy="by_element")
        table_chunks = [c for c in chunks if c.metadata.get("table_ids")]
        assert len(table_chunks) > 0

    def test_token_estimate(self, complex_doc):
        chunks = chunk_document(complex_doc)
        for c in chunks:
            assert c.token_estimate > 0
            # Estimate should be roughly 1.3x word count
            word_count = len(c.text.split())
            assert abs(c.token_estimate - int(word_count * 1.3)) < 5
