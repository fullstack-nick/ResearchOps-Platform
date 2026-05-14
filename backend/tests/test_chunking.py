from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.search.chunking import ChunkText, PageText, chunk_pages, normalize_read_result


def test_normalize_read_result_from_dict_pages() -> None:
    result: dict[str, Any] = {
        "pages": [
            {
                "page_number": 1,
                "lines": [{"content": "Hello world"}, {"content": "Line two"}],
            },
            {"pageNumber": 2, "lines": [{"content": "Second page"}]},
        ]
    }

    pages = normalize_read_result(result)

    assert pages == [
        PageText(page_number=1, text="Hello world\nLine two"),
        PageText(page_number=2, text="Second page"),
    ]


def test_normalize_read_result_from_objects() -> None:
    result = SimpleNamespace(
        pages=[
            SimpleNamespace(
                page_number=1,
                lines=[
                    SimpleNamespace(content="Alpha"),
                    SimpleNamespace(content="Beta"),
                ],
            )
        ]
    )

    pages = normalize_read_result(result)

    assert pages == [PageText(page_number=1, text="Alpha\nBeta")]


def test_normalize_read_result_falls_back_to_content() -> None:
    result: dict[str, Any] = {"pages": [], "content": "Whole document text"}

    assert normalize_read_result(result) == [
        PageText(page_number=1, text="Whole document text")
    ]


def test_normalize_read_result_empty_payload() -> None:
    assert normalize_read_result({}) == []


def test_chunk_pages_short_page_is_single_chunk() -> None:
    pages = [PageText(page_number=3, text="A short page.")]

    chunks = chunk_pages(pages, chunk_size=1200, overlap=200)

    assert chunks == [
        ChunkText(chunk_index=0, page_number=3, content="A short page.", char_count=13)
    ]


def test_chunk_pages_splits_long_text_with_overlap() -> None:
    text = "".join(chr(ord("a") + (index % 26)) for index in range(2500))
    pages = [PageText(page_number=1, text=text)]

    chunks = chunk_pages(pages, chunk_size=1000, overlap=200)

    assert len(chunks) == 3
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.page_number == 1 for chunk in chunks)
    assert all(chunk.char_count <= 1000 for chunk in chunks)
    # 200-char overlap window is shared between consecutive chunks.
    assert chunks[0].content[800:] == chunks[1].content[:200]
    assert chunks[2].char_count == 900


def test_chunk_pages_keeps_page_numbers_across_pages() -> None:
    pages = [
        PageText(page_number=1, text="First page text."),
        PageText(page_number=2, text="Second page text."),
    ]

    chunks = chunk_pages(pages, chunk_size=1200, overlap=100)

    assert [(chunk.chunk_index, chunk.page_number) for chunk in chunks] == [
        (0, 1),
        (1, 2),
    ]
