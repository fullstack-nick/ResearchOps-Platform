from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class ChunkText:
    chunk_index: int
    page_number: int | None
    content: str
    char_count: int


def normalize_read_result(result: Any) -> list[PageText]:
    """Turn an Azure Document Intelligence ``prebuilt-read`` result into page text.

    Accepts both SDK result objects and plain dict payloads so tests can drive
    the pipeline without live Azure calls.
    """
    page_texts: list[PageText] = []
    pages = _get(result, "pages")
    if isinstance(pages, Sequence) and not isinstance(pages, (str, bytes, bytearray)):
        for index, page in enumerate(cast(Sequence[Any], pages)):
            page_number = _get(page, "page_number", "pageNumber")
            number = int(page_number) if page_number is not None else index + 1
            page_text = _page_text(page)
            if page_text:
                page_texts.append(PageText(page_number=number, text=page_text))
    if page_texts:
        return page_texts

    content = _get(result, "content")
    if content is not None and str(content).strip():
        return [PageText(page_number=1, text=str(content).strip())]
    return []


def chunk_pages(pages: list[PageText], chunk_size: int, overlap: int) -> list[ChunkText]:
    """Split page text into overlapping, page-attributed chunks for retrieval."""
    safe_size = max(chunk_size, 1)
    safe_overlap = max(min(overlap, safe_size - 1), 0)
    step = max(safe_size - safe_overlap, 1)
    chunks: list[ChunkText] = []
    chunk_index = 0
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        if len(text) <= safe_size:
            chunks.append(
                ChunkText(
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    content=text,
                    char_count=len(text),
                )
            )
            chunk_index += 1
            continue
        start = 0
        while start < len(text):
            window = text[start : start + safe_size].strip()
            if window:
                chunks.append(
                    ChunkText(
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        content=window,
                        char_count=len(window),
                    )
                )
                chunk_index += 1
            if start + safe_size >= len(text):
                break
            start += step
    return chunks


def _page_text(page: Any) -> str:
    lines = _get(page, "lines")
    line_texts: list[str] = []
    if isinstance(lines, Sequence) and not isinstance(lines, (str, bytes, bytearray)):
        for line in cast(Sequence[Any], lines):
            content = _get(line, "content")
            if content is not None and str(content).strip():
                line_texts.append(str(content).strip())
    if line_texts:
        return "\n".join(line_texts).strip()
    content = _get(page, "content")
    return str(content).strip() if content is not None else ""


def _get(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, Any], value)
        for name in names:
            if name in mapping:
                return mapping[name]
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None
