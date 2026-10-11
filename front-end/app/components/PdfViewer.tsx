"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";
import { X } from "lucide-react";
import { DocumentLoader } from "./documents/DocumentLoader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { PdfPage } from "./pdf/PdfPage";
import { PdfToolbar } from "./pdf/PdfToolbar";
import type { PdfCitation } from "./pdf/types";
type Props = {
  filename: string;
  url: string;
  onClose: () => void;
  citations?: PdfCitation[];
  fullSize?: boolean;
  citationTools?: boolean;
};
export function PdfViewer({
  filename,
  url,
  onClose,
  citations = [],
  fullSize = false,
  citationTools = true,
}: Props) {
  const viewport = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [zoom, setZoom] = useState(1);
  const [page, setPage] = useState(1);
  const [width, setWidth] = useState(0);
  const [error, setError] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [citationMode, setCitationMode] = useState(false);
  const [citation, setCitation] = useState(0);
  const onError = useCallback(
    () => setError("Não foi possível renderizar este PDF."),
    [],
  );
  useEffect(() => {
    let task: PDFDocumentLoadingTask | null = null;
    let cancelled = false;
    void (async () => {
      try {
        const js = await import("pdfjs-dist");
        js.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();
        task = js.getDocument({ url });
        const next = await task.promise;
        if (!cancelled) setPdf(next);
      } catch {
        if (!cancelled) setError("Não foi possível carregar este PDF.");
      }
    })();
    return () => {
      cancelled = true;
      void task?.destroy();
    };
  }, [url]);
  const attachViewport = useCallback((element: HTMLDivElement | null) => {
    viewport.current = element;
    if (element) setWidth(element.clientWidth);
  }, []);
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [fullscreen, fullSize, pdf]);
  function goPage(n: number, y = 0) {
    const el = viewport.current;
    const target = el?.querySelector<HTMLElement>(`[data-pdf-page="${n}"]`);
    if (!el || !target) return;
    el.scrollTo({
      top:
        target.getBoundingClientRect().top -
        el.getBoundingClientRect().top +
        el.scrollTop +
        target.offsetHeight * y -
        16,
      behavior: "auto",
    });
    setPage(n);
  }
  function goCitation(n: number) {
    if (n < 0 || n >= citations.length) return;
    setCitation(n);
    const a = citations[n].anchors[0];
    if (a) goPage(a.page, a.y ?? 0);
  }
  const surfacePosition = useRef({ page: 1, y: 0 });
  const restoring = useRef(false);
  function changeFullscreen(next: boolean) {
    const el = viewport.current;
    const target = el?.querySelector<HTMLElement>(`[data-pdf-page="${page}"]`);
    const y =
      el && target
        ? Math.max(
            0,
            (el.getBoundingClientRect().top -
              target.getBoundingClientRect().top) /
              target.offsetHeight,
          )
        : 0;
    surfacePosition.current = { page, y };
    restoring.current = true;
    setFullscreen(next);
  }
  useEffect(() => {
    if (!restoring.current) return;
    const timer = setTimeout(() => {
      goPage(surfacePosition.current.page, surfacePosition.current.y);
      restoring.current = false;
    }, 150);
    return () => clearTimeout(timer);
  }, [fullscreen]);
  const content = (
    <section className={cn("relative flex size-full min-h-0 min-w-0 flex-col overflow-hidden text-foreground", (fullscreen || fullSize) && "bg-sidebar")}>
      <header className="relative flex h-14 shrink-0 items-center justify-center border-b px-12">
        <p className="min-w-0 w-full truncate text-center text-sm font-medium" title={filename}>
          {filename}
        </p>
        <Button
          aria-label="Fechar visualizador"
          size="icon-sm"
          variant="ghost"
          className="absolute right-3"
          onClick={onClose}
        >
          <X />
        </Button>
      </header>
      <div
        ref={attachViewport}
        data-pdf-scroll
        className="relative min-h-0 flex-1 overflow-auto pb-24 pt-4"
        onScroll={() => {
          const el = viewport.current;
          if (!el || restoring.current) return;
          const pages = Array.from(
            el.querySelectorAll<HTMLElement>("[data-pdf-page]"),
          );
          const bounds = el.getBoundingClientRect();
          const current = pages.reduce<HTMLElement | null>((best, p) => {
            const r = p.getBoundingClientRect();
            const visible = Math.max(
              0,
              Math.min(r.bottom, bounds.bottom) - Math.max(r.top, bounds.top),
            );
            const previous = best?.getBoundingClientRect();
            const previousVisible = previous
              ? Math.max(
                  0,
                  Math.min(previous.bottom, bounds.bottom) -
                    Math.max(previous.top, bounds.top),
                )
              : 0;
            return visible > previousVisible ? p : best;
          }, null);
          if (current) setPage(Number(current.dataset.pdfPage));
        }}
      >
        {error ? (
          <p role="alert" className="p-6 text-center text-sm text-destructive">
            {error}
          </p>
        ) : !pdf ? (
          <div
            className="absolute inset-0 flex items-center justify-center"
          >
            <DocumentLoader label="Carregando PDF" />
          </div>
        ) : (
          <div className="flex min-w-full w-max flex-col items-center gap-4 px-4">
            {Array.from({ length: pdf.numPages }, (_, i) => (
              <PdfPage
                key={i + 1}
                document={pdf}
                number={i + 1}
                width={width}
                zoom={zoom}
                anchors={citations
                  .flatMap((c) => c.anchors)
                  .filter((a) => a.page === i + 1)}
                onError={onError}
              />
            ))}
          </div>
        )}
      </div>
      {pdf && (
        <PdfToolbar
          zoom={zoom}
          setZoom={setZoom}
          page={page}
          total={pdf.numPages}
          goPage={goPage}
          fullscreen={fullscreen}
          toggleFullscreen={
            fullSize ? undefined : () => changeFullscreen(!fullscreen)
          }
          citationMode={citationMode}
          toggleMode={
            citationTools
              ? () => {
                  setCitationMode((v) => !v);
                  if (!citationMode) goCitation(citation);
                }
              : undefined
          }
          citation={citation}
          citations={citations.length}
          goCitation={goCitation}
        />
      )}
    </section>
  );
  return (
    <>
      {!fullscreen && content}
      <Dialog open={fullscreen} onOpenChange={changeFullscreen}>
        <DialogContent
          className="app-glass-background h-dvh w-screen max-w-none gap-0 rounded-none p-0 sm:max-w-none"
          showCloseButton={false}
        >
          <DialogTitle className="sr-only">{filename}</DialogTitle>
          <DialogDescription className="sr-only">
            PDF em tela cheia
          </DialogDescription>
          {fullscreen && content}
        </DialogContent>
      </Dialog>
    </>
  );
}
