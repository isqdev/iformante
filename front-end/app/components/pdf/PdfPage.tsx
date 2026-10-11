"use client";
import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import type { PdfAnchor } from "./types";
import { DocumentLoader } from "../documents/DocumentLoader";
export function PdfPage({
  document,
  number,
  width,
  zoom,
  anchors,
  onError,
}: {
  document: PDFDocumentProxy;
  number: number;
  width: number;
  zoom: number;
  anchors: PdfAnchor[];
  onError: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(false);
  const [ratio, setRatio] = useState(0.707);
  const [renderedWidth, setRenderedWidth] = useState<number | null>(null);
  const renderWidth = Math.max(100, Math.min(920, width - 32)) * zoom;
  useEffect(() => {
    let cancelled = false;
    void document.getPage(number).then((p) => {
      const v = p.getViewport({ scale: 1 });
      if (!cancelled) setRatio(v.width / v.height);
    });
    return () => {
      cancelled = true;
    };
  }, [document, number]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { root: el.closest("[data-pdf-scroll]"), rootMargin: "1000px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!visible || width <= 0) return;
    let task: RenderTask | null = null;
    let cancelled = false;
    void (async () => {
      const page = await document.getPage(number);
      if (cancelled || !canvas.current) return;
      const viewport = page.getViewport({
        scale: renderWidth / page.getViewport({ scale: 1 }).width,
      });
      const outputScale = Math.min(2, window.devicePixelRatio || 1);
      const el = canvas.current;
      el.width = Math.floor(viewport.width * outputScale);
      el.height = Math.floor(viewport.height * outputScale);
      const context = el.getContext("2d");
      if (!context) return;
      task = page.render({
        canvas: el,
        canvasContext: context,
        viewport,
        transform: [outputScale, 0, 0, outputScale, 0, 0],
      });
      await task.promise;
      if (!cancelled) setRenderedWidth(renderWidth);
    })().catch((e) => {
      if (!cancelled && e?.name !== "RenderingCancelledException") onError();
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [document, number, width, renderWidth, visible, onError]);
  return (
    <div
      ref={ref}
      data-pdf-page={number}
      className="relative shrink-0 bg-white shadow-sm"
      style={{ width: renderWidth, height: renderWidth / ratio }}
    >
      {visible && renderedWidth !== renderWidth && (
        <div className="absolute inset-0 flex items-center justify-center">
          <DocumentLoader label={`Renderizando página ${number}`} />
        </div>
      )}
      <canvas
        ref={canvas}
        className="relative size-full"
        aria-label={`Página ${number}`}
      />
      {anchors
        .filter((a) => a.x !== undefined)
        .map((a, i) => (
          <div
            key={i}
            aria-hidden="true"
            className="pointer-events-none absolute rounded-sm bg-green-200/45 mix-blend-multiply"
            style={{
              left: `${a.x! * 100}%`,
              top: `${a.y! * 100}%`,
              width: `${a.width! * 100}%`,
              height: `${a.height! * 100}%`,
            }}
          />
        ))}
    </div>
  );
}
