from dataclasses import dataclass
import re
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class ExtractedWebPage:
    title: str
    markdown: str


class WebPageExtractor:
    async def extract(self, source_url: str) -> ExtractedWebPage:
        self._validate_url(source_url)
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(
                f"https://r.jina.ai/{source_url}",
                headers={
                    "X-Target-Selector": "main",
                    "X-Remove-Selector": "header, footer, nav, aside, .sidebar",
                    "X-Retain-Links": "text",
                },
            )
        response.raise_for_status()
        markdown = response.text.strip()
        if not markdown:
            raise ValueError("Nao foi possivel extrair conteudo da pagina.")
        return ExtractedWebPage(
            title=self._extract_title(markdown, source_url),
            markdown=markdown,
        )

    def _validate_url(self, source_url: str) -> None:
        parsed = urlparse(source_url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("A URL deve usar HTTP ou HTTPS.")
        if parsed.username or parsed.password:
            raise ValueError("A URL nao pode conter credenciais.")
        if hostname != "ifpr.edu.br" and not hostname.endswith(".ifpr.edu.br"):
            raise ValueError("Apenas paginas do dominio ifpr.edu.br sao permitidas.")

    def _extract_title(self, markdown: str, source_url: str) -> str:
        match = re.search(r"^Title:\s*(.+)$", markdown, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip()[:255]
        match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
        if match:
            return match.group(1).strip()[:255]
        return urlparse(source_url).path.rstrip("/").split("/")[-1][:255] or "Pagina IFPR"
