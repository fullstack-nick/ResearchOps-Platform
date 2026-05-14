from pathlib import Path

import pytest
from app.documents.storage import sanitize_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../invoice.pdf", "invoice.pdf"),
        ("..\\invoice.pdf", "invoice.pdf"),
        ("supplier invoice final.pdf", "supplier_invoice_final.pdf"),
        ("***.pdf", "pdf"),
        ("", "document.pdf"),
    ],
)
def test_sanitize_filename_removes_path_and_unsafe_characters(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_limits_length() -> None:
    name = f"{'a' * 260}.pdf"
    safe = sanitize_filename(name)
    assert len(safe) <= 180
    assert Path(safe).suffix == ".pdf"
