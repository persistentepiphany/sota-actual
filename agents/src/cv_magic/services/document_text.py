"""
Document text extraction for CV Magic.

Extracts readable text from PDF, DOCX, and plain text files.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import os
from typing import Optional


@dataclass(frozen=True)
class ExtractedText:
    """Result of text extraction"""
    text: str
    method: str


def _extension_from_filename(filename: Optional[str]) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower().lstrip(".")


def _decode_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_text_from_bytes(
    *,
    data: bytes,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> ExtractedText:
    """
    Extracts readable text from common document formats.

    Supported:
      - PDF via `pypdf`
      - DOCX via `python-docx`
      - text/* and unknown binaries via best-effort decode
    """
    ext = _extension_from_filename(filename)
    ct = (content_type or "").lower()

    # PDF extraction
    if ext == "pdf" or ct == "application/pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError("Missing PDF dependency. Install `pypdf`.") from e
        
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        return ExtractedText(text="\n".join(parts).strip(), method="pdf:pypdf")

    # DOCX extraction
    if ext == "docx" or ct in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }:
        try:
            import docx  # python-docx
        except ImportError as e:
            raise RuntimeError("Missing DOCX dependency. Install `python-docx`.") from e
        
        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs if p.text]
        return ExtractedText(text="\n".join(parts).strip(), method="docx:python-docx")

    # Plain text
    if ct.startswith("text/") or ext in {"txt", "md", "rtf", "csv"}:
        return ExtractedText(text=_decode_text_bytes(data).strip(), method="text:decode")

    # Best effort for unknown formats
    return ExtractedText(text=_decode_text_bytes(data).strip(), method="best-effort:decode")
