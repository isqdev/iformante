"use client";
import { useEffect, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Maximize,
  Minimize,
  Minus,
  Plus,
  Quote,
  Settings2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
type Props = {
  zoom: number;
  setZoom: (zoom: number) => void;
  page: number;
  total: number;
  goPage: (page: number) => void;
  fullscreen: boolean;
  toggleFullscreen?: () => void;
  citationMode: boolean;
  toggleMode?: () => void;
  citation: number;
  citations: number;
  goCitation: (index: number) => void;
};
export function PdfToolbar(p: Props) {
  const [draft, setDraft] = useState(String(p.page));
  useEffect(() => {
    queueMicrotask(() => setDraft(String(p.page)));
  }, [p.page]);
  function submitPage() {
    const n = Number(draft);
    if (Number.isInteger(n) && n >= 1 && n <= p.total) p.goPage(n);
    else setDraft(String(p.page));
  }
  return (
    <div
      role="toolbar"
      aria-label={
        p.citationMode ? "Navegação das citações" : "Ferramentas do PDF"
      }
      className="pdf-toolbar absolute bottom-4 left-1/2 z-10 flex h-12 max-w-[calc(100%-1rem)] -translate-x-1/2 items-center gap-1 rounded-full border bg-background px-2 text-foreground shadow-lg"
    >
      {p.citationMode ? (
        <>
          <Button
            aria-label="Citação anterior"
            size="icon-sm"
            variant="ghost"
            disabled={p.citation <= 0}
            onClick={() => p.goCitation(p.citation - 1)}
          >
            <ChevronLeft />
          </Button>
          <span className="whitespace-nowrap px-2 text-xs">
            {p.citations ? p.citation + 1 : 0} / {p.citations} citações
          </span>
          <Button
            aria-label="Próxima citação"
            size="icon-sm"
            variant="ghost"
            disabled={p.citation >= p.citations - 1}
            onClick={() => p.goCitation(p.citation + 1)}
          >
            <ChevronRight />
          </Button>
        </>
      ) : (
        <>
          <Button
            aria-label="Diminuir zoom"
            size="icon-sm"
            variant="ghost"
            disabled={p.zoom <= 0.5}
            onClick={() =>
              p.setZoom(Math.max(0.5, Math.round((p.zoom - 0.1) * 10) / 10))
            }
          >
            <Minus />
          </Button>
          <span className="min-w-9 text-center text-xs">
            {Math.round(p.zoom * 100)}%
          </span>
          <Button
            aria-label="Aumentar zoom"
            size="icon-sm"
            variant="ghost"
            disabled={p.zoom >= 2}
            onClick={() =>
              p.setZoom(Math.min(2, Math.round((p.zoom + 0.1) * 10) / 10))
            }
          >
            <Plus />
          </Button>
          <Input
            aria-label="Página atual"
            inputMode="numeric"
            value={draft}
            className="h-8 w-11 rounded-full px-1 text-center"
            onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
            onBlur={submitPage}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submitPage();
              }
            }}
          />
          <span className="whitespace-nowrap pr-1 text-xs">/ {p.total}</span>
        </>
      )}
      {p.toggleFullscreen && (
        <Button
          aria-label={
            p.fullscreen ? "Voltar ao painel lateral" : "Ver em tela cheia"
          }
          size="icon-sm"
          variant="ghost"
          onClick={p.toggleFullscreen}
        >
          {p.fullscreen ? <Minimize /> : <Maximize />}
        </Button>
      )}
      {p.toggleMode && (
        <Button
          aria-label={p.citationMode ? "Configurações do PDF" : "Ver citações"}
          size="icon-sm"
          variant="ghost"
          onClick={p.toggleMode}
        >
          {p.citationMode ? <Settings2 /> : <Quote />}
        </Button>
      )}
    </div>
  );
}
