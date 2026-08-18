from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from fastapi import UploadFile


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

    async def save_pdf_upload(
        self,
        upload: UploadFile,
        document_id: str,
        max_bytes: int = 25 * 1024 * 1024,
    ) -> DownloadedPdf:
        filename = Path(upload.filename or "documento.pdf").name
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Envie um arquivo PDF.")

        document_dir = self.document_dir(document_id)
        document_dir.mkdir(parents=True, exist_ok=True)
        target = document_dir / "original.pdf"
        temporary = document_dir / "original.pdf.tmp"
        written = 0

        try:
            with temporary.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError("O PDF excede o limite de 25 MB.")
                    output.write(chunk)

            with temporary.open("rb") as pdf_file:
                signature = pdf_file.read(5)
            if written == 0 or not signature.startswith(b"%PDF-"):
                raise ValueError("O arquivo enviado nao e um PDF valido.")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

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
