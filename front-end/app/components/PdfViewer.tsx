"use client";

import {useEffect, useRef, useState} from "react";
import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  RenderTask,
} from "pdfjs-dist";
import {
  ChevronLeft,
  ChevronRight,
  Minus,
  Plus,
  X,
} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Skeleton} from "@/components/ui/skeleton";

type PdfViewerProps = {
  filename: string;
  url: string;
  onClose: () => void;
};

export function PdfViewer({filename, url, onClose}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let loadingTask: PDFDocumentLoadingTask | null = null;
    let cancelled = false;

    void (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();
        loadingTask = pdfjs.getDocument({url});
        const nextDocument = await loadingTask.promise;

        if (!cancelled) setDocument(nextDocument);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar este PDF.");
      }
    })();

    return () => {
      cancelled = true;
      void loadingTask?.destroy();
    };
  }, [url]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const observer = new ResizeObserver(([entry]) => {
      setViewportWidth(entry.contentRect.width);
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!document || !canvas || viewportWidth <= 0) return;

    let renderTask: RenderTask | null = null;
    let cancelled = false;

    void (async () => {
      const page = await document.getPage(pageNumber);
      if (cancelled) return;

      const originalViewport = page.getViewport({scale: 1});
      const availableWidth = Math.max(viewportWidth - 32, 240);
      const scale = (availableWidth / originalViewport.width) * zoom;
      const viewport = page.getViewport({scale});
      const outputScale = window.devicePixelRatio || 1;
      const context = canvas.getContext("2d");

      if (!context) return;

      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      renderTask = page.render({
        canvas,
        canvasContext: context,
        viewport,
        transform:
          outputScale === 1
            ? undefined
            : [outputScale, 0, 0, outputScale, 0, 0],
      });
      await renderTask.promise;
    })().catch((renderError: unknown) => {
      if (
        !cancelled &&
        (!(renderError instanceof Error) ||
          renderError.name !== "RenderingCancelledException")
      ) {
        setError("Nao foi possivel renderizar esta pagina.");
      }
    });

    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [document, pageNumber, viewportWidth, zoom]);

  return (
    <section className="flex size-full min-h-0 flex-col bg-transparent">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b px-3">
        <p className="min-w-0 flex-1 truncate text-sm font-medium">{filename}</p>
        <Button
          aria-label="Fechar visualizador"
          size="icon-sm"
          variant="ghost"
          onClick={onClose}
        >
          <X />
        </Button>
      </header>

      <div className="flex h-12 shrink-0 items-center justify-center gap-1 border-b px-2">
        <Button
          aria-label="Pagina anterior"
          disabled={!document || pageNumber <= 1}
          size="icon-sm"
          variant="ghost"
          onClick={() => setPageNumber((current) => current - 1)}
        >
          <ChevronLeft />
        </Button>
        <span className="min-w-20 text-center text-xs text-muted-foreground">
          {document ? `${pageNumber} / ${document.numPages}` : "— / —"}
        </span>
        <Button
          aria-label="Proxima pagina"
          disabled={!document || pageNumber >= document.numPages}
          size="icon-sm"
          variant="ghost"
          onClick={() => setPageNumber((current) => current + 1)}
        >
          <ChevronRight />
        </Button>
        <div className="mx-1 h-5 border-l" />
        <Button
          aria-label="Diminuir zoom"
          disabled={zoom <= 0.6}
          size="icon-sm"
          variant="ghost"
          onClick={() => setZoom((current) => Math.max(0.6, current - 0.2))}
        >
          <Minus />
        </Button>
        <span className="min-w-12 text-center text-xs text-muted-foreground">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          aria-label="Aumentar zoom"
          disabled={zoom >= 2}
          size="icon-sm"
          variant="ghost"
          onClick={() => setZoom((current) => Math.min(2, current + 0.2))}
        >
          <Plus />
        </Button>
      </div>

      <div
        ref={viewportRef}
        className="flex min-h-0 flex-1 items-start justify-center overflow-auto bg-muted/40 p-4"
      >
        {error ? (
          <div className="m-auto max-w-xs text-center text-sm text-destructive">
            {error}
          </div>
        ) : !document ? (
          <Skeleton className="aspect-[3/4] h-auto w-[min(100%,32rem)]" />
        ) : (
          <canvas ref={canvasRef} className="bg-white shadow-sm" />
        )}
      </div>
    </section>
  );
}
