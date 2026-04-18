"""Regression tests for canonical .dox integrity."""

from __future__ import annotations

from dox.converters.to_json import to_dict
from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    CodeBlock,
    CrossRef,
    Figure,
    FormField,
    FormFieldType,
    KeyValuePair,
    Paragraph,
    Table,
    TableCell,
    TableRow,
)
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer
from dox.validator import DoxValidator


def test_paragraph_roundtrip_preserves_extended_metadata():
    doc = DoxDocument(
        frontmatter=Frontmatter(version="1.0"),
        elements=[
            Paragraph(
                text="Company Confidential",
                page=1,
                element_id="p1",
                confidence=0.91,
                reading_order=0,
                lang="en",
                is_furniture=True,
            )
        ],
    )

    text = DoxSerializer().serialize(doc)
    parsed = DoxParser().parse(text)
    para = parsed.elements[0]

    assert para.page == 1
    assert para.element_id == "p1"
    assert para.confidence == 0.91
    assert para.reading_order == 0
    assert para.lang == "en"
    assert para.is_furniture is True


def test_code_block_roundtrip_preserves_metadata():
    doc = DoxDocument(
        frontmatter=Frontmatter(version="1.0"),
        elements=[
            CodeBlock(
                code="x = 1",
                language="python",
                page=2,
                element_id="code-1",
                confidence=0.8,
                reading_order=4,
                lang="python",
            )
        ],
    )

    text = DoxSerializer().serialize(doc)
    parsed = DoxParser().parse(text)
    code = parsed.elements[0]

    assert code.language == "python"
    assert code.page == 2
    assert code.element_id == "code-1"
    assert code.confidence == 0.8
    assert code.reading_order == 4
    assert code.lang == "python"


def test_inline_block_attributes_with_quotes_roundtrip():
    doc = DoxDocument(
        frontmatter=Frontmatter(version="1.0"),
        elements=[
            KeyValuePair(key='He said "Hi"', value='Value "quoted"'),
            FormField(
                field_name="name",
                field_type=FormFieldType.TEXT,
                value='John "Johnny" Doe',
                element_id="form-1",
                page=3,
            ),
        ],
    )

    text = DoxSerializer().serialize(doc)
    parsed = DoxParser().parse(text)

    kv = parsed.elements[0]
    form = parsed.elements[1]
    assert kv.key == 'He said "Hi"'
    assert kv.value == 'Value "quoted"'
    assert form.value == 'John "Johnny" Doe'
    assert form.element_id == "form-1"
    assert form.page == 3


def test_figure_roundtrip_preserves_escaped_caption_and_binary_fields():
    doc = DoxDocument(
        frontmatter=Frontmatter(version="1.0"),
        elements=[
            Figure(
                caption='Caption with ] and "quotes"',
                source="img).png",
                figure_id="f1",
                element_id="fig-e1",
                page=2,
                confidence=0.8,
                reading_order=5,
                image_type="diagram",
                image_data="YWJjMTIzPT0=",
            )
        ],
    )

    text = DoxSerializer().serialize(doc)
    parsed = DoxParser().parse(text)
    fig = parsed.elements[0]

    assert isinstance(fig, Figure)
    assert fig.caption == 'Caption with ] and "quotes"'
    assert fig.source == "img).png"
    assert fig.figure_id == "f1"
    assert fig.element_id == "fig-e1"
    assert fig.page == 2
    assert fig.confidence == 0.8
    assert fig.reading_order == 5
    assert fig.image_type == "diagram"
    assert fig.image_data == "YWJjMTIzPT0="


def test_crossref_roundtrip_preserves_metadata():
    doc = DoxDocument(
        frontmatter=Frontmatter(version="1.0"),
        elements=[
            CrossRef(
                ref_type="table",
                ref_id="t1",
                page=4,
                element_id="xref-1",
                reading_order=7,
            )
        ],
    )

    text = DoxSerializer().serialize(doc)
    parsed = DoxParser().parse(text)
    ref = parsed.elements[0]

    assert isinstance(ref, CrossRef)
    assert ref.ref_type == "table"
    assert ref.ref_id == "t1"
    assert ref.page == 4
    assert ref.element_id == "xref-1"
    assert ref.reading_order == 7


def test_table_validation_uses_semantic_width_with_colspan():
    table = Table(
        table_id="t1",
        rows=[
            TableRow(
                cells=[
                    TableCell(text="Header", is_header=True, colspan=2),
                    TableCell(text="H2", is_header=True),
                ],
                is_header=True,
            ),
            TableRow(
                cells=[
                    TableCell(text="A"),
                    TableCell(text="B"),
                    TableCell(text="C"),
                ]
            ),
        ],
    )
    doc = DoxDocument(frontmatter=Frontmatter(version="1.0"), elements=[table])

    result = DoxValidator().validate(doc)
    assert not any("semantic width" in issue.message for issue in result.warnings)


def test_json_includes_figure_image_data_when_present():
    doc = DoxDocument(
        frontmatter=Frontmatter(version="1.0"),
        elements=[
            Figure(
                source="img.png",
                caption="Logo",
                image_type="logo",
                image_data="aGVsbG8=",
            )
        ],
    )

    data = to_dict(doc)
    figure = data["elements"][0]
    assert figure["image_type"] == "logo"
    assert figure["image_data"] == "aGVsbG8="
