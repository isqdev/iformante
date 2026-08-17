from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
import pymupdf4llm


PDF_URL = (
    "https://ifpr.edu.br/paranavai/wp-content/uploads/sites/21/2025/01/"
    "PPC-de-Engenharia-de-Software-%E2%80%93-2025.pdf"
)
OUTPUT_PATH = Path(__file__).with_name("ppc_engenharia_software_2025.md")
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


def download_pdf(url: str, destination: Path) -> None:
    downloaded_bytes = 0

    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()

        with destination.open("wb") as pdf_file:
            for chunk in response.iter_bytes():
                downloaded_bytes += len(chunk)

                if downloaded_bytes > MAX_DOWNLOAD_BYTES:
                    raise ValueError("O PDF excede o limite de 50 MB.")

                pdf_file.write(chunk)

    if downloaded_bytes == 0:
        raise ValueError("O PDF baixado esta vazio.")


def main() -> None:
    with NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
        pdf_path = Path(temporary_file.name)

    try:
        print(f"Baixando: {PDF_URL}")
        download_pdf(PDF_URL, pdf_path)

        print("Extraindo o PDF como Markdown com pymupdf4llm...")
        markdown = pymupdf4llm.to_markdown(pdf_path)
        OUTPUT_PATH.write_text(markdown, encoding="utf-8")

        print(f"Resultado salvo em: {OUTPUT_PATH}")
        print(f"Caracteres extraidos: {len(markdown)}")
    finally:
        pdf_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
