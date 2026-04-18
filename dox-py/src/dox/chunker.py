"""
RAG-optimized chunker for .dox documents.

Produces semantically meaningful chunks that respect document structure:
  - Never splits mid-table or mid-code-block
  - Preserves heading hierarchy as chunk metadata
  - Includes cross-reference context
  - Supports configurable chunk strategies

Designed for direct use with LangChain, LlamaIndex, and any RAG pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dox.models.document import DoxDocument
from dox.models.elements import (
    Annotation,
    Chart,
    CodeBlock,
    CrossRef,
    Element,
    Figure,
    Footnote,
    FormField,
    Heading,
    KeyValuePair,
    ListBlock,
    MathBlock,
    Paragraph,
    Table,
)
from dox.serializer import DoxSerializer


class ChunkStrategy(str, Enum):
    """How to split the document into chunks."""
    BY_HEADING = "by_heading"          # One chunk per heading section
    BY_ELEMENT = "by_element"          # One chunk per element (table, paragraph, etc.)
    BY_PAGE = "by_page"                # One chunk per page (requires spatial data)
    FIXED_SIZE = "fixed_size"          # Fixed token-count chunks (respects element boundaries)
    SEMANTIC = "semantic"              # Semantic grouping (heading + related content)


@dataclass
class DoxChunk:
    """A single chunk from a .dox document, ready for embedding/retrieval."""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    elements: list[Element] = field(default_factory=list)

    @property
    def token_estimate(self) -> int:
        """Rough token estimate (words * 1.3 for English text)."""
        return int(len(self.text.split()) * 1.3)


@dataclass
class ChunkConfig:
    """Configuration for chunking behavior."""
    strategy: ChunkStrategy = ChunkStrategy.SEMANTIC
    max_tokens: int = 512
    min_tokens: int = 50
    overlap_tokens: int = 0
    include_heading_path: bool = True     # Include parent headings in chunk metadata
    include_table_as_markdown: bool = True  # Render tables as Markdown in chunk text
    include_confidence: bool = True        # Include confidence scores in metadata
    heading_level_split: int = 2           # Split at this heading level (1-6); 2 = split at ##


class DoxChunker:
    """
    Split a DoxDocument into chunks for RAG pipelines.

    Usage:
        chunker = DoxChunker()
        chunks = chunker.chunk(doc)

        # Or with custom config:
        config = ChunkConfig(strategy=ChunkStrategy.BY_HEADING, max_tokens=1024)
        chunks = DoxChunker(config).chunk(doc)

        # LangChain integration:
        from langchain.schema import Document
        lc_docs = [Document(page_content=c.text, metadata=c.metadata) for c in chunks]
    """

    def __init__(self, config: ChunkConfig | None = None):
        self.config = config or ChunkConfig()
        self._serializer = DoxSerializer()

    def chunk(self, doc: DoxDocument) -> list[DoxChunk]:
        """Chunk a document according to the configured strategy."""
        strategy = self.config.strategy

        if strategy == ChunkStrategy.BY_HEADING:
            return self._chunk_by_heading(doc)
        elif strategy == ChunkStrategy.BY_ELEMENT:
            return self._chunk_by_element(doc)
        elif strategy == ChunkStrategy.BY_PAGE:
            return self._chunk_by_page(doc)
        elif strategy == ChunkStrategy.FIXED_SIZE:
            return self._chunk_fixed_size(doc)
        elif strategy == ChunkStrategy.SEMANTIC:
            return self._chunk_semantic(doc)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    # ------------------------------------------------------------------
    # Strategy: Semantic (default, recommended)
    # ------------------------------------------------------------------

    def _chunk_semantic(self, doc: DoxDocument) -> list[DoxChunk]:
        """
        Smart semantic chunking:
        1. Group elements under their nearest heading.
        2. If a group exceeds max_tokens, split at natural boundaries.
        3. Standalone tables and code blocks are always their own chunks.
        """
        chunks: list[DoxChunk] = []
        heading_path: list[str] = []
        current_group: list[Element] = []
        current_heading: Heading | None = None

        for element in doc.elements:
            if isinstance(element, Heading):
                # Flush the current group
                if current_group:
                    chunks.extend(
                        self._group_to_chunks(current_group, heading_path, doc)
                    )
                    current_group = []

                # Update heading path
                level = element.level
                heading_path = heading_path[:level - 1]
                while len(heading_path) < level - 1:
                    heading_path.append("")
                heading_path.append(element.text)
                current_heading = element
                current_group.append(element)

            elif isinstance(element, (Table, CodeBlock)) and self._element_tokens(element) > self.config.min_tokens:
                # Large tables and code blocks get their own chunk
                if current_group:
                    chunks.extend(
                        self._group_to_chunks(current_group, heading_path, doc)
                    )
                    current_group = []
                chunks.append(self._element_to_chunk(element, heading_path, doc))
            else:
                current_group.append(element)

        # Flush remaining
        if current_group:
            chunks.extend(self._group_to_chunks(current_group, heading_path, doc))

        return chunks

    def _group_to_chunks(
        self, elements: list[Element], heading_path: list[str], doc: DoxDocument
    ) -> list[DoxChunk]:
        """Convert a group of elements into one or more chunks."""
        text = self._elements_to_text(elements)
        tokens = int(len(text.split()) * 1.3)

        if tokens <= self.config.max_tokens:
            return [self._make_chunk(text, elements, heading_path, doc)]

        # Split into sub-chunks respecting element boundaries
        chunks: list[DoxChunk] = []
        current_elements: list[Element] = []
        current_text_parts: list[str] = []
        current_tokens = 0

        for el in elements:
            el_text = self._element_to_text(el)
            el_tokens = int(len(el_text.split()) * 1.3)

            if current_tokens + el_tokens > self.config.max_tokens and current_elements:
                chunks.append(
                    self._make_chunk(
                        "\n\n".join(current_text_parts),
                        current_elements,
                        heading_path,
                        doc,
                    )
                )
                # Overlap: carry trailing elements from previous chunk
                overlap_elements: list[Element] = []
                overlap_texts: list[str] = []
                overlap_tokens = 0
                if self.config.overlap_tokens > 0:
                    for oe, ot in reversed(
                        list(zip(current_elements, current_text_parts))
                    ):
                        oe_tokens = int(len(ot.split()) * 1.3)
                        if overlap_tokens + oe_tokens > self.config.overlap_tokens:
                            break
                        overlap_elements.insert(0, oe)
                        overlap_texts.insert(0, ot)
                        overlap_tokens += oe_tokens

                current_elements = list(overlap_elements)
                current_text_parts = list(overlap_texts)
                current_tokens = overlap_tokens

            current_elements.append(el)
            current_text_parts.append(el_text)
            current_tokens += el_tokens

        if current_elements:
            chunks.append(
                self._make_chunk(
                    "\n\n".join(current_text_parts),
                    current_elements,
                    heading_path,
                    doc,
                )
            )

        return chunks

    # ------------------------------------------------------------------
    # Strategy: By heading
    # ------------------------------------------------------------------

    def _chunk_by_heading(self, doc: DoxDocument) -> list[DoxChunk]:
        chunks: list[DoxChunk] = []
        heading_path: list[str] = []
        current_elements: list[Element] = []

        for element in doc.elements:
            if isinstance(element, Heading) and element.level <= self.config.heading_level_split:
                if current_elements:
                    text = self._elements_to_text(current_elements)
                    chunks.append(self._make_chunk(text, current_elements, heading_path, doc))
                    current_elements = []

                level = element.level
                heading_path = heading_path[:level - 1]
                while len(heading_path) < level - 1:
                    heading_path.append("")
                heading_path.append(element.text)

            current_elements.append(element)

        if current_elements:
            text = self._elements_to_text(current_elements)
            chunks.append(self._make_chunk(text, current_elements, heading_path, doc))

        return chunks

    # ------------------------------------------------------------------
    # Strategy: By element
    # ------------------------------------------------------------------

    def _chunk_by_element(self, doc: DoxDocument) -> list[DoxChunk]:
        chunks: list[DoxChunk] = []
        heading_path: list[str] = []

        for element in doc.elements:
            if isinstance(element, Heading):
                level = element.level
                heading_path = heading_path[:level - 1]
                while len(heading_path) < level - 1:
                    heading_path.append("")
                heading_path.append(element.text)

            chunks.append(self._element_to_chunk(element, heading_path, doc))

        return chunks

    # ------------------------------------------------------------------
    # Strategy: By page
    # ------------------------------------------------------------------

    def _chunk_by_page(self, doc: DoxDocument) -> list[DoxChunk]:
        if not doc.spatial_blocks:
            # Fallback to semantic if no spatial data
            return self._chunk_semantic(doc)

        page_map: dict[int, list[Element]] = {}
        # Try to assign elements to pages via spatial data
        for element in doc.elements:
            page = element.page or 1
            page_map.setdefault(page, []).append(element)

        # If all elements are on page 1 (no page info), fall back
        if len(page_map) <= 1 and len(doc.elements) > 5:
            return self._chunk_semantic(doc)

        chunks: list[DoxChunk] = []
        for page_num in sorted(page_map.keys()):
            elements = page_map[page_num]
            text = self._elements_to_text(elements)
            chunks.append(DoxChunk(
                text=text,
                metadata={
                    "source": doc.frontmatter.source,
                    "page": page_num,
                    "element_count": len(elements),
                },
                elements=elements,
            ))

        return chunks

    # ------------------------------------------------------------------
    # Strategy: Fixed size
    # ------------------------------------------------------------------

    def _chunk_fixed_size(self, doc: DoxDocument) -> list[DoxChunk]:
        return self._chunk_semantic(doc)  # Semantic already handles max_tokens

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _element_to_chunk(
        self, element: Element, heading_path: list[str], doc: DoxDocument
    ) -> DoxChunk:
        text = self._element_to_text(element)
        return self._make_chunk(text, [element], heading_path, doc)

    def _make_chunk(
        self,
        text: str,
        elements: list[Element],
        heading_path: list[str],
        doc: DoxDocument,
    ) -> DoxChunk:
        metadata: dict[str, Any] = {
            "source": doc.frontmatter.source,
            "lang": doc.frontmatter.lang,
        }

        if self.config.include_heading_path and heading_path:
            metadata["heading_path"] = " > ".join(h for h in heading_path if h)
            metadata["section"] = heading_path[-1] if heading_path else ""

        # Element types in chunk
        type_set = {type(e).__name__ for e in elements}
        metadata["element_types"] = sorted(type_set)
        metadata["element_count"] = len(elements)

        # Table IDs
        table_ids = [e.table_id for e in elements if isinstance(e, Table) and e.table_id]
        if table_ids:
            metadata["table_ids"] = table_ids

        # Confidence (minimum across elements)
        if self.config.include_confidence:
            confidences = [e.confidence for e in elements if e.confidence is not None]
            if confidences:
                metadata["min_confidence"] = min(confidences)

        return DoxChunk(text=text.strip(), metadata=metadata, elements=elements)

    def _elements_to_text(self, elements: list[Element]) -> str:
        return "\n\n".join(self._element_to_text(e) for e in elements)

    def _element_to_text(self, element: Element) -> str:
        if isinstance(element, Heading):
            return f"{'#' * element.level} {element.text}"
        elif isinstance(element, Paragraph):
            return element.text
        elif isinstance(element, Table):
            if self.config.include_table_as_markdown:
                return self._table_to_markdown(element)
            return f"[Table: {element.table_id or 'unnamed'}, {element.num_rows}×{element.num_cols}]"
        elif isinstance(element, CodeBlock):
            lang = element.language or ""
            return f"```{lang}\n{element.code}\n```"
        elif isinstance(element, MathBlock):
            return f"$${element.expression}$$"
        elif isinstance(element, FormField):
            return f"{element.field_name}: {element.value}"
        elif isinstance(element, Chart):
            return f"[Chart: {element.chart_type}, data from {element.data_ref}]"
        elif isinstance(element, Annotation):
            return f"[{element.annotation_type}: {element.text}]"
        elif isinstance(element, KeyValuePair):
            return f"{element.key}: {element.value}"
        elif isinstance(element, Figure):
            return f"[Figure: {element.caption}]"
        elif isinstance(element, Footnote):
            return f"[^{element.number}]: {element.text}"
        elif isinstance(element, ListBlock):
            items = []
            for idx, item in enumerate(element.items):
                marker = f"{element.start + idx}." if element.ordered else "-"
                items.append(f"{marker} {item.text}")
            return "\n".join(items)
        elif isinstance(element, CrossRef):
            return f"[ref:{element.ref_type}:{element.ref_id}]"
        return str(element)

    def _table_to_markdown(self, table: Table) -> str:
        if not table.rows:
            return f"[Empty table: {table.table_id or 'unnamed'}]"

        lines: list[str] = []
        if table.caption:
            lines.append(f"**{table.caption}**")

        num_cols = table.num_cols
        headers = table.header_rows()
        data = table.data_rows()

        if headers:
            for row in headers:
                cells = " | ".join(c.text for c in row.cells)
                lines.append(f"| {cells} |")
            lines.append("|" + "|".join("---" for _ in range(num_cols)) + "|")

        for row in data:
            cells = " | ".join(c.text for c in row.cells)
            lines.append(f"| {cells} |")

        return "\n".join(lines)

    def _element_tokens(self, element: Element) -> int:
        text = self._element_to_text(element)
        return int(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def chunk_document(
    doc: DoxDocument,
    strategy: str = "semantic",
    max_tokens: int = 512,
    **kwargs: Any,
) -> list[DoxChunk]:
    """
    Convenience function to chunk a .dox document.

    Args:
        doc: The DoxDocument to chunk.
        strategy: "semantic", "by_heading", "by_element", "by_page", "fixed_size".
        max_tokens: Maximum tokens per chunk.
        **kwargs: Additional ChunkConfig options.

    Returns:
        List of DoxChunk objects ready for embedding.
    """
    config = ChunkConfig(
        strategy=ChunkStrategy(strategy),
        max_tokens=max_tokens,
        **kwargs,
    )
    return DoxChunker(config).chunk(doc)


def to_langchain_documents(chunks: list[DoxChunk]) -> list[Any]:
    """
    Convert DoxChunks to LangChain Document objects.

    Requires langchain-core installed.
    """
    try:
        from langchain_core.documents import Document
    except ImportError:
        raise ImportError("langchain-core required. Install with: pip install langchain-core")

    return [
        Document(page_content=chunk.text, metadata=chunk.metadata)
        for chunk in chunks
    ]


def to_llama_index_nodes(chunks: list[DoxChunk]) -> list[Any]:
    """
    Convert DoxChunks to LlamaIndex TextNode objects.

    Requires llama-index-core installed.
    """
    try:
        from llama_index.core.schema import TextNode
    except ImportError:
        raise ImportError("llama-index-core required. Install with: pip install llama-index-core")

    return [
        TextNode(
            text=chunk.text,
            metadata=chunk.metadata,
            excluded_embed_metadata_keys=["element_types", "element_count"],
        )
        for chunk in chunks
    ]
