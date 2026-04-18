"""Deterministic fuzz-style regression tests for canonical .dox round-trips."""

from __future__ import annotations

import random
import string

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Figure,
    FormField,
    FormFieldType,
    Heading,
    KeyValuePair,
    ListBlock,
    ListItem,
    Paragraph,
)
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer


TEXT_CHARS = string.ascii_letters + string.digits + ' [](){}:/_-.,\'"\\'
SOURCE_CHARS = string.ascii_letters + string.digits + "/_.-()"


def _rand_text(rng: random.Random, *, min_len: int = 4, max_len: int = 24) -> str:
    size = rng.randint(min_len, max_len)
    text = "".join(rng.choice(TEXT_CHARS) for _ in range(size))
    inserts = ['::', '\\"', "\\\\", '"]', '(x)']
    for token in inserts[: rng.randint(1, len(inserts))]:
        pos = rng.randint(0, len(text))
        text = text[:pos] + token + text[pos:]
    return text


def _rand_source(rng: random.Random) -> str:
    stem = "".join(rng.choice(SOURCE_CHARS) for _ in range(rng.randint(5, 12)))
    ext = rng.choice([".png", ".jpg", ".svg"])
    return stem + ext


def test_fuzz_inline_attribute_roundtrip():
    parser = DoxParser()
    serializer = DoxSerializer()
    rng = random.Random(1337)

    for _ in range(40):
        key = _rand_text(rng)
        value = _rand_text(rng)
        form_value = _rand_text(rng)
        doc = DoxDocument(
            frontmatter=Frontmatter(version="1.0"),
            elements=[
                KeyValuePair(key=key, value=value),
                FormField(
                    field_name="name",
                    field_type=FormFieldType.TEXT,
                    value=form_value,
                ),
            ],
        )

        parsed = parser.parse(serializer.serialize(doc))
        kv = parsed.elements[0]
        form = parsed.elements[1]
        assert kv.key == key
        assert kv.value == value
        assert form.value == form_value


def test_fuzz_figure_roundtrip():
    parser = DoxParser()
    serializer = DoxSerializer()
    rng = random.Random(2026)

    for _ in range(30):
        caption = _rand_text(rng)
        source = _rand_source(rng)
        doc = DoxDocument(
            frontmatter=Frontmatter(version="1.0"),
            elements=[
                Figure(
                    caption=caption,
                    source=source,
                    figure_id=f"fig-{rng.randint(1, 999)}",
                )
            ],
        )

        parsed = parser.parse(serializer.serialize(doc))
        fig = parsed.elements[0]
        assert isinstance(fig, Figure)
        assert fig.caption == caption
        assert fig.source == source


def test_fuzz_mixed_content_roundtrip():
    parser = DoxParser()
    serializer = DoxSerializer()
    rng = random.Random(77)

    for idx in range(20):
        title = _rand_text(rng, min_len=6, max_len=18)
        para = _rand_text(rng, min_len=12, max_len=40)
        list_items = [ListItem(text=_rand_text(rng)) for _ in range(3)]
        doc = DoxDocument(
            frontmatter=Frontmatter(version="1.0"),
            elements=[
                Heading(level=1, text=title, element_id=f"h-{idx}"),
                Paragraph(text=para, page=1, reading_order=idx),
                ListBlock(
                    items=list_items,
                    ordered=bool(idx % 2),
                    start=3 if idx % 2 else 1,
                    element_id=f"list-{idx}",
                    page=1,
                ),
                KeyValuePair(key=_rand_text(rng), value=_rand_text(rng)),
            ],
        )

        reparsed = parser.parse(serializer.serialize(doc))
        assert len(reparsed.elements) == 4
        assert reparsed.elements[0].text == title
        assert reparsed.elements[1].text == para
        assert reparsed.elements[2].element_id == f"list-{idx}"
        if idx % 2:
            assert reparsed.elements[2].start == 3
