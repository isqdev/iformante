from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import httpx


class DownloadDocumentUseCase:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or Path(__file__).resolve().parents[2] / "downloads"

    async def execute(self, url: str) -> Path:
        parsed_url = urlparse(url)

        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Informe uma URL HTTP ou HTTPS valida.")

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.storage_dir / self._build_filename(parsed_url.path)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                with target_path.open("wb") as document_file:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            document_file.write(chunk)

        return target_path

    def _build_filename(self, url_path: str) -> str:
        original_name = Path(unquote(url_path)).name
        suffix = Path(original_name).suffix if original_name else ""

        return f"document-{uuid4().hex}{suffix}"
