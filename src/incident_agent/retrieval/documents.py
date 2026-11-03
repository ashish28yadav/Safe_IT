"""Load operational documents and produce reproducible, attributed chunks."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from incident_agent.retrieval.models import (
    DocumentChunk, IngestionError, IngestionReport, KnowledgeDocument,
)

_FIELD = re.compile(r"^\s*(?:\*\*)?(Document ID|Service|Incident category|Category|Document type|Type)\s*:\s*(?:\*\*)?\s*(.*?)\s*$", re.I)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)
_SUPPORTED = {".md", ".markdown", ".txt", ".pdf"}
_SERVICE_ALIASES = {
    "payment": "payment-service", "authentication": "authentication-service",
    "notification": "notification-service", "postgres": "postgres-database",
}


def _stable_id(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


class DocumentLoader:
    """Load Markdown, text and PDF files; collect errors instead of hiding them."""

    def __init__(self, max_file_bytes: int = 5_000_000) -> None:
        self.max_file_bytes = max_file_bytes

    def load(self, root: Path) -> tuple[tuple[KnowledgeDocument, ...], tuple[IngestionError, ...]]:
        documents: list[KnowledgeDocument] = []
        errors: list[IngestionError] = []
        seen_ids: set[str] = set()
        if not root.exists():
            return (), (IngestionError(root.name or "knowledge_base", "Knowledge base directory does not exist"),)
        for path in sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in _SUPPORTED):
            try:
                if path.stat().st_size > self.max_file_bytes:
                    raise ValueError(f"file exceeds {self.max_file_bytes} byte limit")
                text = self._read(path)
                document = self._normalize(path, root, text)
                if not document.content.strip():
                    raise ValueError("document has no usable text")
                if document.document_id in seen_ids:
                    raise ValueError(f"duplicate document ID: {document.document_id}")
                seen_ids.add(document.document_id)
                documents.append(document)
            except Exception as exc:
                detail = str(exc).replace(str(path), path.name).replace(str(path.resolve()), path.name)
                detail = re.sub(r"[A-Za-z]:[\\/][^\s:'\"]+", "<path>", detail)
                detail = re.sub(r"(?<![\w])/(?:[^\s/'\"]+/)*[^\s/'\"]+", "<path>", detail)
                errors.append(IngestionError(path.name, f"{type(exc).__name__}: {detail[:300]}"))
        return tuple(documents), tuple(errors)

    @staticmethod
    def _read(path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            try:
                import fitz
            except ImportError as exc:
                raise RuntimeError("PDF ingestion requires the PyMuPDF dependency") from exc
            with fitz.open(path) as pdf:
                return "\n\n".join(page.get_text("text") for page in pdf)
        return path.read_text(encoding="utf-8-sig")

    @staticmethod
    def _normalize(path: Path, root: Path, raw: str) -> KnowledgeDocument:
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[\t\f\v ]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        fields: dict[str, str] = {}
        for line in text.splitlines():
            match = _FIELD.match(line)
            if match:
                fields[match.group(1).lower()] = match.group(2).strip()
        first_heading = _HEADING.search(text)
        title = first_heading.group(1).strip() if first_heading else path.stem.replace("-", " ").title()
        source = path.relative_to(root).as_posix()
        document_id = fields.get("document id") or f"doc-{_stable_id(source)}"
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", document_id):
            raise ValueError("document ID must be 1-120 letters, digits, dot, underscore, colon, or hyphen")
        content = "\n".join(line for line in text.splitlines() if not _FIELD.match(line)).strip()
        service = fields.get("service", "general").strip().casefold()
        service = _SERVICE_ALIASES.get(service, service)
        return KnowledgeDocument(
            document_id=document_id,
            title=title,
            source=source,
            service=service,
            category=fields.get("incident category", fields.get("category", "operations")).strip().lower(),
            document_type=fields.get("document type", fields.get("type", "runbook")).strip().lower(),
            content=content,
        )


def _paragraph_chunks(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    return [" ".join(words[start:start + size]) for start in range(0, len(words), step)]


def chunk_documents(
    documents: tuple[KnowledgeDocument, ...] | list[KnowledgeDocument],
    *, chunk_size: int = 220, overlap: int = 40, strategy: str = "structure",
) -> tuple[DocumentChunk, ...]:
    """Create fixed word-window or heading-aware chunks with stable IDs."""
    if chunk_size < 20 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be >= 20 and overlap must be in [0, chunk_size)")
    if strategy not in {"structure", "fixed"}:
        raise ValueError("strategy must be 'structure' or 'fixed'")
    output: list[DocumentChunk] = []
    for document in documents:
        if strategy == "fixed":
            sections = [("Document", document.content)]
        else:
            headings = list(_HEADING.finditer(document.content))
            if not headings:
                sections = [("Document", document.content)]
            else:
                sections = []
                if document.content[:headings[0].start()].strip():
                    sections.append(("Introduction", document.content[:headings[0].start()].strip()))
                for index, heading in enumerate(headings):
                    end = headings[index + 1].start() if index + 1 < len(headings) else len(document.content)
                    section_text = document.content[heading.end():end].strip()
                    sections.append((heading.group(1).strip(), section_text))
        ordinal = 0
        for section, text in sections:
            for content in _paragraph_chunks(text, chunk_size, overlap):
                ordinal += 1
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                identity = "|".join((
                    document.document_id, strategy, str(ordinal), section, document.title,
                    document.source, document.service, document.category,
                    document.document_type, content_hash,
                ))
                chunk_id = f"{document.document_id}-{strategy}-{ordinal:04d}-{_stable_id(identity, 16)}"
                output.append(DocumentChunk(
                    document_id=document.document_id, chunk_id=chunk_id, title=document.title,
                    source=document.source, service=document.service, category=document.category,
                    document_type=document.document_type, section=section,
                    content_hash=content_hash, content=content,
                ))
    return tuple(output)


def ingest_directory(
    root: Path, *, chunk_size: int = 220, overlap: int = 40, strategy: str = "structure",
) -> IngestionReport:
    documents, errors = DocumentLoader().load(root)
    chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap, strategy=strategy)
    return IngestionReport(documents, chunks, errors)
