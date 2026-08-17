from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx


@dataclass(frozen=True)
class DownloadedPdf:
    filename: str
    path: Path


class DocumentStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def download_pdf(self, url: str, document_id: str) -> DownloadedPdf:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("A URL do documento deve usar HTTP ou HTTPS.")

        source_name = Path(unquote(parsed.path)).name
        if source_name and not source_name.lower().endswith(".pdf"):
            raise ValueError("A URL deve apontar para um arquivo PDF.")
        filename = source_name or f"{document_id}.pdf"

        document_dir = self.document_dir(document_id)
        document_dir.mkdir(parents=True, exist_ok=True)
        target = document_dir / "original.pdf"
        temporary = document_dir / "original.pdf.tmp"
        timeout = httpx.Timeout(connect=15, read=120, write=30, pool=15)

        first_chunk = True
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
            ) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    with temporary.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            if first_chunk:
                                if "pdf" not in content_type and not chunk.startswith(b"%PDF-"):
                                    raise ValueError("A URL informada nao retornou um PDF.")
                                first_chunk = False
                            output.write(chunk)
            if first_chunk:
                raise ValueError("O PDF retornado esta vazio.")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return DownloadedPdf(filename=filename, path=target)

    def persist_markdown(
        self,
        document_id: str,
        extracted: str,
        indexed: str,
    ) -> tuple[Path, Path]:
        document_dir = self.document_dir(document_id)
        document_dir.mkdir(parents=True, exist_ok=True)
        extracted_path = self._atomic_write(
            document_dir / "extracted.md",
            extracted,
        )
        indexed_path = self._atomic_write(
            document_dir / "indexed.md",
            indexed,
        )
        return extracted_path, indexed_path

    def document_dir(self, document_id: str) -> Path:
        return self._root / document_id

    def _atomic_write(self, target: Path, content: str) -> Path:
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return target
